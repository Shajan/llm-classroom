"""
Weather question with OpenAI function calling, written as an agent loop.

The core idea of an "agent" is a simple loop:

    1. Send the conversation (plus the list of available tools) to the model.
    2. If the model asks to call tools, run them, append the results to the
       conversation, and go back to step 1.
    3. If the model answers with plain text (no tool calls), it is done.

The model decides which tools to call and in what order. Our code never
hardcodes "call location first, then weather" - it just keeps looping until
the model stops asking for tools. A cap on tool runs (MAX_TOOL_RUNS) is the
safety check that guarantees the loop ends.
"""
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

MODEL = "gpt-4o-mini"

# SAFETY CHECK: the most tool executions we allow for a single question.
# This question needs exactly 2 (location, then weather), so 2 is enough.
#
# WARNING - why this matters for cost:
# Every loop iteration sends the ENTIRE conversation to the model again,
# including every earlier tool result. So each extra tool run makes every
# later request bigger, and total tokens grow much faster than the number of
# runs. If this check is removed and the model gets stuck (keeps calling
# tools, retries a failing tool, or ping-pongs between tools), the loop never
# ends on its own and token usage - and your bill - keeps climbing until the
# context window fills up or you kill the process.
MAX_TOOL_RUNS = 2


# ---------------------------------------------------------------------------
# Tools: plain Python functions the model can ask us to run.
# The model never runs these itself - it only asks, and our loop runs them.
# ---------------------------------------------------------------------------

def get_current_location():
    """
    Tool to get the current location based on IP address using ipapi.co.
    Returns location information including city, region, country, and coordinates.
    """
    try:
        print("  Getting location from ipapi.co...")
        response = requests.get(
            "https://ipapi.co/json/",
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; WeatherApp/1.0)'}
        )
        response.raise_for_status()

        data = response.json()

        location_info = {
            "city": data.get("city", "Unknown"),
            "region": data.get("region", "Unknown"),
            "country": data.get("country_name", "Unknown"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone", "Unknown")
        }

        # Validate that we got useful location data
        if location_info.get("latitude") is not None and location_info.get("longitude") is not None:
            return location_info
        else:
            raise ValueError("No coordinates received from ipapi.co")

    except Exception as e:
        # Return the error to the model instead of crashing. The model can read
        # it and explain the problem to the user (or try something else).
        print(f"  Error getting location: {e}")
        return {"error": f"Failed to get location: {e}"}


def get_weather(latitude, longitude, city="Unknown"):
    """
    Get current weather information for given coordinates.
    Uses wttr.in - a free weather service that doesn't require API keys.
    Returns weather data in JSON format.
    """
    try:
        # Format: wttr.in/{latitude},{longitude}?format=j1
        url = f"https://wttr.in/{latitude},{longitude}"
        params = {
            'format': 'j1',  # JSON format
            'lang': 'en'     # English language
        }

        print(f"  Getting weather from wttr.in for ({latitude}, {longitude})...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        current = data['current_condition'][0]
        nearest_area = data['nearest_area'][0] if data.get('nearest_area') else {}

        # Extract location information
        location_name = nearest_area.get('areaName', [{}])[0].get('value', city)
        region = nearest_area.get('region', [{}])[0].get('value', '')
        country = nearest_area.get('country', [{}])[0].get('value', '')

        location_str = location_name
        if region and region != location_name:
            location_str += f", {region}"
        if country:
            location_str += f", {country}"

        return {
            "location": location_str,
            "temperature": f"{current['temp_C']}°C ({current['temp_F']}°F)",
            "description": current['weatherDesc'][0]['value'],
            "humidity": f"{current['humidity']}%",
            "wind_speed": f"{current['windspeedKmph']} km/h",
            "wind_direction": current['winddir16Point'],
            "feels_like": f"{current['FeelsLikeC']}°C ({current['FeelsLikeF']}°F)",
            "uv_index": current['uvIndex'],
            "visibility": f"{current['visibility']} km",
            "pressure": f"{current['pressure']} mb",
            "cloud_cover": f"{current['cloudcover']}%"
        }
    except requests.RequestException as e:
        return {"error": f"Error getting weather data: {e}"}
    except (KeyError, IndexError) as e:
        return {"error": f"Error parsing weather data: {e}"}


# ---------------------------------------------------------------------------
# Tool definitions: what we tell the model about each tool.
# The model only sees these names, descriptions and JSON schemas - never the
# Python code. Good descriptions are how the model knows when to use a tool.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_location",
            "description": "Get the user's current location (city and coordinates) based on their IP address.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a latitude/longitude. Needs coordinates, so get the location first if you don't have them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location"
                    },
                    "city": {
                        "type": "string",
                        "description": "City name for reference"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        }
    }
]

# Map tool names (as the model knows them) to the Python functions that run them.
# Adding a new tool = write the function, add a schema to TOOLS, add it here.
TOOL_FUNCTIONS = {
    "get_current_location": get_current_location,
    "get_weather": get_weather,
}


def execute_tool(name, arguments):
    """Run the tool the model asked for and return a JSON-serializable result."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        # The model asked for a tool that doesn't exist. Tell it, don't crash.
        return {"error": f"Unknown tool: {name}"}
    try:
        return func(**arguments)
    except TypeError as e:
        # The model sent wrong or missing arguments. Report it so the model can retry.
        return {"error": f"Bad arguments for {name}: {e}"}


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

def run_agent(client, question):
    """Answer a question, letting the model call tools as many times as it needs."""

    # The conversation is the agent's memory. Every model reply and every tool
    # result is appended here, and the whole list is sent on each call.
    # The model itself is stateless: it only knows what is in this list.
    messages = [
        {"role": "system", "content": "You are a helpful weather assistant. Use the tools to get real data; never guess."},
        {"role": "user", "content": question},
    ]

    loop_count = 0   # how many times we have asked the model (loop iterations)
    tool_runs = 0    # how many tools we have actually executed (the safety-checked number)
    total_tokens = 0 # tokens used across all calls, to show the cost of each iteration

    while True:
        loop_count += 1

        # SAFETY CHECK: once the tool budget is spent, forbid further tool calls.
        # tool_choice="none" forces the model to answer with what it already has,
        # which guarantees this is the last iteration.
        # Remove this check and nothing stops the loop: see the MAX_TOOL_RUNS warning.
        budget_spent = tool_runs >= MAX_TOOL_RUNS
        tool_choice = "none" if budget_spent else "auto"

        # Tell the model why it can't call tools any more. If the budget ran out
        # before it was finished, it may otherwise reply "I will now check the
        # weather..." - a promise it can't keep. (If it already has everything,
        # this note is harmless.) This forced call is always the last loop, so
        # the note is added only once.
        if budget_spent:
            messages.append({
                "role": "system",
                "content": "Tool run limit reached; no more tools can be called. "
                           "Answer now with the information you have, and say plainly what you could not find out.",
            })

        print(f"\n[Loop {loop_count}] Asking the model "
              f"(tool runs so far: {tool_runs}/{MAX_TOOL_RUNS}, tool_choice={tool_choice})...")

        # Step 1: send the conversation and the tool list to the model.
        # tool_choice="auto" lets the model decide: answer now, or call tools.
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice=tool_choice,
        )
        message = response.choices[0].message

        # Show token usage per call. Watch the prompt tokens grow each loop:
        # that is the whole conversation being resent.
        usage = response.usage
        total_tokens += usage.total_tokens
        print(f"  Tokens this call: prompt={usage.prompt_tokens}, "
              f"completion={usage.completion_tokens}, running total={total_tokens}")

        # Step 3 (checked first): no tool calls means the model has its final answer.
        if not message.tool_calls:
            print(f"\nDone: {loop_count} loop(s), {tool_runs} tool run(s), {total_tokens} tokens total.")
            return message.content.strip()

        # Step 2: the model wants tools. First record its request in the
        # conversation. The API requires this assistant message to come before
        # the tool results that answer it.
        messages.append(message)

        # The model may ask for several tools in one turn. Run each one and
        # reply with a "tool" message. Every tool_call_id must get exactly one
        # reply, or the next API call fails.
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            # Arguments arrive as a JSON string written by the model.
            # It can be malformed, so parse it defensively.
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            # SAFETY CHECK: the model may ask for several tools in one turn,
            # which could push us past the budget. Refuse the extra ones.
            # We still must reply to this tool_call_id, so send an error result.
            if tool_runs >= MAX_TOOL_RUNS:
                print(f"  BLOCKED: {name} (tool run limit of {MAX_TOOL_RUNS} reached)")
                result = {"error": f"Tool run limit ({MAX_TOOL_RUNS}) reached. Answer with the information you have."}
            else:
                tool_runs += 1
                print(f"  Tool run {tool_runs}/{MAX_TOOL_RUNS}: {name}({arguments})")
                result = execute_tool(name, arguments)
                print(f"  Result: {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,  # links this result to the request
                "content": json.dumps(result),
            })

        # Loop back: the model now sees the tool results and decides what to do next.
        # If the budget is now spent, the next iteration forces a final answer.


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return

    client = OpenAI(api_key=api_key)

    # A generic question: the model must work out on its own that it needs
    # the location first, then the weather for that location.
    question = "What is the current weather here?"
    print(f"Question: {question}")

    try:
        answer = run_agent(client, question)
        print(f"\nAnswer: {answer}")
    except Exception as e:
        print(f"Error occurred while making the request: {e}")


if __name__ == "__main__":
    main()

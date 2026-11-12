import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

def get_current_location():
    """
    Tool to get the current location based on IP address using ipapi.co.
    Returns location information including city, region, country, and coordinates.
    """
    try:
        print("Getting location from ipapi.co...")
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
            print("Successfully got location from ipapi.co")
            return location_info
        else:
            raise ValueError("No coordinates received from ipapi.co")
            
    except Exception as e:
        print(f"Error getting location: {e}")
        return None

def get_weather(latitude, longitude, city="Unknown"):
    """
    Get current weather information for given coordinates.
    Uses wttr.in - a free weather service that doesn't require API keys.
    Returns weather data in JSON format.
    """
    try:
        # Use wttr.in API - free service, no API key required
        # Format: wttr.in/{latitude},{longitude}?format=j1
        url = f"https://wttr.in/{latitude},{longitude}"
        params = {
            'format': 'j1',  # JSON format with current weather only
            'lang': 'en'     # English language
        }
        
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
        return {
            "error": f"Error getting weather data: {e}"
        }
    except (KeyError, IndexError) as e:
        return {
            "error": f"Error parsing weather data: {e}"
        }


def execute_function(function_name, arguments):
    """
    Execute the requested function with given arguments.
    """
    if function_name == "get_current_location":
        return get_current_location()
    elif function_name == "get_weather":
        return get_weather(**arguments)
    else:
        return f"Unknown function: {function_name}"

# Safety check: the most tools we will run for one question.
# This question needs exactly 2 (location, then weather).
#
# Why this matters: every time around the loop, the WHOLE conversation
# (including every earlier tool result) is sent to the model again. If this
# check is removed and the model keeps asking for tools, the loop never ends
# and token usage (and cost) keeps growing with every round.
MAX_TOOL_RUNS = 2

def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    
    # Get API key from environment variables
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Define tools for OpenAI function calling
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_location",
                "description": "Get the user's current location based on IP address using ipapi.co. This must be called first before getting weather data.",
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
                "description": "Get comprehensive current weather information for specific coordinates using wttr.in (free service, no API key required). This should be called after getting the location coordinates.",
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
    
    # The question to ask - generic approach that lets the model figure out the steps
    question = "What is the current weather here?"
    print(f"Asking OpenAI: {question}")
    
    # The conversation. Every model reply and tool result is added here,
    # and the whole list is sent to the model each time around the loop.
    messages = [{"role": "user", "content": question}]
    
    loop_count = 0  # how many times we have asked the model
    tool_runs = 0   # how many tools we have run (checked against MAX_TOOL_RUNS)
    
    try:
        # The agent loop: ask the model, run the tools it asks for, repeat
        # until it answers without asking for a tool.
        while True:
            loop_count += 1
            print(f"\nLoop {loop_count}")
            
            # Safety check: once the limit is reached, tool_choice="none"
            # stops the model from asking for more tools, so it must answer.
            # This guarantees the loop ends.
            if tool_runs >= MAX_TOOL_RUNS:
                tool_choice = "none"
            else:
                tool_choice = "auto"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
            message = response.choices[0].message
            
            # No tool calls means the model has its final answer: stop looping.
            if not message.tool_calls:
                print(f"\nAnswer: {message.content.strip()}")
                break
            
            # Add the model's tool request to the conversation
            messages.append(message)
            
            # Run each tool the model asked for and add its result
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                
                # Safety check: the model can ask for several tools at once,
                # so check the limit before every run, not just once per loop.
                # Every request still needs a reply, so send back an error.
                if tool_runs >= MAX_TOOL_RUNS:
                    function_result = {"error": "Tool run limit reached"}
                else:
                    tool_runs += 1
                    function_args = json.loads(tool_call.function.arguments)
                    print(f"Executing function: {function_name} (tool run {tool_runs} of {MAX_TOOL_RUNS})")
                    function_result = execute_function(function_name, function_args)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(function_result)
                })
        
    except Exception as e:
        print(f"Error occurred while making the request: {e}")

if __name__ == "__main__":
    main()

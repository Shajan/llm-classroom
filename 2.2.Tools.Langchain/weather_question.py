import os
import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool

# The same agent as 2.1.Tools, using LangChain.
# The tool functions are the same as 2.1. Two things change:
#   1. @tool builds each tool's schema from its type hints and docstring,
#      so there is no hand-written `tools` list.
#   2. create_agent() runs the agent loop that 2.1 writes by hand.

@tool
def get_current_location() -> dict:
    """Get the user's current location based on IP address using ipapi.co. This must be called first before getting weather data."""
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

@tool
def get_weather(latitude: float, longitude: float, city: str = "Unknown") -> dict:
    """Get comprehensive current weather information for specific coordinates using wttr.in (free service, no API key required). This should be called after getting the location coordinates."""
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


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    if not os.getenv('OPENAI_API_KEY'):
        print("Error: OPENAI_API_KEY not found in environment variables")
        return

    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[get_current_location, get_weather],
        # Safety check, same as MAX_TOOL_RUNS in 2.1: at most 2 tool runs.
        # Every time around the loop, the WHOLE conversation is sent to the
        # model again. If this check is removed and the model keeps asking for
        # tools, token usage (and cost) keeps growing with every round.
        middleware=[ToolCallLimitMiddleware(run_limit=2, exit_behavior="end")],
    )

    question = "What is the current weather here?"
    print(f"Asking OpenAI: {question}")

    try:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        print(f"\nAnswer: {result['messages'][-1].content}")
    except Exception as e:
        print(f"Error occurred while making the request: {e}")

if __name__ == "__main__":
    main()

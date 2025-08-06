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

def main():
    load_dotenv("../.env")
    
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
    
    try:
        print(f"Asking OpenAI: What is the current weather here?")
        
        # Send initial request with tools
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": question}
            ],
            tools=tools,
            tool_choice="auto"
        )
        
        # Process the response
        message = response.choices[0].message
        
        # Check if the model wants to call functions
        if message.tool_calls:
            # Prepare messages for the conversation
            messages = [
                {"role": "user", "content": question},
                message
            ]
            
            # Execute each function call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"Executing function: {function_name}")
                
                # Call the function
                function_result = execute_function(function_name, function_args)
                
                # Add function result to messages
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(function_result)
                })
            
            # Get final response with function results
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            # Handle potential second round of function calls
            final_message = final_response.choices[0].message
            
            if final_message.tool_calls:
                # Add the assistant's message to conversation
                messages.append(final_message)
                
                # Execute any additional function calls
                for tool_call in final_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"Executing function: {function_name}")
                    
                    # Call the function
                    function_result = execute_function(function_name, function_args)
                    
                    # Add function result to messages
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_result)
                    })
                
                # Get the final answer
                final_answer_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages
                )
                
                answer = final_answer_response.choices[0].message.content.strip()
            else:
                answer = final_message.content.strip()
            
            print(f"\nAnswer: {answer}")
        else:
            # If no function calls, just show the response
            answer = message.content.strip()
            print(f"Answer: {answer}")
        
    except Exception as e:
        print(f"Error occurred while making the request: {e}")

if __name__ == "__main__":
    main()

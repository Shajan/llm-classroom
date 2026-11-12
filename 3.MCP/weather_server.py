"""
MCP server exposing the same two weather tools as 2.1.Tools.

The tool functions are the same as 2.1. The only MCP-specific parts are:
  - MCPServer("weather") creates the server
  - @mcp.tool() publishes a function as a tool (schema comes from the
    type hints, description from the docstring - like @tool in 2.2)
  - mcp.run() talks to the client over stdin/stdout

Because stdout carries the protocol, never print() in an MCP server.
"""
import requests
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("weather")

@mcp.tool()
def get_current_location():
    """Get the user's current location based on IP address using ipapi.co. This must be called first before getting weather data."""
    try:
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
        return None

@mcp.tool()
def get_weather(latitude: float, longitude: float, city: str = "Unknown"):
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


if __name__ == "__main__":
    mcp.run()

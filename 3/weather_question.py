import os
import json
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Optional

from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field


class LocationTool(BaseTool):
    """Tool to get the current location based on IP address using ipapi.co."""
    
    name: str = "get_current_location"
    description: str = "Get the user's current location based on IP address using ipapi.co. This must be called first before getting weather data."
    
    def _run(self) -> Dict[str, Any]:
        """
        Get current location information including city, region, country, and coordinates.
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
            return {"error": f"Failed to get location: {e}"}


class WeatherInput(BaseModel):
    """Input schema for weather tool."""
    latitude: float = Field(description="Latitude of the location")
    longitude: float = Field(description="Longitude of the location")
    city: Optional[str] = Field(default="Unknown", description="City name for reference")


class WeatherTool(BaseTool):
    """Tool to get current weather information for given coordinates."""
    
    name: str = "get_weather"
    description: str = "Get comprehensive current weather information for specific coordinates using wttr.in (free service, no API key required). This should be called after getting the location coordinates."
    args_schema: type[BaseModel] = WeatherInput
    
    def _run(self, latitude: float, longitude: float, city: str = "Unknown") -> Dict[str, Any]:
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


def create_weather_agent():
    """Create and configure the weather agent using LangChain."""
    
    # Load environment variables
    load_dotenv("../.env")
    
    # Get API key from environment variables
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("Error: OPENAI_API_KEY not found in environment variables")
    
    # Initialize the language model
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0
    )
    
    # Create tools
    tools = [LocationTool(), WeatherTool()]
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are a helpful weather assistant. When asked about the weather, you should:
1. First get the user's current location using the get_current_location tool
2. Then use the get_weather tool with the coordinates from the location to get current weather information
3. Provide a clear, friendly response about the weather conditions

Always use the tools to get real-time data rather than making assumptions."""),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    # Create the agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True
    )
    
    return agent_executor


def main():
    """Main function to run the weather agent."""
    try:
        # Create the weather agent
        agent_executor = create_weather_agent()
        
        # The question to ask
        question = "What is the current weather here?"
        
        print(f"Asking the weather agent: {question}")
        print("-" * 50)
        
        # Run the agent
        result = agent_executor.invoke({"input": question})
        
        print("-" * 50)
        print(f"Final Answer: {result['output']}")
        
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()

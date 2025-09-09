# Weather Application - LangChain Implementation

This folder contains a LangChain-based implementation of the weather application from folder `2.1.Tools`.

## Key Differences from Folder 2.1.Tools

### Folder 2.1.Tools (Original Tools Implementation)
- Uses OpenAI's function calling directly
- Manual handling of function execution and response processing
- Explicit conversation management with message arrays
- Direct OpenAI API client usage

### This Folder (LangChain Implementation)
- Uses LangChain's agent framework with OpenAI functions
- Declarative tool definitions using LangChain's `BaseTool` class
- Automatic agent orchestration and conversation management
- Built-in prompt templates and system message handling
- Pydantic models for input validation
- Cleaner separation of concerns

## Core Functionality (Same as Folder 2.1.Tools)

1. **Location Detection**: Uses IP-based geolocation via ipapi.co to get user's current coordinates
2. **Weather Retrieval**: Fetches current weather data using wttr.in (free service, no API key required)
3. **Natural Language Interface**: Processes user questions about weather and automatically determines which tools to use

## Architecture Benefits

The LangChain implementation provides:
- **Better Tool Management**: Tools are self-contained classes with clear interfaces
- **Automatic Agent Logic**: LangChain handles the tool selection and execution flow
- **Enhanced Error Handling**: Built-in error handling and retry mechanisms
- **Extensibility**: Easy to add new tools or modify existing ones
- **Type Safety**: Pydantic models ensure proper input validation
- **Observability**: Built-in verbose mode for debugging agent decisions

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python weather_question.py
```

The application will automatically:
1. Detect your location based on your IP address
2. Fetch current weather conditions
3. Provide a natural language response about the weather

## Environment Variables

Make sure you have an `.env` file in the parent directory with:
```
OPENAI_API_KEY=your_openai_api_key_here
```

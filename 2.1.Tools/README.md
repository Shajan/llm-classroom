# Weather Application - Tools / Direct Function Calling Implementation

This folder (`2.1.Tools`) contains the direct OpenAI function-calling implementation of the weather application.

It demonstrates how to:
- Define tool (function) schemas inline and pass them to OpenAI's Chat Completions API
- Let the model decide which functions to call and in what order (`tool_choice="auto"`)
- Execute those functions locally and feed structured JSON results back into the conversation

## Features
- IP-based geolocation using `ipapi.co`
- Real-time weather data via `wttr.in` (no API key required)
- Two tools: `get_current_location` and `get_weather`
- Graceful error handling and validation
- Clear console logging of function execution steps

## How It Works
1. The user question ("What is the current weather here?") is sent with the tool definitions.
2. The model responds with one or more `tool_calls` (typically first `get_current_location`, then `get_weather`).
3. The script executes each function, appends the results as `tool` messages, and sends a follow-up request to get the final natural language answer.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
From the repository root (so the parent `.env` is discovered):
```bash
python 2.1.Tools/weather_question.py
```

## Environment Variables
Ensure the parent directory (`..`) has a `.env` file with:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Relationship to LangChain Version
The LangChain agent-based version lives in `../2.2.Tools.Langchain` and provides:
- Declarative tool classes (`BaseTool`)
- Automatic agent planning and orchestration
- Pydantic-based input validation

This folder keeps the minimal, transparent version for learning the raw function calling flow before introducing LangChain abstractions.

## Extending
To add another tool:
1. Write a Python function that returns JSON-serializable data.
2. Add a new entry to the `tools` list with its JSON schema.
3. Handle its execution in `execute_function`.
4. Ask a question that would require the model to call it.

## Troubleshooting
- If no function calls are produced, try rewording the question to imply real-time data.
- Network issues (timeouts) will print an error and the model may answer with limited information.
- Ensure your system clock and internet connection are working correctly for API calls.

Enjoy exploring function calling!

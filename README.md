# LLM Classroom

A collection of simple examples and exercises for working with Large Language Models (LLMs) and AI APIs.

## Structure

This repository contains multiple projects, each in its own numbered folder:
- `/llm.shell` - Interactive LLM Chat Interface (Streamlit App)
- `/1` - OpenAI API Question Example
- `/2` - Weather Question with Function Calling

Each folder contains its own `requirements.txt` file with the specific dependencies needed for that project.

## Prerequisites

- Python 3.7+
- OpenAI API key (stored in `.env` file)
- Internet connection for API calls

## Setup

1. **Ensure API key is configured:**
   Create a `.env` file in the root folder (same folder as this README) with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

2. **Setup Python environment** (if not already done):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or .venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies:**
   Example: for project in folder 'XXX'
   ```bash
   pip install -r XXX/requirements.txt
   ```

4. **Execute the main function:**
   ```bash
   python XXX/yyy.py
   ```


## Projects

### Interactive LLM Chat Interface (Folder: `/llm.shell`)

A modern web-based chat interface built with Streamlit that provides an interactive conversation experience with OpenAI's language models.

**What it does:**
- Provides a real-time chat interface similar to ChatGPT
- Automatically detects and lists available OpenAI models you have access to
- Maintains conversation history throughout the session
- Allows you to switch between different OpenAI models
- Includes chat management features (clear history, message counts)

**Features:**
- **Dynamic Model Selection:** Automatically fetches and displays only the OpenAI models you have access to
- **Real-time Chat:** Interactive chat interface with immediate responses
- **Conversation Management:** Clear chat history, view message statistics
- **Modern UI:** Clean, responsive design built with Streamlit
- **Error Handling:** Comprehensive error handling for API issues
- **Session Persistence:** Maintains chat history during your session

**Run the app (from root folder):**
   ```bash
   # Install dependencies
   pip install -r llm.shell/requirements.txt
   
   # Start the Streamlit app
   streamlit run llm.shell/app.py
   ```

**Expected Behavior:**
- Opens a web browser with the chat interface at `http://localhost:8501`
- Sidebar shows available OpenAI models and chat controls
- Main area provides the chat interface
- Real-time conversation with selected language model
- Statistics showing message counts and conversation metrics


### 1. OpenAI API Question Example (Folder: `/1`)

A simple Python script that demonstrates how to send HTTP requests to OpenAI's API and display the response.

**What it does:**
- Connects to OpenAI's API using a secure API key
- Sends a question: "What is the capital of France?"
- Displays the AI's response in a clear format
- Includes proper error handling and environment variable management

**Features:**
- Minimal and easy-to-understand code
- Secure API key management using environment variables
- Uses the cost-effective `gpt-4o-mini` model
- Proper error handling for API failures
- Clear output formatting

**Run the script:**
   ```bash
   python 1/openai_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the capital of France?
Answer: The capital of France is Paris.
```

### 2. Weather Question with Function Calling (Folder: `/2`)

An advanced Python script that demonstrates OpenAI's function calling capabilities to get real-time weather information.

**What it does:**
- Asks the AI model: "What is the current weather here?"
- Automatically detects your location using IP geolocation
- Fetches real-time weather data using free APIs
- Provides natural language weather reports

**Features:**
- **Two custom tools/functions:**
  - `get_current_location()`: Gets location based on IP address (uses ipapi.co - free service)
  - `get_weather()`: Gets weather data for given coordinates (uses Open-Meteo API - free service)
- OpenAI function calling integration
- No additional API keys required for weather data
- Comprehensive error handling
- Real-time data from external APIs

**Run the script (from root folder):**
   ```bash
   python 2/weather_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the current weather here?
Executing function: get_current_location
Executing function: get_weather

Answer: Based on your current location in [City], the weather is currently [temperature] with [description]. The humidity is [humidity] and wind speed is [wind speed].
```


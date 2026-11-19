# LLM Classroom

A collection of simple examples and exercises for working with Large Language Models (LLMs) and AI APIs.

## Structure

This repository contains multiple projects, each in its own numbered folder:
- `/llm.shell` - Interactive LLM Chat Interface (Streamlit App)
- `/1.HelloLLM` - OpenAI API Question Example
- `/2.1.Tools` - Weather Question with Function Calling
- `/2.2.Tools.Langchain` - Weather Question with LangChain Agents
- `/3.MCP` - Model Context Protocol (MCP): tools served from separate processes
- `/4.RAG` - RAG (Retrieval-Augmented Generation): answer from your own documents
- `/5.Agent` - Long-running, checkpointed equity research pipeline

Each folder contains its own `requirements.txt` file with the specific dependencies needed for that project.

## Prerequisites

- Python 3.7+ (3.10+ for `/5.Agent`)
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


### 1. OpenAI API Question Example (Folder: `/1.HelloLLM`)

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
   python 1.HelloLLM/openai_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the capital of France?
Answer: The capital of France is Paris.
```

### 2.1. Weather Question with Function Calling (Folder: `/2.1.Tools`)

A Python script that shows OpenAI function calling as an agent loop: the model keeps asking for tools until it has enough to answer.

**What it does:**
- Asks the AI model: "What is the current weather here?"
- Loops: send the conversation to the model, run the tools it asks for, add the results, repeat until it answers
- Counts loops, and stops after 2 tool runs as a safety check (without it, a model that keeps calling tools would keep using tokens)

**Tools:**
- `get_current_location()`: Gets location based on IP address (uses ipapi.co - free service)
- `get_weather()`: Gets weather data for given coordinates (uses wttr.in - free service)

**Run the script (from root folder):**
   ```bash
   python 2.1.Tools/weather_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the current weather here?

Loop 1
Executing function: get_current_location (tool run 1 of 2)

Loop 2
Executing function: get_weather (tool run 2 of 2)

Loop 3

Answer: The current weather in [City] is [temperature] and [description] ...
```

### 2.2. Weather Question with LangChain (Folder: `/2.2.Tools.Langchain`)

The same agent as 2.1, using LangChain. The tool functions are the same; two things change:
- **`@tool` decorator:** builds each tool's schema from its type hints and docstring, replacing the hand-written `tools` list
- **`create_agent(...)`:** runs the agent loop that 2.1 writes by hand

The same 2-tool-run safety check is set with `ToolCallLimitMiddleware(run_limit=2)`.

**Run the script (from root folder):**
   ```bash
   pip install -r 2.2.Tools.Langchain/requirements.txt
   python 2.2.Tools.Langchain/weather_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the current weather here?

Answer: The current weather in [City] is [temperature] and [description] ...
```

### 3. MCP: Tools from Separate Servers (Folder: `/3.MCP`)

The 2.2 agent (`create_agent`), but the tools live in separate processes called MCP (Model Context Protocol) servers. The chat client defines no tools. It starts the servers listed in `mcp_config.yaml`, asks each one for its tools, wraps them as LangChain tools, and passes the agent's tool calls to them.

**Files:**
- `weather_server.py`: the same two tools as 2.1, published with `@mcp.tool()`
- `browser_server.py`: a second server that opens a web page and returns its text
- `mcp_config.yaml`: which servers to start; add a server here to add tools
- `chat_client.py`: starts the servers, collects their tools, runs the 2.2 agent

**Run (from root folder):**
   ```bash
   pip install -r 3.MCP/requirements.txt
   python -m playwright install chromium
   python 3.MCP/chat_client.py
   ```

Then ask "What is the weather here?" or "Browse https://en.wikipedia.org/wiki/Kerala and tell me its capital."

### 4. RAG: Answer from Your Own Documents (Folder: `/4.RAG`)

RAG (Retrieval-Augmented Generation) lets the model answer questions about documents it has never seen. `docs/handbook.txt` is a made-up company handbook.

**How it works:**
- **Index:** split the documents into chunks and turn each chunk into an embedding (a vector that captures its meaning)
- **Retrieve:** embed the question and find the closest chunks
- **Generate:** paste those chunks into the prompt and ask the model, with the same call as 1.HelloLLM

**Run (from root folder):**
   ```bash
   pip install -r 4.RAG/requirements.txt
   python 4.RAG/rag_chat.py
   ```

**Expected Output:**
```
Indexed 6 chunks from docs/

You (empty line to quit): How many vacation days do I get?
  retrieved [0.55] Vacation. Full-time employees at Brightleaf Robotics get 22 ...
  retrieved [0.32] Remote work. Employees may work from home on Mondays and Fri...

Assistant: You get 22 days of paid vacation per year.
```

### 5. Equity Research Pipeline (Folder: `/5.Agent`)

A long-running, checkpointed pipeline that researches a U.S.-listed stock and estimates a fair value. It does not call an LLM; it shows the long-running, resumable side of agent design (caching, retries, checkpoints, graceful shutdown).

**What it does:**
- Fetches SEC EDGAR filings (company submissions and XBRL facts) with caching and retry
- Builds income, balance sheet and cash flow tables and computes key ratios
- Looks up market cap, peers and a sector benchmark ETF via yfinance
- Gets the 10-year Treasury rate from FRED (or uses a 4% default)
- Blends a 5-year DCF (60%) with a peer P/E valuation (40%)
- Saves `state.json` checkpoints and writes `valuation_report.md`

**Run the script (from root folder):**
   ```bash
   pip install -r 5.Agent/requirements.txt

   # Optional: these are read from the shell environment, not from .env
   export SEC_API_EMAIL=you@example.com
   export FRED_API_KEY=your_fred_key

   python 5.Agent/agent.py --ticker AAPL
   ```

Outputs go to `5.Agent/output/<TICKER>/`. See `5.Agent/README.md` and `5.Agent/docs/` for details. Educational use only; not investment advice.


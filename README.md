# LLM Classroom

A collection of simple examples and exercises for working with Large Language Models (LLMs) and AI APIs.

## Structure

This repository contains multiple projects, each in its own numbered folder:
- `/llm.shell` - Interactive LLM Chat Interface (Streamlit App)
- `/1.HelloLLM` - OpenAI API Question Example
- `/2.1.Tools` - Weather Question with Function Calling
- `/2.2.Tools.Langchain` - Weather Question with LangChain Agents
- `/3.MCP` - Model Context Protocol (MCP): tools served from separate processes
- `/4.1.RAG` - RAG (Retrieval-Augmented Generation): answer from your own documents
- `/4.2.RAG.VectorDB` - The same RAG, with a vector database (Chroma)
- `/5.Agent` - Long-running agent that resumes after it is stopped

Each folder contains its own `requirements.txt` file with the specific dependencies needed for that project.

## Prerequisites

- Python 3.10+
- OpenAI API key (stored in `.env` file)
- Internet connection for API calls

## Setup

1. **Ensure API key is configured:**
   Copy `.env.example` to `.env` in the root folder (same folder as this README), then add your OpenAI API key:
   ```bash
   cp .env.example .env
   ```
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
   `LANGSMITH_API_KEY` is optional. It turns on tracing in 3.MCP.

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

4. **Run the example:** each project below shows its run command. Run everything from the root folder.


## Projects

### Interactive LLM Chat Interface (Folder: `/llm.shell`)

A web chat interface for OpenAI models, built with Streamlit.

**What it does:**
- A chat interface similar to ChatGPT that keeps the conversation history during the session
- Lists the low-cost `mini`/`nano` GPT models your API key can use (default `gpt-4o-mini`)
- Sidebar with a Clear Chat button and message counts

**Run the app (from root folder):**
   ```bash
   # Install dependencies
   pip install -r llm.shell/requirements.txt
   
   # Start the Streamlit app
   streamlit run llm.shell/app.py
   ```

This opens the chat interface in your browser at `http://localhost:8501`.


### 1. OpenAI API Question Example (Folder: `/1.HelloLLM`)

The smallest possible example: send one question to the model with the OpenAI Python library and print the answer.

**What it does:**
- Reads the API key from `.env`
- Sends "What is the capital of France?" to the low-cost `gpt-4o-mini` model
- Prints the answer

**Run the script (from root folder):**
   ```bash
   pip install -r 1.HelloLLM/requirements.txt
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
   pip install -r 2.1.Tools/requirements.txt
   python 2.1.Tools/weather_question.py
   ```

**Expected Output:**
```
Asking OpenAI: What is the current weather here?

Loop 1
Executing function: get_current_location (tool run 1 of 2)
Getting location from ipapi.co...
Successfully got location from ipapi.co

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
Getting location from ipapi.co...
Successfully got location from ipapi.co

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

### 4.1. RAG: Answer from Your Own Documents (Folder: `/4.1.RAG`)

RAG (Retrieval-Augmented Generation) lets the model answer questions about documents it has never seen. `docs/handbook.txt` is a made-up company handbook.

**How it works:**
- **Index:** split the documents into chunks and turn each chunk into an embedding (a vector that captures its meaning)
- **Retrieve:** embed the question and find the closest chunks
- **Generate:** paste those chunks into the prompt and ask the model, with the same call as 1.HelloLLM

**Run (from root folder):**
   ```bash
   pip install -r 4.1.RAG/requirements.txt
   python 4.1.RAG/rag_chat.py
   ```

**Expected Output:**
```
Indexed 6 chunks from docs/

You (empty line to quit): How many vacation days do I get?
  retrieved [0.55] Vacation. Full-time employees at Brightleaf Robotics get 22 ...
  retrieved [0.32] Remote work. Employees may work from home on Mondays and Fri...

Assistant: You get 22 days of paid vacation per year.
```

### 4.2. RAG with a Vector Database (Folder: `/4.2.RAG.VectorDB`)

The same as 4.1, but the chunks and embeddings are stored in Chroma, a vector database, instead of a NumPy array:
- **Store:** saved to `chroma_db/` on disk, so the documents are embedded once, not on every start
- **Search:** `collection.query(...)` replaces the dot product and sort from 4.1

It returns the same chunks with the same scores as 4.1.

**Run (from root folder):**
   ```bash
   pip install -r 4.2.RAG.VectorDB/requirements.txt
   python 4.2.RAG.VectorDB/rag_chat.py
   ```

### 5. Agent: Long-Running and Resumable (Folder: `/5.Agent`)

The 2.2 agent researches a stock (SEC filings and Yahoo Finance tools) and estimates a fair value. The new idea is a **checkpointer**: the agent's state is saved after every step, so a run that is stopped part way resumes from the last saved step.

**Run (from root folder):**
   ```bash
   pip install -r 5.Agent/requirements.txt
   python 5.Agent/research_agent.py NVDA
   ```

Press Ctrl+C after the first `Tool:` line, then run the same command again. It prints `Resuming the stopped run for NVDA` and finishes. Educational only; not investment advice.

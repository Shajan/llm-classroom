# LLM Classroom

A collection of simple examples and exercises for working with Large Language Models (LLMs) and AI APIs.

## Structure

This repository contains multiple projects, each in its own numbered folder:
- `/llm.shell` - Interactive LLM Chat Interface (Streamlit App)
- `/1` - OpenAI API Question Example
- `/2` - Weather Question with Function Calling
- `/3` - Weather Question with LangChain Agents
- `/3.MCP` - Model Context Protocol (MCP) multi-server tools + terminal & Streamlit chat clients
- `/4` - RAG Chat Application (Retrieval-Augmented Generation)

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

### 3. Weather Question with LangChain Agents (Folder: `/3`)

A sophisticated implementation of the weather application using LangChain's agent framework, demonstrating modern AI development patterns and best practices.

**What it does:**
- Implements the same weather functionality as folder 2, but using LangChain
- Uses LangChain agents for automatic tool orchestration
- Provides the same natural language weather reporting capabilities
- Demonstrates modern AI application architecture

**Key Improvements over Folder 2:**
- **Agent Framework:** Uses LangChain's `create_openai_functions_agent` for automatic tool selection and execution
- **Tool Classes:** Implements tools as proper LangChain `BaseTool` classes with clear interfaces
- **Type Safety:** Uses Pydantic models for input validation and type checking
- **Better Architecture:** Cleaner separation of concerns and more maintainable code
- **Built-in Features:** Automatic conversation management, prompt templates, and enhanced error handling
- **Observability:** Built-in verbose mode for debugging agent decisions

**Features:**
- **Two LangChain tools:**
  - `LocationTool`: IP-based location detection using ipapi.co
  - `WeatherTool`: Weather data retrieval using wttr.in API with Pydantic input validation
- Automatic agent orchestration and tool selection
- System message-driven behavior with clear instructions
- Enhanced error handling and retry mechanisms
- Type-safe tool inputs with schema validation
- Verbose execution mode for debugging

**Run the script (from root folder):**
   ```bash
   # Install LangChain dependencies
   pip install -r 3/requirements.txt
   
   # Run the LangChain implementation
   python 3/weather_question.py
   ```

**Expected Output:**
```
Asking the weather agent: What is the current weather here?
--------------------------------------------------
> Entering new AgentExecutor chain...
[Tool execution details with verbose logging]
--------------------------------------------------
Final Answer: Based on your current location in [City], the weather is currently [temperature] with [description]. The humidity is [humidity] and wind speed is [wind speed].
```

**Architecture Benefits:**
- More declarative approach to defining agent behavior
- Easier to extend with new tools or modify existing ones
- Better debugging capabilities with built-in verbose mode
- Enhanced type safety and input validation
- Cleaner prompt management with system messages
- Automatic conversation flow management

### 3.MCP. Model Context Protocol Multi-Tool Chat (Folder: `/3.MCP`)

An educational implementation of the emerging Model Context Protocol (MCP) pattern. It shows how to expose external tool capabilities (weather lookup, web search, Playwright browsing) via lightweight JSONL MCP servers and let an OpenAI model call them automatically—either from a terminal chat or a Streamlit UI.

**What it provides:**
- Multiple standalone MCP servers (weather, search, optional Playwright browser)
- A shared `MCPManager` (`mcp_core.py`) that spawns enabled servers, lists tools, and dispatches tool calls
- A terminal chat client (`chat_client.py`) that performs automatic tool calling (function-calling style)
- A Streamlit chat UI (`streamlit_app.py`) to enable/disable/add servers dynamically
- Config-driven server list (`mcp_config.yaml`)
- Screenshot / large-payload sanitization to control token costs

**Primary Servers (all JSONL over stdio):**
- `mcp_server.py` – location + weather (`get_current_location`, `get_weather`)
- `mcp_search_server.py` – lightweight DuckDuckGo instant answer search (`web_search`)
- `mcp_playwright_server.py` – headless (or headed) Chromium browsing & optional screenshot capture (`browse_page`)

**Why MCP here?**
It demonstrates the pattern of: model decides -> tool call -> external capability -> result fed back to model; while isolating each capability into a simple, restartable subprocess you can extend or replace.

**Quick Start (Terminal Chat):**
```bash
# Install dependencies
pip install -r 3.MCP/requirements.txt

# (Optional) Install browser engine for Playwright tool
python -m playwright install chromium

# Start chat directly (spawns enabled servers listed in mcp_config.yaml)
python 3.MCP/chat_client.py

# Ask something that triggers tools
> What's the weather where I am right now?
```

**Quick Start (Streamlit UI):**
```bash
pip install -r 3.MCP/requirements.txt
streamlit run 3.MCP/streamlit_app.py
```
Opens a browser UI where you can:
- View & toggle servers (enable/disable)
- Add new server definitions (persisted back to `mcp_config.yaml`)
- Chat with automatic tool usage & see tool outputs

**Playwright Browser Tool (Optional):**
```bash
python -m playwright install chromium  # once
export MCP_PLAYWRIGHT_HEADLESS=0       # set to 0 / false for a visible window (optional)
python 3.MCP/chat_client.py            # or use the Streamlit UI
```
Then ask: "Browse https://example.com and extract the main heading." The model may call `browse_page`.

Key tool arguments for `browse_page` (see folder README for full details):
- `url` (required) – http/https URL
- `selector` – optional CSS selector to narrow extraction
- `text_only` (default True) – return text vs raw HTML
- `screenshot` (default True) – capture screenshot (removed from LLM prompt to save tokens)
- `headed` – launch a visible browser window for debugging

**Token Economy Note:** Large screenshot base64 blobs are stripped before being added to the model conversation (a metadata flag indicates omission) to avoid large prompt costs.

**Extending with a New Server:**
1. Write a small script that implements the same minimal protocol (`list_tools` / `call_tool`).
2. Add it to `mcp_config.yaml`:
    ```yaml
    - name: my_custom
       command: python
       args: [3.MCP/my_custom_server.py]
       enabled: true
    ```
3. Restart the chat or Streamlit UI; the new tools appear automatically.

For deeper details (headed mode, screenshot handling, future enhancements) see the dedicated `3.MCP/README.md`.


### 4. RAG Chat Application (Folder: `/4`)

A sophisticated Retrieval-Augmented Generation (RAG) chat application that allows users to upload documents, build a knowledge base, and ask questions based on the uploaded content.

**What it does:**
- Upload documents (PDF, DOCX, TXT) or provide URLs to build a knowledge base
- Automatically processes and indexes documents using vector embeddings
- Answers questions using relevant content from uploaded documents as context
- Provides a modern Streamlit web interface similar to the LLM chat in `/llm.shell`

**Key Features:**
- **Document Processing:** Extract text from PDF, DOCX, and TXT files
- **URL Content:** Fetch and process content from web URLs
- **Vector Database:** Uses ChromaDB for persistent semantic search
- **Smart Chunking:** Splits documents into overlapping chunks for better context
- **RAG Pipeline:** Retrieves relevant context before generating responses
- **Real-time Processing:** Documents are indexed immediately upon upload
- **Multiple Models:** Support for various OpenAI models
- **Knowledge Base Stats:** Monitor the size and content of your knowledge base

**Technical Architecture:**
- **VectorStore:** ChromaDB with Sentence Transformers embeddings (all-MiniLM-L6-v2)
- **DocumentProcessor:** Multi-format text extraction and URL content fetching
- **RAGChat:** Context-aware response generation using retrieved documents
- **Streamlit UI:** Modern web interface with file upload and chat capabilities

**Run the app (from root folder):**
   ```bash
   # Install dependencies
   pip install -r 4/requirements.txt
   
   # Start the RAG chat application
   streamlit run 4/rag_app.py
   ```

**Note:** The application will create the following files during operation:
- `4/chroma_db/` - Vector database storage (persisted between sessions)
- `4/rag_app.log` - Application logs with detailed processing information

These files are excluded from git tracking via `.gitignore`.

**Usage Workflow:**
1. **Upload Documents:** Use the sidebar to upload PDF, DOCX, or TXT files
2. **Add URLs:** Enter web URLs to fetch and index content
3. **Monitor Progress:** Check knowledge base statistics in the sidebar
4. **Ask Questions:** Chat naturally about your uploaded content
5. **Get Contextual Answers:** Receive responses based on your documents

**Expected Behavior:**
- Opens a web browser with the RAG chat interface at `http://localhost:8501`
- Sidebar allows document upload and URL input
- Documents are processed and added to the vector database in real-time
- Main chat area provides contextual responses based on uploaded content
- Knowledge base statistics show the number of indexed document chunks
- Responses include relevant context from the uploaded documents

**Example Interaction:**
```
1. Upload a PDF about machine learning
2. Ask: "What is supervised learning?"
3. Receive: Answer based on the content from your uploaded PDF, 
   with relevant excerpts used as context for the response
```


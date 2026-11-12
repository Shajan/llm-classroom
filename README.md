# LLM Classroom

A collection of simple examples and exercises for working with Large Language Models (LLMs) and AI APIs.

## Structure

This repository contains multiple projects, each in its own numbered folder:
- `/llm.shell` - Interactive LLM Chat Interface (Streamlit App)
- `/1.HelloLLM` - OpenAI API Question Example
- `/2.1.Tools` - Weather Question with Function Calling
- `/2.2.Tools.Langchain` - Weather Question with LangChain Agents
- `/3.MCP` - Model Context Protocol (MCP): tools served from separate processes
- `/4.RAG` - RAG Chat Application (Retrieval-Augmented Generation)
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

The 2.1 agent, but the tools live in separate processes called MCP (Model Context Protocol) servers. The chat client defines no tools. It starts the servers listed in `mcp_config.yaml`, asks each one for its tools, and passes the model's tool calls to them.

**Files:**
- `weather_server.py`: the same two tools as 2.1, published with `@mcp.tool()`
- `browser_server.py`: a second server that opens a web page and returns its text
- `mcp_config.yaml`: which servers to start; add a server here to add tools
- `chat_client.py`: starts the servers, collects their tools, runs the 2.1 agent loop

**Run (from root folder):**
   ```bash
   pip install -r 3.MCP/requirements.txt
   python -m playwright install chromium
   python 3.MCP/chat_client.py
   ```

Then ask "What is the weather here?" or "Browse https://example.com and tell me the main heading."

### 4. RAG Chat Application (Folder: `/4.RAG`)

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
   pip install -r 4.RAG/requirements.txt
   
   # Start the RAG chat application
   streamlit run 4.RAG/rag_app.py
   ```

**Note:** The application will create the following files during operation:
- `4.RAG/chroma_db/` - Vector database storage (persisted between sessions)
- `4.RAG/rag_app.log` - Application logs with detailed processing information

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


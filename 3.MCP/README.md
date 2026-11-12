# MCP Example

The 2.2 agent (`create_agent`), but the tools live in separate processes called **MCP servers**. The chat client doesn't define any tools. It asks the servers what they offer and passes the agent's tool calls to them.

## Files

| File | What it shows |
|---|---|
| `weather_server.py` | The same two tools as 2.1, published with `@mcp.tool()` |
| `browser_server.py` | A second server: opens a web page and returns its text |
| `mcp_config.yaml` | Which servers the client starts |
| `chat_client.py` | Starts the servers, collects their tools, runs the 2.2 agent |

## How It Works

1. **Server:** `MCPServer("weather")` creates a server. `@mcp.tool()` publishes a function as a tool. The schema comes from the type hints and the description from the docstring, like `@tool` in 2.2.
2. **Connect:** the client starts each server in `mcp_config.yaml` as a subprocess and talks to it over stdin/stdout. It calls `initialize` (handshake), then `list_tools`.
3. **Bridge:** each MCP tool is wrapped as a LangChain `StructuredTool`. MCP and LangChain both describe parameters with JSON Schema, so the server's schema passes through unchanged.
4. **Agent:** the wrapped tools go to `create_agent`, exactly as in 2.2. When the agent calls a tool, the wrapper sends `call_tool` to the server that owns it.

To add tools, write a new server and add it to `mcp_config.yaml`. The client code doesn't change.

Because stdout carries the protocol, an MCP server must never `print()`.

## Setup

From the repository root:

```bash
pip install -r 3.MCP/requirements.txt
python -m playwright install chromium   # for browser_server.py
```

The client reads `OPENAI_API_KEY` from the `.env` file in the repository root.

## Run

```bash
python 3.MCP/chat_client.py
```

Try:

```
What is the weather here?
Browse https://example.com and tell me the main heading.
```

Press Enter on an empty line to quit.

As in 2.2, `ToolCallLimitMiddleware` caps tool runs per question (3 here, since a question may need both servers). Without it, a model that keeps calling tools would keep using tokens.

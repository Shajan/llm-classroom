# MCP Example

The 2.1.Tools agent, but the tools live in separate processes called **MCP servers**. The chat client doesn't define any tools. It asks the servers what they offer and passes the model's tool calls to them.

## Files

| File | What it shows |
|---|---|
| `weather_server.py` | The same two tools as 2.1, published with `@mcp.tool()` |
| `browser_server.py` | A second server: opens a web page and returns its text |
| `mcp_config.yaml` | Which servers the client starts |
| `chat_client.py` | Starts the servers, collects their tools, runs the 2.1 agent loop |

## How It Works

1. **Server:** `MCPServer("weather")` creates a server. `@mcp.tool()` publishes a function as a tool. The schema comes from the type hints and the description from the docstring, like `@tool` in 2.2.
2. **Connect:** the client starts each server in `mcp_config.yaml` as a subprocess and talks to it over stdin/stdout. It calls `initialize` (handshake), then `list_tools`.
3. **Bridge:** MCP and OpenAI both describe tool parameters with JSON Schema, so converting the tool list is just renaming fields.
4. **Call:** when the model asks for a tool, the client sends `call_tool` to the server that owns it and returns the result to the model.

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

As in 2.1, `MAX_TOOL_RUNS` caps tool runs per question. Without it, a model that keeps calling tools would keep using tokens.

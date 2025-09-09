# MCP Example

This folder contains Model Context Protocol (MCP) servers and simple chat clients (terminal + Streamlit) for experimenting with tool calling.

## Contents

- `mcp_server.py` - MCP server built with the official SDK (`FastMCP`, `@mcp.tool`) exposing `get_current_location` and `get_weather`.
- `mcp_search_server.py` - MCP search server (`web_search`) using DuckDuckGo instant answer API.
- `mcp_playwright_server.py` - MCP Playwright browser server (`browse_page`) for page retrieval, text/HTML extraction & screenshots.
- `chat_client.py` - A terminal chat application that:
  - Lets you chat with an OpenAI model
  - Dynamically loads configured MCP servers
  - Lets the model call MCP tools (function calling style) to enrich answers
- `mcp_config.yaml` - Configuration file listing available MCP servers (local + public examples) and whether they are enabled.
- `requirements.txt` - Python dependencies for this example.

## Quick Start

1. Ensure you have an OpenAI API key in a top-level `.env` file (same style as other examples):

```
OPENAI_API_KEY=sk-...
```

2. Install dependencies (from project root):

```
pip install -r 3.MCP/requirements.txt
```

3. (Optional) Start an individual server manually (they are also auto‑spawned by the clients):

```
python 3.MCP/mcp_server.py
```

4. Run the terminal chat client (spawns all enabled MCP servers via official protocol):

```
python 3.MCP/chat_client.py
```

5. Ask something like:

```
What's the weather where I am right now?
```

The model will call tools exposed by any enabled servers.

## Adding More MCP Servers

Edit `mcp_config.yaml` and either enable existing public entries or add new ones with the pattern:

```yaml
servers:
  - name: my_server
    command: python
    args: ["path/to/server_script.py"]
    enabled: true
```

The chat client will spawn each enabled server as a subprocess and expose its tools to the model.

## Notes

- To add or enable servers edit `mcp_config.yaml` (or use the Streamlit UI).
- Playwright browsing requires: `python -m playwright install chromium`.
- The official MCP server can be tested independently (`python 3.MCP/mcp_server.py`).

Enjoy experimenting!

## Configuration Reference (YAML + Environment Variables)

This section is the authoritative reference for what is CURRENTLY implemented in code.

### `mcp_config.yaml` Schema

```yaml
servers:                # List of MCP server definitions
  - name: local_weather  # (required) Unique server identifier
    command: python      # (required) Executable or absolute interpreter path
    venv: .venv          # (optional) Path to a virtual environment; if present and command == 'python', its python is used
    args:                # (required) Script + any arguments (list form recommended)
      - 3.MCP/mcp_server.py
    enabled: true        # (required) Whether to spawn this server
```

Per‑entry keys:
* name (str, required) – must be unique.
* command (str, required) – literal executable. If it's the generic word `python` and a `venv` is specified, the adapter replaces it with `<venv>/bin/python` when that file exists.
* venv (str, optional) – absolute or relative path to a Python virtual environment root (containing `bin/python` or `Scripts/python.exe` on Windows). Not required if you rely on the parent process interpreter.
* args (list[str], required) – script path followed by any arguments (list form prevents shell quoting issues).
* enabled (bool, required) – only `true` entries are spawned.

Not (yet) implemented but mentioned in earlier docs / future roadmap:
* A per‑server `env` map of additional environment variables.
* Global overrides via `MCP_VENV` or `MCP_PYTHON` (see notes below) – these are currently NOT active in code.

### Environment Variables (Implemented)

Core / API:
* OPENAI_API_KEY – OpenAI key used by `chat_client.py` and `streamlit_app.py`.

Logging – Server Processes (`mcp_server.py`, `mcp_search_server.py`, `mcp_playwright_server.py`):
* MCP_SERVER_LOG_LEVEL – Log level for weather/location server. Default: DEBUG.
* MCP_SEARCH_LOG_LEVEL – Log level for search server. Default: DEBUG.
* MCP_PLAYWRIGHT_LOG_LEVEL – Log level for Playwright server. Default: DEBUG.
* MCP_JSON_LOGS – When set to a truthy value (anything except 0/false/no/off), emit one JSON object per line instead of plain text.
* MCP_LOG_FILE – Path to a shared append‑only log file. Default: `3.MCP/mcp.log` (all servers + adapter append here if writable).

Logging – Adapters / Clients / UI:
* MCP_ADAPTER_LOG – Log level for the new official SDK adapter (`mcp_client_adapter.py`). Default: INFO.
* MCP_CLIENT_LOG – Log level for the legacy JSON‑RPC shim (`mcp_official_client.py`). Default: WARNING.
* MCP_CHAT_LOG_LEVEL – Log level for the Streamlit chat app root logger. Default: INFO.
* MCP_CHAT_LOG_FILE – File path for Streamlit app log file. Default: `3.MCP/streamlit_app.log`.

Playwright / Browser Behavior:
* MCP_PLAYWRIGHT_HEADLESS – Overrides headless mode globally for the Playwright server. Accepted falsey forms (`0`, `false`, `no`, `off`) force a visible window; truthy forms (`1`, `true`, `yes`, `on`) force headless. If unset, defaults to headless unless a tool call argument `headed=true` is provided.

Formatting / Output:
* MCP_JSON_LOGS – (shared) Enables JSON formatting across all three server processes when set truthy (listed again here for completeness).

Interpreter / Virtual Environment Overrides:
* MCP_PYTHON – Absolute path to a Python interpreter that overrides all server commands (highest precedence). If set and exists it is used for every server regardless of per-entry `venv`.
* MCP_VENV – Global virtual environment root; if a server does NOT define its own `venv` and its command is `python` or `python3`, this venv's interpreter is used (unless MCP_PYTHON already took precedence).

### Logging & Debugging Quick Guide

Verbose logging is enabled by default (DEBUG) for servers to ease development. To reduce noise in production:

```bash
export MCP_SERVER_LOG_LEVEL=INFO
export MCP_SEARCH_LOG_LEVEL=INFO
export MCP_PLAYWRIGHT_LOG_LEVEL=INFO
export MCP_ADAPTER_LOG=INFO
python 3.MCP/chat_client.py
```

### Structured (JSON) Logs

Set `MCP_JSON_LOGS=1` (or any truthy value) to switch all MCP servers to emit one JSON object per line, suitable for ingestion by log processors:

```bash
export MCP_JSON_LOGS=1
python 3.MCP/chat_client.py
```

Sample JSON log line:

```json
{"ts":"2025-09-09T15:04:12","lvl":"DEBUG","logger":"mcp_server","msg":"tool=get_weather phase=start latitude=42.36 longitude=-71.06 city=Boston"}
```

### What Gets Logged

Servers:
* Startup, initialization, and tool registration timings
* Each tool invocation (start, end, duration, key result metrics)
* Errors with stack traces (non‑JSON) or serialized exception (JSON)

Client Adapter:
* Server spawn attempts
* Initialization / list_tools timings per server
* Each tool call lifecycle (start, success/error, duration, payload size hints)

Playwright Server adds:
* Screenshot presence, extracted content length, headless vs headed mode

### Tuning Noise

If you only care about errors while keeping JSON output:

```bash
export MCP_JSON_LOGS=1
export MCP_SERVER_LOG_LEVEL=ERROR
export MCP_SEARCH_LOG_LEVEL=ERROR
export MCP_PLAYWRIGHT_LOG_LEVEL=ERROR
python 3.MCP/chat_client.py
```

### Future Ideas
* Correlation IDs per chat turn / tool chain
* Optional log file rotation instead of stderr only
* Toggleable per-tool tracing via config file

Open an issue or PR if you want any of these enhancements.

### Log File Location

By default, all MCP servers and the client adapter now also append logs to a single file:

```
3.MCP/mcp.log
```

Override the location (or name) with:

```bash
export MCP_LOG_FILE=/tmp/my_mcp_session.log
python 3.MCP/chat_client.py
```

If the file handler cannot be created (e.g., permissions), a warning is emitted and logging falls back to stderr only.

NOTE: Multiple MCP server processes write concurrently to the same file. For most development use this is fine; if you need rotation or per‑server separation, you can: (a) set different `MCP_LOG_FILE` per process, or (b) extend the code to use `logging.handlers.RotatingFileHandler`.

## Virtual Environment & Interpreter Selection (Implemented Precedence)

Resolution order per server when determining the actual executable:
1. MCP_PYTHON (if set and exists)
2. Per‑server `venv` (if defined AND original `command` is `python`/`python3`)
3. MCP_VENV (if set, server has no `venv`, and original `command` is `python`/`python3`)
4. Original `command` value

### Example with per‑server venv

```yaml
servers:
  - name: local_weather
    command: python
    venv: /absolute/path/to/venv-weather
    args: [3.MCP/mcp_server.py]
    enabled: true
  - name: playwright_browser
    command: python  # uses whatever interpreter launches the chat client if no venv provided
    args: [3.MCP/mcp_playwright_server.py]
    enabled: true
```

### Troubleshooting
* Enable adapter debug logs: `export MCP_ADAPTER_LOG=DEBUG`.
* Check log lines like: `Spawning MCP server 'local_weather': /abs/path/to/venv-weather/bin/python ['3.MCP/mcp_server.py']` to confirm interpreter resolution.
* Ensure the venv you point to actually contains an interpreter.

## Streamlit UI

You can also launch a Streamlit chat UI that lets you manage MCP servers (enable/disable/add) from the browser:

```
streamlit run 3.MCP/streamlit_app.py
```

Features:
- Toggle existing servers
- Add new server entries (saved to `mcp_config.yaml`)
- Chat with automatic tool calling and view tool outputs

## Playwright Browser Server (mcp-server-playwright style)

You can optionally enable a headless browser tool that lets the model fetch and extract page content.

### 1. Install Python dependencies (includes Playwright driver)

From project root:

```
pip install -r 3.MCP/requirements.txt
```

### 2. Install a browser engine

```
python -m playwright install chromium
```

(You can also install all: `python -m playwright install`)

### 3. Enable the server

Either:
1. Edit `3.MCP/mcp_config.yaml` and set `enabled: true` for the `playwright_browser` entry, or
2. Use the Streamlit UI Servers tab / sidebar toggle.

### 4. Use in chat

Ask something like:

> Browse https://example.com and extract the main heading.

The model will (after tool selection) call `browse_page` with the URL and optionally a selector.

### Tool Parameters

`browse_page`:
- `url` (required): http/https URL
- `selector` (optional): CSS selector to scope extraction
- `text_only` (bool, default True): Return text instead of HTML
- `wait_ms` (int, default 0): Extra wait after load (for dynamic content) up to 15000
 - `screenshot` (bool, default True): Return a base64 screenshot (full page if `full_page` true). NOTE: By default the Streamlit chat app strips the actual `screenshot_base64` from the conversation messages sent to the LLM to save tokens, while still displaying it locally. Set `OMIT_SCREENSHOT_FROM_LLM = False` in `streamlit_app.py` if you want to include it in prompts (not recommended due to token cost).
 - `full_page` (bool, default False): Capture full page instead of viewport
 - `headed` (bool, optional): Set to `true` to launch a visible (non‑headless) Chromium window
 - `keep_open_ms` (int, optional, 0–30000): Extra time (milliseconds) to keep the page open (debug viewing) before closing; mainly useful with `headed: true`

### Showing the Live Browser (Headed Mode)

By default the Playwright server launches Chromium headless. You have two ways to see the real browser window while pages load / are interacted with:

1. Per‑call override (recommended for ad‑hoc debugging):
   Pass `"headed": true` (and optionally `keep_open_ms`) in the `browse_page` tool arguments. Example manual JSON (what the client would send internally):
   ```json
   {
     "type": "call_tool",
     "id": "<req-id>",
     "name": "browse_page",
     "arguments": {
       "url": "https://example.com",
       "headed": true,
       "keep_open_ms": 3000
     }
   }
   ```

2. Environment variable (persistent for all calls):
  Set `MCP_PLAYWRIGHT_HEADLESS=0` (or `false`, `no`, `off`) before launching the chat or Streamlit app.
   ```bash
   export MCP_PLAYWRIGHT_HEADLESS=0   # show browser
   streamlit run 3.MCP/streamlit_app.py
   # or
   python 3.MCP/chat_client.py
   ```
   To force headless explicitly:
   ```bash
   export MCP_PLAYWRIGHT_HEADLESS=1   # or: true / yes / on
   ```

Priority order when deciding headless vs headed:
1. Tool argument `headed` (if provided)
2. Environment variable `MCP_PLAYWRIGHT_HEADLESS`
3. Default: headless (no visible window)

Returned `meta` now includes a `"headless": true|false` flag so you can confirm the mode used.

### Token Usage & Screenshot Omission

Screenshots (base64 PNG) can be very large (hundreds of KB => many thousand tokens). To avoid ballooning prompt size, both the Streamlit UI (`streamlit_app.py`) and the terminal chat client (`chat_client.py`) now REMOVE the raw `screenshot_base64` field before sending tool outputs back to the LLM.

What happens instead:
1. The full tool result (including `screenshot_base64`) is still kept locally for display (image preview in Streamlit / debug print in terminal truncated).
2. A sanitized copy is added to the conversation with:
  - `meta.screenshot_omitted: true`
  - `meta.screenshot_chars`: length of the removed base64 string (approximate size indicator)
  - Any existing `meta.screenshot_bytes` retained if Playwright reported it.
3. The model can reason knowing a screenshot existed (and how large) without incurring the token cost of the raw pixels.

To re-enable embedding the raw screenshot in prompts (NOT recommended):
1. In `streamlit_app.py`, set `OMIT_SCREENSHOT_FROM_LLM = False`.
2. In `chat_client.py`, remove or modify the sanitization block that pops `screenshot_base64` (search for `screenshot_omitted`).

Potential future enhancements (not implemented yet):
- Automatic downscaling and JPEG re-encoding to reduce size instead of full omission.
- On-demand user toggle in the Streamlit sidebar.
- Converting screenshot to a short OCR summary via a vision model (much fewer tokens) before passing to the language model.

If you want any of these, open an issue or implement and submit a PR. :)

### Notes / Troubleshooting for Headed Mode
- On macOS/Linux ensure you are on a machine with a GUI session (or use X forwarding / VNC). In pure remote headless environments you may need a virtual display: `brew install xquartz` (mac headless) or `xvfb-run` on Linux.
- Streamlit will not embed the live browser; it opens as a separate OS window.
- If you forget to close windows and run many calls, you may accumulate Chromium processes; just terminate them or restart the server.
- `keep_open_ms` is capped at 30s to avoid hanging tool calls indefinitely.

### Node.js Alternative (Optional)

If you prefer a Node implementation (closer to emerging official packages):

1. Install Node.js:
  - Download: https://nodejs.org/
  - Or install via nvm (recommended): https://github.com/nvm-sh/nvm
    - macOS quick start: `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash`
2. Initialize a small project under `3.MCP/node_playwright/`:
  ```
  mkdir 3.MCP/node_playwright && cd 3.MCP/node_playwright
  npm init -y
  npm install playwright @modelcontextprotocol/sdk
  npx playwright install chromium
  ```
3. Create a `server.js` similar to the Python server (see earlier assistant message) exposing a `browse` tool.
4. Add to `mcp_config.yaml`:
  ```yaml
  - name: playwright_browser_node
    command: node
    args: [3.MCP/node_playwright/server.js]
    enabled: false
  ```

### Troubleshooting

- If the Playwright server does not appear, check Streamlit logs for import errors.
- Ensure you ran the browser install command (missing browsers cause launch errors).
- Large pages are truncated to keep responses small; refine with a selector.

### Security Note

This demo server does not sandbox navigation. Avoid running it against internal or sensitive endpoints without adding allow‑lists and stricter controls.

---

### Summary Cheat Sheet

YAML keys: name, command, venv (optional), args (list), enabled.

Env vars (implemented): OPENAI_API_KEY, MCP_SERVER_LOG_LEVEL, MCP_SEARCH_LOG_LEVEL, MCP_PLAYWRIGHT_LOG_LEVEL, MCP_JSON_LOGS, MCP_LOG_FILE, MCP_ADAPTER_LOG, MCP_CLIENT_LOG, MCP_CHAT_LOG_LEVEL, MCP_CHAT_LOG_FILE, MCP_PLAYWRIGHT_HEADLESS, MCP_PYTHON, MCP_VENV.

If something here seems outdated, run a quick grep for `os.getenv(` in `3.MCP/` to verify; this README is kept in sync with that source.



# MCP Example

This folder contains a minimal Model Context Protocol (MCP) Server and a simple Chat Client that can talk to one or more MCP servers.

## Contents

- `mcp_server.py` - A minimal MCP server exposing two tools: `get_current_location` and `get_weather` (similar to examples in folders `2/` and `3/`).
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

3. Start the MCP server (in one terminal):

```
python 3.MCP/mcp_server.py
```

4. In another terminal, run the chat client:

```
python 3.MCP/chat_client.py
```

5. Ask something like:

```
What's the weather where I am right now?
```

The model will decide to call `get_current_location` then `get_weather` via MCP.

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

- This is a deliberately thin, educational implementation — no complex session management, retries, or streaming.
- Public MCP server entries are placeholders to show how you would list them; you can replace with real commands.
- Server<->client protocol kept intentionally minimal to demonstrate the concept (JSON lines over stdio).

Enjoy experimenting!

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



#!/usr/bin/env python
"""Streamlit Chat App leveraging MCP servers as tool providers.

Features:
  * View & toggle configured MCP servers (enable/disable)
  * Add new MCP server entries via UI form
  * Persist configuration to `mcp_config.yaml`
  * Start enabled servers and expose their tools to an OpenAI model
  * Interactive chat with automatic tool calling (function calling)

Usage:
  streamlit run 3.MCP/streamlit_app.py
"""
from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from openai import OpenAI

from mcp_client import MCPAdapter

# ---------------------- Logging Setup ----------------------

LOG_LEVEL = os.getenv("MCP_CHAT_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("MCP_CHAT_LOG_FILE", os.path.join(os.path.dirname(__file__), "streamlit_app.log"))

if not logging.getLogger().handlers:
    # Configure root logger only once
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode='a'),
            logging.StreamHandler()
        ]
    )
logger = logging.getLogger("streamlit_app")
logger.info("Streamlit MCP Chat app starting (log level=%s, file=%s)", LOG_LEVEL, LOG_FILE)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'mcp_config.yaml')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ------------------------------------------------------------------
# Configuration Flags
# ------------------------------------------------------------------
# When True, large binary-ish fields like screenshot_base64 will NOT be sent
# to the LLM (they are still retained for local UI display & state). This
# dramatically reduces token consumption while keeping visual context locally.
OMIT_SCREENSHOT_FROM_LLM = True

# ---------------------- Helpers ----------------------

def _safe_rerun():
    """Compatibility wrapper for Streamlit rerun.

    Newer Streamlit versions (>=1.32/1.33) provide st.rerun() and may remove
    st.experimental_rerun(). Older versions only have st.experimental_rerun().
    This wrapper calls whichever is available so the app works across versions.
    """
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        # type: ignore[attr-defined]
        st.experimental_rerun()  # pragma: no cover - legacy path
    else:
        raise RuntimeError("No rerun method available in this Streamlit version.")

@st.cache_resource(show_spinner=False)
def get_mcp_manager() -> MCPAdapter:
    import yaml
    with open(CONFIG_PATH, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    servers_cfg = cfg.get('servers', [])
    mgr = MCPAdapter(servers_cfg)
    mgr.start()
    return mgr


def load_servers() -> List[Dict[str, Any]]:
    import yaml
    if not os.path.exists(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, 'r') as f:
        data = yaml.safe_load(f) or {}
    return data.get('servers', [])


def save_servers(servers: List[Dict[str, Any]]):
    import yaml
    with open(CONFIG_PATH, 'w') as f:
        yaml.safe_dump({'servers': servers}, f, sort_keys=False)
    # Clear cached manager so new servers spawn
    get_mcp_manager.clear()  # type: ignore[attr-defined]
    get_mcp_manager()


def get_openai_client() -> OpenAI:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error('Missing OPENAI_API_KEY in .env at project root')
        raise RuntimeError('Missing OPENAI_API_KEY in .env at project root')
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        logger.exception("Failed to create OpenAI client: %s", e)
        raise


def choose_model(client: OpenAI) -> str:
    try:
        models = client.models.list()
        candidates = [m.id for m in models.data if any(k in m.id.lower() for k in ['gpt', 'o1'])]
        candidates.sort(reverse=True)
        return candidates[0] if candidates else 'gpt-4o-mini'
    except Exception:
        return 'gpt-4o-mini'


# ---------------------- UI Layout ----------------------

st.set_page_config(page_title="MCP Chat", layout="wide")
st.title("🛠️ MCP Chat Playground")
st.caption("Chat with an OpenAI model empowered by configurable MCP servers.")

tab_chat, tab_servers = st.tabs(["Chat", "MCP Servers Config"])

mgr = get_mcp_manager()

with tab_servers:
    st.subheader("Configured Servers")
    st.caption("Edit all server properties in-place. Changes persist to mcp_config.yaml and restart adapters.")
    servers = load_servers()
    if not servers:
        st.info("No servers configured yet. Add one below.")

    changed = False
    expanded_any = False
    for idx, srv in enumerate(list(servers)):
        box_label = f"{srv.get('name')} ({'enabled' if srv.get('enabled') else 'disabled'})"
        with st.expander(box_label, expanded=False):
            cols_top = st.columns([2,2,2,1,1])
            with cols_top[0]:
                name_val = st.text_input("Name", key=f"name_{idx}", value=srv.get('name',''), help="Unique identifier; changing may orphan prior logs.")
            with cols_top[1]:
                cmd_val = st.text_input("Command", key=f"cmd_{idx}", value=srv.get('command','python'), help="Executable or absolute path.")
            with cols_top[2]:
                venv_val = st.text_input("Venv (optional)", key=f"venv_{idx}", value=srv.get('venv',''), help="If set and command=='python' resolves to <venv>/bin/python.")
            with cols_top[3]:
                enabled_val = st.checkbox("Enabled", key=f"enabled_{idx}", value=srv.get('enabled', False))
            with cols_top[4]:
                if st.button("🗑️", key=f"del_{idx}"):
                    servers.pop(idx)
                    changed = True
                    _safe_rerun()
            args_val = st.text_input("Args (space separated)", key=f"args_{idx}", value=" ".join(srv.get('args', [])))
            with st.expander("Per-Server Environment (key=value, one per line)"):
                existing_env = srv.get('env') or {}
                env_text_default = "".join(f"{k}={v}\n" for k,v in existing_env.items())
                env_text = st.text_area("Environment Overrides", key=f"env_{idx}", value=env_text_default, height=120, help="These vars will override the process environment for this server only.")
                # parse env_text into dict
                parsed_env = {}
                for line in env_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):  # comments / blank
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        parsed_env[k.strip()] = v.strip()
            # Detect modifications
            if (name_val != srv.get('name') or cmd_val != srv.get('command') or venv_val != srv.get('venv','') or enabled_val != srv.get('enabled') or args_val.split() != srv.get('args', []) or parsed_env != (srv.get('env') or {})):
                srv['name'] = name_val
                srv['command'] = cmd_val or 'python'
                srv['venv'] = venv_val or None
                if not srv['venv']:
                    srv.pop('venv', None)
                srv['enabled'] = enabled_val
                srv['args'] = args_val.split() if args_val.strip() else []
                srv['env'] = parsed_env
                if not srv['env']:
                    srv.pop('env', None)
                changed = True

    st.markdown("---")
    st.subheader("Add New Server")
    with st.form("add_server_form", clear_on_submit=True):
        new_name = st.text_input("Name", help="Unique identifier")
        new_command = st.text_input("Command", value="python")
        new_args_raw = st.text_input("Args (space separated)", value="3.MCP/mcp_server.py")
        new_venv = st.text_input("Venv (optional)")
        new_env_block = st.text_area("Per-Server Env (key=value per line)", value="", height=100)
        new_enabled = st.checkbox("Enabled", value=True)
        submitted = st.form_submit_button("Add Server")
        if submitted:
            if not new_name:
                st.warning("Name is required.")
            elif any(s['name'] == new_name for s in servers):
                st.error("Server with that name already exists.")
            else:
                parsed_new_env = {}
                for line in new_env_block.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k,v = line.split('=',1)
                        parsed_new_env[k.strip()] = v.strip()
                entry = {
                    'name': new_name,
                    'command': new_command or 'python',
                    'args': new_args_raw.split() if new_args_raw else [],
                    'enabled': new_enabled
                }
                if new_venv.strip():
                    entry['venv'] = new_venv.strip()
                if parsed_new_env:
                    entry['env'] = parsed_new_env
                servers.append(entry)
                changed = True

    if changed:
        save_servers(servers)
        st.success("Configuration saved and servers restarted.")

with tab_chat:
    st.subheader("Chat")
    if 'conversation' not in st.session_state:
        system_prompt = (
            "You are a helpful assistant with access to real-time tools. For ANY question about current weather, "
            "temperature, forecast, or 'here', you MUST: 1) Call get_current_location then 2) get_weather with the coordinates. "
            "Do not finalize answer until weather retrieved. Use search tools for queries that benefit from fresh info."
        )
        st.session_state.conversation = [{"role": "system", "content": system_prompt}]
        st.session_state.messages_display = []

    client = get_openai_client()
    model = st.session_state.get('model') or choose_model(client)
    st.session_state.model = model

    st.caption(f"Model: {model}")

    tools_spec = mgr.build_openai_tools_spec()
    if not tools_spec:
        st.warning("No MCP tools are currently enabled.")
        logger.warning("No tools spec built (no enabled tools)")
    else:
        st.info(f"Loaded {len(tools_spec)} tool definitions from enabled servers.")
        logger.info("Loaded %d tool definitions", len(tools_spec))

    user_input = st.text_input("Your message", key="user_input")
    col_send, col_clear = st.columns([1,1])
    send_clicked = col_send.button("Send", type="primary")
    clear_clicked = col_clear.button("Clear Conversation")

    if clear_clicked:
        # Also clear any persisted last browsing preview (screenshot, title, url)
        for k in [
            'conversation', 'messages_display',
            'last_browse_url', 'last_browse_title', 'last_browse_screenshot'
        ]:
            st.session_state.pop(k, None)
        _safe_rerun()

    if send_clicked and user_input.strip():
        logger.info("User message: %s", user_input.strip())
        st.session_state.conversation.append({"role": "user", "content": user_input.strip()})
        st.session_state.messages_display.append(("user", user_input.strip()))

        used_tools = 0
        max_tool_rounds = 4
        final_answer = ""
        while True:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=st.session_state.conversation,
                    tools=tools_spec if tools_spec else None,
                    tool_choice='auto' if tools_spec else None,
                    temperature=0.4,
                    max_tokens=700
                )
            except Exception as e:
                logger.exception("OpenAI chat completion failed: %s", e)
                st.session_state.messages_display.append(("assistant", f"Error from OpenAI: {e}"))
                break
            msg = response.choices[0].message
            logger.debug("Model raw message: %s", msg)
            if msg.tool_calls and used_tools < max_tool_rounds:
                logger.info("Model requested %d tool calls (round %d)", len(msg.tool_calls), used_tools + 1)
                st.session_state.conversation.append({
                    'role': 'assistant', 'content': None, 'tool_calls': msg.tool_calls
                })
                for tc in msg.tool_calls:
                    fname = tc.function.name
                    qualified = mgr.resolve_function_name(fname)
                    logger.debug("Resolving tool '%s' -> '%s'", fname, qualified)
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}
                        logger.warning("Failed parsing arguments for tool %s; defaulting to {}", fname)
                    if not qualified:
                        tool_result = {"error": f"Could not resolve tool {fname}"}
                        logger.error("Could not resolve tool name '%s'", fname)
                    else:
                        # Inject Playwright overrides if this is the browse_page tool
                        if fname.endswith("browse_page") and 'playwright_headed' in st.session_state:
                            overrides = {
                                'headed': st.session_state.playwright_headed,
                                'keep_open_ms': st.session_state.playwright_keep_open_ms,
                                'screenshot': st.session_state.playwright_capture_screenshot,
                                'full_page': st.session_state.playwright_full_page,
                            }
                            # Do not override user-specified values unless absent
                            for k, v in overrides.items():
                                args.setdefault(k, v)
                            logger.debug("Applied Playwright overrides: %s", overrides)
                        tool_result = mgr.call_tool(qualified, args)
                    # Sanitize large base64 fields before logging
                    if isinstance(tool_result, dict) and 'screenshot_base64' in tool_result:
                        logged_copy = dict(tool_result)
                        b64v = logged_copy.get('screenshot_base64')
                        if isinstance(b64v, str):
                            logged_copy['screenshot_base64'] = f"<omitted {len(b64v)} chars base64 screenshot>"
                        tool_log_payload = logged_copy
                    else:
                        tool_log_payload = tool_result
                    logger.info("Tool %s result: %s", fname, tool_log_payload)
                    # Prepare sanitized payload for the LLM conversation to trim giant fields
                    if OMIT_SCREENSHOT_FROM_LLM and isinstance(tool_result, dict) and 'screenshot_base64' in tool_result:
                        sanitized = dict(tool_result)  # shallow copy
                        try:
                            b64_len = len(tool_result.get('screenshot_base64') or '')
                        except Exception:  # pragma: no cover - defensive
                            b64_len = 0
                        # Remove the raw base64 to avoid ballooning tokens
                        sanitized.pop('screenshot_base64', None)
                        # Annotate meta so the model knows a screenshot existed
                        meta_obj = sanitized.setdefault('meta', {}) if isinstance(sanitized, dict) else {}
                        meta_obj['screenshot_omitted'] = True
                        meta_obj['screenshot_bytes'] = meta_obj.get('screenshot_bytes')  # keep existing if present
                        if b64_len and 'screenshot_chars' not in meta_obj:
                            meta_obj['screenshot_chars'] = b64_len
                        conversation_payload = sanitized
                    else:
                        conversation_payload = tool_result

                    st.session_state.conversation.append({
                        'tool_call_id': tc.id,
                        'role': 'tool',
                        'name': fname,
                        'content': json.dumps(conversation_payload)
                    })
                    used_tools += 1
                    # Store structured message (role, tool_name, tool_result_dict) to avoid stringifying base64
                    st.session_state.messages_display.append(("tool", fname, tool_result))
                if used_tools >= max_tool_rounds:
                    logger.warning("Reached max tool rounds (%d); stopping tool loop", max_tool_rounds)
                    break
                else:
                    continue
            else:
                final_answer = msg.content or ''
                st.session_state.conversation.append({'role': 'assistant', 'content': final_answer})
                logger.info("Assistant final answer length=%d chars", len(final_answer))
                break

        if final_answer:
            st.session_state.messages_display.append(("assistant", final_answer))

    # If we have a last browsed page, surface a live view (iframe) + last screenshot above the chat history
    if 'last_browse_url' in st.session_state:
        with st.container(border=True):
            st.markdown("### 🌐 Last Browsed Page")
            cols_preview = st.columns([3,1])
            with cols_preview[0]:
                st.caption(st.session_state.get('last_browse_title') or st.session_state['last_browse_url'])
                # Attempt to embed live page (may be blocked by X-Frame-Options)
                try:
                    components.html(
                        f"""
                        <iframe src='{st.session_state['last_browse_url']}' width='100%' height='500' 
                                sandbox='allow-same-origin allow-scripts allow-popups allow-forms'
                                style='border:1px solid #ccc;border-radius:6px;'></iframe>
                        <div style='font-size:12px;color:#666;margin-top:4px;'>If the site blocks embedding you may see a blank frame.</div>
                        """,
                        height=560,
                    )
                except Exception as _e:  # noqa: BLE001
                    st.info("Could not embed page (blocked by site or browser). Use the open button instead.")
            with cols_preview[1]:
                st.link_button("Open Page", st.session_state['last_browse_url'])
                if 'last_browse_screenshot' in st.session_state:
                    st.image(
                        f"data:image/png;base64,{st.session_state['last_browse_screenshot']}",
                        caption="Screenshot", use_column_width=True
                    )
            st.divider()

    for entry in st.session_state.get('messages_display', []):
        # Support legacy tuple (role, text) and new structured (role, tool_name, dict)
        if not entry:
            continue
        role = entry[0]
        if role == 'user':
            st.chat_message("user").write(entry[1])
        elif role == 'assistant':
            st.chat_message("assistant").write(entry[1])
        elif role == 'tool':
            if len(entry) == 3 and isinstance(entry[2], dict):
                tool_name = entry[1]
                data = entry[2]
                meta = data.get('meta', {}) if isinstance(data, dict) else {}
                title = meta.get('title') or meta.get('url') or tool_name
                with st.expander(f"Tool: {tool_name} | {title}"):
                    b64 = data.get('screenshot_base64') if isinstance(data, dict) else None
                    if b64:
                        st.session_state['last_browse_url'] = meta.get('url') or st.session_state.get('last_browse_url')
                        st.session_state['last_browse_title'] = meta.get('title') or st.session_state.get('last_browse_title')
                        st.session_state['last_browse_screenshot'] = b64
                        st.image(f"data:image/png;base64,{b64}", caption=meta.get('title') or 'Screenshot')
                    st.code(json.dumps(data, indent=2)[:8000], language='json')
            else:
                # Fallback legacy formatting
                _, text = entry[0], entry[1]
                with st.expander(f"Tool Output: {text[:60]}..."):
                    st.write(text)

st.sidebar.header("Servers Quick Toggle")
servers_sidebar = load_servers()
if servers_sidebar:
    quick_changed = False
    for s in servers_sidebar:
        new_val = st.sidebar.checkbox(s['name'], value=s.get('enabled', False))
        if new_val != s.get('enabled'):
            s['enabled'] = new_val
            quick_changed = True
    if quick_changed:
        save_servers(servers_sidebar)
        st.sidebar.success("Saved. Restarted servers.")

# ---------------- Playwright (Browser) Options -----------------
playwright_enabled = any(s['name'] == 'playwright_browser' and s.get('enabled') for s in servers_sidebar)
st.sidebar.markdown("---")
st.sidebar.subheader("Playwright Browser Options")
if playwright_enabled:
    # Persist selections in session_state
    if 'playwright_headed' not in st.session_state:
        st.session_state.playwright_headed = False
    if 'playwright_keep_open_ms' not in st.session_state:
        st.session_state.playwright_keep_open_ms = 0
    if 'playwright_full_page' not in st.session_state:
        st.session_state.playwright_full_page = False
    if 'playwright_capture_screenshot' not in st.session_state:
        st.session_state.playwright_capture_screenshot = True

    st.session_state.playwright_headed = st.sidebar.checkbox(
        "Show live browser window (headed)", value=st.session_state.playwright_headed,
        help="If checked, Chromium launches with a visible window instead of headless."
    )
    st.session_state.playwright_keep_open_ms = st.sidebar.slider(
        "Keep window open after load (ms)", 0, 30000, st.session_state.playwright_keep_open_ms, step=500,
        help="Extra debug viewing time before the page closes (only meaningful in headed mode)."
    )
    with st.sidebar.expander("Advanced capture"):
        st.session_state.playwright_capture_screenshot = st.checkbox(
            "Capture screenshot", value=st.session_state.playwright_capture_screenshot,
            help="Disable to skip screenshot base64 payload."
        )
        st.session_state.playwright_full_page = st.checkbox(
            "Full page screenshot", value=st.session_state.playwright_full_page,
            help="Scroll & stitch full page (may be tall)."
        )
    st.sidebar.caption("Overrides are injected into every browse_page tool call.")
else:
    st.sidebar.info("Enable the 'playwright_browser' server to configure live browser options.")

# Patch: apply overrides when browse_page tool is invoked
st.sidebar.markdown("---")
st.sidebar.caption("MCP Chat Demo — configuration stored in mcp_config.yaml")

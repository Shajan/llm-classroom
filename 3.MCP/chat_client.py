#!/usr/bin/env python
"""Terminal Chat Client that can use MCP servers as tool providers.

Flow:
 1. Load MCP server definitions from mcp_config.yaml
 2. Spawn each enabled server (subprocess with stdio JSONL protocol)
 3. Aggregate tool schemas from all servers
 4. Chat with OpenAI model; when model requests a function call, dispatch to matching MCP tool
 5. Return tool result to model and continue until final answer

This mirrors the style of folder llm.shell but stays minimal & terminal-based.
"""
import os
import sys
import json
import yaml
from typing import Dict, Any, List
from dotenv import load_dotenv
from openai import OpenAI
from mcp_client import MCPAdapter

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'mcp_config.yaml')

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Uses official MCP protocol via MCPAdapter (see mcp_client.py). Legacy JSON-RPC shim removed.


def choose_model(client: OpenAI) -> str:
    try:
        models = client.models.list()
        candidates = [m.id for m in models.data if any(k in m.id.lower() for k in ['gpt', 'o1'])]
        candidates.sort(reverse=True)
        return candidates[0] if candidates else 'gpt-4o-mini'
    except Exception:
        return 'gpt-4o-mini'


def main():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print('Missing OPENAI_API_KEY in .env (project root)')
        sys.exit(1)

    try:
        client = OpenAI(api_key=api_key)
    except TypeError as e:
        # Commonly caused by openai/httpx version mismatch (httpx>=0.28 removed 'proxies')
        print("Error creating OpenAI client (likely dependency version mismatch):", e)
        print("Try: pip install --upgrade 'openai>=1.0.0' 'httpx<0.28' or reinstall via requirements.txt")
        sys.exit(1)

    # Load config
    with open(CONFIG_PATH, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    servers_cfg = cfg.get('servers', [])
    official = MCPAdapter(servers_cfg)
    official.start()

    tools_spec = official.build_openai_tools_spec()
    if not tools_spec:
        print('No MCP tools available. Proceeding without tools.')

    model = choose_model(client)
    print(f"Using model: {model}")
    print("Type your message. Ctrl+C to exit.\n")

    # Seed conversation with a strong system directive so model prefers tool usage
    system_prompt = (
        "You are a helpful assistant with access to real-time tools. "
        "For ANY question about current weather, temperature, forecast, or 'here', you MUST: \n"
        "  1. Call get_current_location (never assume coordinates).\n"
        "  2. Then immediately call get_weather with the latitude & longitude from that result.\n"
        "Do NOT provide a final answer until AFTER get_weather has been executed.\n"
        "If you have only called get_current_location so far, you are NOT done— continue to call get_weather.\n"
        "Only after both tools have been used should you craft the final natural language answer summarizing conditions.\n"
        "Never invent weather data; always rely strictly on tool outputs."
    )
    conversation: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    try:
        while True:
            user_input = input('You: ').strip()
            if not user_input:
                continue
            conversation.append({'role': 'user', 'content': user_input})

            used_tools = 0
            max_tool_rounds = 4  # safety cap
            answer = ""
            while True:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=conversation,
                        tools=tools_spec if tools_spec else None,
                        tool_choice='auto' if tools_spec else None,
                        temperature=0.5,
                        max_tokens=800
                    )
                    msg = response.choices[0].message
                except AttributeError:
                    # Fallback for newer OpenAI client versions favoring responses API
                    resp = client.responses.create(
                        model=model,
                        input=conversation,
                        temperature=0.5,
                        max_output_tokens=800,
                        tools=tools_spec if tools_spec else None,
                    )
                    # Map responses API output to legacy-like structure
                    choice = resp.output[0] if getattr(resp, 'output', None) else None
                    if choice and hasattr(choice, 'content'):
                        # Simplistic mapping: no tool support here yet (extend as needed)
                        class Obj:  # lightweight shim
                            def __init__(self, content):
                                self.content = content
                                self.tool_calls = []
                        msg = Obj(choice.content[0].text.value if choice.content else '')
                    else:
                        class Obj2:
                            content = ''
                            tool_calls: list = []
                        msg = Obj2()

                if getattr(msg, 'tool_calls', None) and used_tools < max_tool_rounds:
                    conversation.append({
                        'role': 'assistant',
                        'content': None,
                        'tool_calls': msg.tool_calls
                    })
                    for tc in msg.tool_calls:
                        fname = tc.function.name
                        qualified = official.resolve_function_name(fname)
                        if not qualified:
                            print(f"[WARN] Could not resolve tool function name '{fname}' to a server tool.")
                            continue
                        print(f"[DEBUG] Executing tool call: {fname} -> {qualified}")
                        try:
                            fargs = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except json.JSONDecodeError:
                            fargs = {}
                        tool_result = official.call_tool(qualified, fargs)
                        # Sanitize large base64 screenshot field to avoid token bloat
                        if isinstance(tool_result, dict) and 'screenshot_base64' in tool_result:
                            sanitized = dict(tool_result)
                            b64_len = 0
                            try:
                                b64_len = len(sanitized.get('screenshot_base64') or '')
                            except Exception:  # pragma: no cover
                                pass
                            sanitized.pop('screenshot_base64', None)
                            meta_obj = sanitized.setdefault('meta', {}) if isinstance(sanitized, dict) else {}
                            meta_obj['screenshot_omitted'] = True
                            if b64_len:
                                meta_obj.setdefault('screenshot_chars', b64_len)
                            print(f"[DEBUG] Tool result ({fname}) sanitized (omitted screenshot_base64 length={b64_len})")
                            payload_for_llm = sanitized
                        else:
                            print(f"[DEBUG] Tool result ({fname}): {tool_result}")
                            payload_for_llm = tool_result
                        conversation.append({
                            'tool_call_id': tc.id,
                            'role': 'tool',
                            'name': fname,
                            'content': json.dumps(payload_for_llm)
                        })
                        used_tools += 1
                    # loop again to allow chained tool usage
                    if used_tools >= max_tool_rounds:
                        print("[WARN] Reached max tool rounds; proceeding to final answer.")
                        continue
                    else:
                        continue
                else:
                    # Final answer (no tool calls)
                    answer = getattr(msg, 'content', '') or ''
                    conversation.append({'role': 'assistant', 'content': answer})
                    break

            # Fallback reinforcement if weather question but no tools used at all
            if used_tools == 0:
                lowered = user_input.lower()
                if any(k in lowered for k in ["weather", "temperature", "forecast", "here"]):
                    conversation.append({'role': 'user', 'content': 'You did not use the required tools. Please follow the instructions and use get_current_location then get_weather.'})
                    # one more forced iteration
                    continue

            print(f"Assistant: {answer}\n")

    except KeyboardInterrupt:
        print('\nExiting...')
    finally:
        official.shutdown()

if __name__ == '__main__':
    main()

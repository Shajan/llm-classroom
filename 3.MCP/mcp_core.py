"""Core MCP management utilities shared across terminal and Streamlit clients.

This module provides MCPManager which:
  * Loads server definitions from a YAML config
  * Spawns enabled MCP servers (JSONL over stdio)
  * Discovers tools and exposes OpenAI tool spec builder
  * Dispatches tool calls and returns results

The protocol is intentionally minimal and mirrors the one used in `mcp_server.py`.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import uuid
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class MCPServerProcess:
    name: str
    process: subprocess.Popen
    stdout_queue: "queue.Queue[str]"


class MCPManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.servers: Dict[str, MCPServerProcess] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.function_name_map: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)

    # ----------------------- Config -----------------------
    def load_config(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.config_path):
            return []
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        return data.get('servers', [])

    def save_config(self, servers: List[Dict[str, Any]]):
        with open(self.config_path, 'w') as f:
            yaml.safe_dump({'servers': servers}, f, sort_keys=False)

    # ----------------------- Lifecycle -----------------------
    def start_enabled_servers(self):
        self.logger.debug("Starting enabled MCP servers from config: %s", self.config_path)
        for entry in self.load_config():
            if not entry.get('enabled'):
                self.logger.debug("Server '%s' disabled; skipping", entry.get('name'))
                continue
            name = entry['name']
            if name in self.servers:  # already running
                self.logger.debug("Server '%s' already running; skipping spawn", name)
                continue
            command = entry['command']
            args = entry.get('args', [])
            try:
                self.logger.info("Spawning MCP server '%s': %s %s", name, command, " ".join(args))
                proc = subprocess.Popen(
                    [command, *args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
            except FileNotFoundError:
                # Skip servers with invalid command
                self.logger.error("Failed to start server '%s': command not found '%s'", name, command)
                continue
            q: "queue.Queue[str]" = queue.Queue()
            t = threading.Thread(target=self._reader_thread, args=(proc.stdout, q), daemon=True)
            t.start()
            self.servers[name] = MCPServerProcess(name=name, process=proc, stdout_queue=q)
            self.logger.debug("Spawned server '%s' (pid=%s); requesting tools", name, proc.pid)
            self._request_tools(name)

    def stop_server(self, name: str):
        proc = self.servers.pop(name, None)
        if proc:
            try:
                self.logger.info("Stopping server '%s' (pid=%s)", name, proc.process.pid)
                proc.process.terminate()
            except Exception:
                self.logger.exception("Error while stopping server '%s'", name)
                pass

    def restart(self):
        self.logger.info("Restarting all MCP servers")
        self.shutdown()
        self.tools.clear()
        self.function_name_map.clear()
        self.start_enabled_servers()

    def shutdown(self):
        self.logger.info("Shutting down %d MCP servers", len(self.servers))
        for server in list(self.servers.values()):
            try:
                self.logger.debug("Terminating server '%s' (pid=%s)", server.name, server.process.pid)
                server.process.terminate()
            except Exception:
                self.logger.exception("Error terminating server '%s'", server.name)
                pass
        self.servers.clear()

    # ----------------------- Internals -----------------------
    def _reader_thread(self, stream, q: "queue.Queue[str]"):
        for line in stream:
            self.logger.debug("[STDOUT] %s", line.rstrip('\n'))
            q.put(line.rstrip('\n'))

    def _send(self, server_name: str, message: Dict[str, Any]):
        server = self.servers[server_name]
        if not server.process.stdin:
            return
        data = json.dumps(message) + '\n'
        self.logger.debug("--> %s %s", server_name, data.strip())
        server.process.stdin.write(data)
        server.process.stdin.flush()

    def _request_tools(self, server_name: str):
        req_id = str(uuid.uuid4())
        self._send(server_name, {"type": "list_tools", "id": req_id})
        tools_msg = self._wait_for(server_name, req_id)
        if tools_msg and tools_msg.get('type') == 'tool_list':
            self.logger.info("Server '%s' reported %d tools", server_name, len(tools_msg.get('tools', [])))
            for tool in tools_msg.get('tools', []):
                qualified = f"{server_name}:{tool['name']}"
                self.tools[qualified] = {
                    'server': server_name,
                    'name': tool['name'],
                    'schema': tool.get('schema', {}),
                    'description': tool.get('description', '')
                }
        else:
            self.logger.warning("Did not receive tool list from '%s' in time", server_name)

    def _wait_for(self, server_name: str, req_id: str, timeout: float = 5.0):
        import time
        start = time.time()
        q = self.servers[server_name].stdout_queue
        while time.time() - start < timeout:
            try:
                line = q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.logger.debug("Non-JSON line from '%s': %s", server_name, line)
                continue
            if msg.get('id') == req_id:
                self.logger.debug("<-- %s %s", server_name, json.dumps(msg))
                return msg
        return None

    # ----------------------- Tool Calls -----------------------
    def call_tool(self, qualified_name: str, arguments: Dict[str, Any]):
        meta = self.tools.get(qualified_name)
        if not meta:
            self.logger.error("Attempt to call unknown tool '%s'", qualified_name)
            return {'error': f'Unknown tool {qualified_name}'}
        server_name = meta['server']
        req_id = str(uuid.uuid4())
        self.logger.info("Calling tool %s on server '%s' with args=%s", meta['name'], server_name, arguments)
        self._send(server_name, {
            'type': 'call_tool',
            'id': req_id,
            'name': meta['name'],
            'arguments': arguments
        })
        resp = self._wait_for(server_name, req_id, timeout=20.0)
        if not resp:
            self.logger.error("Timeout waiting for tool result %s (%s)", meta['name'], req_id)
            return {'error': 'Timeout waiting for tool result'}
        if resp.get('type') == 'tool_result':
            self.logger.info("Tool %s result: %s", meta['name'], resp.get('content'))
            return resp.get('content')
        self.logger.error("Tool %s error response: %s", meta['name'], resp)
        return {'error': resp.get('error', 'Unknown error')}

    # ----------------------- OpenAI Tools Spec -----------------------
    def build_openai_tools_spec(self) -> List[Dict[str, Any]]:
        name_counts: Dict[str, int] = {}
        for meta in self.tools.values():
            base = meta['name']
            name_counts[base] = name_counts.get(base, 0) + 1
        specs: List[Dict[str, Any]] = []
        self.function_name_map.clear()
        for qname, meta in self.tools.items():
            base = meta['name']
            if name_counts[base] > 1:
                exposed_name = f"{meta['server']}_{base}"
            else:
                exposed_name = base
            self.function_name_map[exposed_name] = qname
            specs.append({
                'type': 'function',
                'function': {
                    'name': exposed_name,
                    'description': f"Tool from server '{meta['server']}': {meta['description']}",
                    'parameters': meta['schema']
                }
            })
        self.logger.debug("Built OpenAI tools spec exposing %d functions", len(specs))
        return specs

    def resolve_function_name(self, fname: str) -> Optional[str]:
        return self.function_name_map.get(fname)


__all__ = ["MCPManager", "MCPServerProcess"]

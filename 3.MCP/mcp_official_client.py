"""Lightweight MCP client for spawning and interacting with FastMCP-based servers.

Implements the minimal subset needed by the demo chat and Streamlit apps:
  * Initialize each server (JSON-RPC over stdio)
  * List tools (tools/list)
  * Call tools (tools/call)

NOTE: This is a pragmatic implementation based on the public MCP JSON-RPC patterns.
It avoids external dependencies and is intentionally synchronous (per call) while
using a reader thread per server.
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

logger = logging.getLogger(__name__)

# Allow opt-in verbose diagnostics without changing app code
_log_level = os.getenv("MCP_CLIENT_LOG", "WARNING").upper()
try:  # BasicConfig is no-op if already configured elsewhere
    logging.basicConfig(level=getattr(logging, _log_level, logging.WARNING))
except Exception:  # pragma: no cover
    pass

@dataclass
class ServerHandle:
    name: str
    process: subprocess.Popen
    stdout_queue: "queue.Queue[str]"
    next_id: int = 0

class MCPOfficialManager:
    def __init__(self, servers_config: List[Dict[str, Any]], init_timeout: float = 5.0):
        self.servers_config = servers_config
        self.init_timeout = init_timeout
        self.servers: Dict[str, ServerHandle] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}  # qualified_name -> meta
        self.function_name_map: Dict[str, str] = {}

    # ---------------- Lifecycle -----------------
    def start(self):
        for entry in self.servers_config:
            if not entry.get("enabled"):
                continue
            name = entry["name"]
            if name in self.servers:
                continue
            cmd = [entry["command"], *entry.get("args", [])]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError:
                logger.error("Command not found for MCP server '%s': %s", name, cmd)
                continue
            q: "queue.Queue[str]" = queue.Queue()
            t = threading.Thread(target=self._reader, args=(proc.stdout, q), daemon=True)
            t.start()
            # stderr logging thread (not JSON)
            if proc.stderr:
                threading.Thread(target=self._stderr_reader, args=(name, proc.stderr), daemon=True).start()
            handle = ServerHandle(name=name, process=proc, stdout_queue=q)
            self.servers[name] = handle
            try:
                self._initialize(handle)
                self._list_tools(handle)
            except Exception as e:  # noqa: BLE001
                logger.exception("Initialization failed for server %s: %s", name, e)

    def shutdown(self):
        for handle in list(self.servers.values()):
            try:
                handle.process.terminate()
            except Exception:  # noqa: BLE001
                pass
        self.servers.clear()
        self.tools.clear()
        self.function_name_map.clear()

    # ---------------- RPC Helpers -----------------
    def _reader(self, stream, q: "queue.Queue[str]"):
        """Read MCP messages framed with Content-Length headers (LSP style).

        Falls back to line-by-line JSON if headers not present (for any legacy
        newline-delimited servers). Each complete JSON message body is put onto
        the queue as a raw JSON string.
        """
        buf = ""
        while True:
            line = stream.readline()  # type: ignore[attr-defined]
            if not line:
                break  # EOF
            # Normalize line endings
            line_stripped = line.rstrip("\r\n")
            if line_stripped.startswith("Content-Length:"):
                # Start of a framed message; parse length then read blank line + body
                try:
                    _, v = line_stripped.split(":", 1)
                    length = int(v.strip())
                except Exception:
                    logger.debug("Malformed Content-Length header: %s", line_stripped)
                    continue
                # Expect blank line
                blank = stream.readline()
                if blank not in ("\n", "\r\n", ""):
                    # Not a blank separator; treat as legacy line and continue
                    logger.debug("Expected blank line after header, got: %r", blank)
                body = stream.read(length)
                if not body:
                    logger.debug("Empty body despite length %s", length)
                    continue
                body_str = body.strip()
                logger.debug("<-- RAW %s", body_str)
                q.put(body_str)
                continue
            else:
                # Legacy fallback: maybe the entire JSON object on one line
                candidate = line_stripped.strip()
                if not candidate:
                    continue
                # Heuristic: must start with '{' to attempt JSON; otherwise ignore noise
                if candidate.startswith('{'):
                    logger.debug("<-- LINE %s", candidate)
                    q.put(candidate)
                else:
                    logger.debug("[IGNORED LINE] %s", candidate)

    def _stderr_reader(self, name: str, stream):  # pragma: no cover - diagnostic helper
        for line in stream:  # type: ignore
            line = line.rstrip("\n")
            if line:
                logger.debug("[STDERR][%s] %s", name, line)

    def _send(self, handle: ServerHandle, method: str, params: Optional[Dict[str, Any]] = None, id_required: bool = True) -> int:
        if not handle.process.stdin:
            raise RuntimeError("Server stdin closed")
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        msg_id = -1
        if id_required:
            msg_id = handle.next_id
            handle.next_id += 1
            msg["id"] = msg_id
        line = json.dumps(msg) + "\n"
        logger.debug("--> %s %s", handle.name, line.strip())
        handle.process.stdin.write(line)
        handle.process.stdin.flush()
        return msg_id

    def _wait_for(self, handle: ServerHandle, msg_id: int, timeout: float) -> Optional[Dict[str, Any]]:
        import time
        start = time.time()
        while time.time() - start < timeout:
            try:
                line = handle.stdout_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Non-JSON line from %s: %s", handle.name, line)
                continue
            if msg.get("id") == msg_id:
                logger.debug("<-- %s %s", handle.name, json.dumps(msg))
                return msg
        return None

    # ---------------- Protocol Methods -----------------
    def _initialize(self, handle: ServerHandle):
        """Perform MCP initialize handshake trying multiple param variants.

        Some server libraries are strict about what keys are accepted. We try a
        sequence of increasingly specific parameter sets until one succeeds.
        """
        variants = [
            {  # minimal (no protocolVersion)
                "capabilities": {},
                "clientInfo": {"name": "llm-classroom", "version": "0.1.0"},
            },
            {  # current spec date
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "llm-classroom", "version": "0.1.0"},
            },
            {  # earlier spec date
                "protocolVersion": "2024-06-01",
                "capabilities": {},
                "clientInfo": {"name": "llm-classroom", "version": "0.1.0"},
            },
        ]
        last_resp: Optional[dict] = None
        for attempt, params in enumerate(variants, start=1):
            logger.debug("Attempt %s initialize params=%s", attempt, params)
            msg_id = self._send(handle, "initialize", params=params, id_required=True)
            resp = self._wait_for(handle, msg_id, self.init_timeout)
            last_resp = resp
            if resp and "error" not in resp:
                logger.debug("Initialize succeeded for %s with variant %s", handle.name, attempt)
                try:
                    # Spec notification name per FastMCP expectations
                    self._send(handle, "notifications/initialized", params=None, id_required=False)
                except Exception:  # pragma: no cover
                    logger.debug("Failed to send 'initialized' notification for %s", handle.name)
                return
            else:
                logger.debug("Initialize variant %s failed for %s: %s", attempt, handle.name, resp)
        raise RuntimeError(f"Initialize failed for {handle.name} after variants: {last_resp}")

    def _list_tools(self, handle: ServerHandle):
        """Attempt to list tools trying several param variants.

        FastMCP / spec evolution ambiguity: some implementations expect no
        params, others accept an empty object, and future versions may add
        pagination keys like cursor / limit. We brute-force a small set.
        """
        variants = [
            None,
            {},  # legacy tolerant servers
            {"cursor": None},
            {"cursor": 0},
            {"limit": 100},
            {"pageSize": 100},
        ]
        last_resp = None
        for attempt, params in enumerate(variants, start=1):
            try:
                logger.debug("Attempt %s tools/list params=%s", attempt, params)
                msg_id = self._send(handle, "tools/list", params=params, id_required=True)
                resp = self._wait_for(handle, msg_id, 5.0)
                last_resp = resp
                if not resp or "error" in resp:
                    logger.debug("tools/list variant %s failed: %s", attempt, resp)
                    continue
                result = resp.get("result") or {}
                tools = result.get("tools", [])
                for t in tools:
                    name = t.get("name")
                    if not name:
                        continue
                    desc = t.get("description", "")
                    schema = t.get("inputSchema") or t.get("schema") or {}
                    qualified = f"{handle.name}:{name}"
                    self.tools[qualified] = {
                        "server": handle.name,
                        "name": name,
                        "schema": schema,
                        "description": desc,
                    }
                if tools:
                    logger.debug("tools/list succeeded for %s with variant %s (found %d tools)", handle.name, attempt, len(tools))
                    return
            except Exception as e:  # noqa: BLE001
                logger.debug("Exception during tools/list attempt %s: %s", attempt, e)
        logger.warning("tools/list failed for %s after %d attempts: %s", handle.name, len(variants), last_resp)

    # ---------------- Public API -----------------
    def build_openai_tools_spec(self) -> List[Dict[str, Any]]:
        # disambiguate duplicates
        counts: Dict[str, int] = {}
        for meta in self.tools.values():
            base = meta["name"]
            counts[base] = counts.get(base, 0) + 1
        self.function_name_map.clear()
        spec: List[Dict[str, Any]] = []
        for qname, meta in self.tools.items():
            base = meta["name"]
            if counts[base] > 1:
                exposed = f"{meta['server']}_{base}"
            else:
                exposed = base
            self.function_name_map[exposed] = qname
            spec.append(
                {
                    "type": "function",
                    "function": {
                        "name": exposed,
                        "description": meta["description"],
                        "parameters": meta["schema"],
                    },
                }
            )
        return spec

    def resolve_function_name(self, name: str) -> Optional[str]:
        return self.function_name_map.get(name)

    def call_tool(self, qualified: str, arguments: Dict[str, Any]) -> Any:
        meta = self.tools.get(qualified)
        if not meta:
            return {"error": f"Unknown tool {qualified}"}
        server_name = meta["server"]
        handle = self.servers.get(server_name)
        if not handle:
            return {"error": f"Server {server_name} not running"}
        msg_id = self._send(
            handle,
            "tools/call",
            params={"name": meta["name"], "arguments": arguments},
            id_required=True,
        )
        resp = self._wait_for(handle, msg_id, 30.0)
        if not resp:
            return {"error": "Timeout waiting for tool result"}
        if "error" in resp:
            return {"error": resp.get("error")}
        result = resp.get("result")
        if result is None:
            return None
        # Attempt to unwrap common MCP content block shapes
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            # content could be list of blocks
            if isinstance(content, list) and content:
                # if single block with 'type' and maybe 'value'
                if len(content) == 1:
                    blk = content[0]
                    if isinstance(blk, dict):
                        if "value" in blk:
                            return blk["value"]
                        # textual forms
                        for key in ("text", "markdown", "string"):
                            if key in blk:
                                return blk[key]
                # Fallback return entire list
                return content
        return result

__all__ = ["MCPOfficialManager"]

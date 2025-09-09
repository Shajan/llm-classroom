"""MCP Client (Adapter)
=======================

Unified synchronous-friendly adapter around the official MCP Python SDK.

This was previously named `mcp_client_adapter.py`; it has been renamed to
`mcp_client.py` for simplicity. Public class: `MCPAdapter`.
"""
from __future__ import annotations

# ...existing code copied from old adapter...

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:  # pragma: no cover
    from mcp import ClientSession, StdioServerParameters, types  # type: ignore
    from mcp.client.stdio import stdio_client  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "The 'mcp' package is required. Install with 'pip install mcp' (optionally mcp[cli])."
    ) from e

logger = logging.getLogger("mcp_adapter")
if not logger.handlers:
    _lvl = os.getenv("MCP_ADAPTER_LOG", "INFO").upper()
    logging.basicConfig(level=getattr(logging, _lvl, logging.INFO))


@dataclass
class _ServerRuntime:
    name: str
    params: StdioServerParameters
    session: Optional[ClientSession] = None
    started: asyncio.Event = field(default_factory=asyncio.Event)
    shutdown: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None
    tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class MCPAdapter:
    """Manage multiple MCP servers via the official SDK with a sync facade."""

    def __init__(self, servers_config: List[Dict[str, Any]], init_timeout: float = 6.0):
        self.servers_config = servers_config
        self.init_timeout = init_timeout
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._servers: Dict[str, _ServerRuntime] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._function_name_map: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._closed = False

    def start(self):  # blocking
        if self._closed:
            raise RuntimeError("MCPAdapter already shutdown")
        if self._loop_thread and self._loop and self._loop.is_running():
            logger.debug("MCPAdapter loop already running; reusing")
        else:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._run_loop, name="MCPAdapterLoop", daemon=True)
            self._loop_thread.start()
        for entry in self.servers_config:
            if not entry.get("enabled", False):
                continue
            name = entry.get("name") or "unnamed"
            if name in self._servers:
                continue
            params = self._build_server_params(entry)
            rt = _ServerRuntime(name=name, params=params)
            self._servers[name] = rt
            rt.task = self._submit(self._start_server(rt))
        for rt in self._servers.values():
            try:
                self._run_coroutine_sync(asyncio.wait_for(rt.started.wait(), timeout=self.init_timeout))
            except Exception:
                logger.warning("Timeout waiting for MCP server '%s' to initialize", rt.name)
        self._aggregate_tools()

    def shutdown(self):  # blocking
        if self._closed:
            return
        self._closed = True
        for rt in list(self._servers.values()):
            if rt.session and not rt.shutdown.is_set():
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(rt.shutdown.set)
        for rt in self._servers.values():
            if rt.task:
                try:
                    rt.task.cancel()
                except Exception:
                    pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=2)
        logger.info("MCPAdapter shutdown complete")

    def build_openai_tools_spec(self) -> List[Dict[str, Any]]:
        with self._lock:
            counts: Dict[str, int] = {}
            for meta in self._tools.values():
                base = meta["name"]
                counts[base] = counts.get(base, 0) + 1
            self._function_name_map.clear()
            spec: List[Dict[str, Any]] = []
            for qualified, meta in self._tools.items():
                base = meta["name"]
                exposed = f"{meta['server']}_{base}" if counts[base] > 1 else base
                self._function_name_map[exposed] = qualified
                schema = meta.get("schema") or {"type": "object", "properties": {}}
                spec.append({
                    "type": "function",
                    "function": {
                        "name": exposed,
                        "description": meta.get("description", ""),
                        "parameters": schema,
                    },
                })
            return spec

    def resolve_function_name(self, name: str) -> Optional[str]:
        with self._lock:
            return self._function_name_map.get(name)

    def call_tool(self, qualified: str, arguments: Dict[str, Any]) -> Any:
        with self._lock:
            meta = self._tools.get(qualified)
        if not meta:
            return {"error": f"Unknown tool {qualified}"}
        server_name = meta["server"]
        rt = self._servers.get(server_name)
        if not rt or not rt.session:
            return {"error": f"Server {server_name} not ready"}
        tool_name = meta["name"]
        try:
            result = self._run_coroutine_sync(rt.session.call_tool(tool_name, arguments=arguments))
        except Exception as e:
            logger.exception("Tool call failed (%s:%s)", server_name, tool_name)
            return {"error": f"Tool call failed: {e}"}
        return self._parse_call_result(result)

    # ---------------- internal helpers ----------------
    def _run_loop(self):
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for t in pending:
                t.cancel()
            try:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    def _submit(self, coro_or_callable):
        if not self._loop:
            raise RuntimeError("Event loop not started")
        if asyncio.iscoroutine(coro_or_callable):
            return asyncio.run_coroutine_threadsafe(coro_or_callable, self._loop)
        self._loop.call_soon_threadsafe(coro_or_callable)
        return None

    def _run_coroutine_sync(self, coro):
        fut = self._submit(coro)
        assert fut is not None
        return fut.result(timeout=self.init_timeout)

    def _build_server_params(self, entry: Dict[str, Any]) -> StdioServerParameters:
        cmd = entry.get("command", "python")
        args = entry.get("args", [])
        venv = entry.get("venv")
        global_python = os.getenv("MCP_PYTHON")
        global_venv = os.getenv("MCP_VENV")

        def _venv_python(root: str) -> str | None:
            if not root:
                return None
            posix = os.path.join(root, "bin", "python")
            if os.path.exists(posix):
                return posix
            win = os.path.join(root, "Scripts", "python.exe")
            if os.path.exists(win):
                return win
            return None

        resolved_cmd = cmd
        if global_python and os.path.exists(global_python):
            resolved_cmd = global_python
        else:
            if venv and cmd in ("python", "python3"):
                vpy = _venv_python(venv)
                if vpy:
                    resolved_cmd = vpy
            elif (not venv) and global_venv and cmd in ("python", "python3"):
                gpy = _venv_python(global_venv)
                if gpy:
                    resolved_cmd = gpy
        env_overrides = entry.get("env") or {}
        env_vars = os.environ.copy()
        for k, v in env_overrides.items():
            env_vars[str(k)] = str(v)
        return StdioServerParameters(command=resolved_cmd, args=args, env=env_vars)

    async def _start_server(self, rt: _ServerRuntime):
        try:
            logger.info("Spawning MCP server '%s': %s %s", rt.name, rt.params.command, rt.params.args)
            async with stdio_client(rt.params) as (read, write):
                async with ClientSession(read, write) as session:
                    rt.session = session
                    await session.initialize()
                    try:
                        tools_resp = await session.list_tools()
                        for t in tools_resp.tools:
                            schema = getattr(t, 'inputSchema', None) or getattr(t, 'schema', None)
                            rt.tools[t.name] = {
                                "server": rt.name,
                                "name": t.name,
                                "description": getattr(t, 'description', '') or '',
                                "schema": schema if isinstance(schema, dict) else {},
                            }
                        logger.info("Server '%s' registered %d tools", rt.name, len(rt.tools))
                    except Exception as e:
                        logger.warning("Failed listing tools for %s: %s", rt.name, e)
                    rt.started.set()
                    await rt.shutdown.wait()
        except Exception as e:
            logger.error("Server task exited (%s): %s", rt.name, e)
            rt.started.set()
        finally:
            logger.debug("Server '%s' task ending", rt.name)

    def _aggregate_tools(self):
        with self._lock:
            self._tools.clear()
            for rt in self._servers.values():
                for tool_name, meta in rt.tools.items():
                    qualified = f"{rt.name}:{tool_name}"
                    self._tools[qualified] = meta

    def _parse_call_result(self, call_result: Any) -> Any:
        try:
            structured = getattr(call_result, 'structuredContent', None)
            if structured:
                if isinstance(structured, (dict, list, str, int, float, bool)):
                    if isinstance(structured, dict) and set(structured.keys()) == {"result"} and isinstance(structured["result"], (dict, list, str, int, float, bool)):
                        return structured["result"]
                    return structured
            contents = getattr(call_result, 'content', []) or []
            texts: List[str] = []
            for blk in contents:
                if hasattr(blk, 'text') and isinstance(getattr(blk, 'text'), str):
                    texts.append(getattr(blk, 'text'))
                elif hasattr(blk, 'value') and isinstance(getattr(blk, 'value'), str):
                    texts.append(getattr(blk, 'value'))
            if len(texts) == 1:
                return texts[0]
            if len(texts) > 1:
                return {"content": texts}
            if structured:
                return structured
            return {"raw": repr(call_result)}
        except Exception as e:
            return {"error": f"Failed to parse tool result: {e}"}

__all__ = ["MCPAdapter"]

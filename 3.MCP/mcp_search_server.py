#!/usr/bin/env python
"""Official MCP (FastMCP) search server using DuckDuckGo instant answer API.

Tool:
  web_search(query: str, max_results: int = 5)
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
import time
import sys
from typing import Dict, Any

import requests

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError("FastMCP not available. Install 'mcp' package.") from e

LOG_LEVEL = os.getenv("MCP_SEARCH_LOG_LEVEL", "DEBUG").upper()
JSON_LOGS = os.getenv("MCP_JSON_LOGS") not in (None, "0", "false", "False")

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "logger": "mcp_search",
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter() if JSON_LOGS else logging.Formatter("%(asctime)s | %(levelname)s | mcp_search | %(message)s"))
logger = logging.getLogger("mcp_search")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
if not logger.handlers:
    logger.addHandler(_handler)
    _default_log_file = os.getenv("MCP_LOG_FILE") or os.path.join(os.path.dirname(__file__), "mcp.log")
    try:
        _fh = logging.FileHandler(_default_log_file, encoding="utf-8")
        _fh.setFormatter(_handler.formatter)
        logger.addHandler(_fh)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to attach file handler for %s", _default_log_file)

mcp = FastMCP("search")


def _search_sync(query: str, max_results: int) -> Dict[str, Any]:
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        if data.get("AbstractText"):
            results.append(
                {
                    "title": data.get("Heading"),
                    "snippet": data.get("AbstractText"),
                    "url": data.get("AbstractURL"),
                }
            )
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(
                    {
                        "title": topic.get("Text")[:60],
                        "snippet": topic.get("Text"),
                        "url": topic.get("FirstURL"),
                    }
                )
            if len(results) >= max_results:
                break
        return {"query": query, "results": results[:max_results]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Search failed: {e}"}


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Lightweight DuckDuckGo instant answer style search (non exhaustive)."""
    start = time.perf_counter()
    max_results = max(1, min(max_results, 10))
    logger.debug("tool=web_search phase=start query=%r max_results=%d", query, max_results)
    result = await asyncio.to_thread(_search_sync, query, max_results)
    dur_ms = (time.perf_counter() - start) * 1000
    rcount = len(result.get("results", [])) if isinstance(result, dict) else -1
    logger.debug(
        "tool=web_search phase=end duration_ms=%0.2f result_count=%d has_error=%s",
        dur_ms,
        rcount,
        "error" in result if isinstance(result, dict) else False,
    )
    return result


def main():  # pragma: no cover
    logger.info("Starting MCP search server interpreter=%s", sys.executable)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

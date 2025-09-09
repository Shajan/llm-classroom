#!/usr/bin/env python
"""Playwright browsing server implemented with FastMCP (official MCP protocol).

Tool:
  browse_page(url, selector?, text_only=True, wait_ms=0, screenshot=True,
              full_page=False, headed=None, keep_open_ms=0)
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import json
import time
import sys
from typing import Any, Dict, Optional

try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception as e:  # pragma: no cover
    sync_playwright = None
    _IMPORT_ERROR = e
else:  # pragma: no cover
    _IMPORT_ERROR = None

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError("FastMCP not available. Install 'mcp'.") from e

TRUNCATE_LIMIT = 8000

LOG_LEVEL = os.getenv("MCP_PLAYWRIGHT_LOG_LEVEL", "DEBUG").upper()
JSON_LOGS = os.getenv("MCP_JSON_LOGS") not in (None, "0", "false", "False")

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "logger": "mcp_playwright",
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter() if JSON_LOGS else logging.Formatter("%(asctime)s | %(levelname)s | mcp_playwright | %(message)s"))
logger = logging.getLogger("mcp_playwright")
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

mcp = FastMCP("playwright_browser")


def _browse_sync(
    url: str,
    selector: Optional[str],
    text_only: bool,
    wait_ms: int,
    screenshot: bool,
    full_page: bool,
    headed: Optional[bool],
    keep_open_ms: int,
) -> Dict[str, Any]:
    start = time.perf_counter()
    if sync_playwright is None:
        logger.error("tool=browse_page error=playwright_not_available detail=%s", _IMPORT_ERROR)
        return {"error": f"playwright not available: {_IMPORT_ERROR}"}
    try:
        logger.debug(
            "tool=browse_page phase=start url=%s selector=%s text_only=%s wait_ms=%d screenshot=%s full_page=%s headed=%s keep_open_ms=%d",
            url,
            selector,
            text_only,
            wait_ms,
            screenshot,
            full_page,
            headed,
            keep_open_ms,
        )
        with sync_playwright() as p:
            env_val = os.getenv("MCP_PLAYWRIGHT_HEADLESS")
            if headed is not None:
                headless_flag = not headed
            elif env_val is not None:
                v = env_val.strip().lower()
                if v in ("0", "false", "no", "off"):
                    headless_flag = False
                elif v in ("1", "true", "yes", "on"):
                    headless_flag = True
                else:
                    headless_flag = True
            else:
                headless_flag = True

            browser = p.chromium.launch(headless=headless_flag)
            page = browser.new_page()
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            if keep_open_ms > 0:
                page.wait_for_timeout(min(keep_open_ms, 30_000))

            if selector:
                try:
                    if text_only:
                        content = page.inner_text(selector)
                    else:
                        el = page.query_selector(selector)
                        content = el.inner_html() if el else "(selector not found)"
                except Exception:  # noqa: BLE001
                    content = "(selector not found)"
            else:
                if text_only:
                    try:
                        content = page.inner_text("body")
                    except Exception:  # noqa: BLE001
                        content = page.content()
                else:
                    content = page.content()
            meta = {
                "url": page.url,
                "title": page.title(),
                "length": len(content),
                "headless": headless_flag,
            }
            screenshot_b64 = None
            if screenshot:
                try:
                    shot_bytes = page.screenshot(full_page=full_page)
                    screenshot_b64 = base64.b64encode(shot_bytes).decode("ascii")
                    meta["screenshot_bytes"] = len(shot_bytes)
                except Exception as e:  # noqa: BLE001
                    meta["screenshot_error"] = str(e)
            browser.close()
            if len(content) > TRUNCATE_LIMIT:
                content = content[:TRUNCATE_LIMIT] + "... [truncated]"
            result: Dict[str, Any] = {"meta": meta, "content": content}
            if screenshot_b64:
                result["screenshot_base64"] = screenshot_b64
            dur_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "tool=browse_page phase=end duration_ms=%0.2f url=%s title=%r length=%d screenshot=%s",
                dur_ms,
                meta.get("url"),
                meta.get("title"),
                meta.get("length"),
                bool(screenshot_b64),
            )
            return result
    except Exception as e:  # noqa: BLE001
        dur_ms = (time.perf_counter() - start) * 1000
        logger.exception("tool=browse_page phase=error duration_ms=%0.2f", dur_ms)
        return {"error": f"Browse failed: {e}"}


@mcp.tool()
async def browse_page(
    url: str,
    selector: Optional[str] = None,
    text_only: bool = True,
    wait_ms: int = 0,
    screenshot: bool = True,
    full_page: bool = False,
    headed: Optional[bool] = None,
    keep_open_ms: int = 0,
) -> Dict[str, Any]:
    """Fetch and optionally extract text/HTML from a web page using Chromium.

    Args mirror the legacy implementation; execution is offloaded to a thread
    because Playwright sync API blocks.
    """
    return await asyncio.to_thread(
        _browse_sync,
        url,
        selector,
        text_only,
        wait_ms,
        screenshot,
        full_page,
        headed,
        keep_open_ms,
    )


def main():  # pragma: no cover
    logger.info("Starting FastMCP Playwright server (browse_page) interpreter=%s", sys.executable)
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

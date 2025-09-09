#!/usr/bin/env python
"""MCP-compatible Playwright browsing server.

Tools:
  - browse_page(url: str, selector: Optional[str], text_only: bool = True, wait_ms: int = 0)
    Fetches a page with a headless Chromium browser and returns either:
      * Extracted inner text of a CSS selector (if provided)
      * Full page text (body) when text_only True
      * Truncated HTML when text_only False

Implementation Notes:
  * Uses sync Playwright API for simplicity (single-threaded request/response style)
  * Designed to mirror the minimal protocol used by other demo servers in this repo
  * Requires: `pip install playwright` then `python -m playwright install chromium`
  * Keep responses small – truncate long outputs to ~8000 chars to stay LLM friendly

Security Considerations:
  * No navigation blocking / URL allow‑list is implemented here (educational demo)
  * JavaScript runs on the visited page; avoid using this against untrusted / sensitive intranet targets
  * For production: add timeouts, content filtering, and rate limiting
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict
import os

TRUNCATE_LIMIT = 8000

import base64

try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception as e:  # pragma: no cover - import guard
    sync_playwright = None  # fallback so we can emit a runtime error when called
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None


def _browse(
    url: str,
    selector: str | None,
    text_only: bool,
    wait_ms: int,
    screenshot: bool,
    full_page: bool,
    headed: bool | None,
    keep_open_ms: int,
) -> Dict[str, Any]:
    if sync_playwright is None:  # Import failed
        return {"error": f"playwright not available: {_IMPORT_ERROR}"}
    try:
        with sync_playwright() as p:
            # Determine headless vs headed
            # Priority: explicit tool arg (headed) > env var MCP_PLAYWRIGHT_HEADLESS > default True
            # Env var accepts: "0"/"false" -> headed, "1"/"true" -> headless
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
            # Optional extra debug viewing window AFTER interactions & before capture/close
            if keep_open_ms > 0:
                # Clamp to max 30s to avoid hanging server excessively
                page.wait_for_timeout(min(keep_open_ms, 30_000))

            content: str
            if selector:
                try:
                    if text_only:
                        content = page.inner_text(selector)
                    else:
                        el = page.query_selector(selector)
                        content = el.inner_html() if el else "(selector not found)"
                except Exception:
                    content = "(selector not found)"
            else:
                if text_only:
                    try:
                        content = page.inner_text("body")
                    except Exception:
                        content = page.content()
                else:
                    content = page.content()
            meta = {
                "url": page.url,
                "title": page.title(),
                "length": len(content),
                "headless": headless_flag,
            }
            screenshot_b64: str | None = None
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
            return result
    except Exception as e:  # broad demo error capture
        return {"error": f"Browse failed: {e}"}


TOOLS = {
    "browse_page": {
        "func": lambda args: _browse(
            url=args["url"],
            selector=args.get("selector"),
            text_only=args.get("text_only", True),
            wait_ms=args.get("wait_ms", 0),
            screenshot=args.get("screenshot", True),
            full_page=args.get("full_page", False),
            headed=args.get("headed"),
            keep_open_ms=args.get("keep_open_ms", 0),
        ),
        "description": "Fetch and optionally extract text/HTML from a web page using Chromium (headless by default; set headed to true for visible browser).",
        "schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Absolute URL (http/https)"},
                "selector": {"type": "string", "description": "Optional CSS selector to scope extraction"},
                "text_only": {"type": "boolean", "default": True, "description": "Return inner text instead of HTML"},
                "wait_ms": {"type": "integer", "default": 0, "minimum": 0, "maximum": 15000, "description": "Extra wait after load (milliseconds)"},
                "screenshot": {"type": "boolean", "default": True, "description": "Capture a screenshot and return as base64."},
                "full_page": {"type": "boolean", "default": False, "description": "Capture full page (may be tall)."},
                "headed": {"type": "boolean", "description": "Launch with a visible (non-headless) browser window."},
                "keep_open_ms": {"type": "integer", "default": 0, "minimum": 0, "maximum": 30000, "description": "Extra debug time (ms) to keep the page open (headed mode) before closing."},
            },
            "required": ["url"],
        },
    }
}


def _send(obj: Dict[str, Any]):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _handle(msg: Dict[str, Any]):
    mtype = msg.get("type")
    req_id = msg.get("id")
    if mtype == "list_tools":
        tools_public = [
            {"name": name, "description": meta["description"], "schema": meta["schema"]}
            for name, meta in TOOLS.items()
        ]
        _send({"type": "tool_list", "id": req_id, "tools": tools_public})
    elif mtype == "call_tool":
        name = msg.get("name")
        args = msg.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            _send({"type": "error", "id": req_id, "error": f"Unknown tool {name}"})
            return
        try:
            result = tool["func"](args)
            _send({"type": "tool_result", "id": req_id, "content": result})
        except Exception as e:  # noqa: BLE001
            _send({"type": "error", "id": req_id, "error": str(e)})
    else:
        _send({"type": "error", "id": req_id, "error": f"Unknown message type {mtype}"})


def main():  # pragma: no cover - CLI entry point
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            _send({"type": "error", "id": None, "error": f"JSON decode error: {e}"})
            continue
        _handle(msg)


if __name__ == "__main__":  # pragma: no cover
    main()

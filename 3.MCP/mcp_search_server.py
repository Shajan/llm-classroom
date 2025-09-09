#!/usr/bin/env python
"""Simple MCP-compatible search server using DuckDuckGo instant answer API (no key).

Tools:
  - web_search(query: str, max_results: int = 5)

This is intentionally kept lightweight and unauthenticated for demo purposes.
"""
import sys
import json
import requests
from typing import Any, Dict


def web_search(query: str, max_results: int = 5):
    # Use DuckDuckGo's instant answer API (not a full web search, but okay for demo)
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        # Abstract + RelatedTopics as faux search results
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading"),
                "snippet": data.get("AbstractText"),
                "url": data.get("AbstractURL")
            })
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text")[:60],
                    "snippet": topic.get("Text"),
                    "url": topic.get("FirstURL")
                })
            if len(results) >= max_results:
                break
        return {"query": query, "results": results[:max_results]}
    except Exception as e:
        return {"error": f"Search failed: {e}"}


TOOLS = {
    "web_search": {
        "func": lambda args: web_search(**args),
        "description": "Lightweight DuckDuckGo instant answer search (not exhaustive).",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5}
            },
            "required": ["query"]
        }
    }
}


def send(obj: Dict[str, Any]):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def handle(msg: Dict[str, Any]):
    mtype = msg.get("type")
    req_id = msg.get("id")
    if mtype == "list_tools":
        tools_public = [
            {"name": name, "description": meta["description"], "schema": meta["schema"]}
            for name, meta in TOOLS.items()
        ]
        send({"type": "tool_list", "id": req_id, "tools": tools_public})
    elif mtype == "call_tool":
        name = msg.get("name")
        args = msg.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            send({"type": "error", "id": req_id, "error": f"Unknown tool {name}"})
            return
        try:
            result = tool["func"](args)
            send({"type": "tool_result", "id": req_id, "content": result})
        except Exception as e:
            send({"type": "error", "id": req_id, "error": str(e)})
    else:
        send({"type": "error", "id": req_id, "error": f"Unknown message type {mtype}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            send({"type": "error", "id": None, "error": f"JSON decode error: {e}"})
            continue
        handle(msg)


if __name__ == "__main__":
    main()

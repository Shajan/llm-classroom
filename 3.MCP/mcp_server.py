#!/usr/bin/env python
"""
Minimal MCP Server exposing two tools over stdio using a simple JSONL protocol.
Tools:
  - get_current_location
  - get_weather (requires latitude & longitude)

Protocol (very small subset for demonstration):
Client -> Server JSON lines:
  {"type": "list_tools", "id": "<req id>"}
  {"type": "call_tool", "id": "<req id>", "name": "tool_name", "arguments": {...}}

Server -> Client JSON lines:
  {"type": "tool_list", "id": "<req id>", "tools": [{"name":..., "description":..., "schema":{...}}]}
  {"type": "tool_result", "id": "<req id>", "content": <any JSON-serializable>}
  {"type": "error", "id": "<req id>", "error": "message"}

Run directly: python 3.MCP/mcp_server.py
"""
import sys
import json
import requests
import logging
from typing import Any, Dict

import os

_srv_log_level = os.getenv("MCP_SERVER_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _srv_log_level, logging.INFO),
    format="%(asctime)s | %(levelname)s | mcp_server | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("mcp_server")


def get_current_location() -> Dict[str, Any]:
    try:
        resp = requests.get(
            "https://ipapi.co/json/", timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; MCPDemo/1.0)'}
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "city": data.get("city", "Unknown"),
            "region": data.get("region", "Unknown"),
            "country": data.get("country_name", "Unknown"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone", "Unknown")
        }
    except Exception as e:
        return {"error": f"Failed to get location: {e}"}


def get_weather(latitude: float, longitude: float, city: str = "Unknown") -> Dict[str, Any]:
    try:
        url = f"https://wttr.in/{latitude},{longitude}"
        params = {"format": "j1", "lang": "en"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data['current_condition'][0]
        nearest_area = data.get('nearest_area', [{}])[0]
        location_name = nearest_area.get('areaName', [{}])[0].get('value', city)
        region = nearest_area.get('region', [{}])[0].get('value', '')
        country = nearest_area.get('country', [{}])[0].get('value', '')
        loc = location_name
        if region and region != location_name:
            loc += f", {region}"
        if country:
            loc += f", {country}"
        return {
            "location": loc,
            "temperature": f"{current['temp_C']}°C ({current['temp_F']}°F)",
            "description": current['weatherDesc'][0]['value'],
            "humidity": f"{current['humidity']}%",
            "wind_speed": f"{current['windspeedKmph']} km/h",
            "wind_direction": current['winddir16Point'],
            "feels_like": f"{current['FeelsLikeC']}°C ({current['FeelsLikeF']}°F)",
            "uv_index": current['uvIndex'],
            "visibility": f"{current['visibility']} km",
            "pressure": f"{current['pressure']} mb",
            "cloud_cover": f"{current['cloudcover']}%"
        }
    except Exception as e:
        return {"error": f"Failed to get weather: {e}"}


TOOLS = {
    "get_current_location": {
        "func": lambda args: get_current_location(),
        "description": "Get the user's current location based on IP (ipapi.co). Call before get_weather.",
        "schema": {"type": "object", "properties": {}, "required": []}
    },
    "get_weather": {
        "func": lambda args: get_weather(**args),
        "description": "Get current weather for coordinates using wttr.in.",
        "schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "city": {"type": "string"}
            },
            "required": ["latitude", "longitude"]
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
        logger.debug("Received list_tools request id=%s", req_id)
        tools_public = [
            {"name": name, "description": meta["description"], "schema": meta["schema"]}
            for name, meta in TOOLS.items()
        ]
        send({"type": "tool_list", "id": req_id, "tools": tools_public})
    elif mtype == "call_tool":
        name = msg.get("name")
        args = msg.get("arguments") or {}
        logger.info("Tool call '%s' args=%s id=%s", name, args, req_id)
        tool = TOOLS.get(name)
        if not tool:
            logger.error("Unknown tool '%s'", name)
            send({"type": "error", "id": req_id, "error": f"Unknown tool {name}"})
            return
        try:
            result = tool["func"](args)
            logger.debug("Tool '%s' result=%s", name, result)
            send({"type": "tool_result", "id": req_id, "content": result})
        except Exception as e:
            logger.exception("Exception while executing tool '%s'", name)
            send({"type": "error", "id": req_id, "error": str(e)})
    else:
        logger.warning("Unknown message type '%s' id=%s", mtype, req_id)
        send({"type": "error", "id": req_id, "error": f"Unknown message type {mtype}"})


def main():
    # Simple loop reading JSON lines from stdin
    logger.info("MCP server starting; waiting for JSONL messages on stdin")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s line=%s", e, line)
            send({"type": "error", "id": None, "error": f"JSON decode error: {e}"})
            continue
        handle(msg)

if __name__ == "__main__":
    main()

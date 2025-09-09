#!/usr/bin/env python
"""MCP Server (decorator-based) exposing real tools via the official
Model Context Protocol Python SDK.

Replaces the earlier ad‑hoc JSONL implementation with the canonical
`@mcp.tool()` decorator approach. This enables interoperability with
MCP-compliant clients (Claude Desktop, IDE agents, etc.) without the
custom protocol shim used elsewhere in the demo.

Tools Provided:
  * get_current_location() -> Geo/IP metadata
  * get_weather(latitude: float, longitude: float, city: Optional[str]) -> Weather summary

Running:
  python 3.MCP/mcp_server.py

If the MCP SDK is not installed, add it:
  pip install mcp  (official SDK – or adjust if the package name differs)

Notes:
  * Network I/O is executed in a thread pool (requests is sync) so the
    async tool functions remain non-blocking for the event loop.
  * Returned objects are JSON‑serializable (dict / primitives) per MCP spec.
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
import time
import sys
from typing import Any, Dict, Optional

import requests

# ---------------------------------------------------------------------------
# MCP SDK Import (supports both current canonical paths & fallbacks)
# ---------------------------------------------------------------------------
try:  # Preferred (official SDK layout – FastMCP convenience wrapper)
    from mcp.server.fastmcp import FastMCP  # type: ignore
    _FASTMCP_AVAILABLE = True
except Exception:  # pragma: no cover - fallback attempt
    try:
        from fastmcp import FastMCP  # type: ignore
        _FASTMCP_AVAILABLE = True
    except Exception as _import_err:  # pragma: no cover - final failure
        FastMCP = None  # type: ignore
        _FASTMCP_AVAILABLE = False
        _FASTMCP_ERROR = _import_err  # type: ignore


LOG_LEVEL = os.getenv("MCP_SERVER_LOG_LEVEL", "DEBUG").upper()
JSON_LOGS = os.getenv("MCP_JSON_LOGS") not in (None, "0", "false", "False")

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "logger": "mcp_server",
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

_handler = logging.StreamHandler()
if JSON_LOGS:
    _handler.setFormatter(_JsonFormatter())
else:
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | mcp_server | %(message)s"))
logger = logging.getLogger("mcp_server")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
if not logger.handlers:
    logger.addHandler(_handler)
    # Add default file logging (override with MCP_LOG_FILE). All MCP servers append to same file by default.
    _default_log_file = os.getenv("MCP_LOG_FILE") or os.path.join(os.path.dirname(__file__), "mcp.log")
    try:
        _fh = logging.FileHandler(_default_log_file, encoding="utf-8")
        # Reuse same formatter style
        _fh.setFormatter(_handler.formatter)
        logger.addHandler(_fh)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to attach file handler for %s", _default_log_file)

if not _FASTMCP_AVAILABLE:  # Fail early with actionable guidance
    raise ImportError(
        "FastMCP (Model Context Protocol SDK) not available. Install with 'pip install mcp' "
        f"(original import error: {_FASTMCP_ERROR})"  # type: ignore[name-defined]
    )


# Instantiate the MCP server. The name is what clients will see.
mcp = FastMCP("location_weather")


# ----------------------------- Helper Functions -----------------------------
def _get_current_location_sync() -> Dict[str, Any]:
    try:
        resp = requests.get(
            "https://ipapi.co/json/",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MCPDemo/2.0)"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "city": data.get("city") or "Unknown",
            "region": data.get("region") or "Unknown",
            "country": data.get("country_name") or "Unknown",
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone") or "Unknown",
            "ip": data.get("ip"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to get location: {e}"}


def _get_weather_sync(latitude: float, longitude: float, city: str | None) -> Dict[str, Any]:
    try:
        url = f"https://wttr.in/{latitude},{longitude}"
        params = {"format": "j1", "lang": "en"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        current = data.get("current_condition", [{}])[0]
        nearest_area = data.get("nearest_area", [{}])[0]
        location_name = (
            nearest_area.get("areaName", [{}])[0].get("value")
            if isinstance(nearest_area.get("areaName"), list)
            else city
        ) or city or "Unknown"
        region = (
            nearest_area.get("region", [{}])[0].get("value")
            if isinstance(nearest_area.get("region"), list)
            else ""
        )
        country = (
            nearest_area.get("country", [{}])[0].get("value")
            if isinstance(nearest_area.get("country"), list)
            else ""
        )
        loc = location_name
        if region and region != location_name:
            loc += f", {region}"
        if country:
            loc += f", {country}"
        return {
            "location": loc,
            "temperature_c": current.get("temp_C"),
            "temperature_f": current.get("temp_F"),
            "description": (current.get("weatherDesc", [{}])[0].get("value") if current.get("weatherDesc") else None),
            "humidity_pct": current.get("humidity"),
            "wind_kmph": current.get("windspeedKmph"),
            "wind_dir": current.get("winddir16Point"),
            "feels_like_c": current.get("FeelsLikeC"),
            "feels_like_f": current.get("FeelsLikeF"),
            "uv_index": current.get("uvIndex"),
            "visibility_km": current.get("visibility"),
            "pressure_mb": current.get("pressure"),
            "cloud_cover_pct": current.get("cloudcover"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to get weather: {e}"}


# ------------------------------- MCP Tools ---------------------------------
@mcp.tool()
async def get_current_location() -> Dict[str, Any]:
    """Get the caller's approximate geolocation via IP (ipapi.co).

    Returns a dict with city, region, country, latitude, longitude, timezone & ip.
    """
    start = time.perf_counter()
    logger.debug("tool=get_current_location phase=start")
    result = await asyncio.to_thread(_get_current_location_sync)
    dur_ms = (time.perf_counter() - start) * 1000
    logger.debug("tool=get_current_location phase=end duration_ms=%0.2f keys=%s", dur_ms, list(result.keys()))
    return result


@mcp.tool()
async def get_weather(
    latitude: float,
    longitude: float,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve current weather conditions for coordinates using wttr.in.

    Provide latitude & longitude (decimal degrees). Optionally pass an already
    known city name for nicer display if reverse-lookup fails.
    """
    start = time.perf_counter()
    logger.debug(
        "tool=get_weather phase=start latitude=%s longitude=%s city=%s", latitude, longitude, city
    )
    result = await asyncio.to_thread(_get_weather_sync, latitude, longitude, city)
    dur_ms = (time.perf_counter() - start) * 1000
    logger.debug("tool=get_weather phase=end duration_ms=%0.2f keys=%s", dur_ms, list(result.keys()) if isinstance(result, dict) else type(result).__name__)
    return result


# ------------------------------- Entry Point -------------------------------
def main():  # pragma: no cover - runtime entry
    logger.info(
        "Starting MCP decorator-based server (tools: get_current_location, get_weather) interpreter=%s",
        sys.executable,
    )
    # FastMCP handles stdio event loop & protocol negotiation.
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

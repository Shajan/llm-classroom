"""
A second MCP server: opens a web page in a headless browser and returns its text.

Same pattern as weather_server.py. The client finds this tool at startup
because it is listed in mcp_config.yaml - no client code changes needed.

Setup (once): python -m playwright install chromium
"""
from mcp.server.mcpserver import MCPServer
from playwright.async_api import async_playwright

mcp = MCPServer("browser")


@mcp.tool()
async def browse_page(url: str) -> str:
    """Open a web page and return its visible text (first 8000 characters)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=30_000)
        text = await page.inner_text("body")
        await browser.close()
    return text[:8000]  # keep the result small: it is sent to the model as tokens


if __name__ == "__main__":
    mcp.run()

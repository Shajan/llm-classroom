"""
Chat client that gets its tools from MCP servers.

This is the 2.2 agent (create_agent) with one change: the tools are not
defined here. The client knows nothing about weather or browsers. At startup it:
  1. starts each server listed in mcp_config.yaml as a subprocess
  2. asks each server for its tools (list_tools)
  3. wraps each MCP tool as a LangChain tool and hands them to create_agent
When the agent calls a tool, the wrapper forwards the call to the server
that owns it (call_tool).
"""
import asyncio
import os
import sys
from contextlib import AsyncExitStack

import yaml
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


def to_langchain_tool(session, mcp_tool):
    """Wrap an MCP tool so create_agent can use it like the @tool functions in 2.2."""

    async def call(**args):
        # The MCP part: forward the call to the server that owns this tool.
        print(f"Calling MCP tool: {mcp_tool.name}({args})")
        result = await session.call_tool(mcp_tool.name, args)
        return "".join(c.text for c in result.content if c.type == "text")

    # MCP and LangChain both describe parameters with JSON Schema,
    # so the server's schema is passed through unchanged.
    return StructuredTool(
        name=mcp_tool.name,
        description=mcp_tool.description,
        args_schema=mcp_tool.input_schema,
        coroutine=call,
    )


async def connect_to_servers(stack):
    """Start every server in the config and collect its tools."""
    with open(os.path.join(HERE, "mcp_config.yaml")) as f:
        config = yaml.safe_load(f)

    tools = []
    for server in config["servers"]:
        # Start the server as a subprocess; we talk to it over stdin/stdout.
        # sys.executable = the same Python running this client.
        params = StdioServerParameters(command=sys.executable,
                                       args=[os.path.join(HERE, server["script"])])
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()  # MCP handshake

        # Ask the server what tools it has.
        for mcp_tool in (await session.list_tools()).tools:
            print(f"Server '{server['name']}' provides tool: {mcp_tool.name}")
            tools.append(to_langchain_tool(session, mcp_tool))

    return tools


async def main():
    load_dotenv(os.path.join(HERE, "..", ".env"))

    # AsyncExitStack shuts down every server when we leave this block.
    async with AsyncExitStack() as stack:
        tools = await connect_to_servers(stack)

        # Same as 2.2, but the tools came from MCP servers.
        agent = create_agent(
            model="openai:gpt-4o-mini",
            tools=tools,
            # Safety check, same as 2.2: at most 3 tool runs per question
            # (one more than 2.2, since a question may need both servers).
            # Every time around the loop the WHOLE conversation is sent to the
            # model again. If this check is removed and the model keeps asking
            # for tools, token usage (and cost) keeps growing with every round.
            middleware=[ToolCallLimitMiddleware(run_limit=3, exit_behavior="end")],
        )

        messages = []  # the conversation, kept across questions
        while True:
            question = input("\nYou (empty line to quit): ").strip()
            if not question:
                break
            messages.append({"role": "user", "content": question})
            result = await agent.ainvoke({"messages": messages})
            messages = result["messages"]
            print(f"\nAssistant: {messages[-1].content}")


if __name__ == "__main__":
    asyncio.run(main())

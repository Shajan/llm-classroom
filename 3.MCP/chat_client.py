"""
Chat client that gets its tools from MCP servers.

This is the 2.1.Tools agent loop with one change: the tools are not defined
here. The client knows nothing about weather or browsers. At startup it:
  1. starts each server listed in mcp_config.yaml as a subprocess
  2. asks each server for its tools (list_tools)
  3. hands those tools to the model
When the model calls a tool, the client forwards the call to the server
that owns it (call_tool).
"""
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

import yaml
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))

# Safety check, same as 2.1: the most tools we will run for one question.
# Every time around the loop the WHOLE conversation is sent to the model
# again. If this check is removed and the model keeps asking for tools,
# token usage (and cost) keeps growing with every round.
MAX_TOOL_RUNS = 3


async def connect_to_servers(stack):
    """Start every server in the config and collect its tools."""
    with open(os.path.join(HERE, "mcp_config.yaml")) as f:
        config = yaml.safe_load(f)

    tools = []          # tool definitions in the format OpenAI expects
    tool_owner = {}     # tool name -> the server session that runs it

    for server in config["servers"]:
        # Start the server as a subprocess; we talk to it over stdin/stdout.
        # sys.executable = the same Python running this client.
        params = StdioServerParameters(command=sys.executable,
                                       args=[os.path.join(HERE, server["script"])])
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()  # MCP handshake

        # Ask the server what tools it has, and convert each to OpenAI's format.
        # MCP and OpenAI both describe parameters with JSON Schema, so this is
        # just a rename of fields.
        for tool in (await session.list_tools()).tools:
            print(f"Server '{server['name']}' provides tool: {tool.name}")
            tool_owner[tool.name] = session
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            })

    return tools, tool_owner


async def main():
    load_dotenv(os.path.join(HERE, "..", ".env"))
    client = OpenAI()

    # AsyncExitStack shuts down every server when we leave this block.
    async with AsyncExitStack() as stack:
        tools, tool_owner = await connect_to_servers(stack)
        messages = []

        while True:
            question = input("\nYou (empty line to quit): ").strip()
            if not question:
                break
            messages.append({"role": "user", "content": question})
            tool_runs = 0

            # The agent loop from 2.1.
            while True:
                # Safety check: once the limit is reached, the model must answer.
                tool_choice = "none" if tool_runs >= MAX_TOOL_RUNS else "auto"
                response = client.chat.completions.create(
                    model="gpt-4o-mini", messages=messages, tools=tools, tool_choice=tool_choice
                )
                message = response.choices[0].message

                if not message.tool_calls:
                    print(f"\nAssistant: {message.content}")
                    messages.append({"role": "assistant", "content": message.content})
                    break

                messages.append(message)
                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    # Safety check before every run: the model can ask for several at once.
                    if tool_runs >= MAX_TOOL_RUNS:
                        result = "Tool run limit reached"
                    else:
                        tool_runs += 1
                        args = json.loads(tool_call.function.arguments)
                        print(f"Calling MCP tool: {name}({args}) (tool run {tool_runs} of {MAX_TOOL_RUNS})")
                        # The MCP part: forward the call to the server that owns this tool.
                        mcp_result = await tool_owner[name].call_tool(name, args)
                        result = "".join(c.text for c in mcp_result.content if c.type == "text")

                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})


if __name__ == "__main__":
    asyncio.run(main())

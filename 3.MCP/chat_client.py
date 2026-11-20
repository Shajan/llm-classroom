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
from datetime import date

import yaml
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))

# The model only knows what was in its training data, which can be months or
# years old, and it tends to agree with whatever the question assumes. This
# prompt tells it to use the tools to check facts and to question the premise.
SYSTEM_PROMPT = """Today's date is {today}.

Your training data has a cutoff date and may be out of date. For anything that
can change over time (news, prices, versions, weather, who holds a role), do
not trust your memory: use the tools to look it up, and say so if you could not.

Do not assume the question is correct. If it contains a wrong or doubtful
assumption, say so instead of going along with it. When the facts you find
disagree with what you expected or with what the user said, trust the facts.

Before you answer, check your answer against what the tools returned. If they
do not support it, correct it or say you are not sure."""


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

    # LangSmith tracing: records every model call and tool call so you can
    # see each step of the agent at smith.langchain.com. LangChain does the
    # recording by itself once tracing is on. Needs LANGSMITH_API_KEY in .env.
    if os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = "3.MCP"

    # AsyncExitStack shuts down every server when we leave this block.
    async with AsyncExitStack() as stack:
        tools = await connect_to_servers(stack)

        # Same as 2.2, but the tools came from MCP servers.
        agent = create_agent(
            model="openai:gpt-4o-mini",
            tools=tools,
            system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
            # Safety check, same as 2.2: at most 3 tool runs per question
            # (one more than 2.2, since a question may need both servers).
            # Every time around the loop the WHOLE conversation is sent to the
            # model again. If this check is removed and the model keeps asking
            # for tools, token usage (and cost) keeps growing with every round.
            middleware=[ToolCallLimitMiddleware(run_limit=3, exit_behavior="end")],
        )

        messages = []  # the conversation, kept across questions
        print("Type /clear to start a new conversation, or an empty line to quit.")
        while True:
            question = input("\nYou: ").strip()
            if not question:
                break
            if question == "/clear":
                # Forget earlier questions and answers, so they are no longer
                # sent to the model (and no longer cost tokens).
                messages = []
                print("Conversation cleared.")
                continue
            messages.append({"role": "user", "content": question})
            result = await agent.ainvoke({"messages": messages})
            messages = result["messages"]
            print(f"\nAssistant: {messages[-1].content}")


if __name__ == "__main__":
    asyncio.run(main())

# Weather Application - LangChain Implementation

The same weather agent as `../2.1.Tools`, using LangChain.

## What Changes from 2.1

The tool functions are the same. Two things change:

| 2.1.Tools (by hand) | 2.2 (LangChain) |
|---|---|
| Hand-written `tools` list with a JSON schema per tool | `@tool` decorator builds it from type hints and the docstring |
| The agent loop: call model, run tools, add results, repeat | `create_agent(...)` then `agent.invoke(...)` |
| `MAX_TOOL_RUNS = 2` safety check | `ToolCallLimitMiddleware(run_limit=2)` |

## Installation

```bash
pip install -r 2.2.Tools.Langchain/requirements.txt
```

Requires LangChain 1.x.

## Usage

From the repository root:

```bash
python 2.2.Tools.Langchain/weather_question.py
```

## Environment Variables

Make sure you have an `.env` file in the parent directory with:
```
OPENAI_API_KEY=your_openai_api_key_here
```

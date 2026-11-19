# Agent Example: a Long-Running Agent That Resumes

The 2.2 agent (`create_agent` + `@tool`) researches a stock and estimates a fair value. One new idea: a **checkpointer**. After every step (a model call or a tool run), the agent's state is saved to `checkpoints.db`. If the run stops part way (Ctrl+C, a crash, a closed laptop), running it again continues from the last saved step instead of starting over.

Real agents can run for minutes or hours and make many paid model calls, so they need this.

## Files

| File | What it shows |
|---|---|
| `research_agent.py` | Two tools, the 2.2 agent, and a SQLite checkpointer |

## How It Works

1. **Tools:** `get_financials` reads the latest annual numbers from the company's SEC 10-K filings. `get_market_data` gets the share price and shares outstanding from Yahoo Finance.
2. **Agent:** `create_agent` as in 2.2, plus `checkpointer=SqliteSaver(...)`. Each ticker's run is saved under its own `thread_id`.
3. **Resume:** at startup the script asks `agent.get_state(config).tasks` whether the saved run still has steps to do. If it does, `agent.invoke(None, config)` continues it. `None` means no new message: just pick up where you left off. If the last run finished, a new one starts.

## Setup

From the repository root:

```bash
pip install -r 5.Agent/requirements.txt
```

The script reads `OPENAI_API_KEY` from the `.env` file in the repository root.

## Run

```bash
python 5.Agent/research_agent.py NVDA
```

To see the resume, press Ctrl+C after the first `Tool:` line, then run the same command again:

```
Researching NVDA
Tool: get_financials(NVDA)
^C
Stopped. Run the same command again to resume.

$ python 5.Agent/research_agent.py NVDA
Resuming the stopped run for NVDA
...
Answer: ...
```

As in 2.2, `ToolCallLimitMiddleware` caps tool runs (4 here). Educational only; not investment advice.

# PRD — Equity Research AI Agent

Date: 2025-09-09
Owner: 5.Agent
Status: Draft (MVP implemented)

## Summary
Build a long-running, resumable AI agent that researches a U.S. publicly traded company and produces a fair market value estimate for its stock. The agent fetches SEC filings, constructs financial statements and key ratios, benchmarks against sector peers and market, incorporates U.S. macro indicators, and blends DCF and relative valuation into a final fair value. All inputs, intermediate artifacts, and outputs are persisted for later reuse and auditability.

## Goals
- Automate periodic equity research for a given ticker
- Reliable data acquisition with caching and rate-limit compliance
- Deterministic, resumable pipeline with checkpoints
- Transparent valuation with explainable inputs

## Non-goals
- Intraday trading signals
- High-frequency data ingestion
- Broker integrations or order execution

## Users and Use Cases
- Individual analysts validating a fair value estimate
- Educators demonstrating an end-to-end fundamental analysis pipeline
- Engineers exploring long-running, checkpointable agent patterns

## Requirements
1) Inputs
   - Ticker (US-listed): e.g., AAPL
   - Optional env: SEC_API_EMAIL, FRED_API_KEY
2) Data fetching
   - Resolve CIK from ticker via SEC index
   - Download company submissions and XBRL company facts
   - Cache raw JSON
3) Processing
   - Build Income, Balance Sheet, Cash Flow dataframes
   - Compute key ratios (margins, leverage, ROA, debt metrics)
4) Benchmarks
   - Sector benchmark ETF and 1Y return
   - Peer list and peer median multiples (e.g., P/E)
   - Market cap for target
5) Macro
   - Risk-free rate (10Y) via FRED when available; fallback constants
   - Market risk premium default 5%
6) Valuation
   - DCF with 5-year horizon, WACC via CAPM, terminal growth 2%
   - Relative valuation using peer median P/E and net income/FCF
   - Blended fair value (default 60% DCF / 40% Relative)
7) Resiliency
   - Checkpoint to output/<TICKER>/state.json every N seconds
   - Resume from checkpoint with --resume
   - Graceful shutdown on SIGINT/SIGTERM
8) Persistence & Artifacts
   - data/: raw cached SEC responses
   - output/<TICKER>/: ratios.csv, valuation_report.md, state.json
9) Observability (MVP)
   - Console logs for milestones and paths

## Acceptance Criteria
- Running `python 5.Agent/agent.py --ticker AAPL --resume` completes without errors
- `output/AAPL/valuation_report.md` exists and includes key ratios and valuation summary
- `output/AAPL/state.json` updates multiple times during a run
- Re-running with `--resume` skips already-completed steps when possible

## Architecture
- Modules
  - fetchers.sec: SEC APIs, caching, retry/backoff
  - processing.financials: build statements and ratios
  - market.market_data: market cap, peers, peer multiples
  - market.industry: sector benchmark mapping (ETF) and returns
  - macro.us_macro: FRED integration with fallbacks
  - valuation.models: DCF + relative blend
  - agent_core.state: Checkpointer and AgentState
  - agent.py: Orchestrates steps, report generation, signals

## Data Model (State)
- AgentState
  - ticker: str
  - step: str (start|fetch_sec|process_financials|market_peers|macro|valuation|report)
  - data_paths: {name: path}
  - notes: free-form dict for intermediate results

## Risks & Mitigations
- SEC rate limits -> backoff + user-agent; local caching
- yfinance instability -> try/except & fallbacks; limit usage to coarse data
- Sparse XBRL tags -> compute with available fields and defaults
- Macro API missing -> default constants

## Future Work
- Robust peer discovery via SIC/NAICS and full comparable set
- EV/EBITDA relative valuation with enterprise value calculation
- Rich report with charts, assumptions, and sensitivity tables
- Scheduler/cron integration for periodic refresh
- Unit tests covering edge cases and data gaps

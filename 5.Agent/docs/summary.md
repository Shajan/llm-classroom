# llm-classroom — Implementation Summary (Context)

Date: 2025-09-09

This document summarizes the equity research agent implemented in `5.Agent` so it can be used as high-level context for tools or other agents.

## Purpose
A long-running, checkpointable agent that researches a U.S.-listed company and produces a fair value estimate for the stock by combining fundamentals (SEC filings), peer/sector/market comparisons, and macroeconomic indicators.

## Top-level Flow
1) Fetch SEC data (company submissions + XBRL facts)
2) Build financial statements (Income, Balance, Cash Flow) and compute key ratios
3) Gather market data: market cap, heuristic peers, peer median P/E
4) Get sector benchmark performance (e.g., XLK for technology)
5) Get U.S. macro indicators (risk-free rate via FRED, fallback defaults)
6) Run valuation: 5-year DCF + relative valuation (P/E) → blended fair value
7) Persist artifacts and checkpoint state; generate a markdown report

## Key Modules (5.Agent)
- `agent.py`: Orchestrates the pipeline, handles loop, checkpointing, and reporting
- `agent_core/state.py`: `AgentState` and `Checkpointer` for resumable runs
- `fetchers/sec.py`: SEC calls with caching and backoff; resolves CIK, pulls submissions and company facts
- `processing/financials.py`: Converts SEC facts into dataframes and computes core ratios
- `market/market_data.py`: Market cap via yfinance; peer discovery (heuristic) and peer multiple aggregation
- `market/industry.py`: Maps sector → benchmark ETF (SPDRs) and computes trailing 1Y return
- `macro/us_macro.py`: Risk-free and market premium via FRED (optional) with safe defaults
- `valuation/models.py`: WACC, DCF, relative valuation, and blended result

## Checkpointing & Persistence
- State file: `5.Agent/output/<TICKER>/state.json` updated periodically and on milestones
- Raw data cache: `5.Agent/data/` contains SEC responses (submissions, company facts)
- Intermediate output: `5.Agent/output/<TICKER>/ratios.csv`
- Final report: `5.Agent/output/<TICKER>/valuation_report.md`
- Resume: pass `--resume` to continue from last state; SIGINT/SIGTERM cause graceful save

## Data & Models
- Financials: Subset of common us-gaap tags; ratios: Gross/Operating/Net margins, leverage, ROA, debt metrics
- Macro: `rf_rate` (10Y) and `market_risk_premium` (~5% default)
- Valuation: DCF (5 years, growth from revenue CAGR when available, terminal growth 2%, WACC via CAPM-like estimate) and Relative (peer median P/E × earnings/FCF); blended default 60/40

## How to Run
- Dependencies at `5.Agent/requirements.txt` (use workspace task to install)
- Example
  ```bash
  # macOS, bash
  source .venv/bin/activate
  python 5.Agent/agent.py --ticker AAPL --resume
  ```

## Notes & Limitations
- yfinance and public endpoints may be intermittent; code includes retries and fallbacks
- Peer discovery is heuristic in MVP; improve with SIC/NAICS mappings
- Educational use only; not investment advice

## Related Docs
- `5.Agent/README.md`: Feature overview and quick start
- `5.Agent/docs/prd.md`: Product requirements, acceptance criteria, architecture

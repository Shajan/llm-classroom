# 5.Agent — Equity Research Agent

An end-to-end, long‑running equity research agent that:
- Fetches and caches SEC filings (10‑K/10‑Q) via the SEC EDGAR API
- Builds historical financial statements and key ratios
- Benchmarks the company against sector peers and broad market indices
- Incorporates U.S. macro environment indicators
- Produces a fair value estimate (DCF + relative valuation blend)
- Periodically checkpoints state so it can resume after interruption

## Features
- Robust fetchers with retry and user agent compliance for SEC API
- Local on-disk cache for raw data and normalized datasets
- Pluggable valuation models with explainable outputs
- Incremental job runner with resumable checkpoints

## Quick start

1) Create and activate a Python 3.10+ environment.

2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Set optional environment variables:
- `SEC_API_EMAIL`: your email for SEC API user-agent policy (recommended)

4) Run the agent for a ticker (e.g., AAPL):

```bash
python agent.py --ticker AAPL --resume --save-every 120
```

- `--resume` resumes from last checkpoint if available.
- `--save-every` controls checkpoint frequency in seconds.

Outputs will be written to `5.Agent/output/<TICKER>/` including normalized datasets, intermediate artifacts, and a final `valuation_report.md`.

## Data sources
- SEC EDGAR (company submissions, 10‑K/10‑Q, XBRL facts)
- Sector/industry peer list via public reference (SEC taxonomy + SIC); price data via Yahoo Finance (yfinance)
- Macro indicators via FRED (optional) or fallback to public JSON endpoints

## Valuation models
- DCF: 5-year explicit forecast + terminal value (Gordon growth), WACC estimation via CAPM
- Relative: EV/EBITDA and P/E peer median blend
- Final fair value = weighted blend (default 60% DCF / 40% Relative)

## Checkpointing & resume
- Each run keeps a `state.json` with milestones and cached data hashes.
- On restart with `--resume`, the agent continues from the last incomplete step.

## Notes
- This project is for educational purposes; not investment advice.
- APIs used here have rate limits. Be respectful and cache results.

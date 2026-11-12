# 5.Agent — Equity Research Agent

An end-to-end, long‑running equity research pipeline. It does not call an LLM; it shows the long-running side of agent design (caching, retries, checkpoints, graceful shutdown). It:
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

3) Set optional environment variables. They are read from the shell environment; the code does not load a `.env` file, so `export` them (see `.env.example` for the names):
- `SEC_API_EMAIL`: your email for SEC API user-agent policy (recommended)
- `FRED_API_KEY`: FRED key for the live 10-year Treasury rate (otherwise 4% is used)

4) Run the agent for a ticker (e.g., AAPL):

```bash
python agent.py --ticker AAPL --resume --save-every 120
```

- `--resume` loads the previous `state.json` (notes and data paths). It does not skip steps; every run executes all steps, but SEC data is served from the local cache.
- `--save-every` controls checkpoint frequency in seconds.
- `--loop-interval N` reruns the pipeline every N seconds until stopped.

Outputs will be written to `5.Agent/output/<TICKER>/` including normalized datasets, intermediate artifacts, and a final `valuation_report.md`.

## Data sources
- SEC EDGAR (company submissions, 10‑K/10‑Q, XBRL facts)
- Market cap, sector benchmark ETF and a small hardcoded peer list via Yahoo Finance (yfinance)
- Risk-free rate via FRED (optional) or fixed defaults (4% risk-free, 5% market risk premium)

## Valuation models
- DCF: 5-year explicit forecast + terminal value (Gordon growth), WACC estimation via CAPM
- Relative: peer median P/E (default 15 if no peers) times net income
- Final value = weighted blend (default 60% DCF / 40% Relative). Values are total company values, not per share.

## Checkpointing & resume
- Each run keeps `output/<TICKER>/state.json` with the current step, data file paths and notes (peers, benchmark, valuation).
- State is saved every `--save-every` seconds at step boundaries, at the end of a run, and on Ctrl+C / SIGTERM.

## Notes
- This project is for educational purposes; not investment advice.
- APIs used here have rate limits. Be respectful and cache results.

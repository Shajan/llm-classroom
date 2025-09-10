from __future__ import annotations
from typing import Dict
import yfinance as yf
import pandas as pd


SECTOR_TO_ETF = {
    # Common SPDR sector ETFs as benchmarks
    "Technology": "XLK",
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


def get_sector_benchmark(ticker: str) -> Dict[str, float | str]:
    t = yf.Ticker(ticker)
    info = t.info
    sector = info.get("sectorKey") or info.get("sector") or "Unknown"
    etf = SECTOR_TO_ETF.get(sector, "SPY")
    bench = yf.Ticker(etf)
    hist = bench.history(period="1y")
    ret_1y = 0.0
    if not hist.empty:
        ret_1y = float(hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1.0)
    return {"sector": sector, "benchmark_etf": etf, "sector_return_1y": ret_1y}

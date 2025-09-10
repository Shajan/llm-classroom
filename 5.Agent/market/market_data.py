from __future__ import annotations
from typing import Dict, List
import yfinance as yf
import pandas as pd


def get_market_cap(ticker: str) -> float:
    t = yf.Ticker(ticker)
    info = t.fast_info if hasattr(t, "fast_info") else t.info
    mc = info.get("market_cap") or info.get("marketCap")
    if mc is None:
        hist = t.history(period="1d")
        if not hist.empty:
            mc = float(hist["Close"].iloc[-1]) * float(info.get("sharesOutstanding", 1))
    return float(mc) if mc else 0.0


def get_peer_list(ticker: str) -> List[str]:
    # Minimal heuristic: use industry from yfinance and return top tickers from same industry
    t = yf.Ticker(ticker)
    info = t.info
    industry = info.get("industryKey") or info.get("industry")
    if not industry:
        return []
    # We can't query by industry list via yfinance directly; return some well-known large caps as placeholder peers
    # In real deployment, maintain a mapping of SIC/NAICS to peer tickers.
    guesses = {
        "Consumer Electronics": ["AAPL", "MSFT", "GOOGL", "AMZN"],
        "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO"],
    }
    return guesses.get(industry, [ticker])


def peer_multiples_from_peers(peers: List[str]) -> Dict[str, float]:
    pes = []
    for p in peers:
        try:
            t = yf.Ticker(p)
            info = t.fast_info if hasattr(t, "fast_info") else t.info
            pe = info.get("trailingPE") or info.get("trailingPe") or info.get("peTrailing")
            if pe and pe > 0:
                pes.append(float(pe))
        except Exception:
            continue
    out = {}
    if pes:
        out["PE"] = float(pd.Series(pes).median())
    return out

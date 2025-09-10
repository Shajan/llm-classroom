from __future__ import annotations
from typing import Dict
from fredapi import Fred
import os


def get_us_macro_indicators() -> Dict[str, float]:
    # Use FRED if API key is present; otherwise return defaults
    api_key = os.getenv("FRED_API_KEY")
    out = {}
    if api_key:
        fred = Fred(api_key=api_key)
        try:
            # 10-Year Treasury Constant Maturity Rate (DGS10) as risk-free proxy (annualized)
            dgs10 = fred.get_series_latest_release('DGS10').iloc[-1]
            out['rf_rate'] = float(dgs10) / 100.0
        except Exception:
            pass
        try:
            # Market risk premium proxy: equity premium model fallback, else 5%
            out['market_risk_premium'] = 0.05
        except Exception:
            out['market_risk_premium'] = 0.05
    else:
        out['rf_rate'] = 0.04  # fallback
        out['market_risk_premium'] = 0.05
    return out

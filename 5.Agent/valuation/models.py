from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
import pandas as pd


@dataclass
class ValuationResult:
    dcf_value: float
    relative_value: float
    blended_value: float
    details: Dict[str, Any]


def estimate_wacc(rf: float, beta: float, mkt_prem: float, debt_cost: float, tax_rate: float, debt: float, equity: float) -> float:
    v = debt + equity
    if v <= 0:
        return rf + beta * mkt_prem
    w_e = equity / v
    w_d = debt / v
    return w_e * (rf + beta * mkt_prem) + w_d * debt_cost * (1 - tax_rate)


def dcf_valuation(last_fcf: float, growth: float, years: int, wacc: float, terminal_growth: float) -> float:
    if years <= 0:
        return max(last_fcf, 0)
    fcf = last_fcf
    pv = 0.0
    for t in range(1, years + 1):
        fcf = fcf * (1 + growth)
        pv += fcf / ((1 + wacc) ** t)
    tv = (fcf * (1 + terminal_growth)) / (wacc - terminal_growth) if wacc > terminal_growth else 0.0
    pv += tv / ((1 + wacc) ** years)
    return float(pv)


def relative_valuation(metric: float, peer_median_multiple: float) -> float:
    return float(metric * peer_median_multiple)


def blend_values(dcf_value: float, relative_value: float, w_dcf: float = 0.6) -> float:
    return float(w_dcf * dcf_value + (1 - w_dcf) * relative_value)


def run_valuation(financials: pd.DataFrame, market_caps: Dict[str, float], target_ticker: str, peer_multiples: Dict[str, float], rf: float, mkt_prem: float, beta: float = 1.0) -> ValuationResult:
    # Derive inputs
    latest_year = financials.dropna(how='all').index.max()
    net_income = float(financials.loc[latest_year, "NetIncomeLoss"]) if "NetIncomeLoss" in financials.columns else np.nan
    dep = float(financials.loc[latest_year, "DepreciationDepletionAndAmortization"]) if "DepreciationDepletionAndAmortization" in financials.columns else 0.0
    capex = float(financials.loc[latest_year, "PaymentsToAcquirePropertyPlantAndEquipment"]) if "PaymentsToAcquirePropertyPlantAndEquipment" in financials.columns else 0.0
    operating_cf = float(financials.loc[latest_year, "NetCashProvidedByUsedInOperatingActivities"]) if "NetCashProvidedByUsedInOperatingActivities" in financials.columns else np.nan
    revenues = float(financials.loc[latest_year, "Revenues"]) if "Revenues" in financials.columns else np.nan
    assets = float(financials.loc[latest_year, "Assets"]) if "Assets" in financials.columns else np.nan
    debt = float(financials.loc[latest_year, "LongTermDebtNoncurrent"]) if "LongTermDebtNoncurrent" in financials.columns else 0.0

    # FCF proxy
    last_fcf = operating_cf - capex if not np.isnan(operating_cf) and not np.isnan(capex) else (net_income + dep - capex)

    # Growth assumptions from 3-year revenue CAGR if available
    years_sorted = sorted(financials.index.dropna())
    growth = 0.03
    if len(years_sorted) >= 4 and "Revenues" in financials.columns:
        try:
            r0 = float(financials.loc[years_sorted[-4], "Revenues"])  # 3 years back
            r1 = float(financials.loc[years_sorted[-1], "Revenues"])  # latest
            if r0 > 0 and r1 > 0:
                growth = (r1 / r0) ** (1 / 3) - 1
        except Exception:
            pass

    # WACC estimation
    equity = market_caps.get(target_ticker.upper(), max(assets - debt, 1.0))
    debt_cost = 0.05
    tax_rate = 0.21
    wacc = estimate_wacc(rf=rf, beta=beta, mkt_prem=mkt_prem, debt_cost=debt_cost, tax_rate=tax_rate, debt=debt, equity=equity)

    dcf_val = dcf_valuation(last_fcf=max(last_fcf, 0.0), growth=max(min(growth, 0.2), -0.1), years=5, wacc=max(wacc, 0.03), terminal_growth=0.02)

    # Relative valuation: use P/E peer median if available, fallback to EV/EBITDA placeholder
    pe = peer_multiples.get("PE", 15.0)
    rel_metric = net_income if net_income > 0 else last_fcf
    rel_val = relative_valuation(metric=max(rel_metric, 1.0), peer_median_multiple=pe)

    blended = blend_values(dcf_val, rel_val, w_dcf=0.6)
    return ValuationResult(
        dcf_value=dcf_val,
        relative_value=rel_val,
        blended_value=blended,
        details={
            "latest_year": latest_year,
            "growth_assumption": growth,
            "last_fcf": last_fcf,
            "wacc": wacc,
            "inputs": {
                "net_income": net_income,
                "operating_cf": operating_cf,
                "capex": capex,
                "revenues": revenues,
                "assets": assets,
                "debt": debt,
                "equity": equity,
            },
        },
    )

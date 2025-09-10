from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd


@dataclass
class FinancialStatements:
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame


def _extract_series(facts: Dict[str, Any], tag: str, measure: str = "USD") -> pd.Series:
    series = []
    if tag in facts.get("facts", {}).get("us-gaap", {}):
        for item in facts["facts"]["us-gaap"][tag].get("units", {}).get(measure, []):
            if "fy" in item and "val" in item and "end" in item:
                series.append((item["fy"], item["val"]))
    if not series:
        return pd.Series(dtype=float)
    df = pd.DataFrame(series, columns=["fy", tag]).dropna().drop_duplicates("fy").set_index("fy").sort_index()
    return df[tag]


def build_financials_from_company_facts(facts: Dict[str, Any]) -> FinancialStatements:
    # Extract a subset of common tags
    tags_income = [
        "Revenues",
        "CostOfRevenue",
        "GrossProfit",
        "OperatingExpenses",
        "OperatingIncomeLoss",
        "NetIncomeLoss",
    ]
    tags_balance = [
        "Assets",
        "Liabilities",
        "StockholdersEquity",
        "CashAndCashEquivalentsAtCarryingValue",
        "LongTermDebtNoncurrent",
    ]
    tags_cash = [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInFinancingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "DepreciationDepletionAndAmortization",
    ]

    income = pd.DataFrame({t: _extract_series(facts, t) for t in tags_income})
    balance = pd.DataFrame({t: _extract_series(facts, t) for t in tags_balance})
    cashflow = pd.DataFrame({t: _extract_series(facts, t) for t in tags_cash})

    return FinancialStatements(income=income, balance=balance, cashflow=cashflow)


def compute_key_ratios(fin: FinancialStatements) -> pd.DataFrame:
    df = pd.DataFrame(index=fin.income.index.union(fin.balance.index).sort_values())
    # Merge
    for part in [fin.income, fin.balance, fin.cashflow]:
        for col in part.columns:
            df[col] = part[col]
    # Ratios
    df["GrossMargin"] = df["GrossProfit"] / df["Revenues"]
    df["OperatingMargin"] = df["OperatingIncomeLoss"] / df["Revenues"]
    df["NetMargin"] = df["NetIncomeLoss"] / df["Revenues"]
    df["Leverage"] = df["Liabilities"] / df["StockholdersEquity"]
    df["ROA"] = df["NetIncomeLoss"] / df["Assets"]
    df["DebtToAssets"] = df["LongTermDebtNoncurrent"] / df["Assets"]
    return df

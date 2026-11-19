"""
A long-running agent that can resume after it is stopped.

This is the 2.2 agent (create_agent + @tool) with one new idea: a checkpointer.
After every step (a model call or a tool run) the agent's state is saved to
checkpoints.db. If the run is stopped (Ctrl+C, crash, closed laptop), running
the script again continues from the last saved step instead of starting over.

Usage: python 5.Agent/research_agent.py [TICKER]
Educational only; not investment advice.
"""
import os
import sys
from datetime import date

import requests
import yfinance as yf
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver

HERE = os.path.dirname(os.path.abspath(__file__))
SEC_HEADERS = {"User-Agent": "llm-classroom example admin@example.com"}  # the SEC requires a User-Agent
SEC_TAGS = {  # our name -> SEC XBRL tags (companies use different tags for the same number)
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_spending": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}


def annual_values(facts, tag):
    """Full-year values of one tag from 10-K filings, as {fiscal year end: value}."""
    rows = facts["facts"]["us-gaap"].get(tag, {}).get("units", {}).get("USD", [])
    # A 10-K also contains quarterly numbers; keep only values that cover a full year.
    return {r["end"][:4]: r["val"] for r in rows if r["form"] == "10-K" and "start" in r
            and (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days > 350}


@tool
def get_financials(ticker: str) -> dict:
    """Get the latest annual revenue, net income, operating cash flow and capital spending (USD) from the company's SEC 10-K filings."""
    print(f"Tool: get_financials({ticker})")
    companies = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=30).json()
    cik = next((c["cik_str"] for c in companies.values() if c["ticker"] == ticker.upper()), None)
    if cik is None:
        return {"error": f"Unknown ticker {ticker}"}
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    facts = requests.get(url, headers=SEC_HEADERS, timeout=30).json()
    result = {}
    for name, tags in SEC_TAGS.items():
        # If several tags have data, use the one with the most recent year.
        values = max((annual_values(facts, tag) for tag in tags), key=lambda v: max(v, default=""))
        latest = max(values, default=None)
        result[name] = {"year": latest, "usd": values.get(latest)}
    return result


@tool
def get_market_data(ticker: str) -> dict:
    """Get the current share price, market cap, shares outstanding, trailing P/E and sector from Yahoo Finance."""
    print(f"Tool: get_market_data({ticker})")
    info = yf.Ticker(ticker).info
    return {key: info.get(key) for key in ["currentPrice", "marketCap", "sharesOutstanding", "trailingPE", "sector"]}


def main():
    load_dotenv(os.path.join(HERE, "..", ".env"))
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    question = (f"Research {ticker}. Estimate a fair value per share as: latest free cash flow "
                "(operating cash flow minus capital spending) x 25 / shares outstanding. "
                "Show the numbers you used and compare with the current price. Keep it short.")

    # Each ticker gets its own saved run, found by thread_id.
    config = {"configurable": {"thread_id": ticker}}

    with SqliteSaver.from_conn_string(os.path.join(HERE, "checkpoints.db")) as checkpointer:
        agent = create_agent(
            model="openai:gpt-4o-mini",
            tools=[get_financials, get_market_data],
            # Safety check, same as 2.2: without it, a model that keeps calling
            # tools keeps resending the whole conversation (more tokens, more cost).
            middleware=[ToolCallLimitMiddleware(run_limit=4, exit_behavior="end")],
            checkpointer=checkpointer,  # the new part: save state after every step
        )

        if agent.get_state(config).tasks:
            # The saved run still has steps to do: it was stopped part way.
            # Passing None (no new message) continues from the last saved step.
            print(f"Resuming the stopped run for {ticker}")
            request = None
        else:
            checkpointer.delete_thread(ticker)  # the last run finished (or none): start fresh
            print(f"Researching {ticker}")
            request = {"messages": [{"role": "user", "content": question}]}

        try:
            result = agent.invoke(request, config)
            print(f"\nAnswer: {result['messages'][-1].content}")
        except KeyboardInterrupt:
            print("\nStopped. Run the same command again to resume.")


if __name__ == "__main__":
    main()

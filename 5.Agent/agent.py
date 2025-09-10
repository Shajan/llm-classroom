from __future__ import annotations
import argparse
from pathlib import Path
import json
from typing import Dict
import time
import signal
import pandas as pd

from agent_core.state import Checkpointer
from fetchers.sec import get_company_submissions, get_company_facts
from processing.financials import build_financials_from_company_facts, compute_key_ratios
from market.market_data import get_market_cap, get_peer_list, peer_multiples_from_peers
from market.industry import get_sector_benchmark
from macro.us_macro import get_us_macro_indicators
from valuation.models import run_valuation


def write_markdown_report(base_dir: Path, ticker: str, ratios_df, valuation_result) -> None:
    out_dir = base_dir / "output" / ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    report_fp = out_dir / "valuation_report.md"
    lines = []
    lines.append(f"# Valuation Report — {ticker}\n")
    lines.append("## Key Ratios\n")
    # Avoid optional tabulate dependency; use to_string for markdown code block
    ratios_txt = ratios_df.tail(5).to_string()
    lines.append("```\n" + str(ratios_txt) + "\n```")
    lines.append("\n## Valuation\n")
    lines.append(json.dumps(valuation_result.__dict__, indent=2))
    report_fp.write_text("\n\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Equity Research Agent")
    parser.add_argument("--ticker", required=True, help="US stock ticker (e.g., AAPL)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--save-every", type=int, default=120, help="Checkpoint frequency in seconds")
    parser.add_argument("--loop-interval", type=int, default=0, help="If >0, run continuously with this sleep interval (seconds) between refreshes")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    ticker = args.ticker.upper()

    cp = Checkpointer(base_dir=base_dir, ticker=ticker, save_every_seconds=getattr(args, "save_every", 120))
    state = cp.maybe_load(resume=args.resume)

    stop_flag = {"stop": False}

    def _graceful_stop(signum, frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _graceful_stop)
    signal.signal(signal.SIGTERM, _graceful_stop)

    def run_once():
        nonlocal state
        print(f"[agent] Start run for {ticker}")
        # Step 1: Fetch SEC data
        state.step = "fetch_sec"
        cp.touch()
        subs = get_company_submissions(base_dir, ticker)
        cik = str(subs.get("cik", "")).zfill(10)
        facts = get_company_facts(base_dir, cik)
        state.data_paths["company_submissions"] = str((base_dir/"data"/ticker/"submissions.json").resolve())
        state.data_paths["company_facts"] = str((base_dir/"data"/cik/"company_facts.json").resolve())
        cp.touch()

        # Step 2: Build financials and ratios
        state.step = "process_financials"
        fin = build_financials_from_company_facts(facts)
        ratios = compute_key_ratios(fin)
        ratios_fp = base_dir / "output" / ticker / "ratios.csv"
        ratios_fp.parent.mkdir(parents=True, exist_ok=True)
        ratios.to_csv(ratios_fp)
        state.data_paths["ratios"] = str(ratios_fp.resolve())
        cp.touch()

        # Step 3: Market and peers
        state.step = "market_peers"
        mc = get_market_cap(ticker)
        peers = get_peer_list(ticker)
        peer_mults = peer_multiples_from_peers(peers)
        sector_bench = get_sector_benchmark(ticker)
        market_caps: Dict[str, float] = {ticker: mc}
        state.notes["peers"] = peers
        state.notes["sector_benchmark"] = sector_bench
        cp.touch()

        # Step 4: Macro
        state.step = "macro"
        macro = get_us_macro_indicators()
        rf = float(macro.get("rf_rate", 0.04))
        mkt_prem = float(macro.get("market_risk_premium", 0.05))
        cp.touch()

        # Step 5: Valuation
        state.step = "valuation"
        valuation = run_valuation(
            financials=ratios,
            market_caps=market_caps,
            target_ticker=ticker,
            peer_multiples=peer_mults,
            rf=rf,
            mkt_prem=mkt_prem,
        )
        state.notes["valuation"] = valuation.__dict__
        cp.touch()

        # Step 6: Report
        state.step = "report"
        write_markdown_report(base_dir, ticker, ratios, valuation)
        cp.save_now()
        print(f"[agent] Done. Report: {base_dir / 'output' / ticker / 'valuation_report.md'}")

    # Run once or in a loop
    try:
        if args.loop_interval and args.loop_interval > 0:
            while not stop_flag["stop"]:
                run_once()
                if stop_flag["stop"]:
                    break
                time.sleep(args.loop_interval)
        else:
            run_once()
    finally:
        cp.save_now()


if __name__ == "__main__":
    main()

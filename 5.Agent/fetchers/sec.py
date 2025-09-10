import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import json
import requests
import backoff

SEC_BASE = "https://data.sec.gov"
HEADERS = {
    "User-Agent": f"EquityAgent/1.0 (email: {os.getenv('SEC_API_EMAIL','email@example.com')})"
}


def cache_path(base_dir: Path, ticker: str, name: str) -> Path:
    p = base_dir / "data" / ticker.upper() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@backoff.on_exception(backoff.expo, (requests.RequestException,), max_tries=5)
def _get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    time.sleep(0.2)  # be gentle
    return resp


def _company_tickers_index(base_dir: Path, force: bool = False) -> Dict[str, Any]:
    fp = base_dir / "data" / "company_tickers.json"
    if fp.exists() and not force:
        return json.loads(fp.read_text())
    url = f"{SEC_BASE}/files/company_tickers.json"
    r = _get(url)
    data = r.json()
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(data))
    return data


def _resolve_cik_from_ticker(base_dir: Path, ticker: str) -> str:
    idx = _company_tickers_index(base_dir)
    # The JSON is a dict with integer keys; values have 'ticker' and 'cik_str'
    for _, v in idx.items():
        if str(v.get("ticker", "")).upper() == ticker.upper():
            return str(v.get("cik_str")).zfill(10)
    raise RuntimeError(f"Unable to resolve CIK for ticker {ticker}")


def get_company_submissions(base_dir: Path, cik_or_ticker: str, use_cache: bool = True) -> Dict[str, Any]:
    ticker_or_cik = cik_or_ticker.strip()
    if ticker_or_cik.isdigit():
        cik = str(ticker_or_cik).zfill(10)
        ticker = cik
    else:
        ticker = ticker_or_cik.upper()
        cik = _resolve_cik_from_ticker(base_dir, ticker)

    ticker_map_fp = cache_path(base_dir, ticker, "submissions.json")
    if use_cache and ticker_map_fp.exists():
        return json.loads(ticker_map_fp.read_text())

    subm_url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    r = _get(subm_url)
    subs = r.json()
    ticker_map_fp.write_text(json.dumps(subs, indent=2))
    return subs


def get_company_facts(base_dir: Path, cik: str, use_cache: bool = True) -> Dict[str, Any]:
    fp = cache_path(base_dir, cik, "company_facts.json")
    if use_cache and fp.exists():
        import json
        return json.loads(fp.read_text())
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json"
    r = _get(url)
    data = r.json()
    import json
    fp.write_text(json.dumps(data, indent=2))
    return data

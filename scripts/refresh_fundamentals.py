#!/usr/bin/env python3
"""Refresh the bundled fundamentals seed file.

Run: .venv/bin/python scripts/refresh_fundamentals.py
"""
import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quantcontext.engine.data import fetch_sp500_tickers, fetch_nasdaq100_tickers, fetch_financials

SEED_PATH = Path(__file__).parent.parent / "src" / "quantcontext" / "data" / "fundamentals_seed.json"
MAX_WORKERS = 20


def _fetch_one(ticker: str) -> tuple[str, dict | None]:
    try:
        return ticker, fetch_financials(ticker)
    except Exception as e:
        print(f"  SKIP {ticker}: {e}")
        return ticker, None


def main():
    sp500 = fetch_sp500_tickers()
    nasdaq100 = fetch_nasdaq100_tickers()
    all_tickers = sorted(set(sp500 + nasdaq100))

    print(f"Fetching fundamentals for {len(all_tickers)} tickers ({MAX_WORKERS} workers)...")

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in all_tickers}
        done = 0
        for future in as_completed(futures):
            ticker, data = future.result()
            done += 1
            if data is not None:
                results[ticker] = data
            if done % 50 == 0:
                print(f"  {done}/{len(all_tickers)} done...")

    seed = {
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "count": len(results),
        "tickers": results,
    }

    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_PATH, "w") as f:
        json.dump(seed, f, indent=2)

    print(f"Wrote {len(results)} tickers to {SEED_PATH}")


if __name__ == "__main__":
    main()

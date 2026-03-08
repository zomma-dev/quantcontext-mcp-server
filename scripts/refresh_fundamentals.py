#!/usr/bin/env python3
"""Refresh all bundled seed data (fundamentals, ticker lists, Fama-French factors).

Run: .venv/bin/python scripts/refresh_fundamentals.py

Generates:
  src/quantcontext/data/fundamentals_seed.json
  src/quantcontext/data/sp500_tickers.json
  src/quantcontext/data/nasdaq100_tickers.json
  src/quantcontext/data/ff_factors.csv
"""
import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quantcontext.engine.data import (
    fetch_sp500_tickers,
    fetch_nasdaq100_tickers,
    fetch_financials,
    _download_french_factors,
)

SEED_DIR = Path(__file__).parent.parent / "src" / "quantcontext" / "data"
MAX_WORKERS = 20


def _fetch_one(ticker: str) -> tuple[str, dict | None]:
    try:
        return ticker, fetch_financials(ticker)
    except Exception as e:
        print(f"  SKIP {ticker}: {e}")
        return ticker, None


def refresh_tickers() -> tuple[list[str], list[str]]:
    """Refresh S&P 500 and Nasdaq 100 ticker lists."""
    now = datetime.now().strftime("%Y-%m-%d")

    print("Fetching S&P 500 tickers from Wikipedia...")
    sp500 = fetch_sp500_tickers()
    sp500_seed = {"generated": now, "count": len(sp500), "tickers": sp500}
    sp500_path = SEED_DIR / "sp500_tickers.json"
    with open(sp500_path, "w") as f:
        json.dump(sp500_seed, f, indent=2)
    print(f"  Wrote {len(sp500)} tickers to {sp500_path}")

    print("Fetching Nasdaq 100 tickers from Wikipedia...")
    nasdaq100 = fetch_nasdaq100_tickers()
    nasdaq100_seed = {"generated": now, "count": len(nasdaq100), "tickers": nasdaq100}
    nasdaq100_path = SEED_DIR / "nasdaq100_tickers.json"
    with open(nasdaq100_path, "w") as f:
        json.dump(nasdaq100_seed, f, indent=2)
    print(f"  Wrote {len(nasdaq100)} tickers to {nasdaq100_path}")

    return sp500, nasdaq100


def refresh_factors():
    """Refresh Fama-French factor data."""
    print("Downloading Fama-French factors from Ken French's site...")
    df = _download_french_factors()
    factors_path = SEED_DIR / "ff_factors.csv"
    # Include generation date as a comment in the first line
    with open(factors_path, "w") as f:
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d')}\n")
        df.to_csv(f)
    print(f"  Wrote {len(df)} rows to {factors_path}")


def refresh_fundamentals(sp500: list[str], nasdaq100: list[str]):
    """Refresh fundamentals seed using parallel yfinance fetch."""
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

    seed_path = SEED_DIR / "fundamentals_seed.json"
    with open(seed_path, "w") as f:
        json.dump(seed, f, indent=2)
    print(f"  Wrote {len(results)} tickers to {seed_path}")


def main():
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Seed directory: {SEED_DIR}\n")

    sp500, nasdaq100 = refresh_tickers()
    refresh_factors()
    refresh_fundamentals(sp500, nasdaq100)

    print("\nAll seed data refreshed.")


if __name__ == "__main__":
    main()

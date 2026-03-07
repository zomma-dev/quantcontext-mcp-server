"""Generate seed cache files for hosting.

Run this script to produce the cache files you'll host at MARKET_DATA_BASE_URL.
Users can then run `quantcontext-warmup --url <your-url>` for a fast cold start.

Usage:
    python scripts/generate_seed_cache.py

Output files written to ~/.cache/quantcontext/:
    sp500_tickers.json       — S&P 500 constituent list
    nasdaq100_tickers.json   — Nasdaq-100 constituent list
    ff_factors.parquet       — Fama-French daily factors (3 years)
    prices.parquet           — Daily close prices for all tickers (3 years)

Host these files at a static URL (GitHub Releases, S3, Cloudflare R2, etc.)
and set MARKET_DATA_BASE_URL to that base path.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantcontext.engine.data import (
    CACHE_DIR,
    FACTORS_CACHE_PATH,
    PRICES_CACHE_PATH,
    fetch_nasdaq100_tickers,
    fetch_sp500_tickers,
    get_factors,
    _download_prices,
    _write_cached_prices,
)

END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
CHUNK_SIZE = 50   # tickers per yfinance batch
CHUNK_DELAY = 2   # seconds between chunks to avoid rate limiting


def _fetch_prices_chunked(tickers: list[str], start: str, end: str):
    import pandas as pd

    all_frames = []
    chunks = [tickers[i:i + CHUNK_SIZE] for i in range(0, len(tickers), CHUNK_SIZE)]
    for i, chunk in enumerate(chunks):
        print(f"    chunk {i + 1}/{len(chunks)}: {chunk[0]} … {chunk[-1]}", end="", flush=True)
        try:
            frame = _download_prices(chunk, start, end)
            all_frames.append(frame)
            print(f" ({len(frame)} days)")
        except Exception as exc:
            print(f" FAILED: {exc}")
        if i < len(chunks) - 1:
            time.sleep(CHUNK_DELAY)

    if not all_frames:
        raise RuntimeError("No price data fetched")

    merged = all_frames[0]
    for frame in all_frames[1:]:
        merged = merged.combine_first(frame)
    return merged


def main() -> None:
    print(f"QuantContext seed cache generator")
    print(f"Period : {START_DATE} → {END_DATE}")
    print(f"Output : {CACHE_DIR}\n")

    # 1. Ticker lists
    print("1/4  Fetching S&P 500 constituents...")
    sp500 = fetch_sp500_tickers()
    print(f"     {len(sp500)} tickers\n")

    print("2/4  Fetching Nasdaq-100 constituents...")
    nasdaq = fetch_nasdaq100_tickers()
    print(f"     {len(nasdaq)} tickers\n")

    # 2. Fama-French factors
    print("3/4  Fetching Fama-French factors...")
    factors = get_factors(START_DATE, END_DATE)
    factors.to_parquet(FACTORS_CACHE_PATH)
    print(f"     {len(factors)} trading days → {FACTORS_CACHE_PATH}\n")

    # 3. Prices — chunked to avoid rate limiting
    all_tickers = sorted(set(sp500 + nasdaq))
    print(f"4/4  Fetching prices for {len(all_tickers)} tickers in chunks of {CHUNK_SIZE}...")
    prices = _fetch_prices_chunked(all_tickers, START_DATE, END_DATE)
    _write_cached_prices(prices)
    size_mb = PRICES_CACHE_PATH.stat().st_size / 1_000_000 if PRICES_CACHE_PATH.exists() else 0
    print(f"\n     {len(prices)} days x {len(prices.columns)} tickers ({size_mb:.1f} MB) → {PRICES_CACHE_PATH}")

    print(f"\nDone. Upload the files in {CACHE_DIR} to your static host.")
    print("Then users can run: quantcontext-warmup --url <your-base-url>")


if __name__ == "__main__":
    main()

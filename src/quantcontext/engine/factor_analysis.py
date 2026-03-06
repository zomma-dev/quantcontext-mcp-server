"""Fama-French factor regression for backtest returns.

Decomposes strategy returns into factor exposures (market, size, value, momentum)
and estimates alpha with statistical significance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantcontext.engine.data import get_factors


def run_factor_regression(equity_curve: list[dict]) -> dict | None:
    """Run 4-factor regression on backtest returns.

    Args:
        equity_curve: list of {date, value} dicts from backtest

    Returns:
        {alpha_daily, alpha_annualized, alpha_tstat, factors, r_squared, residual_vol}
        or dict with "error" key if insufficient data.
    """
    if len(equity_curve) < 30:
        return {"error": "Insufficient data for factor regression (need 30+ days)"}

    df = pd.DataFrame(equity_curve)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["return"] = df["value"].pct_change()
    df = df.dropna()

    if len(df) < 30:
        return {"error": "Insufficient return data for factor regression"}

    start = df.index[0].strftime("%Y-%m-%d")
    end = df.index[-1].strftime("%Y-%m-%d")

    try:
        factors = get_factors(start, end)
    except Exception as e:
        return {"error": f"Could not load factor data: {e}"}

    merged = df[["return"]].join(factors, how="inner")
    merged = merged.dropna()

    if len(merged) < 30:
        return {"error": "Insufficient overlapping data between returns and factors"}

    y = merged["return"].values - merged["RF"].values

    factor_names = ["Mkt-RF", "SMB", "HML", "Mom"]
    available_factors = [f for f in factor_names if f in merged.columns]
    X = merged[available_factors].values

    X_with_const = np.column_stack([np.ones(len(X)), X])

    try:
        XtX = X_with_const.T @ X_with_const
        Xty = X_with_const.T @ y
        betas = np.linalg.solve(XtX, Xty)

        y_hat = X_with_const @ betas
        residuals = y - y_hat
        n, k = X_with_const.shape
        sigma2 = (residuals @ residuals) / (n - k)
        var_betas = sigma2 * np.linalg.inv(XtX)
        se_betas = np.sqrt(np.diag(var_betas))

        t_stats = betas / se_betas

        ss_res = residuals @ residuals
        ss_tot = (y - y.mean()) @ (y - y.mean())
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        alpha_daily = float(betas[0])
        alpha_annualized = float((1 + alpha_daily) ** 252 - 1)

        result = {
            "alpha_daily": round(alpha_daily, 6),
            "alpha_annualized": round(alpha_annualized, 4),
            "alpha_tstat": round(float(t_stats[0]), 2),
            "factors": {},
            "r_squared": round(float(r_squared), 4),
            "residual_vol": round(float(np.sqrt(sigma2) * np.sqrt(252)), 4),
        }

        for i, factor_name in enumerate(available_factors):
            result["factors"][factor_name] = {
                "loading": round(float(betas[i + 1]), 4),
                "tstat": round(float(t_stats[i + 1]), 2),
            }

        return result

    except np.linalg.LinAlgError:
        return {"error": "Singular matrix in factor regression"}

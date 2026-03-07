"""QuantContext MCP Server — deterministic quant tools for AI trading agents.

Provides stock screening, backtesting, and factor analysis tools via MCP.
Every number is computed, not generated. Same input always produces same output.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from typing import Annotated

from pydantic import Field
from mcp.server.fastmcp import FastMCP, Context

# ── Engine imports ──
from quantcontext.engine.pipeline_executor import execute_pipeline
from quantcontext.engine.backtest_engine import run_backtest
from quantcontext.engine.factor_analysis import run_factor_regression
from quantcontext.engine.skills.pipeline_skills.registry import SKILL_REGISTRY
from quantcontext.engine.data import get_and_clear_warnings

# ── Server ──

mcp = FastMCP(
    name="quantcontext_mcp",
    instructions=(
        "QuantContext provides deterministic quantitative trading tools: stock screening, "
        "backtesting, and Fama-French factor analysis. Tools compose naturally: "
        "screen_stocks → backtest_strategy → factor_analysis.\n\n"

        "WHEN TO ASK VS PROCEED:\n"
        "- If the user specifies a strategy (e.g. 'value stocks', 'momentum', 'low PE'), "
        "proceed directly — map their intent to the closest screen_type and config.\n"
        "- If the request is completely open-ended (e.g. 'screen some stocks', 'run a backtest'), "
        "ask ONE clarifying question: what kind of stocks or strategy they have in mind. "
        "Do not ask multiple questions at once.\n"
        "- For backtests, if no time period is mentioned, default to the last 2 years. "
        "If no rebalance frequency is mentioned, default to monthly.\n\n"

        "MAPPING USER INTENT TO TOOLS:\n"
        "- 'value', 'cheap', 'low PE' → fundamental_screen or value_screen\n"
        "- 'momentum', 'trending', 'winners' → momentum_screen\n"
        "- 'quality', 'profitable', 'strong balance sheet' → quality_screen\n"
        "- 'oversold', 'mean reversion', 'bounce' → mean_reversion\n"
        "- 'technical', 'RSI', 'moving average' → technical_signal\n"
        "- 'multi-factor', 'blend' → factor_model\n\n"

        "SENSIBLE DEFAULTS (use when not specified):\n"
        "- universe: sp500\n"
        "- rebalance: monthly\n"
        "- sizing: equal_weight\n"
        "- backtest period: 2 years ending today\n"
        "- initial capital: $100,000\n"
        "- momentum lookback: 200 days, top 20%\n"
        "- value screen: pe_lt=20\n"
        "- fundamental screen: pe_lt=15, roe_gt=0.10\n\n"

        "BEFORE RUNNING ANY TOOL, always state:\n"
        "1. The exact strategy in plain English (e.g. 'Screening S&P 500 for stocks with PE < 15 and ROE > 12%').\n"
        "2. Every parameter being used, including defaults that were not explicitly specified "
        "(e.g. 'universe: sp500 (default), rebalance: monthly (default), lookback: 200 days (default)').\n"
        "3. The exact tool call you are about to make, formatted as a JSON code block.\n"
        "Only call the tool after presenting this summary. "
        "This lets the user confirm or correct the strategy before computation runs."
    ),
)

# ── Valid universes ──

VALID_UNIVERSES = {"sp500", "russell2000", "nasdaq100"}

CHARACTER_LIMIT = 25000  # Maximum response size in characters


def _truncate_response(response_str: str) -> str:
    """Truncate response if it exceeds CHARACTER_LIMIT."""
    if len(response_str) <= CHARACTER_LIMIT:
        return response_str
    try:
        data = json.loads(response_str)
        data["truncated"] = True
        data["truncation_message"] = (
            f"Response truncated from {len(response_str)} characters to fit within "
            f"{CHARACTER_LIMIT} character limit. Use filters or pagination to reduce results."
        )
        # Aggressively trim all list fields (top-level and nested in trades)
        for key in ("results", "equity_curve"):
            if key in data and isinstance(data[key], list) and len(data[key]) > 5:
                data[key] = data[key][:5]
        if "trades" in data and isinstance(data["trades"], dict):
            if "recent_trades" in data["trades"] and isinstance(data["trades"]["recent_trades"], list):
                data["trades"]["recent_trades"] = data["trades"]["recent_trades"][:5]
        result = json.dumps(data)
        if len(result) <= CHARACTER_LIMIT:
            return result
        # Still too large — strip all list fields entirely
        data = {k: v for k, v in data.items() if not isinstance(v, list)}
        data["truncated"] = True
        data["truncation_message"] = "Response too large; list data removed. Use filters to reduce results."
        return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Response too large to serialize", "truncated": True})


def _validate_universe(universe: str) -> str | None:
    """Return a JSON error string if universe is invalid, else None."""
    if universe not in VALID_UNIVERSES:
        valid = ", ".join(sorted(VALID_UNIVERSES))
        return json.dumps({
            "error": f"Invalid universe: '{universe}'. Valid options: {valid}",
            "code": "INVALID_UNIVERSE",
        })
    return None


# ── Tool 1: Screen Stocks ──

SCREEN_TYPES = list(SKILL_REGISTRY.keys())

SCREEN_CONFIG_HELP = {
    "fundamental_screen": "pe_lt, roe_gt, debt_equity_lt, revenue_growth_gt (all optional floats)",
    "quality_screen": "roe_gt, debt_equity_lt, profit_margin_gt (all optional floats)",
    "momentum_screen": "lookback_days (int, default 200), top_pct (float 0-1, default 0.2)",
    "value_screen": "pe_lt (float), top_n (int, default 30)",
    "factor_model": "weights dict with value/momentum/quality/volatility (floats summing to 1), top_n (int)",
    "technical_signal": "rsi_period (int), sma_short (int), sma_long (int)",
    "mean_reversion": "lookback_days (int), z_threshold (float, default -1.5)",
}


@mcp.tool(
    name="screen_stocks",
    annotations={
        "title": "Screen Stocks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def screen_stocks(
    universe: Annotated[str, Field(
        description="Stock universe to screen. Options: sp500, russell2000, nasdaq100"
    )] = "sp500",
    screen_type: Annotated[str, Field(
        description=(
            "Type of screen to run. Options: fundamental_screen (filter by PE/ROE/debt), "
            "quality_screen (filter by ROE/margins), momentum_screen (rank by price momentum), "
            "value_screen (rank by valuation), factor_model (multi-factor ranking), "
            "technical_signal (RSI/SMA/Bollinger), mean_reversion (z-score below threshold)"
        ),
    )] = "fundamental_screen",
    config: Annotated[dict | None, Field(
        description=(
            "Screen-specific configuration. Examples: "
            "fundamental_screen: {pe_lt: 15, roe_gt: 12}. "
            "momentum_screen: {lookback_days: 200, top_pct: 0.2}. "
            "value_screen: {pe_lt: 20, top_n: 30}. "
            "factor_model: {weights: {value: 0.3, momentum: 0.3, quality: 0.2, volatility: 0.2}, top_n: 20}. "
            "mean_reversion: {lookback_days: 60, z_threshold: -1.5}. "
            "All parameters are optional — sensible defaults are used."
        ),
    )] = None,
    date: Annotated[str | None, Field(
        description="Date for the screen in YYYY-MM-DD format. Defaults to most recent trading day."
    )] = None,
    ctx: Context | None = None,
) -> str:
    """Screen a stock universe with quantitative filters. Returns ranked candidates with scores and metrics.

    Use this tool when you need to find stocks matching specific criteria — value stocks,
    momentum leaders, quality companies, or multi-factor ranked candidates. Supports 7 screen
    types across 3 universes (S&P 500, Russell 2000, Nasdaq 100).

    After screening, use backtest_strategy to test the screen as a trading strategy,
    or factor_analysis to understand the factor exposures of the selected stocks.
    """
    import pandas as pd

    # Input validation: universe
    if err := _validate_universe(universe):
        return err

    if screen_type not in SKILL_REGISTRY:
        available = ", ".join(SKILL_REGISTRY.keys())
        return json.dumps({
            "error": f"Unknown screen_type: '{screen_type}'. Available: {available}",
            "code": "INVALID_SCREEN_TYPE",
            "help": {k: v for k, v in SCREEN_CONFIG_HELP.items()},
        })

    screen_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
    screen_config = config or {}

    try:
        if ctx is not None:
            await ctx.report_progress(0, 2)
            await ctx.info(f"Screening {universe} with {screen_type} on {screen_date}…")

        pipeline = {
            "universe": universe,
            "stages": [
                {"order": 1, "type": "screen", "skill": screen_type, "config": screen_config},
            ],
        }
        results, candidates = await asyncio.to_thread(execute_pipeline, pipeline, screen_date)

        if ctx is not None:
            await ctx.report_progress(1, 2)
            await ctx.info(f"Pipeline complete — {len(candidates)} candidates found. Formatting results…")

        if candidates.empty:
            if ctx is not None:
                await ctx.report_progress(2, 2)
            return json.dumps({
                "screen_type": screen_type,
                "universe": universe,
                "date": screen_date,
                "count": 0,
                "results": [],
                "message": "No stocks passed the screen criteria. Try relaxing your filters.",
            })

        # Convert to records, limit to top 30
        output = candidates.head(30)
        records = output.to_dict("records")
        # Clean NaN values for JSON serialization
        clean_records = []
        for r in records:
            clean_records.append({k: (None if pd.isna(v) else v) for k, v in r.items()})

        stage_info = results[0] if results else {}

        if ctx is not None:
            await ctx.report_progress(2, 2)

        data_warnings = get_and_clear_warnings()
        response: dict = {
            "screen_type": screen_type,
            "universe": universe,
            "date": screen_date,
            "config": screen_config,
            "universe_size": stage_info.get("input_count", 0),
            "count": len(candidates),
            "showing": len(clean_records),
            "results": clean_records,
        }
        if data_warnings:
            response["warnings"] = data_warnings
        return _truncate_response(json.dumps(response))

    except Exception as e:
        get_and_clear_warnings()  # flush so next call starts clean
        return json.dumps({
            "error": str(e),
            "code": "SCREEN_ERROR",
            "screen_type": screen_type,
            "universe": universe,
        })


# ── Tool 2: Backtest Strategy ──

@mcp.tool(
    name="backtest_strategy",
    annotations={
        "title": "Backtest Strategy",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def backtest_strategy(
    stages: Annotated[list[dict], Field(
        description=(
            "Pipeline stages defining the strategy. Each stage is an object with: "
            "order (int), type ('screen'|'analyze'|'signal'), skill (skill name), config (dict). "
            "Example: [{order: 1, type: 'screen', skill: 'fundamental_screen', config: {pe_lt: 15}}, "
            "{order: 2, type: 'signal', skill: 'momentum_screen', config: {lookback_days: 200, top_pct: 0.3}}]"
        ),
    )],
    universe: Annotated[str, Field(
        description="Stock universe. Options: sp500, russell2000, nasdaq100"
    )] = "sp500",
    rebalance: Annotated[str, Field(
        description="Rebalance frequency. Options: daily, weekly, monthly, quarterly"
    )] = "monthly",
    sizing: Annotated[str, Field(
        description="Position sizing method. Options: equal_weight, inverse_volatility"
    )] = "equal_weight",
    start_date: Annotated[str, Field(
        description="Backtest start date in YYYY-MM-DD format"
    )] = "2023-01-01",
    end_date: Annotated[str | None, Field(
        description="Backtest end date in YYYY-MM-DD format. Defaults to today."
    )] = None,
    max_position_size: Annotated[float | None, Field(
        description="Maximum weight per position (0-1). E.g., 0.1 = 10% max per stock"
    )] = None,
    stop_loss: Annotated[float | None, Field(
        description="Per-position stop loss (0-1). E.g., 0.15 = sell if position drops 15%"
    )] = None,
    max_drawdown: Annotated[float | None, Field(
        description="Maximum portfolio drawdown before going to cash (0-1). E.g., 0.2 = 20%"
    )] = None,
    ctx: Context | None = None,
) -> str:
    """Run a historical backtest on a stock screening strategy. Uses a rebalance-loop engine
    that re-runs the screening pipeline on each rebalance date, sizes positions, enforces risk
    limits, and tracks daily P&L.

    Returns equity curve, trade log, and performance metrics including CAGR, Sharpe ratio,
    maximum drawdown, Calmar ratio, win rate, and turnover.

    The backtest is fully deterministic — same inputs always produce identical results.

    After backtesting, use factor_analysis on the equity_curve to decompose returns into
    Fama-French factors (market, size, value, momentum) and estimate true alpha.
    """
    import pandas as pd

    # Input validation: universe
    if err := _validate_universe(universe):
        return err

    if end_date is None:
        end_date = datetime.date.today().strftime("%Y-%m-%d")

    if ctx is not None:
        await ctx.report_progress(0, 3)
        await ctx.info(f"Setting up backtest pipeline for {universe} ({start_date} to {end_date})…")

    pipeline = {
        "universe": universe,
        "stages": stages,
        "risk_limits": {},
    }
    if max_position_size is not None:
        pipeline["risk_limits"]["max_position_size"] = max_position_size
    if stop_loss is not None:
        pipeline["risk_limits"]["stop_loss"] = stop_loss
    if max_drawdown is not None:
        pipeline["risk_limits"]["max_drawdown"] = max_drawdown

    bt_config = {
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": 100000,
        "rebalance": rebalance,
        "sizing": sizing,
    }

    try:
        if ctx is not None:
            await ctx.report_progress(1, 3)
            await ctx.info("Pipeline configured. Running backtest…")

        result = await asyncio.to_thread(run_backtest, pipeline, bt_config)

        if ctx is not None:
            await ctx.report_progress(2, 3)
            await ctx.info("Backtest complete. Formatting results…")

        equity_curve = result.get("equity_curve", [])
        metrics = result.get("metrics", {})
        trades = result.get("trades", [])

        # Summarize trades
        trade_summary = {
            "total_trades": len(trades),
            "buys": sum(1 for t in trades if t["action"] == "BUY"),
            "sells": sum(1 for t in trades if t["action"] == "SELL"),
            "recent_trades": trades[-10:] if trades else [],
        }

        # Clean NaN
        clean_metrics = {}
        for k, v in metrics.items():
            if isinstance(v, float) and pd.isna(v):
                clean_metrics[k] = None
            else:
                clean_metrics[k] = v

        if ctx is not None:
            await ctx.report_progress(3, 3)

        data_warnings = get_and_clear_warnings()
        response: dict = {
            "strategy": {
                "universe": universe,
                "rebalance": rebalance,
                "sizing": sizing,
                "stages": stages,
                "period": f"{start_date} to {end_date}",
            },
            "metrics": clean_metrics,
            # Full daily curve — required for factor_analysis to work downstream.
            # Pass this directly to factor_analysis as equity_curve.
            "equity_curve": equity_curve,
            "trades": trade_summary,
        }
        if data_warnings:
            response["warnings"] = data_warnings
        return _truncate_response(json.dumps(response))

    except Exception as e:
        get_and_clear_warnings()  # flush so next call starts clean
        return json.dumps({
            "error": str(e),
            "code": "BACKTEST_ERROR",
            "strategy": {"universe": universe, "stages": stages},
        })


# ── Tool 3: Factor Analysis ──

@mcp.tool(
    name="factor_analysis",
    annotations={
        "title": "Factor Analysis",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def factor_analysis(
    equity_curve: Annotated[list[dict], Field(
        description=(
            "Equity curve as a list of {date, value} objects. "
            "Typically from the output of backtest_strategy. "
            "Needs at least 30 data points. "
            "Example: [{date: '2023-01-03', value: 100000}, {date: '2023-01-04', value: 100500}, ...]"
        ),
    )],
    ctx: Context | None = None,
) -> str:
    """Decompose strategy or portfolio returns into Fama-French factors using OLS regression.

    Breaks down returns into exposures to four systematic factors:
    - Mkt-RF (market risk premium): how much return comes from overall market movement
    - SMB (small minus big): size factor exposure
    - HML (high minus low): value factor exposure
    - Mom (momentum): momentum factor exposure

    Also estimates alpha (excess return not explained by factors) with t-statistic
    for statistical significance. A |t-stat| > 2 suggests statistically significant alpha.

    Returns alpha (daily and annualized), factor loadings with t-statistics,
    R-squared (how much of return variance is explained by factors), and residual volatility.

    Use this after backtest_strategy to understand WHERE your returns come from —
    is it genuine alpha or just factor exposure?
    """
    try:
        if ctx is not None:
            await ctx.report_progress(0, 1)
            await ctx.info(f"Running Fama-French factor regression on {len(equity_curve)} data points…")

        result = await asyncio.to_thread(run_factor_regression, equity_curve)

        if ctx is not None:
            await ctx.report_progress(1, 1)

        if result is None:
            return json.dumps({
                "error": "Factor regression returned no results",
                "code": "REGRESSION_NO_RESULT",
            })

        if "error" in result:
            return json.dumps({**result, "code": "REGRESSION_ERROR"})

        # Add interpretation hints
        alpha_tstat = result.get("alpha_tstat", 0)
        if abs(alpha_tstat) >= 2:
            alpha_note = f"Alpha is statistically significant (t-stat={alpha_tstat})"
        else:
            alpha_note = f"Alpha is NOT statistically significant (t-stat={alpha_tstat}, need |t| >= 2)"

        factors = result.get("factors", {})
        dominant_factor = max(factors.items(), key=lambda x: abs(x[1].get("loading", 0))) if factors else None
        if dominant_factor:
            factor_note = f"Dominant factor: {dominant_factor[0]} (loading={dominant_factor[1]['loading']})"
        else:
            factor_note = "No dominant factor identified"

        r_sq = result.get("r_squared", 0)
        if r_sq > 0.7:
            r_sq_note = f"High R² ({r_sq}) — most return variance explained by known factors"
        elif r_sq > 0.4:
            r_sq_note = f"Moderate R² ({r_sq}) — mix of factor and idiosyncratic returns"
        else:
            r_sq_note = f"Low R² ({r_sq}) — returns largely driven by stock-specific factors"

        result["interpretation"] = {
            "alpha": alpha_note,
            "factors": factor_note,
            "r_squared": r_sq_note,
        }

        return _truncate_response(json.dumps(result))

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "code": "FACTOR_ANALYSIS_ERROR",
        })


# ── Entry point ──

def main():
    """Run the QuantContext MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

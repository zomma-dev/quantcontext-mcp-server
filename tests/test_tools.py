"""End-to-end tests for QuantContext MCP tools.

Tests call the tool functions directly (not through MCP protocol)
to verify they return valid JSON with expected structure.

All tests share a single fixed date window (TEST_START / TEST_END / TEST_SCREEN_DATE)
so the price + factor cache only needs to cover one span. After the first run the
cache is warm and subsequent runs complete in seconds.

To pre-warm the cache before running:
    quantcontext-warmup --url https://quantcontext.ai/api/data
"""
import json
import sys

# Fixed date window shared across all tests — maximises cache reuse.
TEST_START = "2023-01-01"
TEST_END   = "2024-12-31"
TEST_SCREEN_DATE = "2024-12-31"


def test_screen_stocks_basic():
    """screen_stocks returns valid JSON with expected fields."""
    from quantcontext.server import screen_stocks
    import asyncio
    result_str = asyncio.run(screen_stocks(
        universe="sp500",
        screen_type="value_screen",
        config={"pe_lt": 20, "top_n": 10},
        date=TEST_SCREEN_DATE,
    ))
    result = json.loads(result_str)
    assert "error" not in result, f"Tool returned error: {result.get('error')}"
    assert result["screen_type"] == "value_screen"
    assert result["universe"] == "sp500"
    assert isinstance(result["count"], int)
    assert isinstance(result["results"], list)
    assert result["count"] > 0, "Expected at least 1 stock to pass value screen"
    print(f"  screen_stocks: {result['count']} stocks found, showing {result['showing']}")


def test_screen_stocks_invalid_type():
    """screen_stocks returns structured error for invalid screen_type."""
    from quantcontext.server import screen_stocks
    import asyncio
    result_str = asyncio.run(screen_stocks(screen_type="nonexistent_screen", date=TEST_SCREEN_DATE))
    result = json.loads(result_str)
    assert "error" in result
    assert "code" in result
    assert "nonexistent_screen" in result["error"]
    print(f"  screen_stocks invalid type: correctly returned error")


def test_screen_stocks_invalid_universe():
    """screen_stocks returns structured error for invalid universe."""
    from quantcontext.server import screen_stocks
    import asyncio
    result_str = asyncio.run(screen_stocks(universe="invalid_universe", date=TEST_SCREEN_DATE))
    result = json.loads(result_str)
    assert "error" in result
    assert result["code"] == "INVALID_UNIVERSE"
    print(f"  screen_stocks invalid universe: correctly returned error")


def test_backtest_strategy_basic():
    """backtest_strategy returns metrics and equity curve."""
    from quantcontext.server import backtest_strategy
    import asyncio
    result_str = asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "value_screen", "config": {"pe_lt": 20, "top_n": 5}},
        ],
        universe="sp500",
        rebalance="quarterly",
        sizing="equal_weight",
        start_date=TEST_START,
        end_date=TEST_END,
    ))
    result = json.loads(result_str)
    assert "error" not in result, f"Tool returned error: {result.get('error')}"
    assert "metrics" in result
    assert "equity_curve" in result
    assert "trades" in result
    metrics = result["metrics"]
    assert "sharpe" in metrics
    assert "total_return" in metrics
    assert "max_drawdown" in metrics
    print(f"  backtest_strategy: return={metrics['total_return']:.2%}, sharpe={metrics['sharpe']}, max_dd={metrics['max_drawdown']:.2%}")


def test_factor_analysis_basic():
    """factor_analysis decomposes returns into factors."""
    from quantcontext.server import backtest_strategy, factor_analysis
    import asyncio
    # First, run a backtest to get an equity curve
    bt_result_str = asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "value_screen", "config": {"pe_lt": 20, "top_n": 10}},
        ],
        universe="sp500",
        rebalance="monthly",
        start_date=TEST_START,
        end_date=TEST_END,
    ))
    bt_result = json.loads(bt_result_str)
    assert "error" not in bt_result, f"Backtest failed: {bt_result.get('error')}"
    equity_curve = bt_result["equity_curve"]
    # Sampled curve may have < 30 points; handle gracefully
    if len(equity_curve) < 30:
        fa_result_str = asyncio.run(factor_analysis(equity_curve=equity_curve))
        fa_result = json.loads(fa_result_str)
        assert fa_result.get("error") or fa_result is None
        print(f"  factor_analysis: correctly handled short curve ({len(equity_curve)} points)")
        return
    # Run factor analysis on the equity curve
    fa_result_str = asyncio.run(factor_analysis(equity_curve=equity_curve))
    fa_result = json.loads(fa_result_str)
    assert "error" not in fa_result, f"Factor analysis failed: {fa_result.get('error')}"
    assert "alpha_annualized" in fa_result
    assert "factors" in fa_result
    assert "r_squared" in fa_result
    assert "interpretation" in fa_result
    print(f"  factor_analysis: alpha={fa_result['alpha_annualized']:.2%}, R²={fa_result['r_squared']:.4f}")
    for name, data in fa_result["factors"].items():
        print(f"    {name}: loading={data['loading']:.4f}, t={data['tstat']:.2f}")


def test_composability():
    """Full pipeline: screen -> backtest -> factor analysis."""
    from quantcontext.server import screen_stocks, backtest_strategy, factor_analysis
    import asyncio
    print("\n  === Composability Test: screen -> backtest -> factor analysis ===")
    # Step 1: Screen
    screen_result = json.loads(asyncio.run(screen_stocks(
        universe="sp500",
        screen_type="fundamental_screen",
        config={"pe_lt": 15, "roe_gt": 10},
        date=TEST_SCREEN_DATE,
    )))
    assert "error" not in screen_result
    print(f"  Step 1 (screen): {screen_result['count']} stocks passed")
    # Step 2: Backtest using the same screen criteria
    bt_result = json.loads(asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "fundamental_screen", "config": {"pe_lt": 15, "roe_gt": 10}},
        ],
        universe="sp500",
        rebalance="monthly",
        start_date=TEST_START,
        end_date=TEST_END,
    )))
    assert "error" not in bt_result
    assert "total_return" in bt_result.get("metrics", {}), f"metrics missing total_return: {bt_result.get('metrics')}"
    print(f"  Step 2 (backtest): return={bt_result['metrics']['total_return']:.2%}, sharpe={bt_result['metrics']['sharpe']}")
    # Step 3: Factor analysis on the backtest
    equity_curve = bt_result["equity_curve"]
    if len(equity_curve) >= 30:
        fa_result = json.loads(asyncio.run(factor_analysis(equity_curve=equity_curve)))
        assert "error" not in fa_result
        print(f"  Step 3 (factor): alpha={fa_result['alpha_annualized']:.2%}, R²={fa_result['r_squared']:.4f}")
    else:
        print(f"  Step 3 (factor): skipped — only {len(equity_curve)} data points (sampled curve)")
    print("  === Composability test passed ===")


def test_all_screen_types():
    """Every screen type returns valid JSON without crashing."""
    from quantcontext.server import screen_stocks
    import asyncio

    SCREEN_CONFIGS = {
        "momentum_screen":   {"lookback_days": 200, "top_pct": 0.2},
        "quality_screen":    {"roe_gt": 10},
        "value_screen":      {"pe_lt": 25, "top_n": 10},
        "mean_reversion":    {"lookback_days": 60, "z_threshold": -1.5},
        "technical_signal":  {"rsi_period": 14, "sma_short": 50, "sma_long": 200},
        "factor_model":      {"weights": {"value": 0.4, "momentum": 0.4, "quality": 0.2}, "top_n": 15},
        "fundamental_screen": {"pe_lt": 20},
    }

    for screen_type, config in SCREEN_CONFIGS.items():
        result = json.loads(asyncio.run(screen_stocks(
            universe="sp500",
            screen_type=screen_type,
            config=config,
            date=TEST_SCREEN_DATE,
        )))
        assert "error" not in result, f"{screen_type} returned error: {result.get('error')}"
        assert result["screen_type"] == screen_type
        assert isinstance(result["count"], int)
        assert isinstance(result["results"], list)
        print(f"  {screen_type}: {result['count']} stocks found")


def test_factor_model_dict_weights():
    """factor_model accepts dict weights without crashing (regression for Bug 2)."""
    from quantcontext.server import screen_stocks
    import asyncio

    result = json.loads(asyncio.run(screen_stocks(
        universe="sp500",
        screen_type="factor_model",
        config={"weights": {"value": 0.3, "momentum": 0.5, "quality": 0.2}, "top_n": 10},
        date=TEST_SCREEN_DATE,
    )))
    assert "error" not in result, f"factor_model with dict weights returned error: {result.get('error')}"
    assert result["count"] > 0, "Expected at least 1 stock from factor_model"
    print(f"  factor_model dict weights: {result['count']} stocks, top ticker: {result['results'][0].get('ticker')}")


def test_composability_momentum():
    """Full pipeline using momentum_screen (price-only, no fundamentals dependency)."""
    from quantcontext.server import backtest_strategy, factor_analysis
    import asyncio
    print("\n  === Momentum composability: backtest -> factor_analysis ===")

    bt_result = json.loads(asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "momentum_screen",
             "config": {"lookback_days": 200, "top_pct": 0.2}},
        ],
        universe="nasdaq100",
        rebalance="monthly",
        start_date=TEST_START,
        end_date=TEST_END,
    )))
    assert "error" not in bt_result, f"Backtest failed: {bt_result.get('error')}"
    assert "total_return" in bt_result["metrics"]
    equity_curve = bt_result["equity_curve"]
    assert len(equity_curve) >= 30, (
        f"Expected ≥30 daily curve points for factor_analysis, got {len(equity_curve)}"
    )
    print(f"  Backtest: return={bt_result['metrics']['total_return']:.2%}, "
          f"sharpe={bt_result['metrics']['sharpe']}, curve_points={len(equity_curve)}")

    fa_result = json.loads(asyncio.run(factor_analysis(equity_curve=equity_curve)))
    assert "error" not in fa_result, f"Factor analysis failed: {fa_result.get('error')}"
    assert "alpha_annualized" in fa_result
    assert "factors" in fa_result
    assert "r_squared" in fa_result
    print(f"  Factor analysis: alpha={fa_result['alpha_annualized']:.2%} "
          f"(t={fa_result['alpha_tstat']:.2f}), R²={fa_result['r_squared']:.4f}")
    print("  === Momentum composability passed ===")


def test_backtest_risk_controls():
    """Backtest with stop_loss, max_drawdown, and max_position_size doesn't corrupt portfolio."""
    from quantcontext.server import backtest_strategy
    import asyncio

    result = json.loads(asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "momentum_screen",
             "config": {"lookback_days": 200, "top_pct": 0.3}},
        ],
        universe="sp500",
        rebalance="monthly",
        start_date=TEST_START,
        end_date=TEST_END,
        stop_loss=0.15,
        max_drawdown=0.20,
        max_position_size=0.10,
    )))
    assert "error" not in result, f"Risk-controlled backtest failed: {result.get('error')}"
    metrics = result["metrics"]
    assert metrics["total_return"] > -1.0, "total_return below -100% — portfolio value went negative"
    assert metrics["max_drawdown"] >= -1.0, "max_drawdown below -100% — impossible value"
    # With a 20% circuit breaker the actual drawdown may exceed 20% slightly (daily granularity),
    # but should never be catastrophic
    assert metrics["max_drawdown"] > -0.97, (
        f"Suspected drawdown artifact: max_drawdown={metrics['max_drawdown']:.2%} "
        "(looks like Bug 3 — position liquidated at zero price)"
    )
    equity_curve = result["equity_curve"]
    values = [p["value"] for p in equity_curve]
    assert all(v > 0 for v in values), "Portfolio value went to zero or negative mid-simulation"
    print(f"  Risk controls: return={metrics['total_return']:.2%}, "
          f"max_dd={metrics['max_drawdown']:.2%}, trades={metrics['total_trades']}")


def test_backtest_inverse_volatility_sizing():
    """inverse_volatility sizing runs without crashing and returns valid metrics."""
    from quantcontext.server import backtest_strategy
    import asyncio

    result = json.loads(asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "momentum_screen",
             "config": {"lookback_days": 126, "top_pct": 0.2}},
        ],
        universe="nasdaq100",
        rebalance="quarterly",
        sizing="inverse_volatility",
        start_date=TEST_START,
        end_date=TEST_END,
    )))
    assert "error" not in result, f"inverse_volatility backtest failed: {result.get('error')}"
    assert "total_return" in result["metrics"]
    print(f"  inverse_volatility sizing: return={result['metrics']['total_return']:.2%}, "
          f"sharpe={result['metrics']['sharpe']}")


def test_multistage_pipeline():
    """Two-stage pipeline (filter then rank) runs without crashing."""
    from quantcontext.server import backtest_strategy
    import asyncio

    result = json.loads(asyncio.run(backtest_strategy(
        stages=[
            {"order": 1, "type": "screen", "skill": "value_screen",
             "config": {"pe_lt": 20, "top_n": 50}},
            {"order": 2, "type": "screen", "skill": "momentum_screen",
             "config": {"lookback_days": 200, "top_pct": 0.3}},
        ],
        universe="sp500",
        rebalance="monthly",
        start_date=TEST_START,
        end_date=TEST_END,
    )))
    assert "error" not in result, f"Multi-stage backtest failed: {result.get('error')}"
    assert "total_return" in result["metrics"]
    print(f"  Multi-stage (value→momentum): return={result['metrics']['total_return']:.2%}, "
          f"sharpe={result['metrics']['sharpe']}")


if __name__ == "__main__":
    tests = [
        ("screen_stocks basic", test_screen_stocks_basic),
        ("screen_stocks invalid type", test_screen_stocks_invalid_type),
        ("screen_stocks invalid universe", test_screen_stocks_invalid_universe),
        ("backtest_strategy basic", test_backtest_strategy_basic),
        ("factor_analysis basic", test_factor_analysis_basic),
        ("composability (screen->backtest->factor)", test_composability),
        ("all screen types", test_all_screen_types),
        ("factor_model dict weights", test_factor_model_dict_weights),
        ("composability with momentum (price-only)", test_composability_momentum),
        ("backtest risk controls", test_backtest_risk_controls),
        ("inverse_volatility sizing", test_backtest_inverse_volatility_sizing),
        ("multi-stage pipeline", test_multistage_pipeline),
    ]
    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\nRunning: {name}")
        try:
            test_fn()
            print(f"  PASSED")
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed > 0:
        sys.exit(1)

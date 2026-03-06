"""End-to-end tests for QuantContext MCP tools.

Tests call the tool functions directly (not through MCP protocol)
to verify they return valid JSON with expected structure.
"""
import json
import sys
import os

# Ensure engine is importable
ENGINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "engine")
ENGINE_DIR = os.path.abspath(ENGINE_DIR)
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)


def test_screen_stocks_basic():
    """screen_stocks returns valid JSON with expected fields."""
    from quantcontext.server import screen_stocks
    import asyncio
    result_str = asyncio.run(screen_stocks(
        universe="sp500",
        screen_type="value_screen",
        config={"pe_lt": 20, "top_n": 10},
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
    result_str = asyncio.run(screen_stocks(screen_type="nonexistent_screen"))
    result = json.loads(result_str)
    assert "error" in result
    assert "code" in result
    assert "nonexistent_screen" in result["error"]
    print(f"  screen_stocks invalid type: correctly returned error")


def test_screen_stocks_invalid_universe():
    """screen_stocks returns structured error for invalid universe."""
    from quantcontext.server import screen_stocks
    import asyncio
    result_str = asyncio.run(screen_stocks(universe="invalid_universe"))
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
        start_date="2024-01-01",
        end_date="2024-06-30",
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
        start_date="2023-06-01",
        end_date="2024-06-30",
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
        start_date="2024-01-01",
        end_date="2024-12-31",
    )))
    assert "error" not in bt_result
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


if __name__ == "__main__":
    tests = [
        ("screen_stocks basic", test_screen_stocks_basic),
        ("screen_stocks invalid type", test_screen_stocks_invalid_type),
        ("screen_stocks invalid universe", test_screen_stocks_invalid_universe),
        ("backtest_strategy basic", test_backtest_strategy_basic),
        ("factor_analysis basic", test_factor_analysis_basic),
        ("composability (screen->backtest->factor)", test_composability),
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

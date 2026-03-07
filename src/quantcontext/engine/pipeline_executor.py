"""Maps pipeline spec stages to deterministic skill functions and executes sequentially."""
from __future__ import annotations

import pandas as pd

from quantcontext.engine.data import get_universe
from quantcontext.engine.skills.pipeline_skills.registry import SKILL_REGISTRY


def execute_pipeline(
    pipeline: dict,
    date: str,
) -> tuple[list[dict], pd.DataFrame]:
    """Run all pipeline stages in order.

    Returns:
        results: list of per-stage result dicts (input_count, output_count, sample, etc.)
        candidates: final DataFrame after all stages
    """
    universe_name = pipeline.get("universe", "sp500")
    stages = sorted(pipeline.get("stages", []), key=lambda s: s.get("order", 0))

    # Avoid 500+ per-ticker yfinance calls when no stage needs fundamental data.
    # Price-only screens (momentum, technical_signal, mean_reversion) set
    # needs_fundamentals=False in their SKILL_META; all others default to True.
    needs_fundamentals = any(
        SKILL_REGISTRY.get(s.get("skill", ""), {}).get("meta", {}).get("needs_fundamentals", True)
        for s in stages
    )

    candidates = get_universe(date, universe_name, fundamentals=needs_fundamentals)

    results: list[dict] = []

    for stage in stages:
        skill_id = stage["skill"]
        if skill_id not in SKILL_REGISTRY:
            raise KeyError(f"Unknown pipeline skill: '{skill_id}'")

        skill = SKILL_REGISTRY[skill_id]
        input_count = len(candidates)
        input_tickers = set(candidates["ticker"].tolist()) if "ticker" in candidates.columns else set()

        output = skill["run"](candidates, stage.get("config", {}), date)
        output_count = len(output)

        sample = output.head(5).to_dict("records") if len(output) > 0 else []

        if "ticker" in output.columns and "ticker" in candidates.columns:
            output_tickers = set(output["ticker"].tolist())
            removed_tickers = input_tickers - output_tickers
            removed = candidates[candidates["ticker"].isin(removed_tickers)].head(5).to_dict("records")
        else:
            removed = []

        results.append({
            "stage": stage,
            "input_count": input_count,
            "output_count": output_count,
            "sample": sample,
            "removed_sample": removed,
        })

        candidates = output

    return results, candidates

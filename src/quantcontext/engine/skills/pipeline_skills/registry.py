"""Central registry mapping skill IDs to their run() functions."""
from quantcontext.engine.skills.pipeline_skills import (
    fundamental_screen,
    quality_screen,
    momentum_screen,
    value_screen,
    factor_model,
    technical_signal,
    mean_reversion,
)

SKILL_REGISTRY: dict[str, dict] = {}

for _module in [
    fundamental_screen,
    quality_screen,
    momentum_screen,
    value_screen,
    factor_model,
    technical_signal,
    mean_reversion,
]:
    _skill_id = _module.SKILL_META["id"]
    SKILL_REGISTRY[_skill_id] = {
        "meta": _module.SKILL_META,
        "run": _module.run,
    }

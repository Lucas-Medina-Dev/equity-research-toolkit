"""Two-way sensitivity tables on the base scenario."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from erkit.config import Config, Scenario
from erkit.valuation import per_share_value


def wacc_growth_grid(
    cfg: Config,
    center_wacc: float,
    wacc_steps: Sequence[float] = (-0.02, -0.01, 0.0, 0.01, 0.02),
    growth_steps: Sequence[float] = (-0.01, -0.005, 0.0, 0.005, 0.01),
) -> pd.DataFrame:
    """Value per share for WACC (rows) × terminal growth (columns)."""
    g0 = cfg.forecast.terminal_growth
    base = cfg.forecast.base
    rows = {}
    for dw in wacc_steps:
        w = center_wacc + dw
        rows[w] = {g0 + dg: per_share_value(cfg, base, w, g0 + dg) for dg in growth_steps}
    df = pd.DataFrame(rows).T
    df.index.name = "WACC"
    df.columns.name = "Terminal growth"
    return df


def margin_growth_grid(
    cfg: Config,
    discount_rate: float,
    margin_shifts: Sequence[float] = (-0.04, -0.02, 0.0, 0.02, 0.04),
    growth_shifts: Sequence[float] = (-0.04, -0.02, 0.0, 0.02, 0.04),
) -> pd.DataFrame:
    """Value per share when the whole base-case margin / growth path shifts.

    This is the operating sensitivity: it answers "what if the business
    simply earns 2 points less margin every year?" rather than tweaking the
    discount rate.
    """
    base = cfg.forecast.base
    rows = {}
    for dm in margin_shifts:
        row = {}
        for dg in growth_shifts:
            s = Scenario(
                "shifted",
                1.0,
                [g + dg for g in base.revenue_growth],
                [m + dm for m in base.ebit_margin],
            )
            row[dg] = per_share_value(cfg, s, discount_rate)
        rows[dm] = row
    df = pd.DataFrame(rows).T
    df.index.name = "EBIT margin shift"
    df.columns.name = "Revenue growth shift"
    return df

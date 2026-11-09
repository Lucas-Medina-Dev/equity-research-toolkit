"""Choosing the valuation case from the company's financial history.

The framework asks one question before any modelling: has the company been
consistently profitable — at least ``min_years`` consecutive, most recent
years of positive EBITDA (and positive free cash flow when it is reported)?

* **Case 1 — high growth / pre-profit.** Revenue-driven DCF in two phases
  (growth, then margin convergence towards profitable peers). Comps carry
  the larger weight because the DCF is dominated by long-dated assumptions.
* **Case 2 — consistently profitable.** Standard FCFF DCF anchored on
  historical cash generation; DCF and comps carry equal weight.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum


class Case(str, Enum):
    HIGH_GROWTH = "case_1_high_growth"
    PROFITABLE = "case_2_profitable"

    @property
    def label(self) -> str:
        return {
            Case.HIGH_GROWTH: "Case 1 — High growth / pre-profit",
            Case.PROFITABLE: "Case 2 — Consistently profitable",
        }[self]

    @property
    def default_weights(self) -> dict[str, float]:
        """Weight of each method in the blended value."""
        return {
            Case.HIGH_GROWTH: {"comps": 0.6, "dcf": 0.4},
            Case.PROFITABLE: {"comps": 0.5, "dcf": 0.5},
        }[self]


def select_case(
    ebitda: Sequence[float | None],
    fcf: Sequence[float | None] | None = None,
    min_years: int = 3,
) -> Case:
    """Return the valuation case given yearly history (oldest first).

    A year counts as profitable when EBITDA is positive and, if FCF is
    provided for that year, FCF is positive too. Only the uninterrupted
    streak ending in the latest year counts: a company that was profitable
    in 2019-2021 and lost money since is Case 1.
    """
    if min_years < 1:
        raise ValueError("min_years must be >= 1")
    if fcf is not None and len(fcf) != len(ebitda):
        raise ValueError("ebitda and fcf must have the same length")

    streak = 0
    for i in range(len(ebitda) - 1, -1, -1):
        e = ebitda[i]
        f = fcf[i] if fcf is not None else None
        if e is None or e <= 0 or (f is not None and f <= 0):
            break
        streak += 1
    return Case.PROFITABLE if streak >= min_years else Case.HIGH_GROWTH


def convergence_margins(
    start_margin: float, target_margin: float, years: int, convergence_years: int
) -> list[float]:
    """Case 1 margin path: linear move to the target, then flat.

    ``convergence_years`` is the year in which the target is reached. The
    terminal year must sit at the target so the Gordon growth value is not
    computed on a margin that is still moving.
    """
    if not 1 <= convergence_years <= years:
        raise ValueError("convergence_years must be between 1 and years")
    step = (target_margin - start_margin) / convergence_years
    return [start_margin + step * min(t, convergence_years) for t in range(1, years + 1)]

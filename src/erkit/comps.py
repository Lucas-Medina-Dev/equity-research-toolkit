"""Trading comparables with explicit outlier control.

Broker and fintech multiples are noisy: aggregators disagree, client cash
distorts enterprise value, and a single richly valued peer can drag a mean
far away from the group. Each multiple is therefore summarised with:

* a minimum number of peers (below it the multiple is not used at all);
* Tukey's fences (Q1 − k·IQR, Q3 + k·IQR) to drop outliers, reported back
  so the exclusion is visible rather than silent;
* the median as the point estimate and the inter-quartile range as the
  valuation range.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

# Which company metric each multiple applies to, and whether it yields
# enterprise value ("ev") or equity value ("equity").
MULTIPLE_SPECS: dict[str, tuple[str, str]] = {
    "ev_ebitda": ("ebitda", "ev"),
    "ev_revenue": ("revenue", "ev"),
    "pe": ("net_income", "equity"),
    "p_book": ("book_equity", "equity"),
}


@dataclass(frozen=True)
class Peer:
    name: str
    ticker: str
    multiples: dict[str, float | None]
    as_of: str = ""
    source: str = ""


@dataclass(frozen=True)
class MultipleStats:
    multiple: str
    used: dict[str, float]
    excluded: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.used)

    @property
    def values(self) -> list[float]:
        return sorted(self.used.values())

    @property
    def median(self) -> float:
        return statistics.median(self.values)

    @property
    def low(self) -> float:
        return _quartiles(self.values)[0]

    @property
    def high(self) -> float:
        return _quartiles(self.values)[1]


def _quartiles(values: Sequence[float]) -> tuple[float, float]:
    """Q1 and Q3 with linear interpolation (same as Excel QUARTILE.INC)."""
    v = sorted(values)
    if len(v) == 1:
        return v[0], v[0]
    q = statistics.quantiles(v, n=4, method="inclusive")
    return q[0], q[2]


def summarize_multiple(
    peers: Sequence[Peer], multiple: str, min_peers: int = 3, iqr_k: float = 1.5
) -> MultipleStats | None:
    """Clean and summarise one multiple across peers.

    Returns ``None`` when fewer than ``min_peers`` usable values remain,
    so thin data never silently drives a valuation.
    """
    if multiple not in MULTIPLE_SPECS:
        raise KeyError(f"unknown multiple '{multiple}'")

    raw: dict[str, float] = {}
    missing: list[str] = []
    for p in peers:
        v = p.multiples.get(multiple)
        if v is None or v <= 0:  # negative multiples are not meaningful
            missing.append(p.ticker)
        else:
            raw[p.ticker] = float(v)

    excluded: dict[str, float] = {}
    if len(raw) >= 4:  # fences need a minimum sample to mean anything
        q1, q3 = _quartiles(list(raw.values()))
        lo, hi = q1 - iqr_k * (q3 - q1), q3 + iqr_k * (q3 - q1)
        excluded = {t: v for t, v in raw.items() if not lo <= v <= hi}
    used = {t: v for t, v in raw.items() if t not in excluded}

    if len(used) < min_peers:
        return None
    return MultipleStats(multiple, used, excluded, missing)


def implied_equity_value(
    multiple_value: float, metric_value: float, kind: str, ev_to_equity_adjustment: float
) -> float:
    """Equity value implied by applying a multiple to the company's metric."""
    if kind == "ev":
        return multiple_value * metric_value + ev_to_equity_adjustment
    if kind == "equity":
        return multiple_value * metric_value
    raise ValueError(f"unknown multiple kind '{kind}'")

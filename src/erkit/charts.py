"""Football field chart: every valuation method on one axis."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from erkit.sensitivity import wacc_growth_grid  # noqa: E402
from erkit.valuation import ValuationResult  # noqa: E402

NAVY = "#0B1F3A"
STEEL = "#3E6A9E"
SAND = "#C9A227"
GREY = "#8A96A8"


def football_field(r: ValuationResult, path: str | Path) -> Path:
    cfg = r.config
    rows: list[tuple[str, float, float, str]] = []
    if cfg.trading_range:
        rows.append(("52-week trading range", *cfg.trading_range, GREY))
    for c in r.comps:
        rows.append(
            (
                f"Comps {c.stats.multiple.replace('_', '/').upper()} (Q1–Q3)",
                c.per_share_low,
                c.per_share_high,
                STEEL,
            )
        )
    grid = wacc_growth_grid(cfg, r.wacc, wacc_steps=(-0.01, 0, 0.01), growth_steps=(-0.005, 0, 0.005))
    rows.append(("DCF base: WACC ±1pt, g ±0.5pt", float(grid.values.min()), float(grid.values.max()), NAVY))
    per = sorted(s.per_share for s in r.scenarios)
    rows.append(("DCF scenarios (bear → bull)", per[0], per[-1], NAVY))

    fig, ax = plt.subplots(figsize=(9, 0.62 * len(rows) + 1.6), dpi=160)
    for i, (_label, lo, hi, color) in enumerate(reversed(rows)):
        ax.barh(i, hi - lo, left=lo, height=0.5, color=color, alpha=0.9)
        ax.text(lo - 0.6, i, f"${lo:,.0f}", va="center", ha="right", fontsize=8, color="#33415C")
        ax.text(hi + 0.6, i, f"${hi:,.0f}", va="center", ha="left", fontsize=8, color="#33415C")
    ax.set_yticks(range(len(rows)), [r_[0] for r_ in reversed(rows)], fontsize=9)

    price = cfg.company.price
    ax.axvline(price, color="#B42318", lw=1.4, ls="--")
    ax.text(price, -0.62, f" Price ${price:.2f}", color="#B42318", fontsize=8, va="center")
    ax.axvline(r.blended_per_share, color=SAND, lw=1.6)
    ax.text(
        r.blended_per_share,
        -0.62,
        f" Blended ${r.blended_per_share:.2f}",
        color="#8A6D00",
        fontsize=8,
        va="center",
    )
    ax.set_ylim(-0.9, len(rows) - 0.4)

    ax.set_xlabel(f"Value per share ({cfg.company.currency})", fontsize=9)
    ax.set_title(
        f"{cfg.company.name} — valuation football field · {r.rating}",
        loc="left",
        fontsize=11,
        color=NAVY,
        fontweight="bold",
        pad=12,
    )
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#E3E8EF", lw=0.8)
    ax.set_axisbelow(True)
    lo_all = min(min(r_[1] for r_ in rows), price)
    hi_all = max(max(r_[2] for r_ in rows), r.blended_per_share)
    ax.set_xlim(lo_all * 0.8, hi_all * 1.08)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path

"""Unlevered free cash flow (FCFF) DCF.

FCFF_t = EBIT_t × (1 − tax) + D&A_t − Capex_t − ΔNWC_t

Revenue, D&A and capex are driven from a revenue base; working capital is
modelled as a share of *incremental* revenue, which is the cleaner choice
for platform businesses with little inventory or receivables.

Terminal value uses the Gordon growth model. The model also reports the
share of enterprise value coming from the terminal value and the exit
EV/EBITDA multiple the terminal value implies — the two sanity checks a
reviewer looks at first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DCFAssumptions:
    revenue_growth: Sequence[float]
    ebit_margin: Sequence[float]
    tax_rate: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_incremental_revenue: float
    terminal_growth: float
    mid_year: bool = True

    def __post_init__(self) -> None:
        if len(self.revenue_growth) != len(self.ebit_margin):
            raise ValueError("revenue_growth and ebit_margin must have the same length")
        if len(self.revenue_growth) == 0:
            raise ValueError("at least one forecast year is required")
        if not 0 <= self.tax_rate < 1:
            raise ValueError("tax_rate must be in [0, 1)")

    @property
    def years(self) -> int:
        return len(self.revenue_growth)


@dataclass(frozen=True)
class DCFResult:
    years: list[int]
    revenue: list[float]
    ebit: list[float]
    nopat: list[float]
    da: list[float]
    capex: list[float]
    delta_nwc: list[float]
    fcff: list[float]
    discount_factors: list[float]
    pv_fcff: list[float]
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    wacc: float
    terminal_growth: float

    @property
    def terminal_share_of_ev(self) -> float:
        return self.pv_terminal_value / self.enterprise_value

    @property
    def implied_exit_ev_ebitda(self) -> float:
        """Terminal value divided by final-year EBITDA (EBIT + D&A)."""
        final_ebitda = self.ebit[-1] + self.da[-1]
        return self.terminal_value / final_ebitda


def run_dcf(base_revenue: float, assumptions: DCFAssumptions, wacc: float, first_year: int) -> DCFResult:
    """Project FCFF from ``base_revenue`` (the last actual or estimated year).

    Cash flows are discounted from the end of the base year. With the
    mid-year convention, year-t cash flow is discounted at t − 0.5. The
    terminal value is discounted at N (end of the explicit forecast), which
    is the conservative convention.
    """
    a = assumptions
    if wacc <= a.terminal_growth:
        raise ValueError(f"WACC ({wacc:.2%}) must exceed terminal growth ({a.terminal_growth:.2%})")
    if base_revenue <= 0:
        raise ValueError("base_revenue must be positive")

    revenue, ebit, nopat, da, capex, dnwc, fcff, dfs, pvs = ([] for _ in range(9))
    prev_rev = base_revenue
    for t in range(1, a.years + 1):
        rev = prev_rev * (1 + a.revenue_growth[t - 1])
        e = rev * a.ebit_margin[t - 1]
        n = e * (1 - a.tax_rate)
        d = rev * a.da_pct_revenue
        c = rev * a.capex_pct_revenue
        w = (rev - prev_rev) * a.nwc_pct_incremental_revenue
        f = n + d - c - w
        period = t - 0.5 if a.mid_year else t
        df = 1 / (1 + wacc) ** period

        revenue.append(rev)
        ebit.append(e)
        nopat.append(n)
        da.append(d)
        capex.append(c)
        dnwc.append(w)
        fcff.append(f)
        dfs.append(df)
        pvs.append(f * df)
        prev_rev = rev

    tv = fcff[-1] * (1 + a.terminal_growth) / (wacc - a.terminal_growth)
    pv_tv = tv / (1 + wacc) ** a.years
    ev = sum(pvs) + pv_tv

    return DCFResult(
        years=[first_year + i for i in range(a.years)],
        revenue=revenue,
        ebit=ebit,
        nopat=nopat,
        da=da,
        capex=capex,
        delta_nwc=dnwc,
        fcff=fcff,
        discount_factors=dfs,
        pv_fcff=pvs,
        terminal_value=tv,
        pv_terminal_value=pv_tv,
        enterprise_value=ev,
        wacc=wacc,
        terminal_growth=a.terminal_growth,
    )

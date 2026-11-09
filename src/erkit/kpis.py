"""Fintech KPIs used in the research framework's financial analysis section."""

from __future__ import annotations

from erkit.config import Config


def _growth(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev <= 0:
        return None
    return curr / prev - 1


def fintech_kpis(cfg: Config) -> dict[str, float | None]:
    h = cfg.history
    rev, ebitda, ni = h.revenue[-1], h.ebitda[-1], h.net_income[-1]
    rev_growth = _growth(rev, h.revenue[-2]) if len(h.revenue) > 1 else None
    ebitda_margin = ebitda / rev if rev and ebitda is not None else None
    out: dict[str, float | None] = {
        "revenue_growth": rev_growth,
        "ebitda_margin": ebitda_margin,
        "net_margin": ni / rev if rev and ni is not None else None,
        # Rule of 40: growth + profitability >= 40% marks a healthy scaling platform
        "rule_of_40": (rev_growth + ebitda_margin)
        if rev_growth is not None and ebitda_margin is not None
        else None,
    }
    accounts = cfg.kpis.get("funded_accounts_m")
    aua = cfg.kpis.get("aua_bn")
    if accounts:
        out["revenue_per_funded_account"] = rev / accounts  # currency units per account
    if aua:
        out["revenue_yield_on_aua"] = rev / (aua * 1000)
    if accounts and aua:
        out["aua_per_funded_account"] = aua * 1000 / accounts  # currency units per account
    return out

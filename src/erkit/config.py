"""Load and validate a company valuation file (YAML).

Every input lives in one human-readable file with a source next to it, so
a reviewer can trace each number. See ``examples/etoro.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from erkit.cases import convergence_margins
from erkit.comps import Peer


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Company:
    name: str
    ticker: str
    currency: str
    units: str
    price: float
    diluted_shares: float
    price_date: str
    valuation_date: str
    revenue_label: str = "Revenue"


@dataclass(frozen=True)
class History:
    years: list[int]
    revenue: list[float | None]
    ebitda: list[float | None]
    net_income: list[float | None]
    fcf: list[float | None] | None = None


@dataclass(frozen=True)
class CostOfCapital:
    risk_free: float
    equity_risk_premium: float
    raw_beta: float
    blume_adjust: bool = True
    country_risk_premium: float = 0.0
    pre_tax_cost_of_debt: float = 0.0
    debt_to_capital: float = 0.0


@dataclass(frozen=True)
class Scenario:
    name: str
    weight: float
    revenue_growth: list[float]
    ebit_margin: list[float]


@dataclass(frozen=True)
class Forecast:
    base_year: int
    base_revenue: float
    tax_rate: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_incremental_revenue: float
    terminal_growth: float
    mid_year: bool
    scenarios: list[Scenario]

    @property
    def base(self) -> Scenario:
        for s in self.scenarios:
            if s.name == "base":
                return s
        return self.scenarios[0]


@dataclass(frozen=True)
class Bridge:
    cash: float
    cash_haircut: float = 0.0
    debt: float = 0.0
    leases: float = 0.0
    other_claims: float = 0.0


@dataclass(frozen=True)
class Config:
    company: Company
    history: History
    ltm: dict[str, float]
    cost_of_capital: CostOfCapital
    forecast: Forecast
    bridge: Bridge
    peers: list[Peer]
    multiples: list[str]
    rating_bands: dict[str, float]
    trading_range: tuple[float, float] | None = None
    kpis: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    weights_override: dict[str, float] | None = None
    min_peers: int = 3


def _req(d: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d:
        raise ConfigError(f"missing '{key}' in {ctx}")
    return d[key]


def _scenarios(f: dict[str, Any]) -> list[Scenario]:
    out = []
    for name, s in _req(f, "scenarios", "forecast").items():
        growth = list(_req(s, "revenue_growth", f"scenario {name}"))
        if "ebit_margin" in s:
            margins = list(s["ebit_margin"])
        elif "margin_convergence" in s:  # Case 1 style path
            mc = s["margin_convergence"]
            margins = convergence_margins(mc["start"], mc["target"], len(growth), mc["years_to_target"])
        else:
            raise ConfigError(f"scenario {name}: give ebit_margin or margin_convergence")
        if len(margins) != len(growth):
            raise ConfigError(f"scenario {name}: growth and margin lengths differ")
        out.append(Scenario(name, float(s.get("weight", 1.0)), growth, margins))
    total = sum(s.weight for s in out)
    if abs(total - 1) > 1e-6:
        raise ConfigError(f"scenario weights must sum to 1 (got {total:.4f})")
    return out


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> Config:
    c = _req(raw, "company", "root")
    h = _req(raw, "history", "root")
    k = _req(raw, "cost_of_capital", "root")
    f = _req(raw, "forecast", "root")
    b = _req(raw, "bridge", "root")
    comps = raw.get("comps", {})

    history = History(
        years=list(h["years"]),
        revenue=list(h["revenue"]),
        ebitda=list(h["ebitda"]),
        net_income=list(h["net_income"]),
        fcf=list(h["fcf"]) if h.get("fcf") else None,
    )
    n = len(history.years)
    for name in ("revenue", "ebitda", "net_income"):
        if len(getattr(history, name)) != n:
            raise ConfigError(f"history.{name} must have {n} values")

    peers = [
        Peer(
            name=p["name"],
            ticker=p["ticker"],
            multiples={m: p.get(m) for m in ("ev_ebitda", "ev_revenue", "pe", "p_book")},
            as_of=str(p.get("as_of", "")),
            source=p.get("source", ""),
        )
        for p in comps.get("peers", [])
    ]
    tr = raw.get("trading_range")

    return Config(
        company=Company(
            name=c["name"],
            ticker=c["ticker"],
            currency=c.get("currency", "USD"),
            units=c.get("units", "m"),
            price=float(c["price"]),
            diluted_shares=float(c["diluted_shares"]),
            price_date=str(c["price_date"]),
            valuation_date=str(c["valuation_date"]),
            revenue_label=c.get("revenue_label", "Revenue"),
        ),
        history=history,
        ltm={key: float(v) for key, v in _req(raw, "ltm", "root").items()},
        cost_of_capital=CostOfCapital(**k),
        forecast=Forecast(
            base_year=int(f["base_year"]),
            base_revenue=float(f["base_revenue"]),
            tax_rate=float(f["tax_rate"]),
            da_pct_revenue=float(f["da_pct_revenue"]),
            capex_pct_revenue=float(f["capex_pct_revenue"]),
            nwc_pct_incremental_revenue=float(f.get("nwc_pct_incremental_revenue", 0.0)),
            terminal_growth=float(f["terminal_growth"]),
            mid_year=bool(f.get("mid_year", True)),
            scenarios=_scenarios(f),
        ),
        bridge=Bridge(**b),
        peers=peers,
        multiples=list(comps.get("multiples", ["ev_ebitda", "pe"])),
        min_peers=int(comps.get("min_peers", 3)),
        rating_bands=raw.get("rating", {"buy_above": 0.15, "sell_below": -0.10}),
        trading_range=(float(tr[0]), float(tr[1])) if tr else None,
        kpis=raw.get("kpis", {}),
        sources=raw.get("sources", {}),
        weights_override=raw.get("weights"),
    )

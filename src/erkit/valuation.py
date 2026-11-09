"""Orchestration: case selection → cost of capital → DCF scenarios → comps → blend."""

from __future__ import annotations

from dataclasses import dataclass

from erkit.bridge import EquityBridge, equity_bridge
from erkit.cases import Case, select_case
from erkit.comps import MULTIPLE_SPECS, MultipleStats, implied_equity_value, summarize_multiple
from erkit.config import Config, Scenario
from erkit.dcf import DCFAssumptions, DCFResult, run_dcf
from erkit.wacc import blume_adjust, capm_cost_of_equity, wacc


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario: Scenario
    dcf: DCFResult
    equity_value: float
    per_share: float


@dataclass(frozen=True)
class CompsOutcome:
    stats: MultipleStats
    metric: str
    metric_value: float
    per_share_low: float
    per_share_mid: float
    per_share_high: float


@dataclass(frozen=True)
class ValuationResult:
    config: Config
    case: Case
    beta: float
    cost_of_equity: float
    wacc: float
    bridge: EquityBridge
    scenarios: list[ScenarioOutcome]
    comps: list[CompsOutcome]
    skipped_multiples: list[str]
    weights: dict[str, float]

    @property
    def base(self) -> ScenarioOutcome:
        for s in self.scenarios:
            if s.scenario.name == "base":
                return s
        return self.scenarios[0]

    @property
    def dcf_per_share(self) -> float:
        """Probability-weighted DCF value per share."""
        return sum(s.scenario.weight * s.per_share for s in self.scenarios)

    @property
    def comps_per_share(self) -> float | None:
        if not self.comps:
            return None
        return sum(c.per_share_mid for c in self.comps) / len(self.comps)

    @property
    def blended_per_share(self) -> float:
        comps = self.comps_per_share
        if comps is None:  # no usable comps: DCF only, flagged in the report
            return self.dcf_per_share
        return self.weights["dcf"] * self.dcf_per_share + self.weights["comps"] * comps

    @property
    def upside(self) -> float:
        return self.blended_per_share / self.config.company.price - 1

    @property
    def rating(self) -> str:
        bands = self.config.rating_bands
        if self.upside >= bands["buy_above"]:
            return "BUY"
        if self.upside <= bands["sell_below"]:
            return "SELL"
        return "HOLD"


def dcf_assumptions(cfg: Config, scenario: Scenario, terminal_growth: float | None = None):
    f = cfg.forecast
    return DCFAssumptions(
        revenue_growth=scenario.revenue_growth,
        ebit_margin=scenario.ebit_margin,
        tax_rate=f.tax_rate,
        da_pct_revenue=f.da_pct_revenue,
        capex_pct_revenue=f.capex_pct_revenue,
        nwc_pct_incremental_revenue=f.nwc_pct_incremental_revenue,
        terminal_growth=f.terminal_growth if terminal_growth is None else terminal_growth,
        mid_year=f.mid_year,
    )


def cost_of_capital(cfg: Config) -> tuple[float, float, float]:
    k = cfg.cost_of_capital
    beta = blume_adjust(k.raw_beta) if k.blume_adjust else k.raw_beta
    ke = capm_cost_of_equity(k.risk_free, beta, k.equity_risk_premium, k.country_risk_premium)
    w = wacc(ke, k.pre_tax_cost_of_debt, cfg.forecast.tax_rate, k.debt_to_capital)
    return beta, ke, w


def per_share_value(
    cfg: Config, scenario: Scenario, discount_rate: float, terminal_growth: float | None = None
) -> float:
    b = cfg.bridge
    br = equity_bridge(b.cash, b.debt, b.leases, b.other_claims, b.cash_haircut)
    res = run_dcf(
        cfg.forecast.base_revenue,
        dcf_assumptions(cfg, scenario, terminal_growth),
        discount_rate,
        cfg.forecast.base_year + 1,
    )
    return br.to_equity(res.enterprise_value) / cfg.company.diluted_shares


def value_company(cfg: Config) -> ValuationResult:
    case = select_case(cfg.history.ebitda, cfg.history.fcf)
    beta, ke, w = cost_of_capital(cfg)
    b = cfg.bridge
    br = equity_bridge(b.cash, b.debt, b.leases, b.other_claims, b.cash_haircut)
    shares = cfg.company.diluted_shares

    scenarios = []
    for s in cfg.forecast.scenarios:
        res = run_dcf(cfg.forecast.base_revenue, dcf_assumptions(cfg, s), w, cfg.forecast.base_year + 1)
        eq = br.to_equity(res.enterprise_value)
        scenarios.append(ScenarioOutcome(s, res, eq, eq / shares))

    comps, skipped = [], []
    for m in cfg.multiples:
        metric, kind = MULTIPLE_SPECS[m]
        stats = summarize_multiple(cfg.peers, m, min_peers=cfg.min_peers)
        metric_value = cfg.ltm.get(metric)
        if stats is None or metric_value is None or metric_value <= 0:
            skipped.append(m)
            continue
        vals = [
            implied_equity_value(x, metric_value, kind, br.net_adjustment) / shares
            for x in (stats.low, stats.median, stats.high)
        ]
        comps.append(CompsOutcome(stats, metric, metric_value, *vals))

    weights = cfg.weights_override or case.default_weights
    return ValuationResult(cfg, case, beta, ke, w, br, scenarios, comps, skipped, weights)


def implied_discount_rate(cfg: Config, target_price: float | None = None, tol: float = 1e-7) -> float | None:
    """Reverse DCF: the discount rate at which the base case equals the price.

    When a DCF shows a large gap to the market, the useful question is not
    "who is right" but "what is the market assuming?". If the implied rate
    is far above any reasonable cost of equity, the market is pricing lower
    cash flows than the base case (cyclicality, governance, regulation),
    not a higher discount rate — and the thesis has to address that.
    """
    price = cfg.company.price if target_price is None else target_price
    base = cfg.forecast.base
    g = cfg.forecast.terminal_growth
    lo, hi = g + 0.001, 1.0

    def f(r: float) -> float:
        return per_share_value(cfg, base, r) - price

    if f(lo) < 0 or f(hi) > 0:  # price outside the reachable range
        return None
    for _ in range(200):  # bisection: value is monotone decreasing in r
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2

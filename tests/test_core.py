import pytest

from erkit import (
    Case,
    DCFAssumptions,
    Peer,
    blume_adjust,
    capm_cost_of_equity,
    equity_bridge,
    relever_beta,
    run_dcf,
    select_case,
    summarize_multiple,
    unlever_beta,
    wacc,
)
from erkit.cases import convergence_margins

# ---------- cost of capital ----------


def test_blume_adjustment_shrinks_towards_one():
    assert blume_adjust(1.0) == pytest.approx(1.0)
    assert blume_adjust(2.08) == pytest.approx(1.7236)
    assert blume_adjust(0.5) > 0.5


def test_hamada_round_trip():
    asset = unlever_beta(1.5, debt_to_equity=0.4, tax_rate=0.25)
    assert relever_beta(asset, 0.4, 0.25) == pytest.approx(1.5)


def test_capm_and_wacc():
    ke = capm_cost_of_equity(0.04, 1.2, 0.05, country_risk_premium=0.01)
    assert ke == pytest.approx(0.11)
    assert wacc(ke, 0.06, 0.25, 0.0) == pytest.approx(ke)
    assert wacc(0.10, 0.06, 0.25, 0.3) == pytest.approx(0.7 * 0.10 + 0.3 * 0.045)


def test_invalid_rates_raise():
    with pytest.raises(ValueError):
        wacc(0.1, 0.05, 1.2, 0.2)
    with pytest.raises(ValueError):
        wacc(0.1, 0.05, 0.2, 1.0)


# ---------- case selection ----------


@pytest.mark.parametrize(
    "ebitda, fcf, expected",
    [
        ([100, 120, 140], None, Case.PROFITABLE),
        ([-50, 10, 20], None, Case.HIGH_GROWTH),  # only 2-year streak
        ([10, 20, 30, -5], None, Case.HIGH_GROWTH),  # streak must end in latest year
        ([None, 117, 304, 317], [None, None, 266, 313], Case.PROFITABLE),
        ([50, 60, 70], [10, -5, 20], Case.HIGH_GROWTH),  # negative FCF breaks the streak
    ],
)
def test_select_case(ebitda, fcf, expected):
    assert select_case(ebitda, fcf) is expected


def test_case_weights_follow_framework():
    assert Case.HIGH_GROWTH.default_weights == {"comps": 0.6, "dcf": 0.4}
    assert Case.PROFITABLE.default_weights == {"comps": 0.5, "dcf": 0.5}


def test_convergence_margins_reach_target_and_stay():
    m = convergence_margins(-0.10, 0.20, years=5, convergence_years=3)
    assert m == pytest.approx([0.0, 0.10, 0.20, 0.20, 0.20])


# ---------- DCF ----------


def _simple(mid_year=False, g=0.02):
    return DCFAssumptions(
        revenue_growth=[0.10],
        ebit_margin=[0.20],
        tax_rate=0.25,
        da_pct_revenue=0.0,
        capex_pct_revenue=0.0,
        nwc_pct_incremental_revenue=0.0,
        terminal_growth=g,
        mid_year=mid_year,
    )


def test_dcf_matches_hand_calculation():
    # Revenue 110, EBIT 22, NOPAT 16.5 = FCF. PV = 15.0
    # TV = 16.5 × 1.02 / 0.08 = 210.375 ; PV TV = 191.25 ; EV = 206.25
    res = run_dcf(100, _simple(), wacc=0.10, first_year=2027)
    assert res.fcff == pytest.approx([16.5])
    assert res.terminal_value == pytest.approx(210.375)
    assert res.enterprise_value == pytest.approx(206.25)
    assert res.years == [2027]


def test_mid_year_convention_raises_value():
    end = run_dcf(100, _simple(mid_year=False), 0.10, 2027).enterprise_value
    mid = run_dcf(100, _simple(mid_year=True), 0.10, 2027).enterprise_value
    assert mid > end


def test_dcf_working_capital_and_capex_reduce_fcf():
    a = DCFAssumptions([0.10], [0.20], 0.25, 0.02, 0.05, 0.10, 0.02, False)
    res = run_dcf(100, a, 0.10, 2027)
    # NOPAT 16.5 + D&A 2.2 − capex 5.5 − ΔNWC 1.0
    assert res.fcff[0] == pytest.approx(12.2)


def test_dcf_rejects_growth_above_wacc():
    with pytest.raises(ValueError, match="must exceed terminal growth"):
        run_dcf(100, _simple(g=0.10), wacc=0.10, first_year=2027)


def test_implied_exit_multiple():
    res = run_dcf(100, _simple(), 0.10, 2027)
    assert res.implied_exit_ev_ebitda == pytest.approx(210.375 / 22)


# ---------- bridge ----------


def test_equity_bridge_with_haircut_and_claims():
    br = equity_bridge(cash=1000, debt=100, leases=50, other_claims=200, cash_haircut=0.25)
    assert br.usable_cash == 750
    assert br.to_equity(3000) == pytest.approx(3400)
    assert br.to_enterprise(3400) == pytest.approx(3000)


# ---------- comps ----------


def _peers(values):
    return [Peer(f"P{i}", f"T{i}", {"ev_ebitda": v}) for i, v in enumerate(values)]


def test_outlier_is_excluded_and_reported():
    stats = summarize_multiple(_peers([4.51, 4.91, 8.4, 29.4]), "ev_ebitda")
    assert stats is not None
    assert "T3" in stats.excluded
    assert stats.median == pytest.approx(4.91)
    assert stats.n == 3


def test_too_few_peers_returns_none():
    assert summarize_multiple(_peers([5.0, 6.0]), "ev_ebitda") is None


def test_missing_and_negative_multiples_are_ignored():
    stats = summarize_multiple(_peers([5.0, None, -3.0, 6.0, 7.0]), "ev_ebitda")
    assert stats.n == 3
    assert set(stats.missing) == {"T1", "T2"}


def test_quartiles_match_excel_quartile_inc():
    stats = summarize_multiple(_peers([1, 2, 3, 4]), "ev_ebitda")
    assert (stats.low, stats.high) == pytest.approx((1.75, 3.25))

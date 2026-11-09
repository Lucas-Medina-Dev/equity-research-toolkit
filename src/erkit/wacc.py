"""Cost of capital: CAPM, beta adjustments and WACC."""

from __future__ import annotations


def blume_adjust(raw_beta: float) -> float:
    """Blume (1975) adjustment: shrink an observed beta towards 1.

    Observed betas mean-revert; the adjustment ``0.67 * beta + 0.33`` is the
    convention used by most data vendors. It matters most for short trading
    histories such as recent IPOs.
    """
    return 0.67 * raw_beta + 0.33


def unlever_beta(levered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada: remove the effect of financial leverage from an equity beta."""
    _check_rate(tax_rate, "tax_rate")
    if debt_to_equity < 0:
        raise ValueError("debt_to_equity must be >= 0")
    return levered_beta / (1 + (1 - tax_rate) * debt_to_equity)


def relever_beta(unlevered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada: apply a target capital structure to an asset beta."""
    _check_rate(tax_rate, "tax_rate")
    if debt_to_equity < 0:
        raise ValueError("debt_to_equity must be >= 0")
    return unlevered_beta * (1 + (1 - tax_rate) * debt_to_equity)


def capm_cost_of_equity(
    risk_free: float, beta: float, equity_risk_premium: float, country_risk_premium: float = 0.0
) -> float:
    """CAPM with an optional additive country risk premium."""
    return risk_free + beta * equity_risk_premium + country_risk_premium


def wacc(
    cost_of_equity: float,
    pre_tax_cost_of_debt: float,
    tax_rate: float,
    debt_to_capital: float,
) -> float:
    """Weighted average cost of capital at a target debt / (debt + equity)."""
    _check_rate(tax_rate, "tax_rate")
    if not 0 <= debt_to_capital < 1:
        raise ValueError("debt_to_capital must be in [0, 1)")
    equity_weight = 1 - debt_to_capital
    return equity_weight * cost_of_equity + debt_to_capital * pre_tax_cost_of_debt * (1 - tax_rate)


def _check_rate(value: float, name: str) -> None:
    if not 0 <= value < 1:
        raise ValueError(f"{name} must be in [0, 1), got {value}")

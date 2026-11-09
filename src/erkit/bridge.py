"""Enterprise value → equity value bridge.

For brokers and other regulated platforms, not all balance-sheet cash is
excess cash: part of it backs regulatory capital and cannot be distributed.
``cash_haircut`` removes that share before adding cash to enterprise value.
Committed outflows (e.g. a signed acquisition not yet closed) are deducted
as ``other_claims`` so they are not counted as distributable cash.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquityBridge:
    cash: float
    cash_haircut: float
    debt: float
    leases: float
    other_claims: float

    @property
    def usable_cash(self) -> float:
        return self.cash * (1 - self.cash_haircut)

    @property
    def net_adjustment(self) -> float:
        """Amount to add to enterprise value to reach equity value."""
        return self.usable_cash - self.debt - self.leases - self.other_claims

    def to_equity(self, enterprise_value: float) -> float:
        return enterprise_value + self.net_adjustment

    def to_enterprise(self, equity_value: float) -> float:
        return equity_value - self.net_adjustment


def equity_bridge(
    cash: float,
    debt: float = 0.0,
    leases: float = 0.0,
    other_claims: float = 0.0,
    cash_haircut: float = 0.0,
) -> EquityBridge:
    if not 0 <= cash_haircut <= 1:
        raise ValueError("cash_haircut must be in [0, 1]")
    if min(cash, debt, leases, other_claims) < 0:
        raise ValueError("bridge items must be non-negative")
    return EquityBridge(cash, cash_haircut, debt, leases, other_claims)

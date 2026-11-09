"""erkit — equity research toolkit.

A small, tested valuation engine implementing a two-case DCF framework
(high-growth / pre-profit vs consistently profitable), trading comparables
with outlier control, scenario weighting, sensitivity analysis and an
Excel export with live formulas.
"""

from erkit.bridge import EquityBridge, equity_bridge
from erkit.cases import Case, select_case
from erkit.comps import MultipleStats, Peer, summarize_multiple
from erkit.dcf import DCFAssumptions, DCFResult, run_dcf
from erkit.valuation import ValuationResult, value_company
from erkit.wacc import blume_adjust, capm_cost_of_equity, relever_beta, unlever_beta, wacc

__all__ = [
    "Case",
    "DCFAssumptions",
    "DCFResult",
    "EquityBridge",
    "MultipleStats",
    "Peer",
    "ValuationResult",
    "blume_adjust",
    "capm_cost_of_equity",
    "equity_bridge",
    "relever_beta",
    "run_dcf",
    "select_case",
    "summarize_multiple",
    "unlever_beta",
    "value_company",
    "wacc",
]

__version__ = "0.1.0"

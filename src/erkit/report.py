"""Plain-text and Markdown summaries of a valuation."""

from __future__ import annotations

from erkit.valuation import ValuationResult, implied_discount_rate


def summary_markdown(r: ValuationResult) -> str:
    cfg = r.config
    c = cfg.company
    implied = implied_discount_rate(cfg)
    lines = [
        f"## {c.name} ({c.ticker}) — {r.rating}",
        "",
        f"*{r.case.label}. Price ${c.price:.2f} ({c.price_date}).*",
        "",
        "| | Value per share |",
        "|---|---:|",
    ]
    for s in r.scenarios:
        lines.append(f"| DCF — {s.scenario.name} ({s.scenario.weight:.0%}) | ${s.per_share:,.2f} |")
    lines.append(f"| **DCF, probability-weighted** | **${r.dcf_per_share:,.2f}** |")
    for comp in r.comps:
        lines.append(
            f"| Comps {comp.stats.multiple} median {comp.stats.median:.1f}x "
            f"({', '.join(comp.stats.used)}) | ${comp.per_share_mid:,.2f} |"
        )
    lines += [
        f"| **Blended ({r.weights['dcf']:.0%} DCF / {r.weights['comps']:.0%} comps)** "
        f"| **${r.blended_per_share:,.2f}** |",
        f"| Upside vs price | {r.upside:+.1%} |",
        "",
        f"- WACC {r.wacc:.2%} (beta {r.beta:.2f}, cost of equity {r.cost_of_equity:.2%})",
        f"- Base case: terminal value = {r.base.dcf.terminal_share_of_ev:.0%} of EV, "
        f"implied exit multiple {r.base.dcf.implied_exit_ev_ebitda:.1f}x EBITDA",
    ]
    if implied is not None:
        lines.append(f"- Reverse DCF: the share price implies a {implied:.1%} discount rate on the base case")
    for comp in r.comps:
        if comp.stats.excluded:
            ex = ", ".join(f"{t} {v:.1f}x" for t, v in comp.stats.excluded.items())
            lines.append(f"- {comp.stats.multiple}: excluded as outlier — {ex}")
    for m in r.skipped_multiples:
        lines.append(f"- {m}: not used, fewer than {cfg.min_peers} valid peers")
    return "\n".join(lines) + "\n"

"""Command line: ``erkit value examples/etoro.yaml --out output/``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from erkit.charts import football_field
from erkit.config import load_config
from erkit.excel import export_workbook
from erkit.report import summary_markdown
from erkit.valuation import implied_discount_rate, value_company


def _value(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    r = value_company(cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = cfg.company.ticker.lower()

    md = summary_markdown(r)
    (out / f"{stem}_summary.md").write_text(md, encoding="utf-8")
    export_workbook(r, out / f"{stem}_valuation.xlsx")
    football_field(r, out / f"{stem}_football_field.png")
    (out / f"{stem}_valuation.json").write_text(
        json.dumps(
            {
                "ticker": cfg.company.ticker,
                "case": r.case.value,
                "rating": r.rating,
                "price": cfg.company.price,
                "dcf_per_share": round(r.dcf_per_share, 4),
                "comps_per_share": None if r.comps_per_share is None else round(r.comps_per_share, 4),
                "blended_per_share": round(r.blended_per_share, 4),
                "upside": round(r.upside, 4),
                "wacc": round(r.wacc, 6),
                "implied_discount_rate": implied_discount_rate(cfg),
                "scenarios": {s.scenario.name: round(s.per_share, 4) for s in r.scenarios},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(md)
    print(f"Outputs written to {out.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="erkit", description="Equity research valuation toolkit")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("value", help="value a company from a YAML file")
    p.add_argument("config", help="path to the company YAML")
    p.add_argument("--out", default="output", help="output directory (default: output/)")
    p.set_defaults(func=_value)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

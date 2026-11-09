"""Excel export with live formulas.

The DCF sheet is not a dump of Python numbers: every projection line is an
Excel formula pointing at named input cells, so a reviewer can change the
WACC or a margin in the workbook and watch the valuation move. The test
suite recalculates the workbook (LibreOffice) and checks it matches the
Python engine to the cent.

Colour code (banking convention): blue = hard-coded input, black = formula.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

from erkit.kpis import fintech_kpis
from erkit.sensitivity import margin_growth_grid, wacc_growth_grid
from erkit.valuation import ValuationResult, implied_discount_rate

NAVY = "0B1F3A"
INPUT_BLUE = Font(color="1F4FD1")
BOLD = Font(bold=True)
HEADER = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
SUBTLE_FILL = PatternFill("solid", fgColor="EEF2F8")
THIN = Side(style="thin", color="B8C2D1")
TOP_BORDER = Border(top=THIN)
PCT = "0.0%"
NUM = "#,##0.0;(#,##0.0)"
PRICE = '"$"#,##0.00'
MULT = '0.0"x"'


def _title(ws, text: str, sub: str = "") -> None:
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="5A6B85")


def _header_row(ws, row: int, values: list, start_col: int = 1) -> None:
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=start_col + i, value=v)
        c.font = HEADER
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center")


def _name(wb: Workbook, name: str, ref: str) -> None:
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def _inputs_sheet(wb: Workbook, r: ValuationResult) -> None:
    cfg = r.config
    k, f, b, c = cfg.cost_of_capital, cfg.forecast, cfg.bridge, cfg.company
    ws = wb.create_sheet("Inputs")
    _title(ws, "Inputs", "Blue = hard-coded input · black = formula. Change any blue cell.")
    rows = [
        # (label, name, value or formula, fmt, is_input)
        ("Risk-free rate", "rf", k.risk_free, "0.00%", True),
        ("Equity risk premium", "erp", k.equity_risk_premium, "0.00%", True),
        ("Raw beta", "raw_beta", k.raw_beta, "0.00", True),
        ("Apply Blume adjustment (1 = yes)", "blume", 1 if k.blume_adjust else 0, "0", True),
        ("Beta used", "beta", "=IF(blume=1,0.67*raw_beta+0.33,raw_beta)", "0.00", False),
        ("Country risk premium", "crp", k.country_risk_premium, PCT, True),
        ("Cost of equity (CAPM)", "ke", "=rf+beta*erp+crp", "0.00%", False),
        ("Pre-tax cost of debt", "kd", k.pre_tax_cost_of_debt, PCT, True),
        ("Debt / capital", "dtc", k.debt_to_capital, PCT, True),
        ("Tax rate", "tax", f.tax_rate, PCT, True),
        ("WACC", "wacc", "=(1-dtc)*ke+dtc*kd*(1-tax)", "0.00%", False),
        (None, None, None, None, None),
        (f"Base revenue {f.base_year}E ({c.units})", "base_rev", f.base_revenue, NUM, True),
        ("D&A, % revenue", "da_pct", f.da_pct_revenue, PCT, True),
        ("Capex, % revenue", "capex_pct", f.capex_pct_revenue, PCT, True),
        ("NWC, % incremental revenue", "nwc_pct", f.nwc_pct_incremental_revenue, PCT, True),
        ("Terminal growth", "tg", f.terminal_growth, PCT, True),
        ("Mid-year convention (1 = yes)", "midyear", 1 if f.mid_year else 0, "0", True),
        (None, None, None, None, None),
        ("Cash & short-term investments", "cash", b.cash, NUM, True),
        ("Cash haircut (regulatory capital)", "haircut", b.cash_haircut, PCT, True),
        ("Financial debt", "debt", b.debt, NUM, True),
        ("Lease liabilities", "leases", b.leases, NUM, True),
        ("Other claims", "other_claims", b.other_claims, NUM, True),
        ("Diluted shares (m)", "shares", c.diluted_shares, "#,##0.00", True),
        (f"Share price ({c.price_date})", "price", c.price, PRICE, True),
    ]
    for i, (label, name, val, fmt, is_input) in enumerate(rows, start=4):
        if label is None:
            continue
        ws.cell(row=i, column=1, value=label)
        cell = ws.cell(row=i, column=2, value=val)
        cell.number_format = fmt
        if is_input:
            cell.font = INPUT_BLUE
        else:
            cell.font = BOLD
        _name(wb, name, f"Inputs!$B${i}")
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 14


def _dcf_sheet(wb: Workbook, r: ValuationResult) -> None:
    cfg = r.config
    base = r.base
    n = len(base.dcf.years)
    ws = wb.create_sheet("DCF")
    _title(
        ws,
        f"DCF — base case ({cfg.company.units} {cfg.company.currency})",
        f"{r.case.label}. Live formulas: edit growth / margin rows or the Inputs sheet.",
    )
    cols = [get_column_letter(3 + i) for i in range(n)]
    _header_row(ws, 4, ["", f"{cfg.forecast.base_year}E"] + [f"{y}E" for y in base.dcf.years])

    labels = {
        5: "Revenue growth",
        6: cfg.company.revenue_label,
        7: "EBIT margin",
        8: "EBIT",
        9: "Taxes on EBIT",
        10: "NOPAT",
        11: "+ D&A",
        12: "− Capex",
        13: "− Δ NWC",
        14: "Unlevered FCF",
        15: "Discount period",
        16: "Discount factor",
        17: "PV of FCF",
    }
    for row, lab in labels.items():
        ws.cell(row=row, column=1, value=lab)
    ws["B6"] = "=base_rev"
    ws["B6"].number_format = NUM

    for i, col in enumerate(cols):
        prev = "B" if i == 0 else cols[i - 1]
        g = ws[f"{col}5"]
        g.value = base.scenario.revenue_growth[i]
        g.font, g.number_format = INPUT_BLUE, PCT
        m = ws[f"{col}7"]
        m.value = base.scenario.ebit_margin[i]
        m.font, m.number_format = INPUT_BLUE, PCT
        formulas = {
            6: f"={prev}6*(1+{col}5)",
            8: f"={col}6*{col}7",
            9: f"=-{col}8*tax",
            10: f"={col}8+{col}9",
            11: f"={col}6*da_pct",
            12: f"=-{col}6*capex_pct",
            13: f"=-({col}6-{prev}6)*nwc_pct",
            14: f"={col}10+{col}11+{col}12+{col}13",
            15: f"={i + 1}-0.5*midyear",
            16: f"=1/(1+wacc)^{col}15",
            17: f"={col}14*{col}16",
        }
        for row, fx in formulas.items():
            cell = ws[f"{col}{row}"]
            cell.value = fx
            cell.number_format = "0.00" if row in (15, 16) else NUM
    for row in (14, 17):
        for col in ["A"] + cols:
            ws[f"{col}{row}"].font = BOLD
            ws[f"{col}{row}"].border = TOP_BORDER

    last = cols[-1]
    out = [
        ("Sum of PV of FCF", f"=SUM({cols[0]}17:{last}17)", NUM),
        ("Terminal value (Gordon)", f"={last}14*(1+tg)/(wacc-tg)", NUM),
        ("PV of terminal value", f"=B20/(1+wacc)^{n}", NUM),
        ("Enterprise value", "=B19+B21", NUM),
        ("Terminal value, % of EV", "=B21/B22", PCT),
        ("Implied exit EV/EBITDA", f"=B20/({last}8+{last}11)", MULT),
        ("+ Usable cash", "=cash*(1-haircut)", NUM),
        ("− Debt, leases, other claims", "=-(debt+leases+other_claims)", NUM),
        ("Equity value", "=B22+B25+B26", NUM),
        ("Value per share", "=B27/shares", PRICE),
        ("Upside vs share price", "=B28/price-1", PCT),
    ]
    for i, (lab, fx, fmt) in enumerate(out, start=19):
        ws.cell(row=i, column=1, value=lab)
        c = ws.cell(row=i, column=2, value=fx)
        c.number_format = fmt
    for row in (22, 27, 28):
        ws[f"A{row}"].font = ws[f"B{row}"].font = BOLD
        ws[f"A{row}"].fill = ws[f"B{row}"].fill = SUBTLE_FILL
    ws.column_dimensions["A"].width = 30
    for col in ["B"] + cols:
        ws.column_dimensions[col].width = 12
    ws.freeze_panes = "B5"


def _grid_sheet(ws, df, top: int, title: str, row_fmt: str, col_fmt: str) -> None:
    ws.cell(row=top, column=1, value=title).font = BOLD
    ws.cell(row=top + 1, column=1, value=f"{df.index.name} ↓ / {df.columns.name} →").font = Font(
        italic=True, color="5A6B85"
    )
    for j, colv in enumerate(df.columns, start=2):
        c = ws.cell(row=top + 1, column=j, value=float(colv))
        c.number_format, c.font, c.fill = col_fmt, HEADER, HEADER_FILL
    for i, (idx, row) in enumerate(df.iterrows(), start=top + 2):
        c = ws.cell(row=i, column=1, value=float(idx))
        c.number_format, c.font = row_fmt, BOLD
        for j, v in enumerate(row.values, start=2):
            ws.cell(row=i, column=j, value=round(float(v), 4)).number_format = PRICE
    rng = f"B{top + 2}:{get_column_letter(1 + len(df.columns))}{top + 1 + len(df)}"
    ws.conditional_formatting.add(
        rng,
        ColorScaleRule(
            start_type="min",
            start_color="F4CCCC",
            mid_type="percentile",
            mid_value=50,
            mid_color="FFFFFF",
            end_type="max",
            end_color="CDE6D0",
        ),
    )


def _sensitivity_sheet(wb: Workbook, r: ValuationResult) -> None:
    ws = wb.create_sheet("Sensitivity")
    _title(
        ws,
        "Sensitivity — value per share, base case",
        "Values computed by the Python engine (Excel data tables are not portable).",
    )
    _grid_sheet(ws, wacc_growth_grid(r.config, r.wacc), 4, "WACC × terminal growth", PCT, PCT)
    _grid_sheet(
        ws,
        margin_growth_grid(r.config, r.wacc),
        13,
        "EBIT margin shift × revenue growth shift (whole path)",
        "+0.0%;-0.0%;0.0%",
        "+0.0%;-0.0%;0.0%",
    )
    ws.column_dimensions["A"].width = 34


def _scenarios_sheet(wb: Workbook, r: ValuationResult) -> None:
    ws = wb.create_sheet("Scenarios")
    _title(ws, "Scenarios", "Probability-weighted DCF")
    _header_row(ws, 4, ["Scenario", "Weight", "EV", "Equity value", "Per share", "TV % EV", "Exit EV/EBITDA"])
    for i, s in enumerate(r.scenarios, start=5):
        vals = [
            s.scenario.name,
            s.scenario.weight,
            s.dcf.enterprise_value,
            s.equity_value,
            s.per_share,
            s.dcf.terminal_share_of_ev,
            s.dcf.implied_exit_ev_ebitda,
        ]
        fmts = [None, PCT, NUM, NUM, PRICE, PCT, MULT]
        for j, (v, fm) in enumerate(zip(vals, fmts, strict=False), start=1):
            c = ws.cell(row=i, column=j, value=v)
            if fm:
                c.number_format = fm
    last = 4 + len(r.scenarios)
    ws.cell(row=last + 1, column=1, value="Weighted").font = BOLD
    c = ws.cell(row=last + 1, column=5, value=f"=SUMPRODUCT(B5:B{last},E5:E{last})")
    c.number_format, c.font = PRICE, BOLD
    for j, w in enumerate([14, 10, 12, 14, 12, 10, 16], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w


def _comps_sheet(wb: Workbook, r: ValuationResult) -> None:
    cfg = r.config
    ws = wb.create_sheet("Comps")
    _title(
        ws,
        "Trading comparables",
        "Outliers removed with Tukey fences (1.5 × IQR). Excluded peers kept for transparency.",
    )
    _header_row(ws, 4, ["Peer", "Ticker", "EV/EBITDA", "EV/Revenue", "P/E", "As of", "Source"])
    for i, p in enumerate(cfg.peers, start=5):
        vals = [
            p.name,
            p.ticker,
            p.multiples.get("ev_ebitda"),
            p.multiples.get("ev_revenue"),
            p.multiples.get("pe"),
            p.as_of,
            p.source,
        ]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=i, column=j, value=v)
            if j in (3, 4, 5) and v is not None:
                c.number_format = MULT
    row = 6 + len(cfg.peers)
    for comp in r.comps:
        s = comp.stats
        ws.cell(row=row, column=1, value=f"{s.multiple} — used: {', '.join(s.used)}").font = BOLD
        if s.excluded:
            ws.cell(row=row, column=4, value=f"excluded (outlier): {', '.join(s.excluded)}").font = Font(
                italic=True, color="B42318"
            )
        for k, (lab, v, ps) in enumerate(
            [
                ("Q1", s.low, comp.per_share_low),
                ("Median", s.median, comp.per_share_mid),
                ("Q3", s.high, comp.per_share_high),
            ],
            start=1,
        ):
            ws.cell(row=row + k, column=1, value=lab)
            ws.cell(row=row + k, column=2, value=v).number_format = MULT
            ws.cell(row=row + k, column=3, value=ps).number_format = PRICE
        row += 5
    for m in r.skipped_multiples:
        ws.cell(
            row=row, column=1, value=f"{m}: not used (fewer than {cfg.min_peers} valid peers)"
        ).font = Font(italic=True, color="5A6B85")
        row += 1
    for j, w in enumerate([34, 10, 12, 12, 10, 12, 10], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w


def _summary_sheet(wb: Workbook, r: ValuationResult) -> None:
    cfg = r.config
    ws = wb.active
    ws.title = "Summary"
    _title(
        ws,
        f"{cfg.company.name} ({cfg.company.ticker}) — valuation summary",
        f"{r.case.label} · price {cfg.company.price_date}",
    )
    implied = implied_discount_rate(cfg)
    rows = [
        ("Rating", r.rating, None),
        ("Share price", cfg.company.price, PRICE),
        ("Blended value per share", r.blended_per_share, PRICE),
        ("Upside", r.upside, PCT),
        (None, None, None),
        ("DCF (probability-weighted)", r.dcf_per_share, PRICE),
        ("Comps (median, average of multiples)", r.comps_per_share, PRICE),
        ("Weights DCF / comps", f"{r.weights['dcf']:.0%} / {r.weights['comps']:.0%}", None),
        (None, None, None),
        ("Beta (Blume-adjusted)" if cfg.cost_of_capital.blume_adjust else "Beta", r.beta, "0.00"),
        ("WACC", r.wacc, PCT),
        ("Reverse DCF: discount rate implied by price", implied, PCT),
    ]
    for i, (lab, v, fmt) in enumerate(rows, start=4):
        if lab is None:
            continue
        ws.cell(row=i, column=1, value=lab)
        c = ws.cell(row=i, column=2, value=v)
        if fmt:
            c.number_format = fmt
    ws["B4"].font = Font(bold=True, size=13, color={"BUY": "1E7B34", "SELL": "B42318"}.get(r.rating, NAVY))
    row = 17
    ws.cell(row=row, column=1, value="Fintech KPIs (last fiscal year)").font = BOLD
    for i, (k, v) in enumerate(fintech_kpis(cfg).items(), start=row + 1):
        ws.cell(row=i, column=1, value=k.replace("_", " "))
        c = ws.cell(row=i, column=2, value=v)
        c.number_format = PCT if v is not None and abs(v) < 5 else "#,##0"
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 16


def _sources_sheet(wb: Workbook, r: ValuationResult) -> None:
    ws = wb.create_sheet("Sources")
    _title(ws, "Sources")
    for i, (k, v) in enumerate(r.config.sources.items(), start=3):
        ws.cell(row=i, column=1, value=k).font = BOLD
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["B"].width = 110


def export_workbook(r: ValuationResult, path: str | Path) -> Path:
    wb = Workbook()
    _summary_sheet(wb, r)
    _inputs_sheet(wb, r)
    _dcf_sheet(wb, r)
    _scenarios_sheet(wb, r)
    _sensitivity_sheet(wb, r)
    _comps_sheet(wb, r)
    _sources_sheet(wb, r)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path

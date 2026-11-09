# Research framework — fintech equity research

This is the methodology `erkit` implements. It was written as the research framework for an equity research division covering listed fintechs (first coverage: eToro and Klarna). Reports are 5–8 pages, in English, and end with a **Buy / Hold / Sell** view **without a price target**: the valuation supports the view; a precise target would claim more accuracy than a student model can deliver.

## Report structure

| # | Section | What it must contain |
|---|---|---|
| 1 | **Company snapshot** | Profile, the business in one line, the investment view, key metrics table, share price performance, top 3 risks |
| 2 | **Business model** | Revenue streams, monetisation mechanics, customer segments, value proposition and moat, unit economics, regulatory context |
| 3 | **Industry & competitive positioning** | TAM, Porter's five forces, competitive landscape, positioning matrix, regulatory environment |
| 4 | **Financial analysis & fintech KPIs** | Standard financials, then KPIs by category (below) |
| 5 | **Valuation** | Case 1 or Case 2 DCF, trading comps, sensitivity, blended value |
| 6 | **Investment thesis, risks & final assessment** | Core thesis, bull and bear case, catalysts, what would change the view, 3×3 risk matrix, final assessment |

## Fintech KPIs

| Category | KPIs |
|---|---|
| Payments | TPV / GMV, take rate, transaction margin |
| Growth & unit economics | Revenue growth, funded accounts / active users, revenue per user, CAC and payback, AUA and revenue yield on AUA |
| Profitability signals | EBITDA margin trajectory (direction matters more than level), Rule of 40, FCF conversion (FCF / net income > 80% = high-quality earnings) |

**Benchmarking rule:** every metric is compared with at least two direct peers over at least three years. Show trends, not snapshots. If a metric deteriorated, explain why: acknowledging weakness makes the thesis more credible.

## Valuation

Valuation is a range, not a number. Always run **both** a DCF and trading comparables; the weight of each depends on the company's financial maturity.

**Decision rule.** Has the company had **3+ consecutive, most recent years of positive EBITDA** (and positive FCF where reported)? → `erkit.select_case`

| | Case 1 — High growth / pre-profit | Case 2 — Consistently profitable |
|---|---|---|
| Example | Klarna, early-stage fintechs | eToro post-IPO, mature fintechs |
| Primary comps | EV / Revenue | EV / EBITDA, P/E |
| DCF role | Sanity check, secondary weight | Co-primary |
| DCF design | Two phases: growth, then margin **convergence** to profitable peers | Standard FCFF, anchored on historical cash generation |
| Projection base | Revenue forecasts | Historical FCF |
| Terminal value | Gordon growth, 2–3%, only once margins have converged | Gordon growth, 2–3% |
| Weighting | **60% comps / 40% DCF** | **50% comps / 50% DCF** |

### Multiples

| Multiple | When to use | Notes |
|---|---|---|
| EV / Revenue | High-growth, pre-profit | Only if peers' revenue lines are comparable (gross vs net) |
| EV / EBITDA | EBITDA positive for 2+ years | More reliable than P/E for fintech |
| P/E | Net income consistently positive | Less relevant for high growth |
| EV / GMV or TPV | Payments, marketplaces | Volume as denominator |
| P / Book | Digital banks, lenders | Read alongside ROE |

### Non-negotiable DCF rules

1. Every assumption is sourced or explicitly justified. No numbers from thin air.
2. Run sensitivity on WACC × terminal growth **and** on the operating drivers (margin, growth).
3. Report the share of EV coming from the terminal value and the exit multiple it implies. Above ~75% of EV, the forecast period is too short or too conservative.
4. Terminal growth never exceeds long-run nominal GDP (2–3%).
5. When the DCF and the market disagree strongly, run a **reverse DCF** and explain what the market is pricing in.

## Review process

Analyst draft → Head of division review (numbers, sources, logic) → President review → publication. A report is blocked if any figure cannot be traced to a source.

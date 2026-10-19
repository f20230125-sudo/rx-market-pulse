# Rx Market Pulse

**What US Medicaid pays for prescription drugs, and why the bill keeps growing.** Seven years of public pharmacy-claims data (2019–2025, 36.1M rows) turned into a tested warehouse, a dashboard, a Power BI project and an Excel model, built as a commercial-analytics case study.

The three projects share one pipeline, so every number agrees across them.

**New: [Commercial Intelligence Agent](docs/commercial-intelligence.md)** at `/ask` in the dashboard. It investigates spending, territory rankings, forecasts and MSD product pipelines using five typed tools. It supports explicit guided mode or real-model inference, and passed 20 real-model smoke questions. [Evaluation artifact](docs/intelligence-evaluation.json).

| | Project | What it is | Tools |
|---|---|---|---|
| 1 | **Market Pulse** | Report and dashboard: where spend grew and why, who sells it, what happens when generics arrive, when patents end, state comparisons, a backtested forecast | DuckDB, SQL, Python, Next.js/TypeScript, Power BI |
| 2 | **Territory Targeting Model** | Excel workbook with live formulas: ranks the 51 states for a therapeutic area, tiers them A/B/C, splits a growth target | Excel (SUMIFS, INDEX/MATCH, PERCENTRANK, MAXIFS), checked against an independent Python calculation |
| 3 | **Drug Data Harmonisation & Quality** | Pipeline that keys 36M rows to products, harmonises names across four sources, quarantines bad rows, and scores itself with 19 checks | Python, DuckDB, SQL, pytest |

## What the data says

All figures are national Medicaid pharmacy spend, **gross of manufacturer rebates**.

- Spend rose **60%**, from $73.0B (2019) to **$116.9B** (2025), while prescriptions stayed level (725M).
- **Brands are 14% of prescriptions and 89% of spend**, and that share has risen every year.
- Why the bill grew, 2022 to 2025 (+$16.8B): fewer prescriptions took away $6.2B; a **shift to costlier products added $11.9B**; spend per prescription for the same product added $2.7B; new products added $8.9B. The five effects add up exactly (checked in tests).
- Immunology (+$12.4B) and diabetes and obesity (+$11.4B) account for more than half of the growth.
- **Two years after generics arrive, the median brand keeps 19% of its spend** (48 molecules). The spread is wide: one brand kept 3% after a year, another kept 76% after two.
- **$13.1B** of 2025 brand spend sits on products whose core patent or exclusivity ends in 2026–2028 (FDA Orange Book).
- Per-enrollee spend differs **3.5×** between the highest and lowest state, but states such as California (2022), New York (2023) and North Carolina changed how they report pharmacy spend, so their growth is not demand. The model flags and neutralises them.
- The forecast now uses **28 quarters**, with model selection on 2022–2023 and a separate 2024–2025 test. The frozen seasonal-drift choice **lost to the seasonal baseline** on that test (9.01% versus 5.54% WAPE). Its 2027 empirical scenario range is about **$117B–$140B**; these are summed quarterly error bounds, not a calibrated annual confidence interval. See [forecast methodology](docs/quarterly-forecast.md).

## The data-quality findings that shaped the build

Found by profiling, then turned into rules, checks and tests:

- **The 51 state rows add up to about 92% of the national total.** The source blanks any cell with fewer than 11 prescriptions in the state rows but counts it in the national row. Summing states would understate the market by 6–7%; national figures use the published national row.
- **Product names in the utilisation file are cut at exactly 10 characters** (`LEVOTHYROX`). Products are identified by NDC instead, joined to the product list and the FDA directory.
- **NDCs are written four ways** (11 digits, and hyphenated 4-4-2, 5-3-2, 5-4-1). A 10-digit code cannot be converted by padding the front; the hyphens say which segment to pad. The conversion is a tested function, and a SQL version used for speed is tested against it.
- 1,488 manufacturer name variants (and 235 labeler codes with more than one name) roll up to parent companies by rule plus a short, tested list of completed acquisitions. Spin-offs (Organon from Merck) are not folded back.
- A therapeutic area for **97.8% of spend**: FDA pharmacologic class first, then the same ingredient, then a curated name list; reviewing the 330 largest products by hand found about a dozen misclassifications (two multiple-sclerosis drugs in oncology, a muscular-dystrophy drug under respiratory), fixed by tightening rules and a short, documented override list. The remaining 2.2% is shown as "Unclassified", never spread across other areas.
- Puerto Rico appears from 2023 only and has no enrollment series, so it is a flagged territory, not a state.

See [`docs/data-quality-scorecard.md`](docs/data-quality-scorecard.md) (generated, not hand-written).

## Run it

```bash
pip install -r requirements.txt
python -m rx.fetch            # downloads ~3 GB of public files into data/raw (about 10 minutes)
python -m rx.build            # stage, model and marts into DuckDB (about 90 seconds)
python -m rx.dq               # data-quality scorecard
python -m rx.forecast         # quarterly forecast, separate model selection and test
pytest                        # 116 tests: unit tests plus data tests against the built warehouse

python -m rx.export_json      # JSON for the dashboard
cd dashboard && npm install && npm run build && npm run start   # http://localhost:3050
npm test && npx playwright test                                  # 27 unit tests, 15 end-to-end tests with axe

python -m rx.workbook         # excel/Territory-Targeting-Model.xlsx
python -m rx.powerbi          # powerbi/RxMarketPulse.pbip (open in Power BI Desktop, then Refresh now; see powerbi/README.md)
```

`data.cms.gov` blocks some regions; this project uses `data.medicaid.gov`, which does not, and openFDA.

## How it fits together

```
 data.medicaid.gov  State Drug Utilization (7 yearly files)  ─┐
 data.medicaid.gov  Drug Rebate Program product list          ─┤  rx.fetch   resumable downloads, row counts checked
 data.medicaid.gov  Medicaid + CHIP enrollment                ─┤      │
 openFDA            National Drug Code directory              ─┤      ▼
 FDA                Orange Book (patents, exclusivities)      ─┘  stage ── typed, nothing removed
                                                                   │
                                                  quarantine ◄─────┤  rows that cannot be keyed, with the reason
                                                                   ▼
                          dim_product (NDC) · dim_state · brand owner · therapeutic area   <- harmonisation
                                                                   │
                                                          fact_sdud (36M rows)
                                                                   ▼
        marts: market · area · product · owner · state · price-volume-mix · generic erosion · patent exposure · forecast
                  │                  │                    │                     │
             dashboard (JSON)    Excel workbook      Power BI project      data-quality scorecard
```

SQL lives in [`sql/`](sql) (numbered, one purpose each); Python in [`src/rx/`](src/rx). Reference rules a reviewer can edit without code: [`data/ref/`](data/ref).

## Verification

- **116 Python tests**: NDC conversion (and a parity test between the SQL and Python versions), manufacturer and ingredient harmonisation, therapeutic-area rules, and *data tests* on the built warehouse (row counts equal the source's published counts, no duplicate keys, mart totals add back to the published national total to the dollar, the price/volume/mix bridge closes).
- **Excel model verified by driving Excel itself**: six input scenarios are evaluated by Excel's own formulas through COM and compared, state by state, with a Python recalculation that shares no code with the workbook (`tools/verify_workbook.py`).
- **Power BI project**: generated from the warehouse, then opened in Power BI Desktop 2.158 to confirm the model loads, all 28 measures evaluate and six pages render; the headline figures match the dashboard (`powerbi/README.md`).
- **Dashboard**: 27 unit tests over the calculations, schema validation of every data file at build time, 15 end-to-end tests including axe accessibility scans in light and dark and a no-sideways-scroll check on a phone.

## What this is not

US Medicaid only, not the whole market and not the UAE (UAE pharmacy sales are not public). Amounts are gross reimbursed before rebates. Brand and generic follow the Medicaid program's own categories. Orange Book dates show where legal protection ends, not when a generic will launch, and biologics are not in the Orange Book. The method carries to any claims or sales data keyed by product; the geography is the example.

## Layout

```
src/rx/        fetch, build, dq, forecast, workbook, powerbi, export_json, and the tested harmonisation modules
sql/           00 macros · 01-02 staging · 03 quarantine · 04 dimensions · 05 facts · 06-11 marts
data/ref/      editable rule files (therapeutic areas, name rules, overrides, states)
data/marts/    the small analysis tables, committed
dashboard/     Next.js report, with tests
excel/         the workbook
powerbi/       Power BI project (TMDL + PBIR) and its CSVs
docs/          data-quality scorecard, case studies (interview order)
tests/  tools/ pytest suite; the Excel verification harness
```

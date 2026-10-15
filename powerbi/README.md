# Power BI project

`RxMarketPulse.pbip` is a Power BI Desktop **project**: plain-text folders instead of one opaque file, so the model, the DAX measures and every report page can be read, diffed and rebuilt.

```
powerbi/
  RxMarketPulse.pbip                  open this in Power BI Desktop (free, Windows)
  RxMarketPulse.SemanticModel/        TMDL: 11 tables, 9 relationships, 28 measures, one parameter (DataFolder)
  RxMarketPulse.Report/               PBIR: 6 pages, a custom theme
  data/                               the CSVs the model loads (generated, 30,372 rows)
```

## Open it

1. Open `RxMarketPulse.pbip` in Power BI Desktop.
2. If the project is not at `D:\claude-workspace\rx-analytics`, change the `DataFolder` parameter (Home, Transform data, Edit parameters) to the full path of the `powerbi\data\` folder, with a trailing backslash. Or run `python -m rx.powerbi` from the repository root, which rewrites the project with the right path.
3. Click **Refresh now** in the yellow banner (twice if it asks again). The project is saved without a data cache, so the first open loads the CSVs.

It was checked by opening it in Power BI Desktop 2.158 (September 2026): the model loads, the 11 tables fill, all 28 measures evaluate, and the six pages render. The headline figures match the web dashboard: $117bn spend in 2025, 725M prescriptions, $161 per prescription, 88.6% brand share of spend; Connecticut $2,139 per enrollee.

## The model

A star schema built from the analysis tables of the warehouse.

| Table | Grain | Role |
|---|---|---|
| `dim_year`, `dim_area`, `dim_state`, `dim_owner` | one row per year, therapeutic area, state, company | filter and label tables |
| `fact_product_year` | year, brand or molecule, brand/generic, owner, area | spend, prescriptions, units (30,000 rows; the long tail of small products keeps its area and owner) |
| `fact_state_area_year`, `fact_state_year` | state, year, area / state, year | state spend; enrollment and the reporting-break flag |
| `fact_pvm` | area, pair of years, step | price/volume/mix bridge |
| `fact_loe` | brand | patent and exclusivity end dates (FDA Orange Book) |
| `fact_erosion` | molecule, quarter since generic entry | brand spend index |
| `fact_quality` | check | the data-quality scorecard |

Columns carry unit suffixes (`spend_usd`, `rx_count`) because a measure and a column may not share a name in one table.

## The measures worth knowing

- **Spend (latest year)**, `VAR y = [Latest Year] RETURN CALCULATE([Spend], dim_year[year] = y)`. A measure cannot sit inside a `CALCULATE` filter, so the year is held in a variable first (Power BI rejected the first version with exactly that error).
- **Spend CAGR**, returns blank when the first year is zero. Without the guard a new product shows −100%.
- **Bridge Change**, picks the selected area and pair of years with `SELECTEDVALUE`, defaulting to "All areas" and 2022–2025, so the waterfall is meaningful with nothing selected.
- **Spend per Enrollee**, defaults to the latest year when no year is chosen. Without it the measure divides several years of spend by several years of enrollment.
- **Company Spend (latest year)**, returns blank for the "All other companies" row so the long tail does not dwarf the top 25 in the bar chart.
- **Median Brand Index**, `MEDIANX(VALUES(fact_erosion[ingredient]), CALCULATE(AVERAGE(...)))`: the median across molecules at each quarter since generic entry.

## Pages

Overview · Growth (the bridge and extra spend by area) · Companies (company slicer opens on Merck (MSD); its brands, growth and protection) · Generics and patents · States (per enrollee, with the reporting-break flag) · Data quality.

## How it was made

`python -m rx.powerbi` writes the whole project from the warehouse marts: CSVs, TMDL and PBIR. Generating it keeps the model, the measures and the report in step with the data, and means the project is reviewable text. Power BI Desktop is the test: each failure it reported (an unknown query group, a measure named like a column, a measure inside a filter, tables that only show "active" fields) was fixed in the generator.

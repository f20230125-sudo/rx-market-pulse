# Quarterly forecast and independent test

The original forecast had seven annual observations and used the same four origins to select and report its method. The replacement uses the warehouse's 28 national quarterly observations, 2019Q1–2025Q4, for each therapeutic area and the market total.

- Initial history: 2019–2021.
- Selection: expanding-origin forecasts whose targets lie in 2022–2023. Choose the lowest weighted absolute percentage error (WAPE) across horizons one to eight quarters.
- Independent test: freeze that choice before 2024, then predict 2024–2025 from expanding origins. Newly observed test history may train later forecasts, but never changes the selected method. Each prediction sees only values available at its origin.
- Final forecast: refit the frozen method on all observations through 2025Q4 and forecast eight quarters, through 2027Q4.

Methods: same quarter last year; that seasonal pattern scaled by the most recent annual growth; and a log-linear time trend with quarter indicators. WAPE is total absolute error divided by total actual spend. MAE, RMSE, nonzero-target MAPE and per-horizon results are exported too.

## Observed national result

| Method | Selection WAPE | Independent test WAPE |
|---|---:|---:|
| Seasonal baseline | 13.85% | **5.54%** |
| Seasonal drift (selected before test) | **3.65%** | 9.01% |
| Trend with quarter effects | 4.37% | 11.65% |

The selected method fails to beat the baseline. The report retains this result; it does not relabel the test as validation and select a new winner. More granularity strengthens the evaluation, not the claim that the model works better.

## Error scenarios

For each horizon, use the 10th and 90th percentiles of historical actual/predicted ratios, pooling neighboring horizons until at least eight residuals are available. Include the point forecast within the displayed bounds. Independent test coverage uses pre-test residuals only. The final forecast can use all historical out-of-origin residuals through 2025 for calibration.

These are empirical scenarios, not guaranteed 80% prediction intervals. Selection and calibration share the validation sample. The 36 overlapping forecast cases per evaluation period are not 36 independent observations. Eight-quarter-ahead accuracy has only one test case; the per-horizon table exposes this. Annual bounds sum quarterly bounds and do not imply a calibrated probability for the annual total.

The model forecasts gross US Medicaid pharmacy reimbursement, not MSD net revenue, UAE sales or patient demand.

Backtests use the current source snapshot, including retrospective harmonization and source revisions. They are not a simulation using historical data vintages.

## Reproduce

Run `python -m rx.forecast` after building the warehouse, or `python -m rx.forecast --inputs data/marts/forecast_quarterly_inputs.csv` to reproduce from the small committed input file without downloading the full warehouse. Full predictions, validation/test scores and coverage are in `forecast_evaluation.json`. `dashboard/public/data/forecast.json` supplies the report and the commercial agent.

Tests perturb all test outcomes to check that the selected method and validation scores cannot change; check origin/target isolation, seasonal alignment beyond a year, zero-valued series, invalid histories and bounds.

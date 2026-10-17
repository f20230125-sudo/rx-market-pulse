# Runbook

## Build

Install Python 3.11+, then run `python -m pip install -e ".[test]"` from this directory. `pai import-slices`, `pai build`, `pai export`, and `pai report` reproduce the delivered analysis offline once dependencies are installed. `data/raw` and `data/warehouse` are generated and ignored by Git.

`pai fetch --source-map data/source-map.json` downloads the exact original CMS bundles and NLM product references, records their SHA-256 hashes, and extracts only the required tables. It requires network access, several GB of temporary disk space and time to download the pharmacy-network-containing bundles. It does not extract the large pharmacy network table. The original acquisition ran successfully in GitHub Actions.

To update periods or products, change the explicit configuration and source map, verify the new record layout and catalogue, regenerate all outputs, and rerun the source audit and tests. Do not append a new contract year to the same analysis without plan lineage handling.

## Power BI

Open `powerbi/PayerAccess.pbip` in Power BI Desktop. The `DataFolder` Power Query parameter must point to the absolute `powerbi/data/` directory with a trailing backslash. `pai export` regenerates the parameter for the current checkout location. Refresh the model, check the four pages, test each slicer and the plan-to-strength interaction, then save a PBIX if needed.

Expected latest snapshot defaults: 367 plans, BELSOMRA 277 listed plans, 80.5075% weighted listing, and 100% of cohort plans with published enrollment. The investigation queue contains 70 plans and 3,212,054 associated members. Change-page PA additions and listing losses are zero, not missing data.

`tools/validate_model.ps1` calls the TMDL parser bundled with the installed Power BI Desktop. This validates semantic model structure without starting an analysis server. It does not execute DAX or render visuals. `python tools/validate_pbir.py` checks generated report JSON against Microsoft's published schemas and requires network access.

## Excel

Open `excel/Payer-Access-Intelligence.xlsx`, enable normal automatic calculation and use the `Analysis` sheet. Inputs are brand C6, strength view C7, region C8, snapshot F6, and minimum enrollment F7. The `Access` sheet contains the exact rows behind the formula results.

The initial view has accurate SQL-derived formula caches, so headline values are visible before recalculation. This is not evidence of Excel execution. `pai verify` performs the independent source audit and uses Excel COM to recalculate eight scenarios; it requires a usable Windows desktop session and `pywin32`. `python tools/verify_calc.py` tests the same scenarios using an installed LibreOffice Calc engine and reports that engine explicitly.

## Review and package

Read `outputs/source-audit.csv`, `outputs/build-receipt.json`, the quality and quarantine CSVs, and the validation receipts. `python tools/package.py` creates the portable portfolio ZIP, excluding generated raw downloads, the warehouse, fictional previews, temporary tests and private/local settings. No credentials or patient data are needed.

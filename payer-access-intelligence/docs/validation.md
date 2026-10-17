# Validation status

Evidence lives in `outputs/`; this file distinguishes implementation checks from application validation.

| Check | Result / receipt |
|---|---|
| Original CMS and NLM acquisition | [Successful run](https://github.com/f20230125-sudo/rx-market-pulse/actions/runs/39008455037); archive hashes and source row counts retained |
| Slice integrity | Every derivative SHA-256 checked before local import and build |
| Analytical failure modes | `tests/test_pipeline.py`; pytest results recorded in CI |
| Independent source audit | 20 sampled plan-brand-snapshot combinations, checked against direct source rows |
| SQL quality gates | Unique grains, no enrollment multiplication, unknown-source handling, paired-cohort handling; four unkeyed enrollment rows explicitly quarantined |
| Power BI semantic model | Microsoft's installed `TmdlSerializer` successfully parses the generated model; receipt `powerbi-model-validation.json` |
| Power BI report schemas | CI validates generated JSON against Microsoft-published schemas; 53 generated JSON files passed; receipt `pbir-schema-validation.json` |
| Workbook calculation | CI checks eight input scenarios / 64 headline values with LibreOffice Calc; all eight scenarios / 64 values passed; receipt `calc-validation.json` |
| Microsoft Excel calculation | Pending: COM activation fails with logon-session error `-2147023584`; no connected document-control session is available |
| Power BI Desktop visuals, DAX and PBIX | Pending: no usable interactive application session. No PBIX or Desktop screenshots are claimed |
| PDF report layout | Four static analytical pages rendered and inspected; generated directly from SQL marts, not exported from Desktop |

Fictional acceptance fixtures are isolated under `outputs/preview/`. They exercise suppression, missing enrollment, mixed flags, partial strength listing, and entries/exits that do not occur in the real two-snapshot cohort. They are not used for portfolio findings.

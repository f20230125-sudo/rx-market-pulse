# Methodology

## Population and dates

The universe is the **367 standalone PDPs present in the CMS plan-information public use file**, identified by `S` contracts. It is not every Medicare enrollee or every plan in the broader enrollment file. Employer plans and other plan types outside the formulary PUF are excluded by using the PUF plan list as the analysis universe. All plans in the delivered cohort have published enrollment and known source access in both snapshots.

The original bundles are `2026_20260122.zip` and `2026_20260819.zip`. Their source member names include `20260131` and `20260831`. Both are contract year 2026. The analysis labels the observations by month and retains the exact archive URL, member filename and acquisition date. It does not claim that all source components were measured on an identical day.

Sources of record:

- [CMS monthly formulary files](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information)
- [CMS plan-level enrollment](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/monthly-enrollment-plan)
- [2026 record layout](https://data.cms.gov/sites/default/files/2025-10/0564eb37-402d-4110-bd98-2d5399dc30e7/PUFRecordLayout-2026.pdf)
- [CMS agreement for use](https://data.cms.gov/sites/default/files/2023-10/4eeb19e1-525b-4a4e-9766-b33ff084fc5c/AGREEMENT-FOR-USE.pdf)
- DailyMed SPL records and RxNorm brand-associated clinical drug concepts from the US National Library of Medicine. Exact IDs, URLs and hashes are in `data/extracts/manifest.json` and `products/catalog.json`.

## Grain and harmonization

| Dataset | Grain |
|---|---|
| `plan_month` | snapshot × contract-plan |
| `drug_strength` | snapshot × formulary × brand × strength |
| `fact_strength` | snapshot × plan × brand × strength |
| `fact_brand` | snapshot × plan × brand |
| `fact_change` | matched/entered/exited plan × brand × strength |
| `fact_brand_change` | known matched plan × brand, carrying August enrollment |
| `mart_review_queue` | one latest-snapshot BELSOMRA plan |

PDP segment IDs must be zero. Plan and formulary identifiers remain text, including leading zeros. NDC conversion uses the segment widths; ambiguous ten-digit unhyphenated codes are rejected. RxCUIs identify the eight branded tablet strengths: BELSOMRA 5/10/15/20 mg, DAYVIGO 5/10 mg and QUVIVIQ 25/50 mg. No clinical equivalence between strengths or brands is implied.

The original plan text contains Windows-1252 characters. A strict UTF-8 validation pass selects UTF-8 when valid; otherwise the reader uses Windows-1252. Transferred slices are UTF-8 with a BOM. Hashes distinguish original bytes from converted derivatives.

Four enrollment rows have blank plan IDs: contracts S3875 and S6939 in each month, with suppressed enrollment values. They cannot be assigned to a plan and are retained in `mart_quarantine`, with original row numbers and explicit reasons. They are not treated as zero-member plans.

## Definitions

- **Listed:** at least one source record for the selected branded strength, with known plan-source access.
- **Any strength:** at least one catalogued strength listed. **All strengths:** every catalogued strength listed. Both coincide within each observed brand-plan in the delivered real data, but acceptance tests cover partial-strength listing.
- **Unlisted:** the assigned formulary is present in the full source and no matching record exists. This does not rule out exceptions or establish that a particular claim will be denied.
- **Unknown:** plan suppression is flagged/unknown, or the assigned formulary is absent from the full source.
- **Plan listing rate:** listed plans / plans with known access in the selected snapshot and view.
- **Enrollment-weighted listing:** published enrollment in listed plans / published enrollment in all known-access plans. Missing enrollment is excluded from both weighted components and disclosed separately.
- **PA/ST/QL:** prior authorization, step therapy and quantity limits. These are separate fields. Package disagreements produce `Mixed`; missing values produce `Unknown`. Brand summaries preserve mixed flags across strengths.
- **Tier:** the published number within that plan. It is not a universal preference, copay or clinical ranking.

The `any_no_pa_st` flag requires a listed strength with neither PA nor ST. It says nothing about QL, affordability, indication-specific criteria or actual dispensing. Indication-based records are explicitly checked; none match the selected eight strengths in these snapshots.

## Comparing snapshots

Plan entries/exits and unknown access are distinguished from real listing changes. The fixed-weight comparison uses the intersection of plans with known listing at both dates, carries **August enrollment to both observations**, and holds the cohort fixed. It therefore separates changes in published listing from changes in enrollment composition. In this case the listing sets and binary restriction flags are unchanged, so the difference in actual monthly weighted rates comes from enrollment composition within the observed cohort.

Tier and quantity-limit detail are retained at strength level for inspection. A stable binary QL flag does not mean the permitted amount/days or all clinical criteria are unchanged. No causal effect on sales, uptake, health outcomes or prescribing is estimated.

## Investigation queue

One latest-snapshot BELSOMRA plan qualifies if it loses a strength, adds PA/ST, or is unlisted while DAYVIGO or QUVIVIQ is listed. Source uncertainty excludes it from a definite access-gap conclusion. Category precedence is strength loss, added restriction, then comparator-only listing. Within a category, associated reported enrollment helps order document review; there is no opaque composite score.

The delivered queue is entirely the comparator-only category: 70 plans, 3,212,054 reported members. Plan membership is counted once in the queue even when both comparators are listed. No revenue conversion factor is applied.

## Provenance and limits

The compact source slices were created from **original CMS downloads**, not the third-party GitHub mirrors reviewed during planning. The original archive hashes, extracted file hashes, full row counts, transformation code and acquisition run URL remain available. Local builds verify every transferred derivative hash before reading it. A hash demonstrates integrity relative to a recorded acquisition; it does not constitute independent substantive validation of CMS's inputs.

Coverage is descriptive, historical and US PDP-specific. It does not establish Gulf access, individual eligibility, actual drug usage, benefit affordability, appropriateness of a restriction or a commercial intervention's effect. Snapshot data can differ from current payer documents. Recheck those documents before operational use.

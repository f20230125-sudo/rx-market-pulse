-- One plan per month. Enrollment never joins directly to drug-package rows.
CREATE OR REPLACE TABLE dim_snapshot AS
SELECT DISTINCT month, 2026 AS contract_year FROM raw_plans;
CREATE OR REPLACE TABLE dim_brand AS SELECT DISTINCT brand FROM raw_products;
CREATE OR REPLACE TABLE plan_month AS
SELECT p.month, p.plan_key, p.contract_id, p.plan_id, p.plan_name, p.organization,
       p.formulary_id, CAST(p.region_code AS INTEGER) region_code, p.region,
       p.suppressed, CAST(p.formulary_complete AS INTEGER) formulary_complete,
       CAST(p.source_row AS INTEGER) plan_source_row,
       TRY_CAST(e.enrollment AS BIGINT) enrollment,
       TRY_CAST(e.enrollment_source_row AS INTEGER) enrollment_source_row
FROM raw_plans p LEFT JOIN raw_enrollment e USING(month, plan_key);
CREATE OR REPLACE TABLE dim_plan AS
SELECT plan_key, contract_id, plan_id, plan_name, organization, region_code, region
FROM plan_month QUALIFY row_number() OVER(PARTITION BY plan_key ORDER BY month DESC)=1;

-- Package records collapse to strength. Conflicting restrictions are 'Mixed', not guessed.
CREATE OR REPLACE TABLE drug_strength AS
SELECT month, formulary_id, brand, CAST(strength_mg AS INTEGER) strength_mg,
       count(*) source_records, count(DISTINCT ndc) package_count,
       string_agg(DISTINCT rxcui, ';' ORDER BY rxcui) rxcuis,
       string_agg(DISTINCT tier, ';' ORDER BY tier) tiers,
       CASE WHEN count(pa)=0 THEN 'Unknown' WHEN count(DISTINCT pa)>1 THEN 'Mixed'
            WHEN count(pa)<count(*) THEN 'Unknown' WHEN bool_or(CAST(pa AS BOOLEAN)) THEN 'Yes' ELSE 'No' END pa,
       CASE WHEN count(st)=0 THEN 'Unknown' WHEN count(DISTINCT st)>1 THEN 'Mixed'
            WHEN count(st)<count(*) THEN 'Unknown' WHEN bool_or(CAST(st AS BOOLEAN)) THEN 'Yes' ELSE 'No' END st,
       CASE WHEN count(ql)=0 THEN 'Unknown' WHEN count(DISTINCT ql)>1 THEN 'Mixed'
            WHEN count(ql)<count(*) THEN 'Unknown' WHEN bool_or(CAST(ql AS BOOLEAN)) THEN 'Yes' ELSE 'No' END ql,
       string_agg(DISTINCT coalesce(ql_amount,'') || '/' || coalesce(ql_days,''), ';') quantity_limit_details,
       min(CAST(source_row AS INTEGER)) first_drug_source_row
FROM raw_drugs GROUP BY ALL;

CREATE OR REPLACE TABLE fact_strength AS
SELECT p.*, s.brand, CAST(s.strength_mg AS INTEGER) strength_mg, s.strength_key,
       CASE WHEN p.formulary_complete=0 THEN 'Unknown' WHEN d.source_records IS NULL THEN 'Unlisted' ELSE 'Listed' END listing,
       CASE WHEN p.formulary_complete=0 OR d.source_records IS NULL THEN NULL ELSE d.pa END pa,
       CASE WHEN p.formulary_complete=0 OR d.source_records IS NULL THEN NULL ELSE d.st END st,
       CASE WHEN p.formulary_complete=0 OR d.source_records IS NULL THEN NULL ELSE d.ql END ql,
       d.tiers, d.rxcuis, d.package_count, d.quantity_limit_details, d.first_drug_source_row,
       CASE WHEN EXISTS(SELECT 1 FROM raw_indications i JOIN raw_drugs dr ON i.rxcui=dr.rxcui AND i.month=dr.month
                        WHERE i.month=p.month AND i.plan_key=p.plan_key AND dr.brand=s.brand AND CAST(dr.strength_mg AS INTEGER)=CAST(s.strength_mg AS INTEGER))
            THEN 'Indication-specific listing; inspect source' ELSE '' END indication_note
FROM plan_month p CROSS JOIN raw_products s
LEFT JOIN drug_strength d ON p.month=d.month AND p.formulary_id=d.formulary_id
                        AND s.brand=d.brand AND CAST(s.strength_mg AS INTEGER)=d.strength_mg;

CREATE OR REPLACE TABLE fact_brand AS
SELECT month, plan_key, contract_id, plan_id, plan_name, organization, formulary_id,
       region_code, region, suppressed, formulary_complete, plan_source_row, enrollment, enrollment_source_row, brand,
       count(*) catalog_strengths, count(*) FILTER(WHERE listing='Listed') listed_strengths,
       CASE WHEN formulary_complete=0 THEN 'Unknown' WHEN count(*) FILTER(WHERE listing='Listed')>0 THEN 'Listed' ELSE 'Unlisted' END listing,
       CASE WHEN formulary_complete=0 THEN NULL WHEN count(*) FILTER(WHERE listing='Listed')=count(*) THEN 1 ELSE 0 END all_strengths_listed,
       CASE WHEN formulary_complete=0 THEN NULL WHEN count(*) FILTER(WHERE listing='Listed')>0 THEN 1 ELSE 0 END any_strength_listed,
       CASE WHEN formulary_complete=0 OR count(*) FILTER(WHERE listing='Listed')=0 THEN NULL
            WHEN count(DISTINCT pa) FILTER(WHERE listing='Listed')>1 THEN 'Mixed' ELSE max(pa) END pa,
       CASE WHEN formulary_complete=0 OR count(*) FILTER(WHERE listing='Listed')=0 THEN NULL
            WHEN count(DISTINCT st) FILTER(WHERE listing='Listed')>1 THEN 'Mixed' ELSE max(st) END st,
       CASE WHEN formulary_complete=0 OR count(*) FILTER(WHERE listing='Listed')=0 THEN NULL
            WHEN count(DISTINCT ql) FILTER(WHERE listing='Listed')>1 THEN 'Mixed' ELSE max(ql) END ql,
       CASE WHEN formulary_complete=0 OR count(*) FILTER(WHERE listing='Listed')=0 THEN NULL
            WHEN count(*) FILTER(WHERE listing='Listed' AND pa='No' AND st='No')>0 THEN 1
            WHEN count(*) FILTER(WHERE listing='Listed' AND (pa IN ('Unknown','Mixed') OR st IN ('Unknown','Mixed')))>0 THEN NULL ELSE 0 END any_no_pa_st,
       string_agg(DISTINCT nullif(indication_note,''), ';') indication_note
FROM fact_strength GROUP BY month, plan_key, contract_id, plan_id, plan_name, organization, formulary_id,
       region_code, region, suppressed, formulary_complete, plan_source_row, enrollment, enrollment_source_row, brand;

-- Full outer join retains entrants/exits. Only known, matched plans enter paired change rates.
CREATE OR REPLACE TABLE fact_change AS
WITH first AS (SELECT * FROM fact_strength WHERE month=(SELECT min(month) FROM dim_snapshot)),
last AS (SELECT * FROM fact_strength WHERE month=(SELECT max(month) FROM dim_snapshot))
SELECT coalesce(a.plan_key,b.plan_key) plan_key, coalesce(a.brand,b.brand) brand,
       coalesce(a.strength_mg,b.strength_mg) strength_mg,
       coalesce(a.strength_key,b.strength_key) strength_key,
       a.month baseline_month, b.month latest_month, a.listing baseline_listing, b.listing latest_listing,
       a.pa baseline_pa, b.pa latest_pa, a.st baseline_st, b.st latest_st, a.ql baseline_ql, b.ql latest_ql,
       a.tiers baseline_tiers, b.tiers latest_tiers,
       a.quantity_limit_details baseline_ql_details, b.quantity_limit_details latest_ql_details,
       b.enrollment latest_enrollment, coalesce(b.region,a.region) region,
       CASE WHEN a.plan_key IS NULL THEN 'Plan entered' WHEN b.plan_key IS NULL THEN 'Plan exited'
            WHEN a.listing='Unknown' OR b.listing='Unknown' THEN 'Unknown access'
            WHEN a.listing='Listed' AND b.listing='Unlisted' THEN 'Listing lost'
            WHEN a.listing='Unlisted' AND b.listing='Listed' THEN 'Listing gained'
            ELSE 'Listing unchanged' END listing_change,
       CASE WHEN a.listing='Listed' AND b.listing='Listed' AND a.pa='No' AND b.pa='Yes' THEN 1 ELSE 0 END pa_added,
       CASE WHEN a.listing='Listed' AND b.listing='Listed' AND a.st='No' AND b.st='Yes' THEN 1 ELSE 0 END st_added,
       CASE WHEN a.listing='Listed' AND b.listing='Listed' AND a.ql='No' AND b.ql='Yes' THEN 1 ELSE 0 END ql_added,
       CASE WHEN a.listing='Listed' AND b.listing='Listed' AND a.tiers IS DISTINCT FROM b.tiers THEN 1 ELSE 0 END tier_changed,
       CASE WHEN a.plan_key IS NOT NULL AND b.plan_key IS NOT NULL AND a.listing<>'Unknown' AND b.listing<>'Unknown' THEN 1 ELSE 0 END comparable,
       a.formulary_id baseline_formulary_id, b.formulary_id latest_formulary_id,
       a.first_drug_source_row baseline_source_row, b.first_drug_source_row latest_source_row
FROM first a FULL JOIN last b USING(plan_key, brand, strength_mg, strength_key)
WHERE (SELECT count(*) FROM dim_snapshot)>1;

CREATE OR REPLACE TABLE mart_summary AS
SELECT month, brand, count(*) AS plan_count, count(*) FILTER(WHERE listing<>'Unknown') known_plans,
       count(*) FILTER(WHERE listing='Listed') listed_plans,
       count(*) FILTER(WHERE all_strengths_listed=1) all_strength_plans,
       count(*) FILTER(WHERE listing='Unknown') unknown_plans,
       count(enrollment) plans_with_enrollment,
       sum(enrollment) reported_enrollment,
       sum(enrollment) FILTER(WHERE listing<>'Unknown') known_access_enrollment,
       sum(enrollment) FILTER(WHERE listing='Listed') listed_enrollment,
       sum(enrollment) FILTER(WHERE listing='Listed' AND pa='Yes') pa_enrollment,
       count(*) FILTER(WHERE listing='Listed' AND pa='Mixed') mixed_pa_plans,
       count(*) FILTER(WHERE any_no_pa_st=1) no_pa_st_plans,
       count(*) FILTER(WHERE listing='Listed')::DOUBLE / nullif(count(*) FILTER(WHERE listing<>'Unknown'),0) plan_listing_rate,
       coalesce(sum(enrollment) FILTER(WHERE listing='Listed'),0)::DOUBLE / nullif(sum(enrollment) FILTER(WHERE listing<>'Unknown'),0) enrollment_listing_rate
FROM fact_brand GROUP BY ALL;

-- A paired cohort with August enrollment held fixed isolates published listing changes.
CREATE OR REPLACE TABLE fact_brand_change AS
 SELECT a.brand, a.plan_key, a.listing baseline_listing, b.listing latest_listing,
        b.enrollment latest_enrollment
 FROM fact_brand a JOIN fact_brand b USING(plan_key,brand)
 WHERE a.month=(SELECT min(month) FROM dim_snapshot) AND b.month=(SELECT max(month) FROM dim_snapshot)
   AND a.listing<>'Unknown' AND b.listing<>'Unknown'
   AND (SELECT count(*) FROM dim_snapshot)>1;
CREATE OR REPLACE TABLE mart_change_summary AS
SELECT brand, count(*) comparable_plans, count(latest_enrollment) plans_with_latest_enrollment,
       sum(latest_enrollment) fixed_enrollment_denominator,
       sum(CASE WHEN baseline_listing='Listed' THEN latest_enrollment ELSE 0 END)::DOUBLE/nullif(sum(latest_enrollment),0) baseline_rate_fixed_weights,
       sum(CASE WHEN latest_listing='Listed' THEN latest_enrollment ELSE 0 END)::DOUBLE/nullif(sum(latest_enrollment),0) latest_rate_fixed_weights,
       count(*) FILTER(WHERE baseline_listing='Unlisted' AND latest_listing='Listed') plans_gained,
       count(*) FILTER(WHERE baseline_listing='Listed' AND latest_listing='Unlisted') plans_lost
FROM fact_brand_change GROUP BY brand;

CREATE OR REPLACE TABLE mart_review_queue AS
WITH comparison AS (
 SELECT a.plan_key,
        bool_or(b.listing='Listed') competitor_listed,
        string_agg(b.brand, ', ' ORDER BY b.brand) FILTER(WHERE b.listing='Listed') listed_competitors
 FROM fact_brand a JOIN fact_brand b USING(month,plan_key)
 WHERE a.month=(SELECT max(month) FROM dim_snapshot) AND a.brand='BELSOMRA' AND b.brand<>'BELSOMRA'
 GROUP BY a.plan_key
), changes AS (
 SELECT plan_key, bool_or(listing_change='Listing lost') lost_strength,
        bool_or(pa_added=1) added_pa, bool_or(st_added=1) added_st,
        string_agg(CAST(strength_mg AS VARCHAR), ', ' ORDER BY strength_mg) FILTER(WHERE listing_change='Listing lost') lost_strengths
 FROM fact_change WHERE brand='BELSOMRA' GROUP BY plan_key
)
SELECT a.*, coalesce(c.listed_competitors,'') listed_competitors,
       CASE WHEN coalesce(ch.lost_strength,false) THEN '1. BELSOMRA strength listing lost'
            WHEN coalesce(ch.added_pa,false) OR coalesce(ch.added_st,false) THEN '2. PA or step therapy added'
            ELSE '3. BELSOMRA unlisted; competitor listed' END investigation,
       coalesce(ch.lost_strengths,'') lost_strengths,
       'Validate current payer documents and clinical criteria before action' next_step
FROM fact_brand a LEFT JOIN comparison c USING(plan_key) LEFT JOIN changes ch USING(plan_key)
WHERE a.month=(SELECT max(month) FROM dim_snapshot) AND a.brand='BELSOMRA' AND a.listing<>'Unknown'
  AND (coalesce(ch.lost_strength,false) OR coalesce(ch.added_pa,false) OR coalesce(ch.added_st,false)
       OR (a.listing='Unlisted' AND c.competitor_listed));

CREATE OR REPLACE TABLE mart_review_queue AS
SELECT *, row_number() OVER(ORDER BY investigation, enrollment DESC NULLS LAST, plan_key) review_rank
FROM mart_review_queue;

CREATE OR REPLACE TABLE mart_source_counts AS SELECT * FROM raw_source_counts;
CREATE OR REPLACE TABLE mart_quarantine AS SELECT * FROM raw_quarantine;
CREATE OR REPLACE TABLE mart_quality AS
SELECT 'Q01' check_id, 'Unique plan-brand-snapshot keys' check_name, 'error' severity,
       CASE WHEN (SELECT count(*) FROM fact_brand)=(SELECT count(DISTINCT (month,plan_key,brand)) FROM fact_brand) THEN 'PASS' ELSE 'FAIL' END status,
       'Enrollment joins only after package-to-strength reduction' detail
UNION ALL SELECT 'Q02', 'Complete eight-strength product catalogue', 'error',
       CASE WHEN (SELECT count(*) FROM raw_products)=8 THEN 'PASS' ELSE 'FAIL' END, 'Four BELSOMRA, two DAYVIGO, two QUVIVIQ strengths'
UNION ALL SELECT 'Q03', 'Enrollment invariant across brands', 'error',
       CASE WHEN NOT EXISTS(SELECT month,plan_key FROM fact_brand GROUP BY ALL HAVING count(DISTINCT enrollment)>1) THEN 'PASS' ELSE 'FAIL' END,
       'A plan has one reported enrollment per snapshot'
UNION ALL SELECT 'Q04', 'Unknown source access retained', 'error',
       CASE WHEN NOT EXISTS(SELECT 1 FROM fact_brand WHERE formulary_complete=0 AND listing<>'Unknown') THEN 'PASS' ELSE 'FAIL' END,
       'Suppressed or missing formularies cannot become unlisted'
UNION ALL SELECT 'Q05', 'Missing enrollment disclosed', 'info',
       CASE WHEN EXISTS(SELECT 1 FROM plan_month WHERE enrollment IS NULL) THEN 'REVIEW' ELSE 'PASS' END,
       CAST((SELECT count(*) FROM plan_month WHERE enrollment IS NULL) AS VARCHAR) || ' plan-months have no published enrollment'
UNION ALL SELECT 'Q06', 'Matched-plan change comparability', 'error',
       CASE WHEN NOT EXISTS(SELECT 1 FROM fact_change WHERE comparable=1 AND (baseline_listing='Unknown' OR latest_listing='Unknown')) THEN 'PASS' ELSE 'FAIL' END,
       'Entry, exit and unknown access are excluded from paired change rates'
UNION ALL SELECT 'Q07', 'Indication-specific listings disclosed', 'info',
       CASE WHEN EXISTS(SELECT 1 FROM fact_strength WHERE indication_note<>'') THEN 'REVIEW' ELSE 'PASS' END,
       CAST((SELECT count(*) FROM fact_strength WHERE indication_note<>'') AS VARCHAR) || ' rows require indication review'
UNION ALL SELECT 'Q08', 'Mixed restriction flags disclosed', 'info',
       CASE WHEN EXISTS(SELECT 1 FROM fact_strength WHERE pa='Mixed' OR st='Mixed' OR ql='Mixed') THEN 'REVIEW' ELSE 'PASS' END,
       'Mixed package-level flags are never coerced to Yes or No'
UNION ALL SELECT 'Q09', 'Unkeyed enrollment rows quarantined', 'info',
       CASE WHEN EXISTS(SELECT 1 FROM raw_quarantine) THEN 'REVIEW' ELSE 'PASS' END,
       CAST((SELECT count(*) FROM raw_quarantine) AS VARCHAR) || ' source rows excluded with recorded reasons';

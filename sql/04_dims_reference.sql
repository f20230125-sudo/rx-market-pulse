-- Reference dimensions: states, enrollment, manufacturer spellings -> parent company, area rules.

-- ---------------------------------------------------------------- states
create or replace table dim_state as
select r.state, r.state_name, r.census_region, r.census_division, cast(r.is_state as boolean) as is_state,
       e.expanded_medicaid
from read_csv('{ref_dir}/states.csv', header = true) r
left join (
    select distinct on (state) state, expanded_medicaid
    from stg_enrollment
    order by state, year desc, month desc
) e using (state);

-- ---------------------------------------------------------------- monthly enrollment, one row per state-month
-- A month can be reported twice, 'P' (preliminary) and 'U' (updated). Keep the updated one.
create or replace table fact_enrollment as
select state, year, month, expanded_medicaid, report_status, enrollment_total
from (
    select *, row_number() over (
        partition by state, year, month
        order by case report_status when 'U' then 0 else 1 end
    ) as rn
    from stg_enrollment
    where enrollment_total is not null
)
where rn = 1;

-- ---------------------------------------------------------------- manufacturer spellings -> parent company
-- Aggregate first: the harmonisation functions are Python, so they should see 1,315 names, not 2M rows.
create or replace table map_labeler_parent as
select
    labeler_name,
    normalise_labeler(labeler_name)  as labeler_key,
    parent_company(labeler_name)     as parent_company,
    ndc_count
from (
    select labeler_name, count(distinct ndc) as ndc_count
    from stg_mdrp
    where labeler_name is not null
    group by 1
);

-- ---------------------------------------------------------------- therapeutic area from pharmacologic class
create or replace table ref_therapeutic_rules as
select cast(priority as integer) as priority, area, pattern
from read_csv('{ref_dir}/therapeutic_area_rules.csv', header = true);

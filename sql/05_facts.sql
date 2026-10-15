-- Facts: utilisation rows that can be keyed to a product.
--
-- state = 'XX' rows are the *national* totals the source publishes. They include small cells that are
-- suppressed (blank) in the state rows, so the sum of the 51 state rows is lower than the XX row
-- (6-7% every year). Never add XX to the states; use XX for national totals and states for comparisons.

create or replace table fact_sdud as
select
    s.utilization_type,
    s.state,
    s.ndc_raw                      as ndc11,
    s.year,
    s.quarter,
    s.suppressed,
    s.units,
    s.prescriptions,
    s.total_amount,
    s.medicaid_amount,
    s.non_medicaid_amount
from stg_sdud s
where regexp_matches(s.ndc_raw, '^[0-9]{11}$');

create or replace view v_fact_national as select * from fact_sdud where state = 'XX';
create or replace view v_fact_state    as select * from fact_sdud where state <> 'XX';

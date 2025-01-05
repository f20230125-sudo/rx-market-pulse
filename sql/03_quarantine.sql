-- Rows that cannot be keyed to a product never reach the facts. They are kept here, with the reason,
-- so nothing disappears silently and the scorecard can state what was set aside.

create or replace table quarantine_sdud as
select
    s.*,
    case
        when not regexp_matches(s.ndc_raw, '^[0-9]{11}$') then 'ndc_not_11_digits'
    end as reason
from stg_sdud s
where not regexp_matches(s.ndc_raw, '^[0-9]{11}$');

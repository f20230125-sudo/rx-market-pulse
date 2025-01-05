-- NDC conversion as SQL macros, so million-row joins do not call out to Python row by row.
-- rx/ndc.py is the reference implementation; tests/test_ndc_macros.py checks these agree with it.

-- Any NDC spelling (11 digits, or hyphenated 4-4-2, 5-3-2, 5-4-1, 5-4-2) -> 11 digits, else NULL.
create or replace macro ndc11_of(s) as (
    case
        when regexp_matches(trim(s), '^[0-9]{4}-[0-9]{4}-[0-9]{2}$')
            then '0' || replace(trim(s), '-', '')
        when regexp_matches(trim(s), '^[0-9]{5}-[0-9]{3}-[0-9]{2}$')
            then split_part(trim(s), '-', 1) || '0' || split_part(trim(s), '-', 2) || split_part(trim(s), '-', 3)
        when regexp_matches(trim(s), '^[0-9]{5}-[0-9]{4}-[0-9]$')
            then split_part(trim(s), '-', 1) || split_part(trim(s), '-', 2) || '0' || split_part(trim(s), '-', 3)
        when regexp_matches(trim(s), '^[0-9]{5}-[0-9]{4}-[0-9]{2}$')
            then replace(trim(s), '-', '')
        when regexp_matches(trim(s), '^[0-9]{11}$')
            then trim(s)
    end
);

-- Product NDC ("0002-1433", "50242-040") -> labeler+product, nine digits.
create or replace macro ndc9_of_product(p) as (
    case
        when regexp_matches(trim(p), '^[0-9]{4}-[0-9]{4}$') then '0' || replace(trim(p), '-', '')
        when regexp_matches(trim(p), '^[0-9]{5}-[0-9]{3}$')
            then split_part(trim(p), '-', 1) || '0' || split_part(trim(p), '-', 2)
        when regexp_matches(trim(p), '^[0-9]{5}-[0-9]{4}$') then replace(trim(p), '-', '')
    end
);

-- Analysis base tables. Every mart reads these, so a number means the same thing everywhere.
--
--   sales_nat    national totals (the published XX rows), by year, quarter and NDC
--   sales_state  state rows, by state, year and NDC (small cells are suppressed in the source)
--
-- NDCs the product list does not know stay in, labelled 'Unknown' / 'Unmatched NDC', so every mart
-- adds back to the published national total exactly. Nothing is dropped to make a chart look clean.

-- A brand keeps one owner across all years: the company whose NDCs carried most of its 2024-25 spend.
-- Without this a product that moved company (Nexplanon: Merck -> Organon in 2021) is split in two.
create or replace table dim_brand_owner as
select product_family, arg_max(parent_company, amt) as owner
from (
    select p.product_family, p.parent_company, sum(f.total_amount) as amt
    from fact_sdud f
    join dim_product p using (ndc11)
    where f.state = 'XX' and f.year >= 2024 and p.market_class = 'Brand'
    group by 1, 2
)
group by 1;

create or replace table sales_nat as
select
    f.year, f.quarter, f.ndc11,
    sum(f.total_amount)                                       as spend,
    sum(f.prescriptions)                                      as rx,
    sum(f.units)                                              as units,
    coalesce(p.market_class, 'Unknown')                       as market_class,
    coalesce(p.therapeutic_area, 'Unclassified')              as area,
    coalesce(p.product_family, 'UNMATCHED NDC')               as family,
    p.ingredient_key                                          as ingredient,
    coalesce(o.owner, p.parent_company, 'Unmatched')          as owner,
    coalesce(p.is_biologic, false)                            as is_biologic
from fact_sdud f
left join dim_product p using (ndc11)
left join dim_brand_owner o on o.product_family = p.product_family and p.market_class = 'Brand'
where f.state = 'XX' and f.year between 2019 and 2025
group by all;

create or replace table sales_state as
select
    f.state, f.year, f.ndc11,
    sum(f.total_amount)                                       as spend,
    sum(f.prescriptions)                                      as rx,
    sum(f.units)                                              as units,
    count(*)                                                  as cells,
    sum(case when f.suppressed then 1 else 0 end)             as cells_suppressed,
    coalesce(p.market_class, 'Unknown')                       as market_class,
    coalesce(p.therapeutic_area, 'Unclassified')              as area
from fact_sdud f
left join dim_product p using (ndc11)
where f.state <> 'XX' and f.year between 2019 and 2025
group by all;

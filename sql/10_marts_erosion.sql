-- Generic erosion: what happens to a brand's market once generics arrive?
--
-- Unit of analysis: an active ingredient (so every brand and generic version of the molecule is counted).
-- Entry quarter t0 = first quarter in which generic versions are at least 10% of the molecule's prescriptions,
-- and only for molecules that started the period (2019 Q1) with generics under 5% - so we see the switch,
-- not a market that was already generic. Brand baseline must be at least $20M in the 4 quarters before t0.

create or replace temp table ero_q as
select ingredient,
       year * 4 + quarter - 1                                          as qi,
       make_date(year, quarter * 3 - 2, 1)                             as quarter_start,
       sum(rx)    filter (where market_class = 'Brand')                as brand_rx,
       sum(rx)    filter (where market_class = 'Generic')              as generic_rx,
       sum(spend) filter (where market_class = 'Brand')                as brand_spend,
       sum(spend) filter (where market_class = 'Generic')              as generic_spend,
       arg_max(family, spend) filter (where market_class = 'Brand')    as brand_family
from sales_nat
where ingredient is not null and market_class in ('Brand', 'Generic')
group by ingredient, year, quarter;

create or replace temp table ero_share as
select *,
       coalesce(generic_rx, 0) / nullif(coalesce(brand_rx, 0) + coalesce(generic_rx, 0), 0) as generic_share
from ero_q;

create or replace temp table ero_events as
with start as (
    select ingredient, generic_share as share_start
    from ero_share where qi = 2019 * 4
),
entry as (
    select ingredient, min(qi) as t0
    from ero_share where generic_share >= 0.10 group by 1
)
select e.ingredient, e.t0,
       (select arg_max(brand_family, brand_spend) from ero_share s where s.ingredient = e.ingredient) as brand_family,
       (select sum(brand_spend) from ero_share s where s.ingredient = e.ingredient and s.qi between e.t0 - 4 and e.t0 - 1) as pre_brand_spend_4q
from entry e
join start using (ingredient)
where coalesce(start.share_start, 0) < 0.05
  and e.t0 >= 2019 * 4 + 4;   -- at least a year of pre-entry history

create or replace table mart_erosion_curve as
select ev.ingredient, ev.brand_family, s.quarter_start,
       s.qi - ev.t0                                                     as quarters_since_entry,
       s.generic_share,
       s.brand_spend, s.generic_spend,
       coalesce(s.brand_spend, 0) + coalesce(s.generic_spend, 0)       as molecule_spend,
       100.0 * coalesce(s.brand_spend, 0) / (ev.pre_brand_spend_4q / 4)  as brand_spend_index,
       100.0 * (coalesce(s.brand_spend, 0) + coalesce(s.generic_spend, 0)) / (ev.pre_brand_spend_4q / 4) as molecule_spend_index
from ero_events ev
join ero_share s on s.ingredient = ev.ingredient
where ev.pre_brand_spend_4q >= 20e6
  and s.qi between ev.t0 - 8 and ev.t0 + 16
order by ev.ingredient, s.qi;

create or replace table mart_erosion_events as
select c.ingredient, c.brand_family,
       min(quarter_start) filter (where quarters_since_entry = 0)        as entry_quarter,
       round(max(brand_spend_index) filter (where quarters_since_entry = -1), 0)  as brand_index_before,
       round(max(brand_spend_index) filter (where quarters_since_entry = 4), 0)   as brand_index_q4,
       round(max(brand_spend_index) filter (where quarters_since_entry = 8), 0)   as brand_index_q8,
       round(100 * max(generic_share) filter (where quarters_since_entry = 4), 1) as generic_share_q4,
       round(100 * max(generic_share) filter (where quarters_since_entry = 8), 1) as generic_share_q8,
       round(max(molecule_spend_index) filter (where quarters_since_entry = 8), 0) as molecule_index_q8,
       round(max(brand_spend) filter (where quarters_since_entry = -1) * 4 / 1e6, 0) as brand_run_rate_before_musd
from mart_erosion_curve c
group by c.ingredient, c.brand_family
order by brand_run_rate_before_musd desc nulls last;

copy mart_erosion_curve  to '{marts_dir}/erosion_curve.csv'  (header, delimiter ',');
copy mart_erosion_events to '{marts_dir}/erosion_events.csv' (header, delimiter ',');

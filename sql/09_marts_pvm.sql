-- Price / volume / mix bridge: why did spend change between two years?
--
-- Per product family (brand name, or molecule for generics) with prescriptions V and spend S:
--   price per prescription P = S / V
--   volume  = (total V1 - total V0) x average P0           more or fewer scripts, at last year's average price
--   mix     = sum_i (V1_i - V1_total x share0_i) x P0_i     scripts moving toward dearer or cheaper products
--   price   = sum_i (P1_i - P0_i) x V1_i                    same product, different spend per script
--   new / lost products are shown on their own, not folded into price.
-- The pieces add exactly to the change in spend (checked in tests). "Price" here is spend per prescription,
-- so it also moves with strength, pack size and days' supply; it is not a list price.

create or replace temp table pvm_base as
select 'All market' as segment, year, family, market_class, sum(rx) as v, sum(spend) as s
from sales_nat group by all
union all
select area, year, family, market_class, sum(rx), sum(spend)
from sales_nat group by all;

create or replace temp table pvm_pairs as
select a.year as y0, b.year as y1
from (select distinct year from sales_nat) a, (select distinct year from sales_nat) b
where b.year > a.year;

create or replace temp table pvm_rows as
select p.y0, p.y1, k.segment, k.family, k.market_class,
       coalesce(b0.v, 0) as v0, coalesce(b0.s, 0) as s0,
       coalesce(b1.v, 0) as v1, coalesce(b1.s, 0) as s1
from pvm_pairs p
cross join (select distinct segment, family, market_class from pvm_base) k
left join pvm_base b0 on b0.segment = k.segment and b0.family = k.family
                     and b0.market_class = k.market_class and b0.year = p.y0
left join pvm_base b1 on b1.segment = k.segment and b1.family = k.family
                     and b1.market_class = k.market_class and b1.year = p.y1
where coalesce(b0.s, 0) <> 0 or coalesce(b1.s, 0) <> 0;

create or replace table mart_pvm as
with ex as (
    select y0, y1, segment,
           sum(v0) as vt0, sum(v1) as vt1, sum(s0) as se0
    from pvm_rows where v0 > 0 and v1 > 0
    group by all
),
parts as (
    select r.y0, r.y1, r.segment,
           sum(r.s0) as spend_0, sum(r.s1) as spend_1,
           sum(case when r.v0 > 0 and r.v1 > 0
                    then (r.v1 - e.vt1 * r.v0 / e.vt0) * (r.s0 / r.v0) end)       as mix,
           sum(case when r.v0 > 0 and r.v1 > 0
                    then (r.s1 / r.v1 - r.s0 / r.v0) * r.v1 end)                  as price,
           sum(case when not (r.v0 > 0 and r.v1 > 0) and r.v1 > 0 then r.s1 end)   as new_products,
           sum(case when not (r.v0 > 0 and r.v1 > 0) and r.v1 <= 0 then -r.s0 end) as lost_products,
           any_value(e.vt0) as vt0, any_value(e.vt1) as vt1, any_value(e.se0) as se0
    from pvm_rows r
    left join ex e using (y0, y1, segment)
    group by r.y0, r.y1, r.segment
)
select y0, y1, segment,
       spend_0, spend_1, spend_1 - spend_0 as change,
       (vt1 - vt0) * (se0 / vt0)                                        as volume,
       coalesce(mix, 0)                                                 as mix,
       coalesce(price, 0)                                               as price,
       coalesce(new_products, 0)                                        as new_products,
       coalesce(lost_products, 0)                                       as lost_products
from parts
order by y0, y1, segment;

copy mart_pvm to '{marts_dir}/pvm.csv' (header, delimiter ',');

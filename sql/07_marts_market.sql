-- Market marts (national). Small tables; each is also written to data/marts/*.csv.

create or replace table mart_market_year as
select year, market_class,
       sum(spend) as spend, sum(rx) as rx, sum(units) as units,
       round(sum(spend) / nullif(sum(rx), 0), 2) as spend_per_rx
from sales_nat group by all order by 1, 2;

create or replace table mart_market_quarter as
select year, quarter, make_date(year, quarter * 3 - 2, 1) as quarter_start,
       sum(spend) as spend, sum(rx) as rx,
       sum(spend) filter (where market_class = 'Brand') as brand_spend,
       sum(rx) filter (where market_class = 'Brand') as brand_rx
from sales_nat group by all order by 1, 2;

create or replace table mart_area_year as
select year, area, market_class,
       sum(spend) as spend, sum(rx) as rx
from sales_nat group by all order by 1, 2, 3;

-- Product families: keep any family that reached $2M in some year; the rest roll into one row per year,
-- so the table stays small and still adds back to the national total.
create or replace table mart_product_year as
with fam as (
    select family, market_class, year,
           sum(spend) as spend, sum(rx) as rx, sum(units) as units,
           arg_max(owner, spend) as owner,
           arg_max(area, spend) as area,
           arg_max(ingredient, spend) as ingredient,
           bool_or(is_biologic) as is_biologic
    from sales_nat group by family, market_class, year
),
big as (select family, market_class from fam group by 1, 2 having max(spend) >= 2e6)
select f.year, f.family, f.market_class, f.owner, f.area, f.ingredient, f.is_biologic, f.spend, f.rx, f.units
from fam f join big using (family, market_class)
union all
select f.year, 'All other products', f.market_class, 'Various', 'Various', null, false,
       sum(f.spend), sum(f.rx), sum(f.units)
from fam f anti join big using (family, market_class)
group by f.year, f.market_class;

create or replace table mart_owner_year as
select year, owner,
       sum(spend) as spend, sum(rx) as rx,
       sum(spend) filter (where market_class = 'Brand') as brand_spend,
       sum(spend) filter (where market_class = 'Generic') as generic_spend
from sales_nat group by all order by 1, spend desc;

copy mart_market_year    to '{marts_dir}/market_year.csv'    (header, delimiter ',');
copy mart_market_quarter to '{marts_dir}/market_quarter.csv' (header, delimiter ',');
copy mart_area_year      to '{marts_dir}/area_year.csv'      (header, delimiter ',');
copy mart_product_year   to '{marts_dir}/product_year.csv'   (header, delimiter ',');
copy mart_owner_year     to '{marts_dir}/owner_year.csv'     (header, delimiter ',');

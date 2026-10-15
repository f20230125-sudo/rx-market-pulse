-- State marts: territory comparisons. State rows have small cells blanked in the source, so a state's
-- spend is its *reported* spend; mart_reconciliation shows how much of the national total that covers.
-- Puerto Rico appears from 2023 and has no enrollment series, so it is kept but flagged is_state = false;
-- comparisons between states use is_state rows only.

create or replace table mart_state_year as
with s as (
    select state, year,
           sum(spend) as spend, sum(rx) as rx,
           sum(spend) filter (where market_class = 'Brand') as brand_spend,
           sum(cells_suppressed)::double / sum(cells)        as suppressed_cell_share
    from sales_state group by all
),
e as (select state, year, avg(enrollment_total) as enrollment from fact_enrollment group by all)
select s.state, d.state_name, d.is_state, d.census_region, d.census_division, d.expanded_medicaid, s.year,
       s.spend, s.rx, s.brand_spend, round(s.suppressed_cell_share, 4) as suppressed_cell_share,
       round(e.enrollment) as enrollment,
       round(s.spend / e.enrollment, 2)  as spend_per_enrollee,
       round(s.rx / e.enrollment, 3)     as rx_per_enrollee,
       round(s.spend / nullif(s.rx, 0), 2) as spend_per_rx,
       round(100 * s.brand_spend / s.spend, 2) as brand_spend_pct
from s
left join e using (state, year)
left join dim_state d using (state)
order by s.year, s.state;

create or replace table mart_state_area_year as
select state, year, area,
       sum(spend) as spend, sum(rx) as rx,
       sum(spend) filter (where market_class = 'Brand') as brand_spend
from sales_state group by all order by 1, 2, 3;

create or replace table mart_reconciliation as
select n.year, n.spend as national_spend, s.spend as state_sum,
       n.spend - s.spend as suppressed_gap,
       round(100 * (n.spend - s.spend) / n.spend, 2) as gap_pct
from (select year, sum(spend) as spend from sales_nat group by 1) n
join (select year, sum(spend) as spend from sales_state group by 1) s using (year)
order by 1;

copy mart_state_year      to '{marts_dir}/state_year.csv'      (header, delimiter ',');
copy mart_state_area_year to '{marts_dir}/state_area_year.csv' (header, delimiter ',');
copy mart_reconciliation  to '{marts_dir}/reconciliation.csv'  (header, delimiter ',');

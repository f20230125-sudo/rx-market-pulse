-- Loss-of-exclusivity exposure from the FDA Orange Book (patents and exclusivities for approved NDAs).
--
-- For each brand family with 2025 spend: the Orange Book entry of its biggest application, and the dates
-- that protect it. "Substance patent" (the drug itself) usually sets the earliest realistic generic entry;
-- later formulation and use patents often fall to challenge or settlement, so both dates are shown.
-- This is a map of where protection ends, not a forecast of when generics launch.
-- Biologics (BLAs) are not in the Orange Book and are reported as their own group, not as unprotected.
-- {as_of} is the date of the Orange Book file used.

create or replace temp table ob_app as
select appl_type, appl_no,
       max(patent_expires) filter (where drug_substance) as substance_patent_expiry,
       max(patent_expires) filter (where drug_product)   as product_patent_expiry,
       max(patent_expires)                               as last_patent_expiry,
       count(*)                                          as patents
from stg_ob_patents group by 1, 2;

create or replace temp table ob_excl as
select appl_type, appl_no, max(exclusivity_expires) as last_exclusivity_expiry
from stg_ob_exclusivity group by 1, 2;

create or replace temp table ob_known as
select distinct appl_type, appl_no from stg_ob_products;

create or replace temp table loe_ndc as
select s.family, s.owner, s.area, sum(s.spend) as spend_2025,
       p.is_biologic,
       case when p.application_number like 'ANDA%' then 'A'
            when p.application_number like 'NDA%'  then 'N'
            when p.application_number like 'BLA%'  then null
            else 'N' end                                                          as appl_type,
       lpad(coalesce(nullif(regexp_extract(p.application_number, '([0-9]+)$', 1), ''),
                     substr(p.mdrp_application_number, 2)), 6, '0')               as appl_no
from sales_nat s
join dim_product p using (ndc11)
where s.year = 2025 and s.market_class = 'Brand'
group by s.family, s.owner, s.area, p.is_biologic, p.application_number, p.mdrp_application_number;

create or replace table mart_loe as
with fam as (
    select family, any_value(owner) as owner, any_value(area) as area,
           sum(spend_2025) as spend_2025, bool_or(is_biologic) as is_biologic,
           arg_max(appl_type, spend_2025) as appl_type, arg_max(appl_no, spend_2025) as appl_no
    from loe_ndc group by family
),
j as (
    select f.*, k.appl_no is not null as in_orange_book,
           a.substance_patent_expiry, a.product_patent_expiry, a.last_patent_expiry, e.last_exclusivity_expiry
    from fam f
    left join ob_known k on k.appl_type = f.appl_type and k.appl_no = f.appl_no
    left join ob_app   a on a.appl_type = f.appl_type and a.appl_no = f.appl_no
    left join ob_excl  e on e.appl_type = f.appl_type and e.appl_no = f.appl_no
)
select family, owner, area, round(spend_2025) as spend_2025, is_biologic, appl_type, appl_no, in_orange_book,
       substance_patent_expiry, product_patent_expiry, last_patent_expiry, last_exclusivity_expiry,
       -- core: the drug-substance patent or an exclusivity; if the product has neither, its latest product/use patent
       coalesce(greatest(substance_patent_expiry, last_exclusivity_expiry),
                greatest(product_patent_expiry, last_exclusivity_expiry),
                last_patent_expiry)                                          as core_protection_end,
       greatest(last_patent_expiry, last_exclusivity_expiry)                 as last_protection_end,
       case
           when is_biologic                                                     then 'Biologic (not in Orange Book)'
           when not in_orange_book                                              then 'No Orange Book entry'
           when greatest(last_patent_expiry, last_exclusivity_expiry) is null   then 'No patent or exclusivity listed'
           when greatest(last_patent_expiry, last_exclusivity_expiry) < date '{as_of}' then 'Listed protection has ended'
           else 'Protected'
       end as status
from j
order by spend_2025 desc;

create or replace table mart_loe_year as
select coalesce(cast(year(core_protection_end) as varchar), status) as protection_end,
       status, count(*) as families, round(sum(spend_2025)) as spend_2025
from mart_loe
group by 1, 2
order by status, protection_end;

create or replace table mart_msd_product_year as
select * from mart_product_year where owner = 'Merck (MSD)' and market_class = 'Brand';

copy mart_loe                to '{marts_dir}/loe.csv'                (header, delimiter ',');
copy mart_loe_year           to '{marts_dir}/loe_year.csv'           (header, delimiter ',');
copy mart_msd_product_year   to '{marts_dir}/msd_product_year.csv'   (header, delimiter ',');

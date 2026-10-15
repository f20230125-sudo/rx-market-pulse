-- Final product dimension: the base columns plus a therapeutic area.
-- Three steps, in order of trust: the product's own FDA class; a class borrowed from another product with
-- the same ingredient; a curated ingredient/brand-name rule (data/ref/name_area_rules.csv).
-- map_name_area is built in Python (rx/areas.py) just before this file runs.

-- ---------------------------------------------------------------- therapeutic area per product
-- Step 1: from the product's own classes. Step 2: borrow from other products with the same ingredient.
create or replace temp table area_direct as
select ndc11, arg_min(area, priority) as area
from (
    select p.ndc11, m.area, m.priority
    from (select ndc11, unnest(pharm_class) as pharm_class from product_base where pharm_class is not null) p
    join map_pharm_class m using (pharm_class)
)
group by ndc11;

create or replace temp table area_by_ingredient as
select ingredient_key, mode(area) as area
from (
    select b.ingredient_key, d.area
    from product_base b join area_direct d using (ndc11)
    where b.ingredient_key is not null
)
group by 1;

create or replace table dim_product as
select
    b.*,
    coalesce(o1.area, o2.area, d.area, i.area, n1.area, n2.area, 'Unclassified') as therapeutic_area,
    case when coalesce(o1.area, o2.area) is not null then 'override'
         when d.area is not null then 'own class'
         when i.area is not null then 'same ingredient'
         when coalesce(n1.area, n2.area) is not null then 'name rule'
         else 'none' end                                             as area_source
from product_base b
left join area_direct d on d.ndc11 = b.ndc11
left join area_by_ingredient i on i.ingredient_key = b.ingredient_key
left join map_name_area n1 on n1.name = b.ingredient_key
left join map_name_area n2 on n2.name = b.product_family
left join map_override_area o1 on o1.name = b.ingredient_key
left join map_override_area o2 on o2.name = b.product_family;

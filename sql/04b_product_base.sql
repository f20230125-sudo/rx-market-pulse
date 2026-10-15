-- Product base: one row per NDC from the product list, enriched from the FDA directory (no therapeutic area yet).
-- map_pharm_class (class string -> area) is built in Python (rx/areas.py) just before this file runs.

-- ---------------------------------------------------------------- FDA directory, one row per package NDC
create or replace temp table fda_pkg as
select distinct on (k.ndc11)
    k.ndc11,
    substr(k.ndc11, 1, 9)                                           as ndc9,
    p.product_ndc, p.brand_name_base, p.brand_name, p.generic_name, p.marketing_category,
    p.application_number, p.ingredients, p.pharm_class, p.dosage_form, p.route, p.rxcui
from stg_fda_package k
join stg_fda_product p using (product_ndc)
where k.ndc11 is not null
order by k.ndc11, (p.pharm_class is null), p.product_ndc;

-- ... and one row per labeler+product (nine digits), for packages the directory does not list.
create or replace temp table fda_prod as
select distinct on (ndc9)
    ndc9_of_product(product_ndc)                                    as ndc9,
    product_ndc, brand_name_base, brand_name, generic_name, marketing_category,
    application_number, ingredients, pharm_class, dosage_form, route, rxcui
from stg_fda_product
where ndc9_of_product(product_ndc) is not null
order by ndc9, (pharm_class is null), product_ndc;

-- Text keys are computed once per distinct string (a few thousand), then joined, because the key
-- functions are Python and must not run once per product row.
create or replace temp table ingredient_keys as
select s as src, ingredient_key(s) as k
from (
    select array_to_string(ingredients, '|') as s from stg_fda_product
    union
    select generic_name from stg_fda_product
)
where s is not null;

-- ---------------------------------------------------------------- product master
create or replace temp table mdrp_latest as
select distinct on (ndc) *
from stg_mdrp
order by ndc, snapshot_year desc, snapshot_quarter desc;

create or replace temp table name_keys as
select name as src, first_name(name) as k from (select distinct fda_product_name as name from stg_mdrp) where name is not null;

create or replace temp table product_base as
with joined as (
    select
        m.ndc                                                       as ndc11,
        substr(m.ndc, 1, 9)                                         as ndc9,
        m.labeler_code, m.labeler_name,
        lp.parent_company,
        m.fda_product_name                                          as product_name_source,
        m.drug_category,
        case when m.drug_category in ('S', 'I') then 'Brand' else 'Generic' end as market_class,
        m.te_code, m.fda_approval_date, m.market_date, m.termination_date, m.cod_status,
        m.fda_application_number                                    as mdrp_application_number,
        case when f.ndc11 is not null then 'package'
             when g.ndc9  is not null then 'product' else 'none' end as fda_match,
        coalesce(f.brand_name_base, g.brand_name_base)              as fda_brand,
        coalesce(f.generic_name, g.generic_name)                    as fda_generic_name,
        coalesce(f.marketing_category, g.marketing_category)        as marketing_category,
        coalesce(f.application_number, g.application_number)        as application_number,
        coalesce(f.ingredients, g.ingredients)                      as ingredients,
        coalesce(f.pharm_class, g.pharm_class)                      as pharm_class,
        coalesce(f.dosage_form, g.dosage_form)                      as dosage_form,
        coalesce(f.route, g.route)                                  as route
    from mdrp_latest m
    left join map_labeler_parent lp on lp.labeler_name = m.labeler_name
    left join fda_pkg  f on f.ndc11 = m.ndc
    left join fda_prod g on g.ndc9 = substr(m.ndc, 1, 9)
),
keyed as (
    select j.*,
        coalesce(k1.k, k2.k)                                        as ingredient_key,
        nk.k                                                        as source_first_name
    from joined j
    left join ingredient_keys k1 on k1.src = array_to_string(j.ingredients, '|')
    left join ingredient_keys k2 on k2.src = j.fda_generic_name
    left join name_keys nk on nk.src = j.product_name_source
)
select
    ndc11, ndc9, labeler_code, labeler_name, parent_company,
    product_name_source, drug_category, market_class, te_code,
    fda_approval_date, market_date, termination_date, cod_status,
    mdrp_application_number, fda_match, marketing_category, application_number,
    marketing_category in ('BLA') or application_number like 'BLA%'   as is_biologic,
    ingredient_key, pharm_class, dosage_form, route,
    -- Brand products are reported under their brand family; generics under the molecule.
    case
        when market_class = 'Brand' then coalesce(upper(fda_brand), source_first_name)
        else coalesce(ingredient_key, source_first_name)
    end                                                             as product_family
from keyed;

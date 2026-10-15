-- openFDA NDC directory: one row per product (product_ndc), plus one row per package (package_ndc).
-- The directory lists products that are currently or recently on the market, so old NDCs seen in
-- Medicaid history can be missing here. The scorecard measures how much spend that affects.

create or replace temp table fda_raw as
select unnest(results) as r from read_json('{fda_json}', maximum_object_size = 300000000);

create or replace table stg_fda_product as
select
    r.product_ndc                                            as product_ndc,
    r.brand_name                                             as brand_name,
    r.brand_name_base                                        as brand_name_base,
    r.generic_name                                           as generic_name,
    r.labeler_name                                           as labeler_name,
    r.marketing_category                                     as marketing_category,
    r.application_number                                     as application_number,
    r.dosage_form                                            as dosage_form,
    array_to_string(r.route, ';')                            as route,
    try_strptime(r.marketing_start_date, '%Y%m%d')::date     as marketing_start_date,
    try_strptime(r.marketing_end_date, '%Y%m%d')::date       as marketing_end_date,
    list_transform(r.active_ingredients, x -> upper(x."name"))   as ingredients,
    r.openfda.unii                                           as unii,
    r.openfda.rxcui                                          as rxcui,
    r.pharm_class                                            as pharm_class,
    r.product_type                                           as product_type
from fda_raw;

create or replace table stg_fda_package as
with pk as (select r.product_ndc as product_ndc, unnest(r.packaging) as pk from fda_raw)
select
    product_ndc,
    pk.package_ndc                                           as package_ndc,
    ndc11_of(pk.package_ndc)                                 as ndc11,
    pk.description                                           as package_description,
    try_strptime(pk.marketing_start_date, '%Y%m%d')::date    as package_start_date,
    try_strptime(pk.marketing_end_date, '%Y%m%d')::date      as package_end_date
from pk;

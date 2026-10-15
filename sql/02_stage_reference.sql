-- Reference sources, staged as published. Dates arrive as MM/DD/YYYY text.

-- Medicaid Drug Rebate Program product list: one row per NDC per reporting quarter (snapshots).
create or replace table stg_mdrp as
select
    cast("Year" as integer)                                     as snapshot_year,
    cast("Quarter" as integer)                                  as snapshot_quarter,
    trim("Labeler Name")                                        as labeler_name,
    trim(NDC)                                                   as ndc,
    "Labeler Code"                                              as labeler_code,
    "Product Code"                                              as product_code,
    "Package Size Code"                                         as package_size_code,
    "Drug Category"                                             as drug_category,   -- S single-source, I innovator multi-source, N non-innovator
    "Drug Type Indicator"                                       as drug_type_indicator,
    try_strptime("Termination Date", '%m/%d/%Y')::date          as termination_date,
    "Unit Type"                                                 as unit_type,
    try_cast("Units Per Pkg Size" as double)                    as units_per_pkg,
    try_strptime("FDA Approval Date", '%m/%d/%Y')::date         as fda_approval_date,
    try_strptime("Market Date", '%m/%d/%Y')::date               as market_date,
    "FDA Therapeutic Equivalence Code"                          as te_code,
    trim("FDA Product Name")                                    as fda_product_name,
    "Clotting Factor Indicator"                                 as clotting_factor,
    "Pediatric Indicator"                                       as pediatric,
    "COD Status"                                                as cod_status,
    "FDA Application Number"                                    as fda_application_number,
    "Line Extension Drug Indicator"                             as line_extension
from read_csv('{mdrp}', header = true, all_varchar = true);

-- Monthly Medicaid + CHIP enrollment by state. A month can appear twice: 'P' (preliminary) and 'U' (updated).
create or replace table stg_enrollment as
select
    "State Abbreviation"                                        as state,
    "State Name"                                                as state_name,
    cast(substr("Reporting Period", 1, 4) as integer)           as year,
    cast(substr("Reporting Period", 5, 2) as integer)           as month,
    "State Expanded Medicaid" = 'Y'                             as expanded_medicaid,
    "Preliminary or Updated"                                    as report_status,
    try_cast("Total Medicaid and CHIP Enrollment" as bigint)    as enrollment_total,
    try_cast("Total Medicaid Enrollment" as bigint)             as enrollment_medicaid
from read_csv('{enrollment}', header = true, all_varchar = true);

-- FDA Orange Book (tilde-delimited): approved small-molecule products, patents, exclusivities.
create or replace table stg_ob_products as
select
    Ingredient                                                  as ingredient,
    "DF;Route"                                                  as dosage_route,
    Trade_Name                                                  as trade_name,
    Applicant                                                   as applicant,
    Strength                                                    as strength,
    Appl_Type                                                   as appl_type,        -- N = NDA, A = ANDA
    Appl_No                                                     as appl_no,
    Product_No                                                  as product_no,
    TE_Code                                                     as te_code,
    try_strptime(Approval_Date, '%b %d, %Y')::date              as approval_date,
    RLD = 'Yes'                                                 as is_reference_listed_drug,
    Applicant_Full_Name                                         as applicant_full_name
from read_csv('{ob_products}', delim = '~', header = true, all_varchar = true, quote = '');

create or replace table stg_ob_patents as
select
    Appl_Type                                                   as appl_type,
    Appl_No                                                     as appl_no,
    Product_No                                                  as product_no,
    Patent_No                                                   as patent_no,
    try_strptime(Patent_Expire_Date_Text, '%b %d, %Y')::date    as patent_expires,
    Drug_Substance_Flag = 'Y'                                   as drug_substance,
    Drug_Product_Flag = 'Y'                                     as drug_product
from read_csv('{ob_patents}', delim = '~', header = true, all_varchar = true, quote = '');

create or replace table stg_ob_exclusivity as
select
    Appl_Type                                                   as appl_type,
    Appl_No                                                     as appl_no,
    Product_No                                                  as product_no,
    Exclusivity_Code                                            as exclusivity_code,
    try_strptime(Exclusivity_Date, '%b %d, %Y')::date           as exclusivity_expires
from read_csv('{ob_exclusivity}', delim = '~', header = true, all_varchar = true, quote = '');

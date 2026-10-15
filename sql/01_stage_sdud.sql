-- Stage the Medicaid State Drug Utilization Data exactly as published, typed but not cleaned.
-- {files} is replaced by build.py with the list of yearly CSVs found in data/raw.

create or replace table stg_sdud as
select
    "Utilization Type"                                  as utilization_type,
    upper(trim(State))                                  as state,
    trim(NDC)                                           as ndc_raw,
    "Labeler Code"                                      as labeler_code,
    "Product Code"                                      as product_code,
    "Package Size"                                      as package_size,
    cast(Year as integer)                               as year,
    cast(Quarter as integer)                            as quarter,
    "Suppression Used" = 'true'                         as suppressed,
    "Product Name"                                      as product_name_raw,
    try_cast("Units Reimbursed" as double)              as units,
    try_cast("Number of Prescriptions" as double)       as prescriptions,
    try_cast("Total Amount Reimbursed" as double)       as total_amount,
    try_cast("Medicaid Amount Reimbursed" as double)    as medicaid_amount,
    try_cast("Non Medicaid Amount Reimbursed" as double) as non_medicaid_amount,
    regexp_extract(filename, '(sdud_\d{4})', 1)       as source_file
from read_csv({files}, header = true, all_varchar = true, filename = true);

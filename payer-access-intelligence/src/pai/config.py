from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MONTHS = ("2026-01", "2026-08")
CONTRACT_YEAR = "2026"
BRANDS = {
    "BELSOMRA": {"ingredient": "suvorexant", "strengths": [5, 10, 15, 20], "setid": "e5b72731-1acb-45b7-9c13-290ad12d3951"},
    "DAYVIGO": {"ingredient": "lemborexant", "strengths": [5, 10], "setid": "7074cb65-77b3-45d2-8e8d-da8dc0f70bfd"},
    "QUVIVIQ": {"ingredient": "daridorexant", "strengths": [25, 50], "setid": "3a2d1503-b816-40c9-9fac-7e03c5a3bcef"},
}
REGIONS = {
    1: "NH / ME", 2: "CT / MA / RI / VT", 3: "New York", 4: "New Jersey",
    5: "DE / DC / MD", 6: "PA / WV", 7: "Virginia", 8: "North Carolina",
    9: "South Carolina", 10: "Georgia", 11: "Florida", 12: "AL / TN", 13: "Michigan",
    14: "Ohio", 15: "IN / KY", 16: "Wisconsin", 17: "Illinois", 18: "Missouri",
    19: "Arkansas", 20: "Mississippi", 21: "Louisiana", 22: "Texas", 23: "Oklahoma",
    24: "Kansas", 25: "IA / MN / MT / NE / ND / SD / WY", 26: "New Mexico",
    27: "Colorado", 28: "Arizona", 29: "Nevada", 30: "OR / WA", 31: "ID / UT",
    32: "California", 33: "Hawaii", 34: "Alaska", 35: "American Samoa",
    36: "Guam", 37: "Northern Mariana Islands", 38: "Puerto Rico", 39: "US Virgin Islands",
}
LAYOUT = "https://data.cms.gov/sites/default/files/2025-10/0564eb37-402d-4110-bd98-2d5399dc30e7/PUFRecordLayout-2026.pdf"
AGREEMENT = "https://data.cms.gov/sites/default/files/2023-10/4eeb19e1-525b-4a4e-9766-b33ff084fc5c/AGREEMENT-FOR-USE.pdf"
FORMULARY_LANDING = "https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information"
ENROLLMENT_LANDING = "https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/monthly-enrollment-plan"

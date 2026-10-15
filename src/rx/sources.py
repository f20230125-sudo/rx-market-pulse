"""Where every input comes from. One place, so the README and the code cannot drift apart.

Medicaid datasets are served by data.medicaid.gov (DKAN). Each year of State Drug Utilization Data
is its own dataset id; the ids below were read from the site's public catalog
(https://data.medicaid.gov/api/1/metastore/schemas/dataset/items) on 15 Oct 2026.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse" / "rx.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

MEDICAID_BASE = "https://data.medicaid.gov/api/1/datastore/query"


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str  # file download URL
    filename: str
    count_url: str | None = None  # DKAN query URL that returns the expected row count


def _dkan(uuid: str) -> tuple[str, str]:
    return (
        f"{MEDICAID_BASE}/{uuid}/0/download?format=csv",
        f"{MEDICAID_BASE}/{uuid}/0?limit=1&count=true&schema=false&keys=true",
    )


# State Drug Utilization Data: one dataset per calendar year. 2026 is a partial year and is left out
# of annual comparisons on purpose.
SDUD_IDS: dict[int, str] = {
    2019: "daba7980-e219-5996-9bec-90358fd156f1",
    2020: "cc318bfb-a9b2-55f3-a924-d47376b32ea3",
    2021: "eec7fbe6-c4c4-5915-b3d0-be5828ef4e9d",
    2022: "200c2cba-e58d-4a95-aa60-14b99736808d",
    2023: "d890d3a9-6b00-43fd-8b31-fcba4c8e2909",
    2024: "61729e5a-7aa8-448c-8903-ba3e0cd0ea3c",
    2025: "158a1baa-5506-400a-8ec3-97756f0b0536",
}

MDRP_PRODUCTS_ID = "0ad65fe5-3ad3-5d79-a3f9-7893ded7963a"  # Drug Products in the Medicaid Drug Rebate Program
ENROLLMENT_ID = "6165f45b-ca93-5bb5-9d06-db29c692a360"  # State Medicaid and CHIP ... Enrollment Data


def all_sources() -> list[Source]:
    out: list[Source] = []
    for year, uuid in SDUD_IDS.items():
        url, count = _dkan(uuid)
        out.append(Source(f"sdud_{year}", f"State Drug Utilization Data {year}", url, f"sdud_{year}.csv", count))
    url, count = _dkan(MDRP_PRODUCTS_ID)
    out.append(Source("mdrp_products", "Drug Products in the Medicaid Drug Rebate Program", url, "mdrp_products.csv", count))
    url, count = _dkan(ENROLLMENT_ID)
    out.append(Source("enrollment", "State Medicaid and CHIP enrollment (monthly)", url, "enrollment.csv", count))
    out.append(
        Source(
            "openfda_ndc",
            "openFDA National Drug Code directory (bulk JSON)",
            "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip",
            "openfda_ndc.json.zip",
        )
    )
    out.append(
        Source(
            "orange_book",
            "FDA Orange Book data files (products, patents, exclusivity)",
            "https://www.fda.gov/media/76860/download",
            "orange_book.zip",
        )
    )
    return out

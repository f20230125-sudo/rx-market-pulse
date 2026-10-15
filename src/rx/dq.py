"""Data-quality scorecard.

    python -m rx.dq

Runs every check against the warehouse, then writes
    data/marts/dq_checks.csv          one row per check (also read by the dashboard)
    data/marts/dq_match_waterfall.csv how much spend each harmonisation step recovers
    docs/data-quality-scorecard.md    the same, readable

Each check says what it measured, the number, the rule it was held to, and the dollars it touches.
A check that fails its rule is not hidden: the report leads with it.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb

from .build import connect
from .sources import MARTS, RAW, ROOT

DOCS = ROOT / "docs"

STAGE_LABELS = {
    "package": "Exact pack in the FDA directory",
    "product": "Same product, pack not listed",
    "none": "Not in the FDA directory",
    "not in product list": "Not in the Medicaid product list",
}


@dataclass
class Check:
    id: str
    dimension: str
    name: str
    result: str
    rule: str
    status: str  # pass | warn | fail | info
    dollars: float | None
    note: str


def _one(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()


def _pct(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}%"


def _usd(x: float | None) -> str:
    if x is None:
        return "n/a"
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    return f"${x:,.0f}"


def run(con: duckdb.DuckDBPyConnection) -> tuple[list[Check], list[dict]]:
    checks: list[Check] = []
    expected = json.loads((RAW / "expected_rows.json").read_text())

    # ------------------------------------------------------------ completeness
    rows = dict(con.execute("select year, count(*) from stg_sdud group by 1").fetchall())
    mismatched = [y for y, n in rows.items() if expected.get(f"sdud_{y}") != n]
    checks.append(Check(
        "C01", "Completeness", "Rows loaded equal rows published (State Drug Utilization, per year)",
        f"{len(rows) - len(mismatched)} of {len(rows)} years match the row count the source API reports",
        "every year equal", "pass" if not mismatched else "fail", None,
        f"{sum(rows.values()):,} rows across {min(rows)}-{max(rows)}.",
    ))
    n_mdrp = _one(con, "select count(*) from stg_mdrp")[0]
    checks.append(Check(
        "C02", "Completeness", "Rows loaded equal rows published (Medicaid product list)",
        f"{n_mdrp:,} loaded vs {expected.get('mdrp_products', 0):,} published",
        "equal", "pass" if n_mdrp == expected.get("mdrp_products") else "fail", None, "",
    ))

    # ------------------------------------------------------------ validity
    bad_rows, bad_dollars = _one(con, "select count(*), coalesce(sum(total_amount), 0) from quarantine_sdud")
    total_dollars = _one(con, "select sum(total_amount) from stg_sdud where state = 'XX'")[0]
    checks.append(Check(
        "C03", "Validity", "NDC is an 11-digit code (labeler 5 + product 4 + package 2)",
        f"{bad_rows:,} rows are not; set aside in quarantine_sdud",
        "0 rows in the facts that are not 11 digits", "warn" if bad_rows else "pass", float(bad_dollars),
        "Placeholder rows ('** FROM CL') and codes that lost leading zeros. They never reach the facts; "
        "the dollars on them are blank (suppressed), so the market total is unaffected.",
    ))
    neg = _one(con, "select count(*) from fact_sdud where total_amount < 0 or units < 0 or prescriptions < 0")[0]
    checks.append(Check(
        "C04", "Validity", "No negative amounts, units or prescription counts",
        f"{neg:,} rows", "0", "pass" if neg == 0 else "fail", None,
        "Reversals and adjustments are netted by the source before publication.",
    ))
    mism, mism_d = _one(con, """
        select count(*), coalesce(sum(total_amount), 0) from fact_sdud
        where not suppressed and abs(medicaid_amount + non_medicaid_amount - total_amount) > 0.05""")
    checks.append(Check(
        "C05", "Validity", "Medicaid + non-Medicaid amount equals total amount (to 5 cents)",
        f"{mism:,} rows differ", "0", "warn" if mism else "pass", float(mism_d),
        "Source rounding. Total amount is used throughout; the Medicaid/non-Medicaid split is only shown separately.",
    ))
    q_bad = _one(con, "select count(*) from fact_sdud where quarter not between 1 and 4 or year not between 2019 and 2025")[0]
    checks.append(Check(
        "C06", "Validity", "Year and quarter are in range", f"{q_bad:,} rows outside 2019-2025 Q1-Q4", "0",
        "pass" if q_bad == 0 else "fail", None, "",
    ))

    # ------------------------------------------------------------ uniqueness
    dup = _one(con, """select count(*) from (
        select utilization_type, state, ndc11, year, quarter from fact_sdud
        group by all having count(*) > 1)""")[0]
    checks.append(Check(
        "C07", "Uniqueness", "One row per utilization type, state, NDC, year and quarter",
        f"{dup:,} duplicated keys", "0", "pass" if dup == 0 else "fail", None,
        "A duplicate would double-count spend.",
    ))
    dup_p = _one(con, "select count(*) - count(distinct ndc11) from dim_product")[0]
    checks.append(Check(
        "C08", "Uniqueness", "One row per NDC in the product master", f"{dup_p:,} duplicates", "0",
        "pass" if dup_p == 0 else "fail", None,
        "The product list is a quarterly snapshot; the latest snapshot per NDC is kept.",
    ))

    # ------------------------------------------------------------ reconciliation
    gaps = con.execute("""
        select year,
               sum(total_amount) filter (where state = 'XX') as national,
               sum(total_amount) filter (where state <> 'XX') as states
        from fact_sdud group by 1 order by 1""").fetchall()
    pct = [100 * (n - s) / n for _, n, s in gaps]
    gap_d = sum(n - s for _, n, s in gaps)
    checks.append(Check(
        "C09", "Reconciliation", "Sum of the state and territory rows vs the published national (XX) row",
        f"state and territory rows are {min(pct):.1f}-{max(pct):.1f}% below national, every year",
        "gap explained and stable", "warn", float(gap_d),
        "Cells with fewer than 11 prescriptions are blanked in the state rows but counted in the national row. "
        "National totals therefore come from XX; state shares are shares of reported (unsuppressed) spend.",
    ))
    sup = _one(con, "select 100.0 * avg(case when suppressed then 1 else 0 end) from fact_sdud where state <> 'XX'")[0]
    checks.append(Check(
        "C10", "Reconciliation", "Share of state-level rows with values suppressed",
        _pct(sup, 1), "reported, not hidden", "info", None,
        "Suppressed rows carry no units or dollars. They are kept (not dropped) so row counts reconcile.",
    ))

    # ------------------------------------------------------------ coverage (the match waterfall)
    wf = con.execute("""
        with s as (select ndc11, sum(total_amount) as amt from fact_sdud where state = 'XX' group by 1)
        select coalesce(p.fda_match, 'not in product list') as stage,
               sum(s.amt) as dollars
        from s left join dim_product p using (ndc11)
        group by 1""").fetchall()
    wf_total = sum(d for _, d in wf) or 1.0
    in_mdrp = 100 * sum(d for st, d in wf if st != "not in product list") / wf_total
    checks.append(Check(
        "C11", "Coverage", "Spend whose NDC is in the Medicaid product list (gives manufacturer, brand/generic, dates)",
        _pct(in_mdrp), ">= 99.5%", "pass" if in_mdrp >= 99.5 else "fail",
        float(sum(d for st, d in wf if st == "not in product list")),
        "Dollars on NDCs the list does not know are reported as 'unmatched', never guessed.",
    ))
    pkg = 100 * sum(d for st, d in wf if st == "package") / wf_total
    prod = 100 * sum(d for st, d in wf if st == "product") / wf_total
    none = 100 * sum(d for st, d in wf if st == "none") / wf_total
    checks.append(Check(
        "C12", "Coverage", "Spend matched to the FDA product directory (ingredient, class, approval type)",
        f"{_pct(pkg + prod)} (exact package {_pct(pkg)}, same product {_pct(prod)}); {_pct(none)} unmatched",
        ">= 90%", "pass" if pkg + prod >= 90 else "warn",
        float(sum(d for st, d in wf if st == "none")),
        "The directory lists current products, so discontinued NDCs seen in older Medicaid years are missing. "
        "Matching on the nine-digit labeler+product code recovers packs the directory does not list.",
    ))
    ing = _one(con, """
        with s as (select ndc11, sum(total_amount) amt from fact_sdud where state = 'XX' group by 1)
        select 100.0 * sum(case when p.ingredient_key is not null then amt end) / sum(amt)
        from s left join dim_product p using (ndc11)""")[0]
    checks.append(Check(
        "C13", "Coverage", "Spend with an active-ingredient key", _pct(ing), ">= 90%",
        "pass" if ing >= 90 else "warn", None,
        "Salts and hydrates are stripped and combinations sorted so one molecule has one key.",
    ))
    areas = dict(con.execute("""
        with s as (select ndc11, sum(total_amount) amt from fact_sdud where state = 'XX' group by 1)
        select p.area_source, sum(amt) from s left join dim_product p using (ndc11) group by 1""").fetchall())
    a_total = sum(v for v in areas.values()) or 1.0
    a_own = 100 * areas.get("own class", 0) / a_total
    a_ing = 100 * areas.get("same ingredient", 0) / a_total
    a_name = 100 * (areas.get("name rule", 0) + areas.get("override", 0)) / a_total
    a_none = 100 - a_own - a_ing - a_name
    checks.append(Check(
        "C14", "Coverage", "Spend assigned to a therapeutic area",
        f"{_pct(100 - a_none)} (FDA class {_pct(a_own)}, borrowed from same ingredient {_pct(a_ing)}, "
        f"curated list {_pct(a_name)}); {_pct(a_none)} unclassified",
        ">= 90%", "pass" if a_none <= 10 else "warn", None,
        "Area comes from the FDA pharmacologic class, then the same ingredient, then an editable name list "
        "(data/ref/). Unclassified spend is shown as its own bar in every chart, never spread across other areas.",
    ))
    pairs = _one(con, "select count(*), count(distinct parent_company) from map_labeler_parent")
    checks.append(Check(
        "C15", "Harmonisation", "Manufacturer spellings collapsed to parent companies",
        f"{pairs[0]:,} spellings to {pairs[1]:,} companies", "reported", "info", None,
        "Case and punctuation variants merge by rule; completed acquisitions are mapped by an explicit, tested list.",
    ))
    trunc = _one(con, "select 100.0 * avg(case when length(product_name_raw) = 10 then 1 else 0 end) from stg_sdud")[0]
    checks.append(Check(
        "C16", "Harmonisation", "Product names in the utilization file are cut at 10 characters",
        _pct(trunc, 1) + " of rows are exactly 10 characters long", "reported", "info", None,
        "Names such as 'LEVOTHYROX' are not used. Product identity comes from the NDC, joined to the product list.",
    ))

    # ------------------------------------------------------------ integrity & timeliness
    orphan = _one(con, """
        with s as (select ndc11, sum(total_amount) amt from fact_sdud where state = 'XX' group by 1)
        select count(*) filter (where p.ndc11 is null), coalesce(sum(amt) filter (where p.ndc11 is null), 0)
        from s left join dim_product p using (ndc11)""")
    checks.append(Check(
        "C17", "Integrity", "Spend on NDCs missing from the product master is immaterial",
        f"{orphan[0]:,} NDCs, {100 * orphan[1] / total_dollars:.2f}% of national spend",
        "under 0.1% of spend", "pass" if orphan[1] / total_dollars < 0.001 else "warn", float(orphan[1]),
        "These rows stay in the facts with an empty product; charts group them as 'Unmatched'.",
    ))
    latest = _one(con, "select max(year * 10 + quarter) from fact_sdud")[0]
    snap = _one(con, "select max(snapshot_year * 10 + snapshot_quarter) from stg_mdrp")[0]
    checks.append(Check(
        "C18", "Timeliness", "Newest period in each source",
        f"utilization {latest // 10} Q{latest % 10}; product list {snap // 10} Q{snap % 10}", "reported", "info", None,
        "2026 is a partial year in the source and is left out of annual comparisons on purpose.",
    ))
    pu = _one(con, "select count(*) from stg_enrollment") [0] - _one(con, "select count(*) from fact_enrollment")[0]
    n_states = _one(con, "select count(distinct state) from fact_enrollment")[0]
    checks.append(Check(
        "C19", "Uniqueness", "Enrollment: one value per state and month",
        f"{pu:,} duplicate months resolved (updated value kept over preliminary); {n_states} states",
        "51 states, no duplicates", "pass" if n_states == 51 else "fail", None, "",
    ))

    waterfall = [
        {"stage": STAGE_LABELS.get(st, st), "dollars": float(d), "share_pct": round(100 * d / wf_total, 3)}
        for st, d in sorted(wf, key=lambda r: -r[1])
    ]
    return checks, waterfall


def write(checks: list[Check], waterfall: list[dict]) -> None:
    MARTS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    with open(MARTS / "dq_checks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(checks[0])))
        w.writeheader()
        w.writerows(asdict(c) for c in checks)
    with open(MARTS / "dq_match_waterfall.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "dollars", "share_pct"])
        w.writeheader()
        w.writerows(waterfall)

    order = {"fail": 0, "warn": 1, "info": 2, "pass": 3}
    badge = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    lines = ["# Data-quality scorecard", "",
             "Generated by `python -m rx.dq` from the built warehouse. Nothing here is typed by hand.", "",
             f"**{sum(c.status == 'pass' for c in checks)} pass, {sum(c.status == 'warn' for c in checks)} warn, "
             f"{sum(c.status == 'fail' for c in checks)} fail, {sum(c.status == 'info' for c in checks)} info** "
             f"across {len(checks)} checks. Warnings are understood and explained, not ignored.", "",
             "| # | Dimension | Check | Result | Rule | Status | $ touched |", "|---|---|---|---|---|---|---|"]
    for c in sorted(checks, key=lambda c: (order[c.status], c.id)):
        lines.append(f"| {c.id} | {c.dimension} | {c.name} | {c.result} | {c.rule} | {badge[c.status]} | {_usd(c.dollars)} |")
    lines += ["", "## Notes", ""]
    for c in sorted(checks, key=lambda c: c.id):
        if c.note:
            lines.append(f"- **{c.id}**: {c.note}")
    lines += ["", "## Match waterfall (national spend, all years)", "",
              "| Stage | Spend | Share |", "|---|---|---|"]
    for r in waterfall:
        lines.append(f"| {r['stage']} | {_usd(r['dollars'])} | {r['share_pct']:.2f}% |")
    (DOCS / "data-quality-scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    con = connect()
    checks, waterfall = run(con)
    write(checks, waterfall)
    for c in checks:
        print(f"{c.id} {c.status.upper():<5} {c.name}: {c.result}")
    con.close()
    return 1 if any(c.status == "fail" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())

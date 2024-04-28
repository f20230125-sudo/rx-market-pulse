"""Export the marts as small JSON files for the dashboard.

    python -m rx.export_json                 # writes dashboard/public/data/*.json

The dashboard never queries the warehouse. It reads these files at build time and validates each one with a
schema, so a column that changes here fails the dashboard build instead of drawing a wrong chart.
Numbers are written as plain arrays aligned to `years` to keep the files small.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

from .build import connect
from .sources import MARTS, RAW, ROOT

OUT = ROOT / "dashboard" / "public" / "data"
YEARS = list(range(2019, 2026))
ALL = "All areas"
PINNED_OWNER = "Merck (MSD)"


def _write(name: str, payload: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _by_year(rows, key_idx: int, year_idx: int, val_idxs: list[int]) -> dict:
    """rows -> {key: [[v per year] per value index]} aligned to YEARS."""
    out: dict = {}
    for r in rows:
        slot = out.setdefault(r[key_idx], [[0.0] * len(YEARS) for _ in val_idxs])
        yi = YEARS.index(int(r[year_idx]))
        for j, vi in enumerate(val_idxs):
            slot[j][yi] = float(r[vi] or 0)
    return out


def export_meta(con) -> list[str]:
    areas = [r[0] for r in con.execute(
        "select area from mart_area_year where year = 2025 group by 1 order by sum(spend) desc").fetchall()]
    as_of = datetime.fromtimestamp((RAW / "orange_book.zip").stat().st_mtime).date().isoformat()
    n_rows = con.execute("select count(*) from stg_sdud").fetchone()[0]
    _write("meta.json", {
        "built": date.today().isoformat(), "years": YEARS, "areas": areas, "orangeBookAsOf": as_of,
        "pinnedOwner": PINNED_OWNER, "rowsLoaded": n_rows,
        "sources": [
            {"name": "State Drug Utilization Data", "by": "CMS / data.medicaid.gov", "use": "spend, prescriptions, units by state, NDC and quarter"},
            {"name": "Drug Products in the Medicaid Drug Rebate Program", "by": "CMS / data.medicaid.gov", "use": "manufacturer, brand/generic category, dates"},
            {"name": "Medicaid and CHIP enrollment (monthly)", "by": "CMS / data.medicaid.gov", "use": "enrollment per state"},
            {"name": "National Drug Code directory", "by": "FDA / openFDA", "use": "ingredient, pharmacologic class, approval type"},
            {"name": "Orange Book data files", "by": "FDA", "use": "patents and exclusivities"},
        ],
    })
    return areas


def export_market(con, areas) -> None:
    rows = con.execute("""select area, year, market_class, sum(spend), sum(rx)
                          from mart_area_year group by 1, 2, 3""").fetchall()
    series: dict = {}
    for seg in [ALL, *areas]:
        series[seg] = {k: [0.0] * len(YEARS) for k in
                       ("brandSpend", "genericSpend", "otherSpend", "brandRx", "genericRx", "otherRx")}
    for area, year, cls, spend, rx in rows:
        yi = YEARS.index(int(year))
        suffix = {"Brand": "brand", "Generic": "generic"}.get(cls, "other")
        for seg in (ALL, area):
            series[seg][f"{suffix}Spend"][yi] += float(spend or 0)
            series[seg][f"{suffix}Rx"][yi] += float(rx or 0)
    _write("market.json", {"years": YEARS, "series": series})


def export_pvm(con) -> None:
    rows = con.execute("""select segment, y0, y1, spend_0, volume, mix, price, new_products, lost_products, spend_1
                          from mart_pvm""").fetchall()
    out: dict = {}
    for seg, y0, y1, s0, vol, mix, price, new, lost, s1 in rows:
        name = ALL if seg == "All market" else seg
        out.setdefault(name, {})[f"{y0}-{y1}"] = {
            "start": float(s0), "volume": float(vol), "mix": float(mix), "price": float(price),
            "newProducts": float(new), "lostProducts": float(lost), "end": float(s1)}
    _write("pvm.json", {"pairs": ["2019-2022", "2022-2025", "2024-2025", "2019-2025"], "segments": out})


def export_owners_and_products(con, areas) -> None:
    owners_by_seg: dict = {}
    for seg in [ALL, *areas]:
        cond = "" if seg == ALL else "where area = ?"
        args = [] if seg == ALL else [seg]
        rows = con.execute(f"""select owner, year, sum(spend), sum(spend) filter (where market_class = 'Brand')
                               from sales_nat {cond} group by 1, 2""", args).fetchall()
        by = _by_year(rows, 0, 1, [2, 3])
        ranked = sorted(by, key=lambda o: -by[o][0][-1])
        keep = ranked[:20]
        if PINNED_OWNER in by and PINNED_OWNER not in keep:
            keep.append(PINNED_OWNER)
        owners_by_seg[seg] = [{"owner": o, "spend": [round(v) for v in by[o][0]], "brandSpend": [round(v) for v in by[o][1]]} for o in keep]
    _write("owners.json", {"segments": owners_by_seg, "pinned": PINNED_OWNER})

    # Product rows for each of the top owners (all areas), joined to patent/exclusivity dates.
    loe = {r[0]: r for r in con.execute("""select family, status, core_protection_end, substance_patent_expiry,
                                                  last_patent_expiry, last_exclusivity_expiry, is_biologic from mart_loe""").fetchall()}
    top_owners = [r[0] for r in con.execute("""select owner from sales_nat where year = 2025 and owner not in ('Unmatched')
                                               group by 1 order by sum(spend) desc limit 40""").fetchall()]
    if PINNED_OWNER not in top_owners:
        top_owners.append(PINNED_OWNER)
    products: dict = {}
    for owner in top_owners:
        rows = con.execute("""select family, year, sum(spend), any_value(area)
                              from sales_nat where owner = ? and market_class = 'Brand' group by 1, 2""", [owner]).fetchall()
        by = _by_year(rows, 0, 1, [2])
        area_of = {}
        for fam, _, _, ar in rows:
            area_of[fam] = ar
        fams = sorted(by, key=lambda f: -(by[f][0][-1] + 0.05 * sum(by[f][0])))[:14]
        items = []
        for fam in fams:
            l = loe.get(fam)
            items.append({
                "family": fam, "area": area_of.get(fam, ""), "spend": [round(v) for v in by[fam][0]],
                "status": l[1] if l else "No Orange Book entry",
                "coreEnd": l[2].isoformat() if l and l[2] else None,
                "substanceEnd": l[3].isoformat() if l and l[3] else None,
                "lastEnd": max([d for d in (l[4], l[5]) if d], default=None).isoformat() if l and (l[4] or l[5]) else None,
            })
        products[owner] = items
    _write("products.json", {"owners": products})


def export_erosion(con) -> None:
    events = con.execute("""select ingredient, brand_family, entry_quarter, brand_run_rate_before_musd,
                                   brand_index_q4, brand_index_q8, generic_share_q4, generic_share_q8, molecule_index_q8
                            from mart_erosion_events order by brand_run_rate_before_musd desc""").fetchall()
    curves = con.execute("""select ingredient, quarters_since_entry, brand_spend_index, generic_share, molecule_spend_index
                            from mart_erosion_curve order by ingredient, quarters_since_entry""").fetchall()
    by: dict = {}
    for ing, k, bi, gs, mi in curves:
        c = by.setdefault(ing, {"k": [], "brandIndex": [], "genericShare": [], "moleculeIndex": []})
        c["k"].append(int(k))
        c["brandIndex"].append(None if bi is None else round(float(bi), 1))
        c["genericShare"].append(None if gs is None else round(float(gs), 4))
        c["moleculeIndex"].append(None if mi is None else round(float(mi), 1))
    _write("erosion.json", {
        "events": [{"ingredient": e[0], "brand": e[1], "entry": e[2].isoformat() if e[2] else None,
                    "runRateMusd": e[3], "brandIndexQ4": e[4], "brandIndexQ8": e[5],
                    "genericShareQ4": e[6], "genericShareQ8": e[7], "moleculeIndexQ8": e[8]} for e in events],
        "curves": by})


def export_loe(con, areas, as_of: str) -> None:
    out: dict = {}
    for seg in [ALL, *areas]:
        cond = "" if seg == ALL else "where area = ?"
        args = [] if seg == ALL else [seg]
        rows = con.execute(f"""select status, coalesce(year(core_protection_end), 0), count(*), sum(spend_2025)
                               from mart_loe {cond} group by 1, 2""", args).fetchall()
        by_year: dict = {}
        groups = {"Biologic (not in Orange Book)": [0, 0.0], "No patent or exclusivity listed": [0, 0.0],
                  "Listed protection has ended": [0, 0.0], "No Orange Book entry": [0, 0.0]}
        for status, yr, n, sp in rows:
            if status == "Protected":
                by_year[str(yr)] = {"families": int(n), "spend": float(sp)}
            else:
                groups[status][0] += int(n)
                groups[status][1] += float(sp or 0)
        out[seg] = {"byYear": by_year, "groups": {k: {"families": v[0], "spend": v[1]} for k, v in groups.items()}}
    top = con.execute("""select family, owner, area, spend_2025, status, core_protection_end, substance_patent_expiry,
                                last_patent_expiry, last_exclusivity_expiry
                         from mart_loe where status = 'Protected' order by spend_2025 desc limit 400""").fetchall()
    _write("loe.json", {"asOf": as_of, "segments": out, "top": [
        {"family": r[0], "owner": r[1], "area": r[2], "spend": float(r[3]), "coreEnd": r[5].isoformat() if r[5] else None,
         "substanceEnd": r[6].isoformat() if r[6] else None,
         "lastEnd": max([d for d in (r[7], r[8]) if d], default=None).isoformat() if (r[7] or r[8]) else None} for r in top]})


def export_states(con, areas) -> None:
    st = con.execute("select state, state_name, census_region, expanded_medicaid from dim_state where is_state order by state").fetchall()
    codes = [s[0] for s in st]
    data: dict = {}
    for seg in [ALL, *areas]:
        cond = "" if seg == ALL else "where area = ?"
        args = [] if seg == ALL else [seg]
        rows = con.execute(f"""select year, state, sum(spend), sum(rx), sum(brand_spend)
                               from mart_state_area_year {cond} group by 1, 2""", args).fetchall()
        per = {str(y): {c: [0, 0, 0] for c in codes} for y in YEARS}
        for year, state, sp, rx, bs in rows:
            if state in per[str(year)]:
                per[str(year)][state] = [round(float(sp or 0)), round(float(rx or 0)), round(float(bs or 0))]
        data[seg] = per
    enroll = {str(y): {} for y in YEARS}
    for state, year, en in con.execute("select state, year, enrollment from mart_state_year where is_state and enrollment is not null").fetchall():
        enroll[str(year)][state] = round(float(en))
    flags = {str(y): {} for y in YEARS}
    for state, year, ffs, yoy in con.execute("""select state, year, ffs_share, yoy_change from mart_state_flags
                                                where state in (select state from dim_state where is_state)""").fetchall():
        flags[str(year)][state] = [float(ffs), None if yoy is None else float(yoy)]
    recon = con.execute("select year, national_spend, state_sum, gap_pct from mart_reconciliation order by 1").fetchall()
    _write("states.json", {
        "states": [{"code": s[0], "name": s[1], "region": s[2], "expanded": bool(s[3]) if s[3] is not None else None} for s in st],
        "data": data, "enrollment": enroll, "flags": flags,
        "reconciliation": [{"year": int(r[0]), "national": float(r[1]), "states": float(r[2]), "gapPct": float(r[3])} for r in recon]})


def export_forecast() -> None:
    fc: dict = {}
    for r in csv.DictReader(open(MARTS / "forecast.csv", encoding="utf-8")):
        seg = ALL if r["segment"] == "All market" else r["segment"]
        slot = fc.setdefault(seg, {"actual": [], "forecast": [], "backtest": []})
        if r["kind"] == "actual":
            slot["actual"].append(float(r["spend"]))
        else:
            slot["forecast"].append({"year": int(r["year"]), "spend": float(r["spend"]), "low": float(r["low"]), "high": float(r["high"]), "method": r["method"]})
    for r in csv.DictReader(open(MARTS / "forecast_backtest.csv", encoding="utf-8")):
        seg = ALL if r["segment"] == "All market" else r["segment"]
        fc[seg]["backtest"].append({"method": r["method"], "mape": float(r["mape_pct"]), "beatsNaive": r["beats_naive"] == "True", "chosen": r["chosen"] == "True"})
    _write("forecast.json", fc)


def export_quality() -> None:
    checks = [dict(r) for r in csv.DictReader(open(MARTS / "dq_checks.csv", encoding="utf-8"))]
    for c in checks:
        c["dollars"] = float(c["dollars"]) if c["dollars"] else None
    wf = [{"stage": r["stage"], "dollars": float(r["dollars"]), "sharePct": float(r["share_pct"])}
          for r in csv.DictReader(open(MARTS / "dq_match_waterfall.csv", encoding="utf-8"))]
    _write("quality.json", {"checks": checks, "waterfall": wf})


def main() -> int:
    con = connect()
    areas = export_meta(con)
    as_of = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))["orangeBookAsOf"]
    export_market(con, areas)
    export_pvm(con)
    export_owners_and_products(con, areas)
    export_erosion(con)
    export_loe(con, areas, as_of)
    export_states(con, areas)
    export_forecast()
    export_quality()
    for p in sorted(OUT.glob("*.json")):
        print(f"{p.name:<16} {p.stat().st_size / 1e3:7.1f} KB")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import csv
import json
from pathlib import Path

import duckdb

from .config import BRANDS, CONTRACT_YEAR, MONTHS, REGIONS, ROOT
from .io import dump_json, query_dicts, rows_csv, sha256
from .normalize import enrollment, flag, identifier, ndc11, normalized_header, text_encoding


def read_rows(path, delimiter="|"):
    with Path(path).open(encoding=text_encoding(Path(path)), errors="strict", newline="") as f:
        for row_number, row in enumerate(csv.DictReader(f, delimiter=delimiter), 2):
            yield row_number, normalized_header(row)


def required(row, names, source):
    missing = set(names) - row.keys()
    if missing:
        raise ValueError(f"{source}: missing columns {sorted(missing)}")


def prepare(raw, stage):
    manifest = json.loads((raw / "manifest.json").read_text())
    if manifest.get("status") != "complete":
        raise ValueError("Acquisition is incomplete; analysis requires a complete manifest.")
    preview = manifest.get("mode") == "preview"
    filtered = manifest.get("transport") == "filtered"
    if filtered:
        if not manifest.get("ci_run_url", "").startswith("https://github.com/"):
            raise ValueError("Filtered transport requires an acquisition run receipt")
        for item in manifest["transport_files"]:
            path = (raw / item["path"]).resolve()
            if not path.is_relative_to(raw.resolve()) or sha256(path) != item["sha256"]:
                raise ValueError(f"Transport integrity failure: {item['path']}")
    if not preview and not filtered:
        for source in manifest["sources"]:
            p = ROOT / source["path"]
            if not p.exists() or sha256(p) != source["sha256"]:
                raise ValueError(f"Source integrity failure: {p}")
    catalog = json.loads((raw / "products" / "catalog.json").read_text())
    lookup = {}
    for item in catalog:
        if item["brand"] not in BRANDS or item["strength_mg"] not in BRANDS[item["brand"]]["strengths"]:
            raise ValueError("Unexpected catalog product")
        previous = lookup.setdefault(item["rxcui"], item)
        if previous != item:
            raise ValueError("Ambiguous RxCUI mapping")
    for brand, cfg in BRANDS.items():
        if {int(x["strength_mg"]) for x in catalog if x["brand"] == brand} != set(cfg["strengths"]):
            raise ValueError(f"Missing catalog strengths for {brand}")
    stage.mkdir(parents=True, exist_ok=True)
    plans, drugs, enrolls, indications, counts, quarantine = [], [], [], [], [], []
    snapshots = sorted(x["month"] for x in manifest["snapshots"])
    if not snapshots or any(m not in MONTHS for m in snapshots):
        raise ValueError("Unexpected or empty snapshot set")
    for month in snapshots:
        folder = raw / month
        metadata = next(x for x in manifest["snapshots"] if x["month"] == month)
        if not preview and not filtered:
            for kind, info in metadata["members"].items():
                if sha256(folder / f"{kind}.txt") != info["sha256"]:
                    raise ValueError(f"Extracted source integrity failure: {month}/{kind}")
            if sha256(folder / "enrollment.csv") != metadata["enrollment_sha256"]:
                raise ValueError(f"Enrollment integrity failure: {month}")
        plan_map = {}
        ids_path = folder / "formulary_ids.json"
        full_formulary_ids = set(json.loads(ids_path.read_text())) if ids_path.exists() else set()
        n = 0
        for rownum, row in read_rows(folder / "plans.txt"):
            rownum = int(row.get("ORIGINAL_SOURCE_ROW", rownum))
            n += 1
            required(row, ["CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "FORMULARY_ID", "PLAN_SUPPRESSED_YN", "PDP_REGION_CODE"], "plans")
            if not row["CONTRACT_ID"].startswith("S"):
                continue
            plan = row["CONTRACT_ID"] + "-" + identifier(row["PLAN_ID"], 3)
            if identifier(row["SEGMENT_ID"], 3) != "000":
                raise ValueError(f"Nonzero segment for standalone PDP: {plan}")
            suppressed = flag(row["PLAN_SUPPRESSED_YN"])
            region = int(row["PDP_REGION_CODE"]) if row["PDP_REGION_CODE"] else 0
            record = {"month": month, "plan_key": plan, "contract_id": row["CONTRACT_ID"], "plan_id": identifier(row["PLAN_ID"], 3),
                      "plan_name": row.get("PLAN_NAME", ""), "organization": row.get("CONTRACT_NAME", ""),
                      "formulary_id": row["FORMULARY_ID"], "region_code": region, "region": REGIONS.get(region, "Unknown region"),
                      "suppressed": "unknown" if suppressed is None else ("yes" if suppressed else "no"),
                      "source_row": rownum}
            if plan in plan_map:
                old = {k: v for k, v in plan_map[plan].items() if k != "source_row"}
                new = {k: v for k, v in record.items() if k != "source_row"}
                if old != new:
                    raise ValueError(f"Conflicting duplicate plan: {month}/{plan}")
            else:
                plan_map[plan] = record
        plans.extend(plan_map.values())
        counts.append({"month": month, "source": "plans", "source_rows": n, "retained_rows": len(plan_map)})
        n, kept = 0, 0
        for rownum, row in read_rows(folder / "formulary.txt"):
            rownum = int(row.get("ORIGINAL_SOURCE_ROW", rownum))
            n += 1
            required(row, ["FORMULARY_ID", "CONTRACT_YEAR", "RXCUI", "NDC", "TIER_LEVEL_VALUE", "PRIOR_AUTHORIZATION_YN", "STEP_THERAPY_YN", "QUANTITY_LIMIT_YN"], "formulary")
            if row["CONTRACT_YEAR"] != CONTRACT_YEAR:
                raise ValueError(f"Wrong contract year at {month}/formulary:{rownum}")
            full_formulary_ids.add(row["FORMULARY_ID"])
            if row["RXCUI"] not in lookup:
                continue
            item = lookup[row["RXCUI"]]
            drugs.append({"month": month, "formulary_id": row["FORMULARY_ID"], "rxcui": row["RXCUI"],
                          "ndc": ndc11(row["NDC"]), "brand": item["brand"], "strength_mg": int(item["strength_mg"]),
                          "tier": int(row["TIER_LEVEL_VALUE"]) if row["TIER_LEVEL_VALUE"] else None,
                          "pa": flag(row["PRIOR_AUTHORIZATION_YN"]), "st": flag(row["STEP_THERAPY_YN"]),
                          "ql": flag(row["QUANTITY_LIMIT_YN"]), "ql_amount": row.get("QUANTITY_LIMIT_AMOUNT", ""),
                          "ql_days": row.get("QUANTITY_LIMIT_DAYS", ""), "source_row": rownum})
            kept += 1
        counts.append({"month": month, "source": "formulary", "source_rows": n, "retained_rows": kept})
        for p in plan_map.values():
            p["formulary_complete"] = int(p["suppressed"] == "no" and p["formulary_id"] in full_formulary_ids)
        enroll_map, n = {}, 0
        for rownum, row in read_rows(folder / "enrollment.csv", ","):
            rownum = int(row.get("ORIGINAL_SOURCE_ROW", rownum))
            n += 1
            contract = row.get("CONTRACT_NUMBER", row.get("CONTRACT_ID", ""))
            if not contract.startswith("S"):
                continue
            if not row.get("PLAN_ID"):
                quarantine.append({"month":month,"source":"enrollment","source_row":rownum,"contract_id":contract,
                                   "reason":"Blank plan ID; cannot assign enrollment to a plan","reported_value":row.get("ENROLLMENT", "")})
                continue
            key = contract + "-" + identifier(row["PLAN_ID"], 3)
            val = enrollment(row.get("ENROLLMENT", ""))
            if key in enroll_map and enroll_map[key]["enrollment"] != val:
                raise ValueError(f"Conflicting enrollment for {month}/{key}")
            enroll_map[key] = {"month": month, "plan_key": key, "enrollment": val, "enrollment_source_row": rownum}
        enrolls.extend(enroll_map.values())
        counts.append({"month": month, "source": "enrollment", "source_rows": n, "retained_rows": len(enroll_map)})
        ipath = folder / "indications.txt"
        if ipath.exists():
            for rownum, row in read_rows(ipath):
                rownum = int(row.get("ORIGINAL_SOURCE_ROW", rownum))
                if row.get("RXCUI") in lookup:
                    indications.append({"month": month, "plan_key": row["CONTRACT_ID"] + "-" + identifier(row["PLAN_ID"], 3),
                                        "rxcui": row["RXCUI"], "disease": row.get("DISEASE", ""), "source_row": rownum})
    products = [{"brand": b, "strength_mg": mg, "strength_key": f"{b} {mg} mg"} for b, cfg in BRANDS.items() for mg in cfg["strengths"]]
    rows_csv(stage / "plans.csv", plans)
    rows_csv(stage / "drugs.csv", drugs, ["month", "formulary_id", "rxcui", "ndc", "brand", "strength_mg", "tier", "pa", "st", "ql", "ql_amount", "ql_days", "source_row"])
    rows_csv(stage / "enrollment.csv", enrolls)
    rows_csv(stage / "products.csv", products)
    rows_csv(stage / "indications.csv", indications, ["month", "plan_key", "rxcui", "disease", "source_row"])
    rows_csv(stage / "quarantine.csv", quarantine, ["month", "source", "source_row", "contract_id", "reason", "reported_value"])
    for count in counts:
        snap = next(x for x in manifest["snapshots"] if x["month"] == count["month"])
        filename = {"plans":"plans.txt", "formulary":"formulary.txt", "enrollment":"enrollment.csv"}[count["source"]]
        count["source_rows"] = snap.get("full_row_counts", {}).get(filename, count["source_rows"])
    rows_csv(stage / "source_counts.csv", counts)
    dump_json(stage / "manifest.json", manifest)
    return manifest


def build(preview=False):
    base = ROOT / "outputs" / "preview" if preview else ROOT
    raw, stage = base / "data" / "raw", base / "data" / "stage"
    manifest = prepare(raw, stage)
    if (manifest["mode"] == "preview") != preview:
        raise ValueError("Real and preview datasets must remain separate")
    warehouse = base / "data" / "warehouse"
    warehouse.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse / "access.duckdb"))
    con.execute("SET preserve_insertion_order = true")
    for name in ["plans", "drugs", "enrollment", "products", "indications", "source_counts", "quarantine"]:
        path = str(stage / f"{name}.csv").replace("'", "''")
        con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS SELECT * FROM read_csv('{path}', header=true, all_varchar=true)")
    con.execute((ROOT / "sql" / "model.sql").read_text())
    marts = base / "data" / "marts"
    tables = ["dim_snapshot", "dim_brand", "dim_plan", "fact_brand", "fact_strength", "fact_change", "fact_brand_change", "mart_summary", "mart_change_summary", "mart_review_queue", "mart_quality", "mart_source_counts", "mart_quarantine"]
    for table in tables:
        rows = query_dicts(con, f"SELECT * FROM {table} ORDER BY ALL")
        rows_csv(marts / f"{table}.csv", rows, [x[0] for x in con.execute(f"SELECT * FROM {table} LIMIT 0").description])
    failed = query_dicts(con, "SELECT * FROM mart_quality WHERE severity='error' AND status='FAIL'")
    if failed:
        raise ValueError(f"Quality gate failed: {failed}")
    receipt = {"mode": manifest["mode"], "snapshots": [x["month"] for x in manifest["snapshots"]],
               "rows": {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables},
               "status": "passed", "source_manifest_sha256": sha256(raw / "manifest.json")}
    dump_json(base / "outputs" / "build-receipt.json", receipt)
    con.close()
    print(json.dumps(receipt, indent=2))
    return base

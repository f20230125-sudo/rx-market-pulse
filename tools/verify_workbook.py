"""Independent check of the Excel model.

    powershell -File tools/excel_probe.ps1 -Path excel/Territory-Targeting-Model.xlsx -Out out.json
    python tools/verify_workbook.py out.json

Excel (driven through COM) evaluates the workbook's own formulas for several input scenarios. This script
recomputes the same scenarios straight from the warehouse, in Python, with no shared code, and compares
every state's spend, growth, percentiles, score, rank and target. Passing means the formulas do what the
Read me says they do.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {  # size, growth, intensity, brand
    "Balanced": (0.35, 0.25, 0.20, 0.20),
    "Growth-led": (0.20, 0.45, 0.20, 0.15),
    "Size-led": (0.55, 0.10, 0.20, 0.15),
}
MIN_BASE = 1_000_000
FFS_THR, SWING_THR = 0.25, 0.40


def percentrank_inc(values: list[float], x: float) -> float:
    return sum(1 for v in values if v < x) / (len(values) - 1)


def expected(con, s: dict) -> dict[str, dict]:
    area_sql = "" if s["area"] == "All areas" else "and area = ?"
    args = [] if s["area"] == "All areas" else [s["area"]]

    def spend(year: int) -> dict[str, tuple[float, float]]:
        rows = con.execute(
            f"""select state, sum(spend), sum(coalesce(brand_spend, 0)) from mart_state_area_year
                where year = ? and state in (select state from dim_state where is_state) {area_sql} group by 1""",
            [year, *args],
        ).fetchall()
        return {st: (sp, br) for st, sp, br in rows}

    base, prior = spend(s["year"]), spend(s["year"] - s["look"])
    enroll = dict(con.execute("select state, enrollment from mart_state_year where year = ? and is_state", [s["year"]]).fetchall())
    names = dict(con.execute("select state, state_name from dim_state where is_state").fetchall())
    order = sorted(names, key=lambda k: names[k])  # the workbook lists states alphabetically by name
    flag_rows = con.execute("select state, year, ffs_share, yoy_change from mart_state_flags").fetchall()
    ffs = {(st, y): f for st, y, f, _ in flag_rows}
    yoy = {(st, y): c for st, y, _, c in flag_rows}

    out: dict[str, dict] = {}
    for st in order:
        d, br = base.get(st, (0.0, 0.0))
        e = prior.get(st, (0.0, 0.0))[0]
        out[st] = {"D": d, "E": e, "brand": br / d if d else 0.0, "H": enroll.get(st, 0.0)}
        out[st]["F"] = (d / e) ** (1 / s["look"]) - 1 if e > 0 else None
    f_values = [v["F"] for v in out.values() if v["F"] is not None]
    med = statistics.median(f_values)
    y1, y0 = s["year"], s["year"] - s["look"]
    for st, v in out.items():
        swing = max([abs(yoy[(st, y)]) for y in range(y0 + 1, y1 + 1) if yoy.get((st, y)) is not None] or [0.0])
        v["U"], v["V"], v["W"] = ffs[(st, y1)], ffs[(st, y0)], swing
        v["X"] = "Check" if (abs(v["U"] - v["V"]) >= FFS_THR or swing >= SWING_THR) else ""
        neutralise = s.get("neut", "Yes") == "Yes" and v["X"] == "Check"
        v["G"] = v["F"] if (v["E"] >= MIN_BASE and v["F"] is not None and not neutralise) else med
        v["I"] = v["D"] / v["H"] if v["H"] else 0.0
    w = WEIGHTS[s["scen"]]
    cols = {"K": [v["D"] for v in out.values()], "L": [v["G"] for v in out.values()],
            "M": [v["I"] for v in out.values()], "N": [v["brand"] for v in out.values()]}
    src = {"K": "D", "L": "G", "M": "I", "N": "brand"}
    for i, (st, v) in enumerate(out.items()):
        for c, s_key in src.items():
            v[c] = percentrank_inc(cols[c], v[s_key])
        v["O"] = 100 * (w[0] * v["K"] + w[1] * v["L"] + w[2] * v["M"] + w[3] * v["N"]) + (7 + i) / 1_000_000
    ranked = sorted(out, key=lambda k: -out[k]["O"])
    total_d = sum(v["D"] for v in out.values())
    total_r = sum(v["O"] * v["D"] for v in out.values())
    for st, v in out.items():
        v["P"] = ranked.index(st) + 1
        v["Q"] = "A" if v["P"] <= s["ta"] else "B" if v["P"] <= s["ta"] + s["tb"] else "C"
        v["S"] = v["D"] + total_d * s["growth"] * (v["O"] * v["D"]) / total_r
    return out


def main(path: str) -> int:
    con = duckdb.connect(str(ROOT / "data" / "warehouse" / "rx.duckdb"), read_only=True)
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    failures = 0
    for sc in data:
        s = sc["inputs"]
        exp = expected(con, s)
        bad = 0
        for row in sc["rows"]:
            st, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, S, U, V, W, X = row
            e = exp[st]
            pairs = [("D", D, e["D"]), ("E", E, e["E"]), ("G", G, e["G"]), ("H", H, e["H"]), ("I", I, e["I"]),
                     ("J", J, e["brand"]), ("K", K, e["K"]), ("L", L, e["L"]), ("M", M, e["M"]), ("N", N, e["N"]),
                     ("O", O, e["O"]), ("S", S, e["S"]), ("U", U, e["U"]), ("V", V, e["V"]), ("W", W, e["W"])]
            for name, got, want in pairs:
                tol = 1e-6 * max(1.0, abs(want)) if name in ("D", "E", "H", "I", "S") else 1e-6
                if abs(float(got) - float(want)) > tol:
                    bad += 1
                    print(f"  {sc['id']} {st} {name}: excel {got!r} vs python {want!r}")
            if (X or "") != e["X"]:
                bad += 1
                print(f"  {sc['id']} {st} flag: excel {X!r} vs python {e['X']!r}")
            if int(P) != e["P"] or Q != e["Q"]:
                bad += 1
                print(f"  {sc['id']} {st} rank/tier: excel {P},{Q} vs python {e['P']},{e['Q']}")
        checks_ok = all(c == "OK" for c in sc["checks"])
        top_py = [n for _, n in sorted((v["P"], k) for k, v in exp.items())][:10]
        names = dict(con.execute("select state, state_name from dim_state").fetchall())
        top_ok = sc["top10"] == [names[k] for k in top_py]
        flagged = sorted(k for k, v in exp.items() if v["X"])
        status = "PASS" if bad == 0 and checks_ok and top_ok else "FAIL"
        failures += status == "FAIL"
        print(f"{sc['id']} {s['area']} / {s['year']} / look {s['look']} / {s['scen']}: {status}  "
              f"(mismatches {bad}, workbook checks {'OK' if checks_ok else sc['checks']}, top-10 match {top_ok}, "
              f"coverage {sc['coverage']:.1%}, flagged {','.join(flagged) or 'none'})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

"""Quarterly forecasts: 2022-23 select a method; 2024-25 test that frozen choice."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from .sources import MARTS, ROOT, WAREHOUSE

METHODS = ("seasonal-naive", "seasonal-drift", "seasonal-trend")
TRAIN_END, SELECT_END, TEST_END, HORIZON = 11, 19, 27, 8


def period(i: int) -> str:
    return f"{2019 + i // 4}Q{i % 4 + 1}"


def predict(method: str, history: list[float], horizon: int = 8) -> list[float]:
    if len(history) < 8 or horizon < 1 or method not in METHODS:
        raise ValueError("need eight quarters, a positive horizon and a known method")
    if any(not math.isfinite(v) or v < 0 for v in history):
        raise ValueError("history must contain finite nonnegative spend")
    if method == "seasonal-trend":

        def features(t):
            return [1, t / 4, *[float(t % 4 == q) for q in (1, 2, 3)]]

        n = len(history)
        coef = np.linalg.lstsq(
            [features(t) for t in range(n)], np.log1p(history), rcond=None
        )[0]
        return [
            max(0.0, math.expm1(min(700, float(np.dot(features(n + h), coef)))))
            for h in range(horizon)
        ]
    growth = sum(history[-4:]) / sum(history[-8:-4]) if sum(history[-8:-4]) else 1
    if method == "seasonal-naive":
        growth = 1
    return [history[-4 + h % 4] * growth ** (1 + h // 4) for h in range(horizon)]


def rolling(values: list[float], method: str, start: int, end: int) -> list[dict]:
    rows = []
    for origin in range(start - 1, end):
        for h, pred in enumerate(predict(method, values[: origin + 1]), 1):
            target = origin + h
            if target > end:
                break
            rows.append(
                {
                    "method": method,
                    "origin": period(origin),
                    "target": period(target),
                    "horizon": h,
                    "actual": values[target],
                    "predicted": pred,
                    "error": pred - values[target],
                }
            )
    return rows


def metrics(rows: list[dict]) -> dict:
    errors = [abs(r["error"]) for r in rows]
    total = sum(r["actual"] for r in rows)
    nz = [r for r in rows if r["actual"] > 0]
    return {
        "n": len(rows),
        "wape": 100 * sum(errors) / total if total else None,
        "mape": 100 * sum(abs(r["error"]) / r["actual"] for r in nz) / len(nz)
        if nz
        else None,
        "mae": float(np.mean(errors)) if rows else None,
        "rmse": float(np.sqrt(np.mean([r["error"] ** 2 for r in rows])))
        if rows
        else None,
    }


def bounds(
    pred: float, horizon: int, residuals: list[dict]
) -> tuple[float, float, int]:
    available = [r for r in residuals if r["predicted"] > 0]
    pool = []
    for radius in range(HORIZON):
        pool = [r for r in available if abs(r["horizon"] - horizon) <= radius]
        if len(pool) >= 8:
            break
    if not pool:
        return pred, pred, 0
    lo, hi = np.quantile([r["actual"] / r["predicted"] for r in pool], [0.1, 0.9])
    return max(0.0, pred * min(1, float(lo))), pred * max(1, float(hi)), len(pool)


def evaluate(values: list[float]) -> dict:
    if len(values) != 28:
        raise ValueError("expected 28 consecutive quarters, 2019Q1 through 2025Q4")
    selection = {m: rolling(values, m, 12, SELECT_END) for m in METHODS}

    def score(m):
        wape = metrics(selection[m])["wape"]
        return wape if wape is not None else float("inf")

    chosen = min(METHODS, key=score)
    test = {m: rolling(values, m, 20, TEST_END) for m in METHODS}
    methods = [
        {
            "method": m,
            "chosen": m == chosen,
            "selection": metrics(selection[m]),
            "test": metrics(test[m]),
            "byHorizon": [
                dict(horizon=h, **metrics([r for r in test[m] if r["horizon"] == h]))
                for h in range(1, 9)
            ],
        }
        for m in METHODS
    ]
    checked = []
    for row in test[chosen]:
        # Holdout coverage uses only pre-holdout residuals to avoid calibration leakage.
        lo, hi, n = bounds(row["predicted"], row["horizon"], selection[chosen])
        checked.append(
            dict(
                **row,
                low=lo,
                high=hi,
                calibrationN=n,
                covered=lo <= row["actual"] <= hi,
            )
        )
    future = []
    for h, pred in enumerate(predict(chosen, values), 1):
        lo, hi, n = bounds(pred, h, selection[chosen] + test[chosen])
        future.append(
            {
                "period": period(TEST_END + h),
                "spend": pred,
                "low": lo,
                "high": hi,
                "method": chosen,
                "calibrationN": n,
            }
        )
    return {
        "actual": [{"period": period(i), "spend": v} for i, v in enumerate(values)],
        "forecast": future,
        "chosen": chosen,
        "methods": methods,
        "holdoutPredictions": checked,
        "holdoutCoverage": sum(r["covered"] for r in checked) / len(checked),
        "holdoutCases": len(checked),
        "selectionEnds": period(SELECT_END),
        "testStarts": period(20),
        "testEnds": period(TEST_END),
        "bandDescription": "Empirical 10th–90th percentile error scenarios, with nearby horizons pooled to at least 8 residuals. Annual ranges sum quarter bounds; no guaranteed coverage.",
    }


def export(
    con, marts: Path = MARTS, out: Path = ROOT / "dashboard/public/data"
) -> dict:
    rows = con.execute("""select 'All market', year,quarter,sum(spend) from sales_nat group by 2,3
        union all select area,year,quarter,sum(spend) from sales_nat group by 1,2,3 order by 1,2,3""").fetchall()
    return export_rows(rows, marts, out)


def export_rows(
    rows: list[tuple], marts: Path = MARTS, out: Path = ROOT / "dashboard/public/data"
) -> dict:
    series: dict[str, list[float]] = {}
    for seg, year, q, spend in rows:
        vals = series.setdefault(seg, [])
        if (year - 2019) * 4 + q - 1 != len(vals):
            raise ValueError(f"missing or duplicate quarter: {seg}")
        vals.append(float(spend))
    payload, annual, back, inputs = {}, [], [], []
    for seg, vals in series.items():
        result = evaluate(vals)
        actual = [sum(vals[i : i + 4]) for i in range(0, 28, 4)]
        future = [
            dict(
                year=2026 + i // 4,
                method=result["chosen"],
                **{
                    k: sum(r[k] for r in result["forecast"][i : i + 4])
                    for k in ("spend", "low", "high")
                },
            )
            for i in (0, 4)
        ]
        naive = next(m for m in result["methods"] if m["method"] == "seasonal-naive")
        bt = [
            {
                "method": m["method"],
                "mape": m["test"]["mape"] or 0,
                "beatsNaive": (m["test"]["wape"] or 0) < (naive["test"]["wape"] or 0),
                "chosen": m["chosen"],
            }
            for m in result["methods"]
        ]
        payload["All areas" if seg == "All market" else seg] = {
            "actual": actual,
            "forecast": future,
            "backtest": bt,
            "quarterly": result,
        }
        annual.extend(
            {
                "segment": seg,
                "year": y,
                "kind": "actual",
                "spend": round(v),
                "low": "",
                "high": "",
                "method": "",
            }
            for y, v in zip(range(2019, 2026), actual)
        )
        annual.extend(dict(segment=seg, kind="forecast", **r) for r in future)
        back.extend(
            {
                "segment": seg,
                "method": m["method"],
                "chosen": m["chosen"],
                "selection_wape": m["selection"]["wape"],
                "test_wape": m["test"]["wape"],
                "test_mape": m["test"]["mape"],
                "test_n": m["test"]["n"],
            }
            for m in result["methods"]
        )
        inputs.extend(dict(segment=seg, **r) for r in result["actual"])
    marts.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("forecast.csv", annual),
        ("forecast_backtest.csv", back),
        ("forecast_quarterly_inputs.csv", inputs),
    ]:
        with (marts / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    out.mkdir(parents=True, exist_ok=True)
    (out / "forecast.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    (marts / "forecast_evaluation.json").write_text(
        json.dumps({k: v["quarterly"] for k, v in payload.items()}, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        type=Path,
        help="Reproduce from the committed quarterly input CSV, without the full warehouse",
    )
    args = parser.parse_args()
    import duckdb

    if args.inputs:
        with args.inputs.open(encoding="utf-8") as f:
            rows = [
                (
                    r["segment"],
                    int(r["period"][:4]),
                    int(r["period"][-1]),
                    float(r["spend"]),
                )
                for r in csv.DictReader(f)
            ]
        data = export_rows(sorted(rows))
    else:
        with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
            data = export(con)
    q = data["All areas"]["quarterly"]
    print(
        f"28 quarters; selected {q['chosen']} before {q['selectionEnds']}; test {q['testStarts']}–{q['testEnds']}"
    )
    for m in q["methods"]:
        print(
            f"{m['method']}: selection WAPE {m['selection']['wape']:.2f}%, test WAPE {m['test']['wape']:.2f}%"
        )
    return 0

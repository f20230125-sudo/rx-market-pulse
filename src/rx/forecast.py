"""Spend forecast with a backtest, so the number comes with an honest error bar.

    python -m rx.forecast

Seven annual points (2019-2025) is not much, and 2024 is a visible dip. So the goal is not a clever model;
it is to show whether any method beats "next year equals this year", and by how much it misses.

Methods (each forecasts one year ahead from the history it is given):
    naive      next year = last year
    drift      last year x (1 + average growth of the last 2 years)
    log-trend  straight line through log(spend) for the last 4 years, extended one year

Backtest: for origin years 2021-2024, forecast the next year, compare with what happened. The method with
the lowest mean absolute percentage error (MAPE) is used for 2026 and 2027, and the 80th percentile of its
backtest errors gives the interval. Segments: the whole market and each therapeutic area.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass

import numpy as np

from .build import connect
from .sources import MARTS

METHODS = ("naive", "drift", "log-trend")
FIRST_ORIGIN, LAST_YEAR, HORIZON_END = 2021, 2025, 2027


def predict(method: str, years: list[int], values: list[float], steps: int = 1) -> float:
    """Forecast `steps` years past the last year in `years` using only the given history."""
    if method == "naive":
        return values[-1]
    if method == "drift":
        growth = (values[-1] / values[-3]) ** 0.5 - 1 if len(values) >= 3 else 0.0
        return values[-1] * (1 + growth) ** steps
    if method == "log-trend":
        n = min(4, len(values))
        x = np.array(years[-n:], dtype=float)
        y = np.log(np.array(values[-n:], dtype=float))
        slope, intercept = np.polyfit(x, y, 1)
        return float(math.exp(intercept + slope * (years[-1] + steps)))
    raise ValueError(method)


@dataclass
class Backtest:
    segment: str
    method: str
    mape: float
    errors: list[float]  # signed percentage errors, forecast vs actual


def backtest(segment: str, years: list[int], values: list[float]) -> list[Backtest]:
    out = []
    for method in METHODS:
        errs = []
        for origin in range(FIRST_ORIGIN, LAST_YEAR):
            k = years.index(origin) + 1
            pred = predict(method, years[:k], values[:k])
            actual = values[years.index(origin + 1)]
            errs.append(100 * (pred - actual) / actual)
        out.append(Backtest(segment, method, float(np.mean(np.abs(errs))), errs))
    return out


def main() -> int:
    con = connect()
    rows = con.execute("select 'All market' as seg, year, sum(spend) from sales_nat group by 2 "
                       "union all select area, year, sum(spend) from sales_nat group by 1, 2 order by 1, 2").fetchall()
    series: dict[str, tuple[list[int], list[float]]] = {}
    for seg, year, spend in rows:
        ys, vs = series.setdefault(seg, ([], []))
        ys.append(int(year))
        vs.append(float(spend))

    back_rows, fc_rows = [], []
    for seg, (ys, vs) in series.items():
        results = backtest(seg, ys, vs)
        best = min(results, key=lambda b: b.mape)
        naive = next(b for b in results if b.method == "naive")
        for b in results:
            back_rows.append({"segment": seg, "method": b.method, "mape_pct": round(b.mape, 2),
                              "beats_naive": b.mape < naive.mape, "chosen": b is best,
                              **{f"error_{FIRST_ORIGIN + i + 1}": round(e, 2) for i, e in enumerate(b.errors)}})
        band = float(np.percentile(np.abs(best.errors), 80)) / 100
        for y, v in zip(ys, vs):
            fc_rows.append({"segment": seg, "year": y, "kind": "actual", "spend": round(v), "low": "", "high": "", "method": ""})
        for steps, year in enumerate(range(LAST_YEAR + 1, HORIZON_END + 1), start=1):
            p = predict(best.method, ys, vs, steps)
            widen = band * math.sqrt(steps)
            fc_rows.append({"segment": seg, "year": year, "kind": "forecast", "spend": round(p),
                            "low": round(p * (1 - widen)), "high": round(p * (1 + widen)), "method": best.method})

    MARTS.mkdir(parents=True, exist_ok=True)
    for name, data in (("forecast_backtest.csv", back_rows), ("forecast.csv", fc_rows)):
        with open(MARTS / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)

    whole = [r for r in back_rows if r["segment"] == "All market"]
    for r in whole:
        print(f"All market  {r['method']:<10} MAPE {r['mape_pct']:>5}%  beats naive: {r['beats_naive']}  chosen: {r['chosen']}")
    wins = sum(1 for r in back_rows if r["chosen"] and r["method"] != "naive")
    print(f"{wins} of {len(series)} segments: a method beat naive in the backtest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

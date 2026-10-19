import math

import pytest

from rx.quarterly import METHODS, bounds, evaluate, metrics, predict, rolling


def seasonal():
    return [100 + (i % 4) * 10 for i in range(28)]


def test_seasonal_baseline_preserves_quarter_alignment_beyond_one_year():
    assert predict("seasonal-naive", seasonal()[:12]) == [100, 110, 120, 130] * 2
    assert predict("seasonal-naive", seasonal()[:13], 4) == [110, 120, 130, 100]


def test_changing_holdout_cannot_change_selected_method_or_validation_results():
    base = seasonal()
    a = evaluate(base)
    b = evaluate(base[:20] + [v * 10 for v in base[20:]])
    assert a["chosen"] == b["chosen"]
    assert [m["selection"] for m in a["methods"]] == [
        m["selection"] for m in b["methods"]
    ]
    assert (
        a["holdoutPredictions"][0]["predicted"]
        == b["holdoutPredictions"][0]["predicted"]
    )
    assert a["holdoutPredictions"][0]["low"] == b["holdoutPredictions"][0]["low"]


def test_rolling_origin_never_reads_its_target_or_later_values():
    a = rolling(seasonal(), "seasonal-drift", 20, 27)
    altered = seasonal()
    altered[-1] = 999999
    b = rolling(altered, "seasonal-drift", 20, 27)
    assert [r["predicted"] for r in a] == [r["predicted"] for r in b]
    assert all(r["origin"] < r["target"] for r in a)
    assert len(a) == 36


@pytest.mark.parametrize("method", METHODS)
def test_zero_series_produces_finite_nonnegative_forecasts(method):
    assert all(math.isfinite(v) and v >= 0 for v in predict(method, [0.0] * 16))


def test_wape_weights_by_actual_volume_and_handles_zero_actuals():
    result = metrics([{"actual": 100, "error": 10}, {"actual": 0, "error": 5}])
    assert result["wape"] == 15
    assert result["mape"] == 10


def test_forecast_has_eight_future_quarters_and_bounds_enclose_point():
    result = evaluate(seasonal())
    assert result["forecast"][0]["period"] == "2026Q1"
    assert result["forecast"][-1]["period"] == "2027Q4"
    assert all(r["low"] <= r["spend"] <= r["high"] for r in result["forecast"])
    assert bounds(0, 8, []) == (0, 0, 0)


def test_incomplete_history_is_rejected_instead_of_silently_misaligned():
    with pytest.raises(ValueError, match="28 consecutive"):
        evaluate(seasonal()[:-1])

"""Invariant 2: the predictions add to 100. Also checks the error and pass-mark code."""
import numpy as np
import pandas as pd
import pytest

from rangecover.evaluate import errors, pass_mark, scale_to_100


def test_predictions_add_to_100():
    rng = np.random.default_rng(0)
    raw = rng.normal(30, 25, size=(500, 3))          # includes negative values
    raw[0] = [0, 0, 0]                                # an all-zero row
    raw[1] = [-5, -1, -3]                             # all negative: zero after clipping
    scaled = scale_to_100(raw)
    np.testing.assert_allclose(scaled.sum(axis=1), 100)
    assert (scaled >= 0).all()
    np.testing.assert_allclose(scaled[0], [100 / 3] * 3)


def test_scaling_keeps_the_ratios():
    np.testing.assert_allclose(scale_to_100([[20, 20, 10]]), [[40, 40, 20]])


def test_mae_and_rmse_known_values():
    true = np.array([[50, 30, 20], [50, 30, 20]])
    pred = np.array([[54, 30, 16], [50, 30, 20]])    # one miss of 4 on green and bare
    e = errors(true, pred)
    assert e["mae_green"] == pytest.approx(2.0)
    assert e["mae_dry"] == pytest.approx(0.0)
    assert e["rmse_green"] == pytest.approx(np.sqrt(8))   # sqrt((16 + 0) / 2)


def _runs(dry, green=10.0, bare=10.0, n=15):
    return pd.DataFrame({"mae_green": green, "mae_dry": dry, "mae_bare": bare},
                        index=range(n))


def test_pass_mark_passes_when_all_three_hold():
    result = pass_mark(_runs(20.0), _runs(18.0, green=10.4, bare=10.4))
    assert result["verdict"] == "pass" and result["dry_wins"] == 15


def test_pass_mark_fails_on_small_gain():
    assert pass_mark(_runs(20.0), _runs(19.0))["verdict"] == "fail"


def test_pass_mark_fails_on_too_few_wins():
    m3 = _runs(15.0)
    m3.loc[:3, "mae_dry"] = 25.0                      # loses 4 runs: 11 wins
    result = pass_mark(_runs(20.0), m3)
    assert result["1_dry_gain_ok"] and not result["2_dry_wins_ok"]


def test_pass_mark_fails_when_green_gets_worse():
    result = pass_mark(_runs(20.0), _runs(17.0, green=10.6))
    assert not result["3_green_bare_ok"] and result["verdict"] == "fail"


def test_pass_mark_needs_the_same_runs():
    with pytest.raises(ValueError):
        pass_mark(_runs(20.0), _runs(18.0, n=14))


def test_dry_gain_range_resamples_sites_and_is_fixed_by_seed():
    """The range brackets the true gain, and the same seed gives the same range."""
    from rangecover.evaluate import dry_gain_range

    rng = np.random.default_rng(1)
    rows = []
    for site in range(40):
        gain = rng.normal(1.0, 1.0)
        for run in range(3):
            for method, err in (("m2", 10 + gain), ("m3", 10.0)):
                rows.append({"run": run, "method": method, "site_unique": f"S{site:04d}-1",
                             "true_dry": 50.0, "pred_dry": 50.0 + err})
    preds = pd.DataFrame(rows)
    out = dry_gain_range(preds)
    assert out["n_sites"] == 40 and out["dry_gain_low"] < 1.0 < out["dry_gain_high"]
    assert dry_gain_range(preds) == out
    assert dry_gain_range(preds, seed=1) != out

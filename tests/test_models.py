"""Step 4 models: the method list, invariant 2 on real model outputs, reproducibility.

The visits, features and labels are made up, so the tests run without the data.
"""
import numpy as np
import pandas as pd
import pytest

from rangecover.evaluate import LABELS
from rangecover.features import PHOTO, SATELLITE, WEATHER
from rangecover.models import METHODS, run_all
from rangecover.splits import make_test_runs


@pytest.fixture(scope="module")
def setup():
    """120 sites (some with 2-3 visits), random features and labels that add to 100."""
    rng = np.random.default_rng(7)
    n_sites = 120
    sites = pd.DataFrame({"site": [f"S{i:03d}" for i in range(n_sites)],
                          "latitude": rng.uniform(-40, -12, n_sites),
                          "longitude": rng.uniform(115, 152, n_sites)})
    visits = sites.loc[sites.index.repeat(rng.choice([1, 1, 2, 3], n_sites))].reset_index(drop=True)
    n = len(visits)
    visits["site_unique"] = [f"V{i:04d}" for i in range(n)]
    visits[LABELS] = rng.dirichlet([2, 3, 2], size=n) * 100
    fixed = pd.DataFrame(rng.normal(size=(n, len(SATELLITE + WEATHER))),
                         columns=SATELLITE + WEATHER)
    photos = rng.normal(size=(n, 768))
    runs = make_test_runs(visits)[:3]
    return visits, fixed, photos, runs


def test_methods_match_the_frozen_list():
    """#1 sat; #2 adds weather; #3 adds photos; #4 is linear on #3's columns."""
    m1, m2, m3, m4 = METHODS
    assert [m.kind for m in METHODS] == ["rf", "rf", "rf", "linear"]
    assert m1.columns == tuple(SATELLITE)
    assert m2.columns == m1.columns + tuple(WEATHER)
    assert m3.columns == m2.columns + tuple(PHOTO)      # the only change from #2: photos
    assert m4.columns == m3.columns


def test_every_method_predicts_rows_that_add_to_100(setup):
    predictions, run_errors = run_all(*setup, n_trees=10)
    pred = predictions[[f"pred_{k}" for k in LABELS]].to_numpy()
    np.testing.assert_allclose(pred.sum(axis=1), 100)
    assert (pred >= 0).all()
    assert set(predictions["method"]) == {m.name for m in METHODS}
    assert len(run_errors) == len(setup[3]) * len(METHODS)


def test_predictions_cover_each_test_visit_once(setup):
    visits, _, _, runs = setup
    predictions, _ = run_all(*setup, n_trees=10)
    for run in runs:
        for method in METHODS:
            rows = predictions[(predictions["run"] == run.run) & (predictions["method"] == method.name)]
            assert sorted(rows["site_unique"]) == sorted(visits["site_unique"].iloc[run.test])


def test_a_rerun_gives_the_same_numbers(setup):
    _, first = run_all(*setup, n_trees=10)
    _, second = run_all(*setup, n_trees=10)
    pd.testing.assert_frame_equal(first, second)

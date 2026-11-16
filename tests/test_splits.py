"""Invariant 1: no site is in both train and test.

The tests use a made-up visit table, so they run without the data (on the Mac
as a smoke test, or in Colab). Some sites have several visits, as in the real
data, because that is how a site could leak across train and test.
"""
import numpy as np
import pandas as pd
import pytest

from rangecover.splits import SEEDS, make_test_runs


@pytest.fixture
def visits() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n_sites = 120
    sites = pd.DataFrame({
        "site": [f"S{i:03d}" for i in range(n_sites)],
        "latitude": rng.uniform(-40, -12, n_sites),
        "longitude": rng.uniform(115, 152, n_sites),
    })
    repeats = rng.choice([1, 1, 1, 2, 3], n_sites)   # some sites have 2-3 visits
    return sites.loc[sites.index.repeat(repeats)].reset_index(drop=True)


def test_no_site_in_both_train_and_test(visits):
    for run in make_test_runs(visits):
        train_sites = set(visits["site"].iloc[run.train])
        test_sites = set(visits["site"].iloc[run.test])
        assert not train_sites & test_sites, f"run {run.run} shares sites"


def test_each_visit_is_tested_once_per_grouping(visits):
    runs = make_test_runs(visits)
    assert len(runs) == 15
    for seed in SEEDS:
        tested = np.concatenate([r.test for r in runs if r.seed == seed])
        assert sorted(tested) == list(range(len(visits)))
    for run in runs:
        assert len(run.train) + len(run.test) == len(visits)


def test_groupings_differ_between_seeds(visits):
    runs = make_test_runs(visits)
    groupings = [{frozenset(r.test) for r in runs if r.seed == s} for s in SEEDS]
    assert groupings[0] != groupings[1] != groupings[2] != groupings[0]


def test_runs_are_reproducible(visits):
    first, second = make_test_runs(visits), make_test_runs(visits)
    assert all(np.array_equal(a.test, b.test) for a, b in zip(first, second))

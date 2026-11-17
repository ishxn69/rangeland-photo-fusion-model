"""Step 3 features: known values, and no leakage from test visits into the PCA.

All inputs are made up, so the tests run without the data.
"""
import numpy as np
import pandas as pd
import pytest

from rangecover.features import (PHOTO, SATELLITE, WEATHER, fixed_features, photo_features,
                                 satellite_features, weather_features)
from rangecover import splits   # module import: pytest would try to collect a bare TestRun


def _crops(values: dict[str, float], n: int = 2) -> np.ndarray:
    """Crops of shape (n, 6, 10, 10) where each band has one constant value."""
    order = ["B2", "B3", "B4", "B8", "B11", "B12"]
    return np.stack([np.full((n, 10, 10), values[b]) for b in order], axis=1)


def _run(n: int = 100, n_test: int = 25) -> splits.TestRun:
    return splits.TestRun(run=0, seed=0, group=0, train=np.arange(n_test, n), test=np.arange(n_test))


def test_band_means_and_indices_known_values():
    crops = _crops({"B2": 0.05, "B3": 0.08, "B4": 0.1, "B8": 0.3, "B11": 0.3, "B12": 0.2})
    table = satellite_features(crops)
    assert list(table.columns) == SATELLITE
    np.testing.assert_allclose(table["B4_mean"], 0.1)
    np.testing.assert_allclose(table["ndvi"], 0.5)        # (0.3 - 0.1) / (0.3 + 0.1)
    np.testing.assert_allclose(table["ndti"], 0.2)        # (0.3 - 0.2) / (0.3 + 0.2)


def test_indices_are_averaged_per_pixel():
    """Index of each pixel, then the mean: not the index of the mean bands."""
    crops = _crops({"B2": 0.1, "B3": 0.1, "B4": 0.1, "B8": 0.3, "B11": 0.3, "B12": 0.2}, n=1)
    crops[0, 3, :5] = 0.1                                  # half the pixels: B8 = B4, NDVI 0
    assert satellite_features(crops)["ndvi"].iloc[0] == pytest.approx(0.25)   # mean of 0.5 and 0


def test_rain_windows_sum_the_latest_months():
    visits = pd.DataFrame({f"rain_m{m:02d}": [float(m)] for m in range(1, 13)})
    table = weather_features(visits)
    assert list(table.columns) == WEATHER
    assert table.iloc[0].tolist() == [6.0, 21.0, 78.0]    # 1..3, 1..6, 1..12


def test_fixed_features_keep_the_row_order():
    visits = pd.DataFrame({f"rain_m{m:02d}": [1.0, 2.0] for m in range(1, 13)})
    crops = _crops({"B2": 0.05, "B3": 0.08, "B4": 0.1, "B8": 0.3, "B11": 0.3, "B12": 0.2})
    table = fixed_features(visits, crops)
    assert list(table.columns) == SATELLITE + WEATHER
    assert table["rain_12m"].tolist() == [12.0, 24.0]


def test_pca_is_fit_on_training_visits_only():
    """Changing the test visits must not change the training columns.

    If the PCA were fit on all visits, new test values would move its
    directions, and with them every training row.
    """
    rng = np.random.default_rng(0)
    photos = rng.normal(size=(100, 768))
    run = _run()
    train_a, test_a, _ = photo_features(photos, run)
    changed = photos.copy()
    changed[run.test] = rng.normal(10, 5, size=(len(run.test), 768))
    train_b, test_b, _ = photo_features(changed, run)
    pd.testing.assert_frame_equal(train_a, train_b)
    assert not np.allclose(test_a, test_b)
    assert list(train_a.columns) == PHOTO and list(train_a.index) == list(run.train)

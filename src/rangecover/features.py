"""Step 3: the feature tables for each test run.

Three groups of input columns, one row per visit, in the row order of
dataset.csv (sorted by site_unique):

- Satellite (8 columns): the mean of each of the 6 bands over the 10 x 10 crop,
  plus the crop means of NDVI (green plants) and NDTI (dry plant matter).
- Weather (3 columns): total rain over the last 3, 6 and 12 months before the
  visit.
- Photos (20 columns): the 768 DINOv2 numbers of each visit, reduced to 20 with
  PCA.

The satellite and weather columns use one visit's own data only. They learn
nothing from other visits, so they are made once for all visits. The PCA does
learn from the data (the directions of largest spread), so it is fit again in
each test run on the training visits only. The test visits are then projected
with that fitted PCA. If the PCA saw the test visits, the test error would be
too good (leakage).

Run (prints the feature sizes and the PCA spread kept in each run; writes
nothing):  uv run python -m rangecover.features
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from rangecover.splits import TestRun

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]        # order of the crop axis 1
RAIN_WINDOWS = (3, 6, 12)                              # months before the visit
N_PCA = 20                                             # photo columns after PCA

SATELLITE = [f"{b}_mean" for b in BANDS] + ["ndvi", "ndti"]
WEATHER = [f"rain_{k}m" for k in RAIN_WINDOWS]
PHOTO = [f"photo_pc{k:02d}" for k in range(1, N_PCA + 1)]


def normalised_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return (a - b) / (a + b) per pixel.

    The frozen crops are surface reflectance with no masked pixels, and the
    smallest band sums are well above 0 (B4 + B8 >= 0.06, B11 + B12 >= 0.08),
    so the division is safe. A zero sum would still give NaN, not a silent 0,
    and `satellite_features` would then stop.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def satellite_features(crops: np.ndarray) -> pd.DataFrame:
    """Make the 8 satellite columns from the crops.

    NDVI = (B8 - B4) / (B8 + B4). Green leaves absorb red (B4) and reflect
    near-infrared (B8), so NDVI rises with green cover.
    NDTI = (B11 - B12) / (B11 + B12). Dry plant matter (cellulose, lignin)
    reflects more at B11 than at B12, while bare soil reflects about the same,
    so NDTI helps separate dry cover from bare ground.

    Each index is calculated per pixel and then averaged over the crop, so it
    describes the plot and not one mixed pixel.

    Args:
        crops: Shape (n, 6, 10, 10), bands in the order of `BANDS`, reflectance.

    Returns:
        A table of shape (n, 8) with the columns in `SATELLITE`.

    Raises:
        ValueError: If the crop shape is wrong or a value is not finite.
    """
    if crops.ndim != 4 or crops.shape[1] != len(BANDS):
        raise ValueError(f"crops must be (n, {len(BANDS)}, h, w), got {crops.shape}")
    band = {name: crops[:, i].astype(float) for i, name in enumerate(BANDS)}
    table = pd.DataFrame({f"{b}_mean": band[b].mean(axis=(1, 2)) for b in BANDS})
    table["ndvi"] = normalised_difference(band["B8"], band["B4"]).mean(axis=(1, 2))
    table["ndti"] = normalised_difference(band["B11"], band["B12"]).mean(axis=(1, 2))
    if not np.isfinite(table.to_numpy()).all():
        raise ValueError("satellite features have NaN or infinite values")
    return table[SATELLITE]


def weather_features(visits: pd.DataFrame) -> pd.DataFrame:
    """Make the rain totals for the last 3, 6 and 12 months.

    `rain_m01` is the month that ends the day before the visit, `rain_m12` the
    month 12 months back (docs/decisions.md "Weather months and grid cell"), so
    the last k months are rain_m01 ... rain_m{k}.

    Args:
        visits: The dataset table with columns rain_m01 ... rain_m12.

    Returns:
        A table of shape (n, 3) with the columns in `WEATHER`, in mm.
    """
    return pd.DataFrame({
        f"rain_{k}m": visits[[f"rain_m{m:02d}" for m in range(1, k + 1)]].sum(axis=1)
        for k in RAIN_WINDOWS
    }, index=visits.index)[WEATHER]


def fixed_features(visits: pd.DataFrame, crops: np.ndarray) -> pd.DataFrame:
    """The satellite and weather columns for all visits (no learning, no leakage)."""
    if len(visits) != len(crops):
        raise ValueError("visits and crops have different row counts")
    sat = satellite_features(crops).set_axis(visits.index)
    return pd.concat([sat, weather_features(visits)], axis=1)


def photo_features(photo_means: np.ndarray, run: TestRun,
                   n_components: int = N_PCA) -> tuple[pd.DataFrame, pd.DataFrame, PCA]:
    """Reduce the 768 DINOv2 numbers to `n_components` for one test run.

    The PCA is fit on the training rows only. The test rows are projected with
    the fitted PCA, so they have no effect on the directions it keeps.

    `svd_solver="full"` gives the exact answer, the same on every machine. The
    default ("auto") would pick a randomised solver for this shape.

    Args:
        photo_means: Shape (n, 768), one row per visit (dinov2_visit_mean.npz).
        run: The test run; `train` and `test` are row positions.
        n_components: How many photo columns to keep.

    Returns:
        The train table, the test table (columns in `PHOTO`, indexed by row
        position) and the fitted PCA (for its explained variance).
    """
    pca = PCA(n_components=n_components, svd_solver="full").fit(photo_means[run.train])
    columns = PHOTO[:n_components]
    train = pd.DataFrame(pca.transform(photo_means[run.train]), index=run.train, columns=columns)
    test = pd.DataFrame(pca.transform(photo_means[run.test]), index=run.test, columns=columns)
    return train, test, pca


def run_tables(fixed: pd.DataFrame, photo_means: np.ndarray,
               run: TestRun) -> tuple[pd.DataFrame, pd.DataFrame, PCA]:
    """Make the training and the test feature table of one test run.

    Args:
        fixed: The satellite and weather columns from `fixed_features`, with a
            0 ... n-1 index (row positions).
        photo_means: Shape (n, 768), same row order as `fixed`.
        run: The test run.

    Returns:
        The train table and the test table, each with the columns
        SATELLITE + WEATHER + PHOTO, indexed by row position, and the fitted PCA.
    """
    photo_train, photo_test, pca = photo_features(photo_means, run)
    train = pd.concat([fixed.iloc[run.train].set_axis(run.train), photo_train], axis=1)
    test = pd.concat([fixed.iloc[run.test].set_axis(run.test), photo_test], axis=1)
    return train, test, pca


def load_inputs() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Read the frozen dataset, its crops and the DINOv2 visit means.

    Returns:
        The visit table (index 0 ... n-1), the crops and the photo means, all in
        the same row order.

    Raises:
        ValueError: If the three files do not list the same visits in the same
            order, or the visit list differs from final_visits.csv.
    """
    visits = pd.read_csv(DATA_DIR / "dataset.csv")
    frozen = pd.read_csv(DATA_DIR / "final_visits.csv")
    crops = np.load(DATA_DIR / "dataset_crops.npz")
    photos = np.load(DATA_DIR / "dinov2_visit_mean.npz")
    order = visits["site_unique"].to_numpy(str)
    for name, ids in [("final_visits.csv", frozen["site_unique"].to_numpy(str)),
                      ("dataset_crops.npz", crops["site_unique"]),
                      ("dinov2_visit_mean.npz", photos["site_unique"])]:
        if not np.array_equal(order, ids):
            raise ValueError(f"{name} does not list the visits of dataset.csv in the same order")
    if list(crops["bands"]) != BANDS:
        raise ValueError(f"dataset_crops.npz bands are {list(crops['bands'])}, expected {BANDS}")
    return visits, crops["crops"], photos["features"].astype(float)


def main() -> None:
    """Build the tables of all 15 runs and print their sizes. Writes nothing."""
    from rangecover.splits import make_test_runs

    visits, crops, photo_means = load_inputs()
    fixed = fixed_features(visits, crops)
    print(f"{len(visits)} visits; {len(SATELLITE)} satellite + {len(WEATHER)} weather "
          f"+ {N_PCA} photo columns")
    for run in make_test_runs(visits):
        train, test, pca = run_tables(fixed, photo_means, run)
        print(f"run {run.run:2d}  train {train.shape}  test {test.shape}  "
              f"PCA keeps {pca.explained_variance_ratio_.sum():.1%} of the photo spread")


if __name__ == "__main__":
    main()

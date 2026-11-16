"""Step 4: train and score the four methods on the 15 test runs.

The methods are fixed in docs/decisions.md ("Pass mark and methods", 2026-11-15):

    #1  random forest   satellite
    #2  random forest   satellite + weather
    #3  random forest   satellite + weather + photos   (compared with #2 for the verdict)
    #4  linear model    satellite + weather + photos

One loop runs every method. Methods differ only in their model kind and input
columns, so the comparison of #2 and #3 changes one thing: the photo columns.
In each test run, every method sees the same training visits, the same test
visits and the same feature table (Step 3, with the PCA fit on training visits
only).

Each model predicts green, dry and bare together (one model with 3 outputs).
Every prediction row is then clipped at 0 and scaled to add to 100.

Outputs:
    DATA_DIR/predictions.csv   one row per (run, method, test visit). Not
                               committed: it holds visit IDs, like data/.
    results/run_errors.csv     MAE and RMSE per (run, method). Committed.

The script always trains again; it does not skip finished runs. The whole loop
takes minutes on a CPU (no GPU needed), and a fresh run is how Tue Step 2
checks that the committed numbers can be made again.

Run (Colab):  uv run python -m rangecover.models
Run (Mac):    uv run python -m rangecover.models --smoke   (2 runs, 50 trees, temp folder)
"""
import argparse
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from rangecover.evaluate import LABELS, errors, scale_to_100
from rangecover.features import PHOTO, SATELLITE, WEATHER, fixed_features, load_inputs, run_tables
from rangecover.atomic import atomic_path
from rangecover.splits import TestRun, make_test_runs

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
SMOKE_DIR = Path(tempfile.gettempdir()) / "models_smoke"   # fixed, like the DINOv2 smoke folder

N_TREES = 500          # random forest size; more trees only lower the run-to-run noise
RF_SEED = 0            # the same forest seed in every run, so a rerun gives the same numbers
RIDGE_ALPHA = 1.0      # fixed, not tuned (docs/decisions.md "Linear model: ridge, fixed")
SMOKE_RUNS = 2
SMOKE_TREES = 50


@dataclass(frozen=True)
class Method:
    """One method: a model kind and its input columns."""
    name: str            # "m1" ... "m4"; the key used in every output
    label: str           # human-readable, for tables and charts
    kind: str            # "rf" or "linear"
    columns: tuple[str, ...]


METHODS = (
    Method("m1", "#1 RF: satellite", "rf", tuple(SATELLITE)),
    Method("m2", "#2 RF: satellite + weather", "rf", tuple(SATELLITE + WEATHER)),
    Method("m3", "#3 RF: satellite + weather + photos", "rf", tuple(SATELLITE + WEATHER + PHOTO)),
    Method("m4", "#4 Linear: all inputs", "linear", tuple(SATELLITE + WEATHER + PHOTO)),
)


def make_model(kind: str, n_trees: int = N_TREES):
    """Return a new, unfitted model of one kind.

    - "rf": a random forest with scikit-learn defaults apart from the tree
      count and the seed. With 3 outputs, each split lowers the summed squared
      error of green, dry and bare, and each leaf stores the mean label row of
      its training visits. Thus a forest prediction already adds to 100.
    - "linear": standardise each column (fit on the training rows), then ridge
      regression with a small fixed penalty. The penalty keeps the weights
      stable when columns move together (the 6 band means, and NDVI with B4
      and B8). A linear prediction also adds to 100 (the 3 labels add to 100
      in every training row), but a value can be below 0, so clipping matters.
    """
    if kind == "rf":
        return RandomForestRegressor(n_estimators=n_trees, random_state=RF_SEED, n_jobs=-1)
    if kind == "linear":
        return make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
    raise ValueError(f"unknown model kind: {kind}")


def predict(model, table: pd.DataFrame) -> np.ndarray:
    """Predict with a fitted model, with the same digits on every rerun.

    A forest trained with n_jobs=-1 also predicts on many threads, and the
    threads add their tree outputs in the order they finish. Floating-point
    addition depends on order, so two runs differed by about 1e-15 (measured).
    Predicting on one thread fixes the order. Training stays parallel: each
    tree's seed is drawn from `random_state` before the threads start.
    """
    if isinstance(model, RandomForestRegressor):
        model.set_params(n_jobs=1)
    return model.predict(table)


def run_all(visits: pd.DataFrame, fixed: pd.DataFrame, photo_means: np.ndarray,
            runs: list[TestRun], methods=METHODS,
            n_trees: int = N_TREES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train and score every method on every test run.

    Args:
        visits: The visit table (index 0 ... n-1) with site_unique and the labels.
        fixed: Satellite and weather columns (`features.fixed_features`).
        photo_means: Shape (n, 768), DINOv2 visit means in the same row order.
        runs: The test runs (`splits.make_test_runs`).
        methods: The methods to run.
        n_trees: Trees per random forest.

    Returns:
        predictions: One row per (run, method, test visit) with the true and
            the predicted green, dry and bare.
        run_errors: One row per (run, method) with MAE and RMSE per label.
    """
    y = visits[LABELS].to_numpy(float)
    predictions, run_errors = [], []
    start = time.perf_counter()
    for run in runs:
        train, test, pca = run_tables(fixed, photo_means, run)
        for method in methods:
            columns = list(method.columns)
            model = make_model(method.kind, n_trees).fit(train[columns], y[run.train])
            pred = scale_to_100(predict(model, test[columns]))
            run_errors.append({"run": run.run, "seed": run.seed, "group": run.group,
                               "method": method.name, "n_train": len(run.train),
                               "n_test": len(run.test), **errors(y[run.test], pred)})
            predictions.append(pd.DataFrame({
                "run": run.run, "method": method.name,
                "site_unique": visits["site_unique"].to_numpy()[run.test],
                **{f"true_{k}": y[run.test, i] for i, k in enumerate(LABELS)},
                **{f"pred_{k}": pred[:, i] for i, k in enumerate(LABELS)},
            }))
        done = run_errors[-len(methods):]
        print(f"run {run.run:2d} done ({time.perf_counter() - start:5.1f} s)  dry MAE  "
              + "  ".join(f"{e['method']} {e['mae_dry']:5.2f}" for e in done), flush=True)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(run_errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--smoke", action="store_true",
                        help=f"{SMOKE_RUNS} runs, {SMOKE_TREES} trees, output in {SMOKE_DIR}")
    args = parser.parse_args()

    visits, crops, photo_means = load_inputs()
    fixed = fixed_features(visits, crops)
    runs = make_test_runs(visits)
    if args.smoke:
        runs, n_trees, pred_dir, results_dir = runs[:SMOKE_RUNS], SMOKE_TREES, SMOKE_DIR, SMOKE_DIR
    else:
        n_trees, pred_dir, results_dir = N_TREES, DATA_DIR, RESULTS_DIR
    print(f"{len(visits)} visits, {len(runs)} test runs, {len(METHODS)} methods, "
          f"{n_trees} trees per forest", flush=True)

    predictions, run_errors = run_all(visits, fixed, photo_means, runs, n_trees=n_trees)
    with atomic_path(pred_dir / "predictions.csv") as tmp:
        predictions.to_csv(tmp, index=False)
    with atomic_path(results_dir / "run_errors.csv") as tmp:
        run_errors.to_csv(tmp, index=False)   # full precision: the pass mark reads this file
    print(f"Saved {len(predictions)} predictions to {pred_dir / 'predictions.csv'}")
    print(f"Saved {len(run_errors)} run errors to {results_dir / 'run_errors.csv'}")


if __name__ == "__main__":
    main()

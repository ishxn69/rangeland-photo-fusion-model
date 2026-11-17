"""Errors and the pass mark.

MAE is the primary measure: the pass mark uses it only. RMSE is reported next to
it for analysis. RMSE gives large misses more weight, so a gap between the two
shows that a few visits have large errors (docs/decisions.md "RMSE as a second
measure").

The pass mark (docs/decisions.md, fixed 2026-11-15) compares method #3 with
method #2. Each condition uses the per-run MAE; "decreases" and "increases" use
the mean over the 15 runs.

Run (dummy-model check):  uv run python -m rangecover.evaluate
"""
import numpy as np
import pandas as pd

LABELS = ["green", "dry", "bare"]
DRY_GAIN = 1.5        # condition 1: dry MAE must drop by at least this
MIN_WINS = 12         # condition 2: method #3 wins dry in at least this many runs
MAX_RISE = 0.5        # condition 3: green and bare MAE may rise by at most this


def scale_to_100(pred: np.ndarray) -> np.ndarray:
    """Make each row of green, dry, bare non-negative and add to 100.

    The models in models.py predict the three labels together, and their raw
    rows already add to 100 (up to rounding): a forest leaf holds mean label
    rows, and a linear fit of labels that add to 100 keeps that sum. But a
    linear model can predict a value below 0, so the clip matters, and this
    step guarantees invariant 2 for any model, not only for these.

    Args:
        pred: Array of shape (n, 3).

    Returns:
        A new array of shape (n, 3). A row that is all zero after clipping
        becomes 100/3 in each column.
    """
    clipped = np.clip(np.asarray(pred, dtype=float), 0, None)
    totals = clipped.sum(axis=1, keepdims=True)
    out = np.full_like(clipped, 100 / clipped.shape[1])
    np.divide(clipped * 100, totals, out=out, where=totals > 0)
    return out


def errors(true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    """MAE and RMSE for each label, in cover points.

    Args:
        true: Shape (n, 3), columns green, dry, bare.
        pred: Same shape.

    Returns:
        {"mae_green": ..., "mae_dry": ..., "mae_bare": ...,
         "rmse_green": ..., "rmse_dry": ..., "rmse_bare": ...}
    """
    diff = np.asarray(pred, dtype=float) - np.asarray(true, dtype=float)
    out = {f"mae_{k}": float(v) for k, v in zip(LABELS, np.abs(diff).mean(axis=0))}
    out |= {f"rmse_{k}": float(v) for k, v in zip(LABELS, np.sqrt((diff ** 2).mean(axis=0)))}
    return out


def pass_mark(m2: pd.DataFrame, m3: pd.DataFrame) -> dict:
    """Check the three pass-mark conditions for method #3 against method #2.

    Args:
        m2, m3: One row per test run, indexed by run number, with columns
            mae_green, mae_dry and mae_bare. Both must have the same runs.

    Returns:
        The numbers behind each condition, each condition (True/False) and
        "verdict" ("pass" only if all three hold).

    Raises:
        ValueError: If the two tables do not have the same runs.
    """
    if not m2.index.sort_values().equals(m3.index.sort_values()):
        raise ValueError("methods #2 and #3 must have the same test runs")
    m3 = m3.loc[m2.index]
    gain = {k: float((m2[f"mae_{k}"] - m3[f"mae_{k}"]).mean()) for k in LABELS}
    wins = int((m3["mae_dry"] < m2["mae_dry"]).sum())
    result = {
        "dry_gain": gain["dry"], "dry_wins": wins, "n_runs": len(m2),
        "green_rise": -gain["green"], "bare_rise": -gain["bare"],
        "1_dry_gain_ok": gain["dry"] >= DRY_GAIN,
        "2_dry_wins_ok": wins >= MIN_WINS,
        "3_green_bare_ok": -gain["green"] <= MAX_RISE and -gain["bare"] <= MAX_RISE,
    }
    passed = result["1_dry_gain_ok"] and result["2_dry_wins_ok"] and result["3_green_bare_ok"]
    result["verdict"] = "pass" if passed else "fail"
    return result


def dry_gain_range(predictions: pd.DataFrame, n_boot: int = 5000, seed: int = 0) -> dict:
    """95% range of the dry gain of method #3 over #2, by a site bootstrap.

    Context only: the pass mark never reads it. The 15 runs share visits (each
    visit is a test visit once per grouping), so a count of wins is not 15
    separate results. Resampling sites gives a range that respects that.

    Each test visit's gain is |error #2| - |error #3| for dry. The gains are
    averaged per site (all runs and visits of the site), and the sites are
    resampled with replacement `n_boot` times.

    Args:
        predictions: One row per (run, method, test visit), from models.py,
            with site_unique ("<site>-<visit>"), true_dry and pred_dry.

    Returns:
        {"dry_gain_low", "dry_gain_high", "share_at_pass_mark", "n_sites"};
        the last share is the part of the resamples with a gain >= DRY_GAIN.
    """
    err = predictions.assign(e=(predictions["pred_dry"] - predictions["true_dry"]).abs())
    wide = err.pivot_table(index=["run", "site_unique"], columns="method", values="e").reset_index()
    site = wide["site_unique"].str.rsplit("-", n=1).str[0]
    per_site = (wide["m2"] - wide["m3"]).groupby(site).mean().to_numpy()
    rng = np.random.default_rng(seed)
    boot = rng.choice(per_site, size=(n_boot, len(per_site))).mean(axis=1)
    low, high = np.percentile(boot, [2.5, 97.5])
    return {"dry_gain_low": float(low), "dry_gain_high": float(high),
            "share_at_pass_mark": float((boot >= DRY_GAIN).mean()), "n_sites": len(per_site)}


def dummy_check() -> pd.DataFrame:
    """Score a model that always predicts the training-label mean.

    Every real method must beat this. If one does not, it learned nothing.

    Returns:
        One row of errors per test run.
    """
    from rangecover.splits import load_visits, make_test_runs

    table = load_visits()
    y = table[LABELS].to_numpy(float)
    rows = []
    for run in make_test_runs(table):
        pred = np.tile(y[run.train].mean(axis=0), (len(run.test), 1))
        rows.append({"run": run.run, **errors(y[run.test], scale_to_100(pred))})
    return pd.DataFrame(rows).set_index("run")


if __name__ == "__main__":
    scores = dummy_check()
    print(scores.round(2).to_string())
    print("\nmean over runs:")
    print(scores.mean().round(2).to_string())

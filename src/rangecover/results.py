"""Step 5: the results table, the dry-cover chart and the verdict.

Reads results/run_errors.csv (from Step 4) and writes, all in results/:

    results_table.csv    mean MAE and RMSE over the test runs, per method, plus
                         the mean-only floor from Step 2.
    verdict.json         the pass-mark numbers, each condition and the verdict.
    dry_mae_by_run.png   dry MAE in each test run, method #2 against method #3
                         (drawn by chart.py).
    results.md           the table, the verdict and the notes beside it, in one
                         page, for the README and the report.

The verdict uses methods #2 and #3 only (docs/decisions.md, "Pass mark and
methods" and "How the pass mark is measured"). Methods #1 and #4 and the floor
are context; they never change it. RMSE never changes it either. The notes
beside the verdict (`notes`) are context too: each label's change with photos,
the site-bootstrap range of the dry gain (from DATA_DIR/predictions.csv) and
the best method. They say what a FAIL does not show; they never change it.

Run (Colab):  uv run python -m rangecover.results
Run (Mac):    uv run python -m rangecover.results --smoke   (reads and writes the smoke folder)
"""
import argparse
import json

import pandas as pd

from rangecover.atomic import atomic_path
from rangecover.chart import dry_chart
from rangecover.evaluate import (DRY_GAIN, LABELS, MAX_RISE, MIN_WINS,
                                 dry_gain_range, dummy_check, pass_mark)
from rangecover.features import PHOTO
from rangecover.models import DATA_DIR, METHODS, RESULTS_DIR, SMOKE_DIR

MEASURES = [f"{m}_{k}" for m in ("mae", "rmse") for k in LABELS]
FLOOR = "floor"                          # the mean-only model, as a reference row


def summary_table(run_errors: pd.DataFrame, floor: pd.DataFrame) -> pd.DataFrame:
    """Mean MAE and RMSE over the test runs, one row per method, floor last.

    Args:
        run_errors: One row per (run, method), from models.py.
        floor: One row per run for the mean-only model (`evaluate.dummy_check`),
            indexed by run; only the runs in `run_errors` are used.

    Returns:
        A table indexed by method key with a `label` column, the 6 measures
        and `n_runs`.
    """
    runs = sorted(run_errors["run"].unique())
    rows = run_errors.groupby("method")[MEASURES].mean()
    rows.loc[FLOOR] = floor.loc[runs, MEASURES].mean()
    order = [m.name for m in METHODS if m.name in rows.index] + [FLOOR]
    labels = {m.name: m.label for m in METHODS} | {FLOOR: "Floor: training mean, no inputs"}
    table = rows.loc[order]
    table.insert(0, "label", [labels[k] for k in order])
    table["n_runs"] = len(runs)
    return table


def verdict(run_errors: pd.DataFrame) -> dict:
    """Apply the frozen pass mark to method #3 against method #2.

    Returns:
        `evaluate.pass_mark` output plus the mean dry MAE of each method.
    """
    by_method = {k: g.set_index("run").sort_index() for k, g in run_errors.groupby("method")}
    result = pass_mark(by_method["m2"], by_method["m3"])
    result["m2_mae_dry"] = float(by_method["m2"]["mae_dry"].mean())
    result["m3_mae_dry"] = float(by_method["m3"]["mae_dry"].mean())
    return result


def change(diff: float) -> str:
    """A signed change in words ("falls 1.64", "rises 0.20"); easier to read than "-1.64"."""
    return "does not change" if round(abs(diff), 2) == 0 else \
        f"{'falls' if diff < 0 else 'rises'} {abs(diff):.2f}"


def notes(table: pd.DataFrame, result: dict) -> list[str]:
    """Context beside the verdict: each error's change with photos, the dry-gain
    range and the best method, so a FAIL is not read as "no gain"."""
    diff = {k: table.loc["m3", f"mae_{k}"] - table.loc["m2", f"mae_{k}"] for k in LABELS}
    words = [f"{k} {change(d)}" for k, d in diff.items()]
    lines = [f"- **Photos and each error.** With photos (#3 against #2), the MAE for "
             f"{', '.join(words[:2])} and {words[2]} cover points."]
    if "dry_gain_low" in result:
        lines.append(
            f"- **Range of the dry gain.** The {result['n_runs']} runs share visits, so {result['dry_wins']} of "
            f"{result['n_runs']} is not {result['n_runs']} separate results. A bootstrap over the "
            f"{result['n_sites']} sites gives a 95% range of {result['dry_gain_low']:+.2f} to "
            f"{result['dry_gain_high']:+.2f} for the dry gain. "
            f"{result['share_at_pass_mark']:.0%} of the resamples reach the {DRY_GAIN} pass mark.")
    methods = {m.name: m for m in METHODS}
    best = table.drop(index=FLOOR)["mae_dry"].idxmin()
    text = (f"- **Best method.** {methods[best].label} has the lowest dry MAE "
            f"({table.loc[best, 'mae_dry']:.2f}).")
    if best not in ("m2", "m3") and set(PHOTO) <= set(methods[best].columns):
        text += (" It uses the photos. No method of the same kind without photos was run "
                 "(the method list is fixed), so the photo gain inside it is not measured.")
    return lines + [text]


def markdown(table: pd.DataFrame, result: dict) -> str:
    """The results page: the table, the three conditions, the verdict and the notes."""
    head = ["Method"] + [f"{m.upper()} {k}" for m, k in (c.split("_") for c in MEASURES)]
    lines = ["# Results", "", f"Mean over {int(table['n_runs'].iloc[0])} site-grouped test runs, "
             "in cover points (lower is better). The pass mark uses MAE only.", "",
             "| " + " | ".join(head) + " |", "|" + "---|" + "---:|" * len(MEASURES)]
    for _, row in table.iterrows():
        lines.append(f"| {row['label']} | " + " | ".join(f"{row[c]:.2f}" for c in MEASURES) + " |")
    ok = {True: "yes", False: "no"}
    lines += ["", "## Verdict: method #3 against method #2", "",
              "| Condition | Needed | Result | Met |", "|---|---|---|---|",
              f"| 1. Dry MAE drops | ≥ {DRY_GAIN} | {result['dry_gain']:+.2f} | {ok[result['1_dry_gain_ok']]} |",
              f"| 2. Runs where #3 has the lower dry MAE | ≥ {MIN_WINS} of 15 | "
              f"{result['dry_wins']} of {result['n_runs']} | {ok[result['2_dry_wins_ok']]} |",
              f"| 3. Green and bare MAE rise | ≤ {MAX_RISE} each | green {change(result['green_rise'])}, "
              f"bare {change(result['bare_rise'])} | {ok[result['3_green_bare_ok']]} |",
              "", f"**Verdict: {result['verdict'].upper()}**", "",
              "## What the verdict does not show", "",
              "The verdict asks if the photo gain reaches the pass mark. These notes "
              "are context and do not change it.", "", *notes(table, result), "",
              "![Dry MAE per test run](dry_mae_by_run.png)", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--smoke", action="store_true", help=f"read and write {SMOKE_DIR}")
    args = parser.parse_args()
    out = SMOKE_DIR if args.smoke else RESULTS_DIR

    run_errors = pd.read_csv(out / "run_errors.csv")
    table = summary_table(run_errors, dummy_check())
    result = verdict(run_errors)
    predictions = (SMOKE_DIR if args.smoke else DATA_DIR) / "predictions.csv"
    if predictions.exists():
        result |= dry_gain_range(pd.read_csv(predictions))
    else:
        print(f"No {predictions}: the results page has no range for the dry gain")

    with atomic_path(out / "results_table.csv") as tmp:
        table.to_csv(tmp)
    with atomic_path(out / "verdict.json") as tmp:
        tmp.write_text(json.dumps(result, indent=2) + "\n")
    dry_chart(run_errors, result, out / "dry_mae_by_run.png")
    with atomic_path(out / "results.md") as tmp:
        tmp.write_text(markdown(table, result))

    print(table.drop(columns="n_runs").round(2).to_string())
    print(f"\n{json.dumps(result, indent=2)}\n\nSaved the table, verdict, chart and page to {out}")


if __name__ == "__main__":
    main()

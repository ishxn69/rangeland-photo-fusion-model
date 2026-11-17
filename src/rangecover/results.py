"""Step 5: the results table, the dry-cover chart and the verdict.

Reads results/run_errors.csv (from Step 4) and writes, all in results/:

    results_table.csv    mean MAE and RMSE over the test runs, per method, plus
                         the mean-only floor from Step 2.
    verdict.json         the pass-mark numbers, each condition and the verdict.
    dry_mae_by_run.png   dry MAE in each test run, method #2 against method #3.
    results.md           the table and the verdict in one page, for the README
                         and the report.

The verdict uses methods #2 and #3 only (docs/decisions.md, "Pass mark and
methods" and "How the pass mark is measured"). Methods #1 and #4 and the floor
are context; they never change it. RMSE never changes it either.

Run (Colab):  uv run python -m rangecover.results
Run (Mac):    uv run python -m rangecover.results --smoke   (reads and writes the smoke folder)
"""
import argparse
import json
import os
from pathlib import Path

# Draw to files only (no screen in Colab or in a terminal). Set through the
# environment, before matplotlib is imported: a Colab notebook sets
# MPLBACKEND=module://matplotlib_inline.backend_inline, `!uv run` passes it on,
# and the project venv has no matplotlib_inline, so `import matplotlib` itself
# fails on that value. matplotlib.use() after the import comes too late.
os.environ["MPLBACKEND"] = "Agg"
import matplotlib.pyplot as plt          # noqa: E402 - must come after the backend is set
import pandas as pd                      # noqa: E402

from rangecover.evaluate import (DRY_GAIN, LABELS, MAX_RISE, MIN_WINS,  # noqa: E402
                                 dummy_check, pass_mark)
from rangecover.atomic import atomic_path  # noqa: E402
from rangecover.models import METHODS, RESULTS_DIR, SMOKE_DIR  # noqa: E402

MEASURES = [f"{m}_{k}" for m in ("mae", "rmse") for k in LABELS]
FLOOR = "floor"                          # the mean-only model, as a reference row
COLOURS = {"m2": "#2a78d6", "m3": "#eb6834"}   # validated pair (dataviz palette slots 1-2)
INK, INK_2, RULE, SURFACE = "#0b0b0b", "#52514e", "#dddcd6", "#fcfcfb"


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


def dry_chart(run_errors: pd.DataFrame, result: dict, path: Path) -> None:
    """Draw the dry MAE of #2 and #3 in each test run as a paired dot plot.

    One column per run. A grey line joins the two dots of a run, so the eye
    reads each run's gain or loss. The two methods differ in colour and in
    marker shape, so the chart also works without colour. Thin vertical rules
    split the runs into their 3 random groupings.
    """
    wide = run_errors.pivot(index="run", columns="method", values="mae_dry").sort_index()
    seeds = run_errors.drop_duplicates("run").set_index("run")["seed"].loc[wide.index]
    x = range(len(wide))

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.vlines(x, wide[["m2", "m3"]].min(axis=1), wide[["m2", "m3"]].max(axis=1),
              color="#a3a29c", linewidth=2, zorder=1)
    for key, marker in (("m2", "o"), ("m3", "D")):
        label = next(m.label for m in METHODS if m.name == key)
        ax.scatter(x, wide[key], s=56 if marker == "o" else 44, marker=marker,
                   color=COLOURS[key], edgecolor=SURFACE, linewidth=1.5, zorder=2, label=label)

    # Split and name the groupings (one per seed).
    for i, (seed, idx) in enumerate(pd.Series(range(len(wide)), index=seeds).groupby(level=0)):
        if i:
            ax.axvline(idx.min() - 0.5, color=RULE, linewidth=1, zorder=0)
        ax.text(idx.mean(), 1.0, f"grouping {i + 1} (seed {seed})", transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=8, color=INK_2)

    ax.set_xticks(list(x), [str(r) for r in wide.index])
    ax.set_xlim(-0.6, len(wide) - 0.4)
    ax.set_xlabel("Test run", color=INK_2)
    ax.set_ylabel("Dry-cover MAE (cover points)", color=INK_2)
    ax.grid(axis="y", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False,
              fontsize=9, labelcolor=INK)

    fig.suptitle(f"Method #3 (with photos) had a lower dry-cover error than #2 in "
                 f"{result['dry_wins']} of {result['n_runs']} test runs",
                 x=0.06, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.06, 0.895,f"Mean dry MAE {result['m2_mae_dry']:.2f} → {result['m3_mae_dry']:.2f} "
             f"(gain {result['dry_gain']:+.2f}). Pass mark: gain ≥ {DRY_GAIN}, ≥ {MIN_WINS} of 15 "
             f"wins, green and bare rise ≤ {MAX_RISE}. Verdict: {result['verdict'].upper()}.",
             fontsize=9, color=INK_2)
    fig.tight_layout(rect=(0.03, 0, 1, 0.89))
    with atomic_path(path) as tmp:
        fig.savefig(tmp, facecolor=SURFACE)
    plt.close(fig)


def markdown(table: pd.DataFrame, result: dict) -> str:
    """The results page: the table, the three conditions and the verdict."""
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
              f"| 3. Green and bare MAE rise | ≤ {MAX_RISE} each | green {result['green_rise']:+.2f}, "
              f"bare {result['bare_rise']:+.2f} | {ok[result['3_green_bare_ok']]} |",
              "", f"**Verdict: {result['verdict'].upper()}**", "",
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

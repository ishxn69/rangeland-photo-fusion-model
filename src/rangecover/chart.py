"""The dry-cover chart for Step 5: method #2 against method #3 in each test run.

Called by results.py. Kept apart so each file stays under ~200 lines.
"""
import os
from pathlib import Path

import pandas as pd

# Draw to files only. Set before the import: Colab passes MPLBACKEND=module://
# matplotlib_inline... to `!uv run`, the venv lacks it, and the import fails.
os.environ["MPLBACKEND"] = "Agg"
import matplotlib.pyplot as plt          # noqa: E402 - must come after the backend is set

from rangecover.atomic import atomic_path  # noqa: E402
from rangecover.evaluate import DRY_GAIN, MAX_RISE, MIN_WINS  # noqa: E402
from rangecover.models import METHODS     # noqa: E402

COLOURS = {"m2": "#2a78d6", "m3": "#eb6834"}   # validated pair (dataviz palette slots 1-2)
INK, INK_2, RULE, SURFACE = "#0b0b0b", "#52514e", "#dddcd6", "#fcfcfb"


def dry_chart(run_errors: pd.DataFrame, result: dict, path: Path) -> None:
    """Draw the dry MAE of #2 and #3 in each test run as a paired dot plot.

    One column per run. A grey line joins the two dots of a run, so the eye
    reads each run's gain or loss. The two methods differ in colour and in
    marker shape, so the chart also works without colour. #2 is a hollow ring
    on top, so it never hides #3 when the two are close. Thin vertical rules
    split the runs into their 3 random groupings.
    """
    wide = run_errors.pivot(index="run", columns="method", values="mae_dry").sort_index()
    seeds = run_errors.drop_duplicates("run").set_index("run")["seed"].loc[wide.index]
    x = range(len(wide))

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.vlines(x, wide[["m2", "m3"]].min(axis=1), wide[["m2", "m3"]].max(axis=1),
              color="#a3a29c", linewidth=2, zorder=1)
    # #2: a hollow ring above #3, so a near-tie (run 1, 17 Nov: 0.03) shows both.
    for key in ("m2", "m3"):
        label = next(m.label for m in METHODS if m.name == key)
        style = (dict(marker="o", s=64, facecolor="none", edgecolor=COLOURS[key], linewidth=2, zorder=3)
                 if key == "m2" else
                 dict(marker="D", s=44, color=COLOURS[key], edgecolor=SURFACE, linewidth=1.5, zorder=2))
        ax.scatter(x, wide[key], label=label, **style)

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

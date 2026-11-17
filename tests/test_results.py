"""Step 5 results: the verdict reads methods #2 and #3 only; the table and page are complete."""
import os
import subprocess
import sys

import pandas as pd

from rangecover.results import FLOOR, MEASURES, change, markdown, summary_table, verdict


def _run_errors(dry: dict[str, float], n_runs: int = 15) -> pd.DataFrame:
    rows = [{"run": r, "seed": r // 5, "group": r % 5, "method": m,
             "mae_green": 10.0, "mae_dry": d, "mae_bare": 10.0,
             "rmse_green": 12.0, "rmse_dry": d + 2, "rmse_bare": 12.0}
            for r in range(n_runs) for m, d in dry.items()]
    return pd.DataFrame(rows)


def test_verdict_ignores_methods_1_and_4():
    """#1 and #4 are far better or worse, but only #2 against #3 decides."""
    errors = _run_errors({"m1": 30.0, "m2": 20.0, "m3": 18.0, "m4": 5.0})
    result = verdict(errors)
    assert result["verdict"] == "pass" and result["dry_wins"] == 15
    assert result["m2_mae_dry"] == 20.0 and result["m3_mae_dry"] == 18.0


def test_table_has_every_method_and_the_floor_last():
    errors = _run_errors({"m1": 22.0, "m2": 20.0, "m3": 18.0, "m4": 19.0})
    floor = pd.DataFrame({c: 25.0 for c in MEASURES}, index=range(15))
    table = summary_table(errors, floor)
    assert list(table.index) == ["m1", "m2", "m3", "m4", FLOOR]
    assert table.loc["m3", "mae_dry"] == 18.0 and table.loc[FLOOR, "mae_dry"] == 25.0
    page = markdown(table, verdict(errors))
    assert "**Verdict: PASS**" in page and page.count("\n| #") == 4


def test_imports_under_the_colab_notebook_backend():
    """A Colab notebook passes MPLBACKEND=module://matplotlib_inline... to `!uv run`.

    The project venv has no matplotlib_inline, so the module must set its own
    backend before matplotlib is imported (Colab run of 17 Nov failed here).
    """
    env = os.environ | {"MPLBACKEND": "module://matplotlib_inline.backend_inline"}
    done = subprocess.run([sys.executable, "-c", "import rangecover.results"],
                          env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_fail_page_shows_the_gain_and_the_best_method():
    """A FAIL with a real gain must not read as "no gain" (critique S1, S2)."""
    errors = _run_errors({"m1": 22.0, "m2": 20.0, "m3": 19.0, "m4": 17.0})
    floor = pd.DataFrame({c: 25.0 for c in MEASURES}, index=range(15))
    table = summary_table(errors, floor)
    result = verdict(errors) | {"dry_gain_low": 0.4, "dry_gain_high": 1.8,
                                "share_at_pass_mark": 0.13, "n_sites": 336}
    page = markdown(table, result)
    assert "**Verdict: FAIL**" in page
    assert "dry falls 1.00" in page and "+0.40 to +1.80" in page
    assert "| green does not change, bare does not change |" in page   # not "+0.00"
    assert "#4 Linear: all inputs has the lowest dry MAE" in page and "uses the photos" in page


def test_change_reads_as_words():
    assert change(-1.636) == "falls 1.64" and change(0.2) == "rises 0.20"
    assert change(-0.001) == "does not change"

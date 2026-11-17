# Results

Mean over 15 site-grouped test runs, in cover points (lower is better). The pass mark uses MAE only.

| Method | MAE green | MAE dry | MAE bare | RMSE green | RMSE dry | RMSE bare |
|---|---:|---:|---:|---:|---:|---:|
| #1 RF: satellite | 12.68 | 15.14 | 10.36 | 17.77 | 19.50 | 13.79 |
| #2 RF: satellite + weather | 12.78 | 14.57 | 10.61 | 17.67 | 18.45 | 14.06 |
| #3 RF: satellite + weather + photos | 11.15 | 13.65 | 10.28 | 14.76 | 16.91 | 13.30 |
| #4 Linear: all inputs | 8.68 | 12.37 | 10.54 | 11.23 | 16.01 | 13.69 |
| Floor: training mean, no inputs | 15.69 | 22.23 | 23.31 | 20.01 | 25.70 | 26.54 |

## Verdict: method #3 against method #2

| Condition | Needed | Result | Met |
|---|---|---|---|
| 1. Dry MAE drops | ≥ 1.5 | +0.92 | no |
| 2. Runs where #3 has the lower dry MAE | ≥ 12 of 15 | 11 of 15 | no |
| 3. Green and bare MAE rise | ≤ 0.5 each | green -1.64, bare -0.32 | yes |

**Verdict: FAIL**

## What the verdict does not show

The verdict asks if the photo gain reaches the pass mark. These notes are context and do not change it.

- **Photos and each error.** With photos (#3 against #2), the MAE for green falls 1.64, dry falls 0.92 and bare falls 0.32 cover points.
- **Range of the dry gain.** The 15 runs share visits, so 11 of 15 is not 15 separate results. A bootstrap over the 336 sites gives a 95% range of +0.37 to +1.82 for the dry gain. 13% of the resamples reach the 1.5 pass mark.
- **Best method.** #4 Linear: all inputs has the lowest dry MAE (12.37). It uses the photos. No method of the same kind without photos was run (the method list is fixed), so the photo gain inside it is not measured.

![Dry MAE per test run](dry_mae_by_run.png)

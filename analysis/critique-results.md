# Critique: results table and verdict (`results/results.md`)
_Reviewed: 2026-11-17 · Audience: Dr. Doe (invented persona) · Decision: use the ground photos in the cover maps, or not._
_Written in ASD-STE100. All numbers come from `results/run_errors.csv` and `data/predictions.csv` (Colab run, 17 Nov), calculated again on the Mac._

## Argument as reconstructed
- **Claim (inferred):** ground photos do not make the cover estimates better by the pass mark. The verdict is FAIL. The results file does not state a claim in words, so this critique uses the verdict as the claim.
- **Subclaim 1:** with photos (#3), the mean dry MAE drops by 0.92 points against #2. The pass mark needs 1.5.
- **Subclaim 2:** #3 has the lower dry MAE in 11 of 15 test runs. The pass mark needs 12.
- **Subclaim 3:** green MAE and bare MAE do not rise (green drops 1.64, bare drops 0.32).
- **Evidence:** 358 visits at 336 sites, 15 site-grouped test runs, MAE per run, mean over runs.
- **Justification:** the pass mark and the method list were fixed on 15 Nov, before any model ran.
- **Certainty:** the files give a pass or fail result only. They give no range for the gain.

## Stock issues
| Dispute | Type | Stock issue | Status | Note |
|---|---|---|---|---|
| #3 is better than #2 by the pass mark | Fact | Truth condition | Supported | Fixed on 15 Nov. The reading of "drops by" was recorded before the model runs. |
| | Fact | Satisfied | Supported | The table and verdict are correct. Calculated again: gain 0.915, 11 wins, green −1.64, bare −0.32. |
| Photos give "no gain" | Fact | Truth condition | Missing | The pass mark tests "enough gain", not "a gain". The files do not test for zero gain. See S1. |
| "Accurate" = low MAE on ground-layer labels | Definition | Useful | Supported | MAE is in cover points. The users read cover points. |
| | Definition | Consistent | Assumed | The label is the ground layer. The 1.5 threshold comes from an all-layer map. This is a recorded limitation (F9). |
| | Definition | Best | Supported | RMSE is reported next to MAE. The two agree. |
| 1.5 points and 12 of 15 are "good enough" | Value | Criteria from goals | Assumed | No user need sets 1.5 points. It is about 15% of a national-map error. |
| | Value | Properly applied | Supported | Applied as written, with no change after the results. |
| A random forest is a fair test of the photos | Value | Criteria from goals | Contradicted | The linear model (#4) is better than every forest. See S2. |
| Use the photos in the maps | Policy | Ill | Assumed | The work does not measure how much the present maps fail the users. |
| | Policy | Blame | Assumed | F9 says satellites cannot see the ground under trees. The work does not test this. See S5. |
| | Policy | Cure | Supported, small | The gain is real but below the pass mark. See S1. |
| | Policy | Cost | Missing | The cost to collect and process photos is not in the work. |
| 358 visits represent the rangelands | Specific → general | Representative | Assumed | 20 visits (18 in Cape York) have no satellite crop. Only visits from 2017-03-28 on. The 30-block design keeps sites apart, but not adjacent blocks. |

## Findings
_Update 2026-11-17: S1 and S2 are now stated in `results/results.md` (section "What the verdict does not show"), the README and `docs/decisions.md` ("Notes beside the verdict"). S3, S4 and S5 are Limitations in `docs/decisions.md` ("Limitations from the results critique"). The verdict does not change._


### Fatal
None. The verdict FAIL follows correctly from the fixed pass mark. The calculation is correct.

### Serious

**S1. FAIL does not mean "photos do not help". The files do not say this.**
- **Where:** `results/results.md`, verdict table. `dry_mae_by_run.png`, subtitle.
- **Stock issue:** Fact, truth condition for "no gain" (missing). Qualification (risk of underclaim).
- **What:** the photos make all three errors smaller. Dry MAE drops 0.92. Green MAE drops 1.64. Bare MAE drops 0.32. A site bootstrap (5,000 samples, seed 0, sites resampled) gives a 95% range of 0.37 to 1.82 for the dry gain. The range does not include zero. The range includes 1.5 (13% of samples are at 1.5 or more).
- **Why it matters:** a reader can see "FAIL" and decide that photos have no value. The data shows a small, real gain that is below the bar.
- **Cheapest fix:** add one sentence under the verdict: "Photos lower all three errors, but the dry gain is below the 1.5-point pass mark." Put the bootstrap range in the report. Do not change the verdict.

**S2. The best method uses photos, but no test shows how much the photos add to it.**
- **Where:** results table, row #4.
- **Stock issue:** Value, criteria from goals (contradicted). The verdict uses the forests only.
- **What:** #4 (linear, all inputs) has dry MAE 12.37 and green MAE 8.68. It is better than #3 on dry in 13 of 15 runs and on green in 15 of 15 runs. There is no linear model with satellite and weather only. Thus the photo gain inside the best model is not known.
- **Why it matters:** Dr. Doe will use the best model, not the forest. The photo gain in that model can be larger or smaller than 0.92. The forest can also be a weak user of the 31 columns at 358 visits.
- **Cheapest fix:** the method list is frozen. Write this as a Limitation in `docs/decisions.md`. Put "linear model, satellite + weather" under Future work. Optional method #5 (linear, photos only) does not answer this question.

**S3. The 15 test runs are not 15 independent results.**
- **Where:** verdict condition 2. Chart title "11 of 15".
- **Stock issue:** Fact, satisfied (execution is correct, but the count can mislead).
- **What:** the 3 groupings use the same 358 visits. Each visit is a test visit 3 times. One run decides the count: the bar is 12 and the result is 11. Run 1 counts as a win by 0.03 points. Only 9 runs have a win of more than 0.5 points.
- **Why it matters:** "11 of 15" looks like strong agreement. A reader can apply a sign test to it, but the test is not correct for runs that share visits.
- **Cheapest fix:** in the report, say that the runs share visits. Give the bootstrap range from S1 next to the count.

**S4. The gain is not the same in the three groupings, and one run supplies a large part of it.**
- **Where:** `run_errors.csv`, chart.
- **Stock issue:** Specific → general, representative (assumed).
- **What:** the mean dry gain is 1.41 (seed 0), 1.14 (seed 1) and 0.20 (seed 2). Run 0 gives a gain of 4.88. Without run 0, the mean gain is 0.63.
- **Why it matters:** the size of the gain depends on which sites are in the test group. The mean of 0.92 is less stable than one number shows.
- **Cheapest fix:** in the report, give the gain for each grouping and the gain without run 0.

**S5. The gain comes from the greener visits. The cause is not tested.**
- **Where:** `data/predictions.csv` (not committed, because it holds visit IDs).
- **Stock issue:** Policy, blame (assumed). Causal wording.
- **What:** split the test visits into three equal parts by true green cover. The dry gain is −0.30 in the least green third, +0.46 in the middle third and +2.70 in the most green third.
- **Why it matters:** F9 says that photos can see the ground under trees. Green cover is not the same as tree cover, so this split does not prove that cause. The report must not say "photos help because they see under trees" as a result.
- **Causal check:** "adding photos lowers the error" is a controlled change of model inputs. The evidence supports this wording. "Photos help *because* they see under trees" is a mechanism. No test in this work examines it.
- **Cheapest fix:** give the split as a description only. Keep the wooded-site split under Future work (F9 has it).

### Minor

**M1. The chart hides one point.** _(Fixed 17 Nov: #2 is now a hollow ring on top.)_ In run 1, the #2 dot is under the #3 diamond (10.79 against 10.76). The chart shows 14 blue dots, not 15. Fix: draw the #2 dots on top, or make them hollow.

**M2. A negative "rise" is hard to read.** _(Fixed 17 Nov: the page writes "falls" or "rises".)_ The verdict table says "green -1.64, bare -0.32" under "rise". Fix: write "green falls 1.64, bare falls 0.32".

**M3. The results are not committed.** `results/` is not in git, and `results.py`, `tests/test_results.py` and the notebook have changes. Tue Step 2 compares a new run with the committed results. Fix: commit before Step 2.

**M4. The pass-mark anchor is not like-for-like.** This is already a Limitation (F9). The report must say it next to the verdict, because the result is between 0.37 and 1.82 and the bar is 1.5.

## What's solid
- The pass mark and method list were fixed before any model ran. The reading of "drops by" was also recorded before the runs.
- The verdict calculation is correct. A mean weighted by test visits gives 0.95, so the mean over runs does not change the result.
- No site is in train and test. The photo PCA is fit on training visits only, in each run.
- Every method is much better than the floor (dry 22.2).
- RMSE agrees with MAE. With photos, green RMSE drops 2.91 and green MAE drops 1.64. Thus the photos remove some large errors.
- The weather adds 0.57 to dry (#1 to #2). This gives a scale for the photo gain of 0.92.

## Pressure point
"Your best model is the linear one, and it uses photos. If I use that model, how much do the photos give me?" The work cannot answer this yet (S2).

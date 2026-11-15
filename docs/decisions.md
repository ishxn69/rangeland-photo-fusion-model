# Decisions

One entry per choice: the options, what was picked, and why.

### 2026-10-28: Framing question for the project
- **Options:** a general model-building exercise on TERN data vs a question tied to one decision.
- **Picked:** a single decision question: do ground photos make cover estimates (green / dry / bare) more accurate than satellite and weather data alone, and if so, how should they be combined? See `analysis/scope.md`.
- **Why:** it answers an investment question someone actually faces (whether to use the photo archive and keep collecting photos), no published work answers it, and a "no" is still a clear, useful result.

### 2026-10-28: Stakeholder
- **Options:** find a real TERN or agency contact; write for no one in particular; invent a realistic persona.
- **Picked:** an invented persona, Dr. John Doe, a senior remote-sensing scientist at a state environment department who decides whether the team adopts ground photos. Renamed on 2026-10-30 because the first name belonged to a real person.
- **Why:** this is a self-directed portfolio project with no real client. A concrete persona keeps the work pointed at a decision and sets what the deliverable must look like (a one-page verdict a non-specialist can defend in one slide). It can be swapped for a real contact if one turns up.
- **End users (added 2026-11-13):** Dr. Doe decides whether to adopt photos. His team improves the cover maps that pastoral lease inspectors and grazing advisers use, and through them station managers, who judge grazing pressure and erosion risk (see `analysis/scope.md`). So what counts as a good estimate is set by what those users need to see on the ground. This is why the labels describe ground cover (see "Which cover labels to use (F9)" below).

### 2026-10-28: Constraints and maintenance
- **Options:** production-style deployment vs portfolio-style reproducibility.
- **Picked:** one semester, Google Colab Pro, and only TERN data already published under CC BY 4.0. Ishan maintains it as a portfolio project: a public repo that rebuilds the data, retrains every method and regenerates the results in one run, with pinned versions, fixed seeds, recorded data versions and saved DINOv2 features. Re-run when TERN releases new surveys or photos.
- **Why:** the persona doesn't need the network itself unless one model that works with or without photos wins clearly. What matters is that a stranger can trust and reproduce the result long after the capstone ends.

### 2026-10-31: Satellite data source and Earth Engine tier
- **Options:** Google Earth Engine vs Microsoft Planetary Computer; GEE Community tier (150 EECU-h, no billing) vs Contributor (1,000 EECU-h, billing account required).
- **Picked:** Google Earth Engine, academic non-commercial registration, Community tier. Planetary Computer is the backup.
- **Why:** GEE filters by date and cloud and crops on its servers, so each visit returns only a 10×10-pixel Sentinel-2 crop. The expected use is a few EECU-hours, well under 150, and Community needs no billing account. The project can upgrade to Contributor later if needed.

### 2026-11-01: Python environment and package manager
- **Options:** `venv` + `pip` with a `requirements.txt` vs `uv` with `pyproject.toml`.
- **Picked:** `uv`. `pyproject.toml` lists the packages the project needs, `uv sync` installs them into a `.venv` kept outside Google Drive (see "Where code, data and environments live" below), and `uv.lock` records the exact versions installed. Scripts run with `uv run`.
- **Why:** committing `uv.lock` makes the code run the same on the Mac and in Colab, which covers the "pinned versions" part of the reproducibility constraint. uv is also faster than pip, and `uv run` means there's no venv to activate.

### 2026-11-01: Choosing 6 frames per photo sequence
- **Options:** pick evenly spaced frames from the full sequence vs remove the label frame first; order frames by number vs by capture time.
- **Picked:** sort by `file_created`, drop the first frame, then pick 6 evenly spaced frames around the circle without using both ends. See `docs/data.md`.
- **Why:** the first frame was a site label or phone in 29 of 30 sampled sequences, frame numbers don't reliably follow capture order, and the two ends show nearly the same view.
- **Limitation:** this rests on 30 sequences checked as thumbnails, so a label frame could still get through. Sequences with no label lose one clean frame.
- **Capture times:** TERN flags every sampled time with `file_created_assumed`, and its API spec doesn't define that field. The rule uses only the order of times within a sequence, which looked right in the sample, so a wrong clock or time zone wouldn't affect it. Don't use these times for time of day. See `docs/data.md`.

### 2026-11-01: Finding the plot centre for satellite crops
- **The problem:** each AusPlots plot is usually a 100 m × 100 m square of land, and its ground measurements describe that whole square. The project cuts a 10×10-pixel Sentinel-2 crop for each visit. At 10 m per pixel, that crop covers 100 m × 100 m, about the same size as the plot. The crop only describes the same land as the labels if it's centred on the middle of the plot, but AusPlots gives just one latitude and longitude per site, so we had to find out which point on the plot that is.
- **Why it matters:** if those coordinates are a corner and we treat them as the centre, the crop lands about 71 m off diagonally. It then overlaps only a quarter of the plot (50 m × 50 m out of 100 m × 100 m), and the other three quarters of the crop show land the labels never measured. A model trained on that would be learning from mismatched inputs and labels, and nothing would crash or warn us.
- **Options:**
  - Coordinates mark the plot centre, so use them as they are.
  - Coordinates mark the south-west corner, so move 50 m east and 50 m north to reach the centre.
  - For plots that don't run north–south and east–west ("not aligned to the grid"): apply the same shift anyway, work out each plot's direction some other way, or leave them out.
- **Picked:** the coordinates mark the south-west corner. Keep only visits with `plot_is_aligned_to_grid` TRUE and shift those to the centre:
  1. Convert the latitude and longitude to the plot's Map Grid of Australia (MGA) zone. Work out the zone from longitude: `floor((longitude + 180) / 6) + 1`.
  2. Add 50 to the easting and 50 to the northing.
  3. Convert back to latitude and longitude if the next step needs them.
- **Why the shift happens in MGA:** latitude and longitude are angles, and a degree of longitude covers a different distance depending on how far north or south you are. MGA coordinates are in metres, so "add 50 m" is plain addition. The manual's own example does this: a south-west corner at easting 362038, northing 6196647 has its centre at 362088, 6196697. Aligned plots are laid out along this same map grid, so the shift follows the plot's sides.
- **Why the zone comes from longitude:** the table's `pit_marker_mga_zones` column is blank for 165 visits, while every visit has a longitude. A formula also gives every plot its zone the same way.
- **Why south-west corner, not centre:** three kinds of evidence agree.
  - **The AusPlots data:** every one of the 1,135 visits has `point = SW`.
  - **The AusPlots manual (v1.2.9, 2012):** it says `100SW` "represents the southwest corner of the plot and is the starting point for marking the plot" (p. 18) and lists "Plot location at SW corner" (p. 46). It also gets the centre by adding 50 m to both values (p. 21).
  - **An independent check against the data:** the manual is older than our visits, so we also compared the coordinates with the recorded soil pit positions on 2026-11-01. The manual says to dig the pit next to the south-west corner. Of 947 visits with usable pit positions, 565 had the pit within 40 m of the coordinates. Centred coordinates would put a south-west pit about 70 m away, but only 19 visits were 40–80 m away. Another 354 were 80–200 m away, and 350 of those lay north, east or north-east of the coordinates, at about 100 m or 141 m. Those are the distances and directions from the south-west corner to the other three corners.
- **Why EcoImages' label doesn't change this:** TERN EcoImages stores the same numbers under the name `centroid_point`, which suggests a centre. The evidence above points to the corner, so that name looks misleading. Neither the manual nor the data explains why it's used, and only 2 sites were compared.
- **Why leave out non-aligned plots:** the shift only works when the plot's sides run north–south and east–west. On a rotated plot, the centre is in some other direction from the corner, and the site table has no column for which way a plot is turned. Applying the shift anyway would put some crops in the wrong place with no warning. Leaving these visits out costs little: 65 of 1,135 visits overall (19 plots of 50 m × 200 m and 46 rotated squares), and 17 of the 406 candidate visits from 2017-03-28 on, leaving 389. Those 389 are still an upper limit, because they haven't been checked for clear satellite images. Every aligned visit is also a 100 m × 100 m square, so this one filter removes the 50 m × 200 m plots too.
- **Why not use the soil pit to find the plot:** the pit is supposed to be next to the south-west corner, but 168 of 348 usable visits from 2017–2021 recorded it 80–200 m from the coordinates. It worked as evidence across many visits, but it isn't reliable for placing any one plot.
- **Limitations:**
  - 188 visits had no usable pit position, or used a different datum (the reference model behind a coordinate), so the soil pit check doesn't cover them.
  - The check assumes the `pit_marker_*` fields mean what their names say.
  - Each site has one set of coordinates across all its visits, so if a plot was re-marked in a slightly different place, the data wouldn't show it.
  - Recorded positions can be several metres off, and many were taken with ordinary GPS. A crop may be up to a pixel or so out even after the shift.

### 2026-11-01: Satellite collection and start date
- **Options:**
  - Earth Engine `COPERNICUS/S2_SR_HARMONIZED`, from 2017-03-28 (406 candidate visits).
  - Earth Engine `COPERNICUS/S2_HARMONIZED`, from 2015-06-27 (516 candidate visits).
  - Planetary Computer `sentinel-2-l2a`, from 2015-06-27 (516 candidate visits).
- **Picked:** Earth Engine `COPERNICUS/S2_SR_HARMONIZED`, using only visits from 2017-03-28 on. Planetary Computer stays the backup.
- **Why this collection:** "SR" means surface reflectance: the images are corrected for haze in the air, so the values are closer to what the ground itself reflects. It's also what the 2026-10-31 choice of Earth Engine already assumed, and Earth Engine crops images on its servers, which keeps the code simple.
- **Why not start earlier:** the earlier start adds about 110 candidate visits on paper, but few of them are likely to survive. Only one Sentinel-2 satellite was flying until 2017, so a visit has fewer images to choose from, and fewer of those will be clear of cloud. We also don't need them: 406 is about double the 200 visits we first guessed, and 389 remain after removing plots not aligned to the grid.
- **Trade-off:** the data doesn't cover 2015 to early 2017, so results say nothing direct about those years. 389 is also an upper limit until visits are checked for clear images.
- **If Earth Engine fails:** C2 and C3 passed on 2026-11-02, but only for one plot and visit. If we switch to Planetary Computer, every visit moves to it, because the two process images differently and mixing them could make visits look different for reasons unrelated to the land.

### 2026-11-02: Maximum gap between satellite image and field visit
**Options:** ±30 days or ±60 days. **Picked:** ±30 days, using the closest image that passes a clear-pixel threshold (see "Clear-pixel threshold" below), with no expert input. **Why:** ±60 days adds little and allows more mismatch between image and labels. Of the 389 candidate visits, 384 have an image with up to 10% tile cloud within ±30 days, and 60 days adds only 5, all from one area in the same week. The closest such image is a median of 2 days from the visit, and within 18 days for 95% of visits. A longer gap could also favour the photos, which are taken around the visit date. **Sensitivity check:** if time allows, rerun at ±15 days (363 visits) instead of ±60, because closest-image selection would leave most visits unchanged at ±60. **Limitation:** these counts use Planetary Computer scene records and whole-tile cloud, so Earth Engine and plot-level counts may differ.

### 2026-11-02: Which Sentinel-2 bands to use
- **The problem:** Sentinel-2 records 13 bands, but `COPERNICUS/S2_SR_HARMONIZED` holds only 12 because it has no B10. We need to choose which ones go into each 10×10 crop.
- **Options:**
  - All 12 available bands.
  - The 10 bands with pixels of 20 m or finer, adding red edge (B5, B6, B7, B8A) to the set below.
  - 6 bands: B2, B3, B4, B8, B11 and B12.
- **Picked:** the 6 bands: blue, green, red, near-infrared and two shortwave infrared.
- **Why these 6:**
  - **Dry versus bare:** dry plants and bare soil look alike in visible and near-infrared light, so separating them usually relies on shortwave infrared ([2021 study](https://doaj.org/article/06131ebb26f94c20a7b9b52cda0682b6)). Dry cover is the national map's weakest component and the project's main test, so B11 and B12 are essential.
  - **Green cover:** living plants absorb red light and strongly reflect near-infrared, so B4 and B8 help detect them.
  - **The planned simple features:** `analysis/plan.md` uses NDVI and NDTI. NDVI needs B4 and B8, and NDTI needs B11 and B12.
  - **Fit with the national map:** the TERN Seasonal Fractional Cover JRSRP v3.0 map's related surface reflectance product uses these same 6 band types, and its cover model was trained on Landsat ([reflectance record](https://data.gov.au/data/dataset/1e572275-0bab-4c2a-8360-e04eed876f4b), [cover record](https://geonetwork.tern.org.au/geonetwork/srv/api/records/13810293-c6b5-442b-bfcd-817700738e0d)). We didn't confirm that these are the exact inputs to the cover model.
- **Why not the others:**
  - **B10:** not in this collection.
  - **B1 and B9:** they're designed to measure aerosols and water vapour, not the ground, and their 60 m pixels are over half the width of the 100 m plot.
  - B5, B6, B7 and B8A: I left these out as a design choice, not because we tested that they are unhelpful. They are 20 m bands, so they do not give sharper spatial detail than the 10 m bands we already use. They measure the “red edge” part of the spectrum—the range between red light (B4) and near-infrared (B8)—which can help distinguish vegetation condition and crop type. However, because our dataset has only a few hundred field visits, we preferred a smaller set of inputs to reduce the risk of the model fitting noise. This reduces the number of values per crop from 1,000 to 600.
- **Limitations:**
  - No band comparison was run on our data.
  - The red-edge bands could still help, and we found no source on what they add to this specific task. Testing them later means downloading the crops again.
  - B11 and B12 are 20 m bands placed on a 10 m grid, so they have less spatial detail than the crop's size suggests.

### 2026-11-02: Clear-pixel threshold for satellite crops
- **The problem:** a pixel counts as clear when its `cs_cdf` score is at least 0.60 and it has data in all 6 bands. We also need a rule for how many of a crop's 100 pixels must be clear before we accept the image.
- **Options:** require all pixels to be clear, or accept a lower share and handle the gaps.
- **Picked:** 100%, provisionally. If no image within ±30 days passes, the visit has no usable satellite crop.
- **Why:** every accepted crop is complete, so no model or simple feature has to handle missing pixels.
- **Evidence so far:** C3 ran on one visit (NTABRT0001, 2020-08-01). All 13 images in the window were 100% clear, and the closest was taken on the visit date. That was a dry-season visit in central Australia, so it shows clear images pass, but says nothing about how many visits 100% will cost.
- **Limitations:**
  - The value was chosen without testing alternatives on our data.
  - C3 didn't exercise the cloud mask on a cloudy image, or the `-1` value that marks masked pixels.
  - Requiring 100% could remove more visits from cloudier regions and seasons, which could skew the dataset.

### 2026-11-02: Where code, data and environments live
- **Options:** keep data in the Mac home directory vs keep it on Google Drive.
- **Picked:** data lives in `data/` inside the project folder on Drive, ignored by Git, as one file per visit. `.venv` stays off Drive on both machines (`~/.venvs/cv_capstone` on the Mac, `/content/.venv` on Colab). Git history stays on the Mac and reaches Colab only through a clone from GitHub.
- **Why:** Colab needs to read the data and save results, and 5 TB covers the storage. Drive still handles thousands of small files badly, and each machine needs its own `.venv`.

### 2026-11-03: Sequences with too few frames
- **The problem:** a sequence is one panorama: a set of photos taken while turning in a full circle at one spot. The project takes 6 frames from each of a visit's 3 sequences, 18 in all, but sequences vary in length. In an earlier sample, most held 11–45 frames (median 23), and one held a single frame. Some visits also have fewer than 3 sequences.
- **Options:**
  - Skip short sequences and keep the visit with fewer photos. No visits are lost, but the code must handle visits with different numbers of photos.
  - Repeat frames to reach 6. The photo count stays the same, but the copies add no new information.
  - Drop any visit without 3 full sequences.
- **Picked:** a sequence needs at least 7 frames, not 6, because the first is dropped as a likely label frame (see "Choosing 6 frames per photo sequence" above), leaving 6 to pick from. Skip shorter sequences. A visit needs at least 3 usable sequences, or it's dropped.
- **Why:** every visit then has 18 distinct photos (3 × 6), so no model has to handle a different number of photos per visit. This also follows the plan's rule of dropping visits with missing inputs, and it costs little.
- **Effect on the project:** the short-sequence rule alone changes almost nothing, but the 3-sequence rule lowers the upper limit on usable visits from 389 to 379. That limit can still fall, because visits haven't been checked for clear satellite images.
- **Evidence:** EcoImages frame listings for all 389 candidate visits on 2026-11-03. Their 1,193 sequences had a median of 21 frames and a maximum of 47.
  - Only 1 sequence had fewer than 7 frames: sequence 1 of WAACEK0003 (2021-06-03), with 2.
  - Every candidate visit listed at least one frame.
  - 10 visits have fewer than 3 usable sequences, leaving 379.

  | Sequences listed for the visit | Visits |
  |---|---|
  | 4 | 37 |
  | 3 | 343 |
  | 2 | 7 |
  | 1 | 2 |

- **Limitations:**
  - 7 of the 10 dropped visits are in Western Australia in June–July 2021, so that region and period will be slightly underrepresented.
  - The rule counts frames listed, not whether they download or show the plot.
- **Still open: visits with 4 sequences.** 37 of the 389 visits (about 1 in 10) have a fourth sequence, and we don't yet know why. It could be a retake, an extra spot on the plot or a different kind of view; none of these has been tested. Using sequences 1–3 keeps every visit at 18 photos, but could keep a bad panorama if the fourth was a retake. Using all 4 gives those visits 24 photos, and dropping them loses 37 visits for no proven reason. Checking thumbnails from a few of these visits should settle it.

### 2026-11-03: Matching visits to photo dates
- **The problem:** survey and photo dates can differ. NTABRT0001's 2012-03-19 visit has photos dated 2012-03-20, so matching on the exact date would lose real pairs.
- **Options:** exact date only; a window of a few days; a longer window.
- **Picked:** match each visit to the closest photo date at the same site, up to 7 days either way. The date gap is saved for each visit.
- **Why:** 42 of the 389 candidate visits would be lost by matching on exact dates. A longer window adds few visits and allows more mismatch between photos and labels. A gap of up to 7 days assumes the ground changes little in that time, which we haven't tested, but most pairs are much closer than that.
- **Effect on the project:** each visit's photos should come from the same trip as its labels, and those 42 visits stay in the dataset. Only 6 of the 389 pairs are 2–6 days apart.
- **Evidence:** on 2026-11-03, using the same matching as `plans/checks/count_visits.R`.

  | Gap between visit and photos | Of the 389 candidates |
  |---|---|
  | 0 days | 347 |
  | 1 day | 36 |
  | 2 days | 3 |
  | 4–6 days | 3 |

  - Of the 511 visits from 2017-03-28 on at sites with panoramas, 406 fall within 7 days (389 of them aligned to the grid). Another 6 are 8–30 days away, 2 are 31–90 days away, and 97 are over a year away, which means those photos come from a different trip.
  - No two of the 389 visits match the same photo date at a site.
- **Limitations:**
  - We don't know why the dates differ, and we didn't look at the 3 visits with gaps of 4–6 days.
  - Results may shift slightly if TERN adds or changes photos.

### 2026-11-13: Which cover labels to use (F9)
- **The problem:** `ausplotsR::fractional_cover()` can calculate green / dry / bare cover in two ways. The default counts the top layer at each point, trees and shrubs included. `ground_fractional = TRUE` leaves out the tall woody vegetation and describes the ground surface: grass, litter and bare soil.
- **Options:** `ground_fractional = FALSE` (the default, all layers) vs `ground_fractional = TRUE` (ground layer).
- **Picked:** `ground_fractional = TRUE`. It is the only label the models learn from. "Dry" = `brown`. Optional, if time allows: the `FALSE` version is saved as extra columns (`green_all`, `dry_all`, `bare_all`) but never modelled.
- **Why:**
  - The ground surface is what controls runoff and erosion. Dr. Doe's team improves maps used by inspectors and grazing advisers, and through them station managers (see "Stakeholder" above). This is what they need to see.
  - A paddock can have a lot of tree canopy and still have little protective grass or litter underneath. The all-layer label counts the canopy leaves as "green", which hides that bare, erosion-prone ground. The ground label shows it.
- **Considered against:**
  - Sentinel-2 looks down on the tree tops. At wooded sites, the satellite-only methods have to estimate a surface they can't directly see, so they start at a disadvantage.
  - Photos are taken at ground level and can see under trees. Part of any photo gain at wooded sites will come from that. This is a real advantage of photos, but the report must say so, so the gain isn't read as photos being better everywhere.
  - The national fractional-cover map estimates cover as seen from above, trees included (`analysis/scope.md`). Its published errors (4.6 green / 9.8 dry / 6.9 bare) aren't a like-for-like benchmark for ground-cover labels.
- **Rule:** the label is fixed before any model runs, and the pass mark is unchanged. Models are not trained on both versions so the better one can be picked afterwards.
- **Limitations:**
  - How much the two versions differ hasn't been measured. An earlier note in `docs/data.md` says the numbers are "quite different", but which sites it was based on wasn't recorded. If time allows, the difference will be measured and recorded there.
  - The pass mark's 1.5-point dry-cover threshold was set as about 15% of the national map's 9.8-point dry-cover error (`analysis/scope.md`). That error comes from the all-layer map, so the anchor isn't like-for-like. The threshold is kept unchanged, because it was fixed before any results, and the report should say where it came from.
  - The difficulty of the satellite baseline depends on how wooded each site is. That wasn't controlled for.
- **Future work:** report the photo gain separately for open and wooded sites, to show where photos help.

### 2026-11-15: Pass mark and methods (fixed before any model runs)
- **The question:** do ground photos make the green, dry and bare cover estimates more accurate than satellite and weather data alone?
- **Main comparison:** method #2 (satellite + weather) against method #3 (satellite + weather + photos), across 15 test runs (5 location groups × 3 random groupings; all visits of one site stay in the same group).
- **Pass mark** (from `analysis/scope.md`, unchanged). All three must hold:
  1. Dry-cover MAE drops by 1.5 points or more.
  2. Method #3 has a lower dry-cover MAE than method #2 in 12 or more of the 15 test runs.
  3. Green MAE and bare MAE do not rise by more than 0.5 points.
- **Methods:**
  1. Random forest: satellite only.
  2. Random forest: satellite + weather.
  3. Random forest: satellite + weather + photos. The verdict compares this with #2.
  4. Linear model: all inputs.
  5. Optional, only if time allows on 17 Nov: linear model on photo features only. It does not change the verdict.
- **Dropped:** the earlier photo-features + one-neural-layer method, and the optional all-layer label columns (`green_all`, `dry_all`, `bare_all`) mentioned under F9.
- **Why record it now:** the pass mark and method list are committed before any model runs, so the verdict can't be tuned to the results.
- **Rule:** neither the pass mark nor the method list changes after results are seen. If methods must be cut for time, #4 goes first, then #1; #2 and #3 are mandatory.

### 2026-11-15: Unknown hits in the labels
- **The problem:** some point-intercept hits have no known cover type (`ausplotsR` calls them "other"; its help page calls them "NA"). They belong to none of green, dry or bare, so the three do not add to 100 on their own.
- **Options:**
  - Keep the unknown share as a fourth label.
  - Remove the unknown hits and scale green, dry and bare again so that they add to 100.
  - Remove visits that have many unknown hits.
- **Picked:** remove the unknown hits and scale again (the plan's rule). Save each visit's unknown share as `na_pct` in `data/visits.csv`. Do not remove any visit for a high `na_pct`.
- **Why:** the plan and the pass mark need three labels that add to 100. Removing visits would change the dataset after the rules were set. Saving `na_pct` keeps the information, so the report can show whether the result depends on these visits.
- **How big the effect is (378 visits):**

  | Unknown share | Visits |
  |---|---|
  | 0% | 195 |
  | Above 0% | 183 |
  | Above 5% | 14 |
  | Above 10% | 11 |
  | Above 20% | 9 |

  - Mean 1.2%, median 0%, largest 41.5%.
  - 183 visits change by a very small amount. 11 visits have more than 10% unknown hits, and their labels move the most.
- **Limitations:**
  - Scaling assumes that the unknown hits would have the same mix of green, dry and bare as the known hits. This was not tested.
  - A visit with 40% unknown hits has labels that are about 1.7 times its known cover. Errors for these visits may be larger.
  - Several of the highest values come from the same area (site codes starting SAAEYB). We did not check why.
- **Future work:** after the results exist, run method #2 and method #3 again without the 11 visits above 10%. If the verdict is the same, say so in the report. If it is different, report that as a limitation. Do not change the dataset or the pass mark.

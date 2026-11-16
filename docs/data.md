# Data notes

Facts about the project's data sources: what they contain, their limits and how to read them.
Choices based on these facts belong in `docs/decisions.md`.

Last updated: 2026-11-16

## Sources

| Source | Provides | Access | Status on 1 Nov 2026 |
|---|---|---|---|
| AusPlots, via `ausplotsR` 2.0.5 | Ground measurements of cover (labels) | No account | Working |
| TERN EcoImages | Ground photos | No key for search or previews | Working |
| Sentinel-2, via Earth Engine | Satellite images | Registered Cloud project | Working for one plot on 2 Nov (C3); cloudy images not tested |
| Sentinel-2, via Planetary Computer | Backup satellite images | No account | Search and signing work; cropping not tested |
| SILO | Daily weather | Email as username; no account | Working for one plot on 2 Nov (C1) |

Data licences and credits are in `DATA_ATTRIBUTION.md`.

## Visit counts

Counted with `plans/checks/count_visits.R` on 2026-11-01. Counts may rise if TERN adds data.

| Group | Count |
|---|---|
| AusPlots visits (822 sites) | 1,135 |
| Site and date pairs with panoramas on EcoImages | 986 |
| Visits with photos within 7 days | 894 |
| ...and on or after 2015-06-27 | 516 |
| ...and on or after 2017-03-28 | 406 |
| ...and aligned to the grid | 389 |
| Visits after the latest photo date (no photos on EcoImages) | 87 |

These are upper limits, not usable visits. A usable visit also needs a clear satellite image near the visit date, and this count doesn't check for one.

### Candidate visit list (2026-11-15)

Made by `R/extract_labels.R`, which applies the rules in `docs/decisions.md` in order. TERN had added visits since 2026-11-01, so the counts differ from the table above.

| Rule | Visits |
|---|---|
| AusPlots visits (all) | 1,147 |
| ...on or after 2017-03-28 | 564 |
| ...and plot aligned to the grid | 534 |
| ...and panorama photos within 7 days | 388 |
| ...and 3 or more sequences with 7 or more frames | **378** |

- **378, not 379:** the earlier count was 389 at the "within 7 days" rule and 379 after the sequence rule. The 10 visits removed by the sequence rule are the same as before. The missing visit drops out at the 7-day rule. We did not find which one, because the old list was not saved.
- **Output files** (in `data/`, not committed): `labels.csv` (`site, visit_date, latitude, longitude, green, dry, bare`) and `visits.csv` (adds `site_unique`, `photo_id`, `photo_date`, `date_gap`, `n_seq_usable`, `na_pct`). Both have 378 rows, no missing values, and every label row adds to 100.
- **Labels:** made with `ground_fractional = TRUE`. Unknown hits were removed, and green, dry and bare were scaled again to add to 100.
- **Unknown hits removed (`na_pct` in `visits.csv`):** ausplotsR 2.0.5 returns the unknown share in a column named `other`, not `NA` as its help page says. Before scaling, green + dry + bare + other adds to 99.9–100.1 for every visit.

  | Unknown share of a visit's hits | Visits (of 378) |
  |---|---|
  | 0% | 195 |
  | Above 0% | 183 |
  | Above 5% | 14 |
  | Above 10% | 11 |
  | Above 20% | 9 |
  | Above 40% | 1 |

  - The mean is 1.19% and the median is 0%. The largest is 41.5% (SAAEYB0008, 2020-09-15).
  - For a visit with 40% unknown hits, scaling makes each of green, dry and bare about 1.7 times larger. Those labels depend on the assumption that the unknown hits look like the known ones. This was not tested.
  - No visit was removed for a high `na_pct`, because the label rules are fixed (see `docs/decisions.md`).
- **Date gaps:** 338 visits have a 0-day gap, 35 have 1 day, and 5 have 2–6 days. 37 visits have 4 usable sequences (sequences 1–3 are used).
- **Mean cover:** green 19%, dry 48%, bare 33%.
- **Frame lists:** saved to `data/frames/` (one JSON per visit, 388 files, including the 10 visits removed later). The photo script can read them.

### Final dataset (Checkpoint 1, 2026-11-16)

Made by `src/rangecover/data/build_dataset.py`, which joins the four sources on the visit and keeps only visits that have every input and pass every check. Frozen from this date: the dataset does not change (see "Final visit list kept out of git" in `docs/decisions.md`).

| Result | Visits |
|---|---|
| Candidate visits | 378 |
| Dropped: no `S2_SR_HARMONIZED` image within ±30 days (QDACYP0004–0024, June–July 2018) | 18 |
| Dropped: no image 100% clear (QDACYP0002 2018-06-07, SATSTP0001 2018-08-10) | 2 |
| **Kept** | **358** (336 sites) |

- **Checks, run on every visit:** labels present, each 0–100 and adding to 100 (±0.01); dates readable, visit between 2017-03-28 and 2021-10-29, photo gap ≤ 7 days and image gap ≤ 30 days (both matching the stored gaps), image before 2022-01-25; coordinates inside Australia; 18 photos that exist and open; crop 100% clear with every value finite and non-negative; 36 weather values, rain ≥ 0 and max ≥ min temperature. No visit failed a check other than the missing crop.
- **Limit of the photo check:** PIL's `verify()` reads each file's structure, not every pixel, so a truncated JPEG could pass. The DINOv2 step decodes every photo. The 385 small photos (under 40 KB) are still not checked by eye.
- **Output files** (in `data/`, not committed): `dataset.csv` (358 rows × 54 columns, no missing values), `dataset_crops.npz` (crops in the same row order, with `site_unique` to check alignment), `final_visits.csv` (`site, site_unique, visit_date, photo_id, image_id`) and `dropped_visits.csv` (each dropped visit and its reason).
- **Final visit list SHA-256:** `44e16692a04ea9f75682e9436940f41e63e45eafb2f273a275d896181bb6c29c`. To confirm a copy is the frozen list, run `shasum -a 256 data/final_visits.csv`.

## AusPlots labels

- `fractional_cover()` returns `bare`, `brown` and `green`, plus `NA` when some hits are unknown.
- "Dry" cover is `brown`.
- `ground_fractional=TRUE` leaves out tall woody vegetation and covers the ground layer only. The project uses it (see "Which cover labels to use (F9)" in `docs/decisions.md`).
- **How far apart the two versions are:** an earlier note said `TRUE` gives "quite different numbers", but which sites and values it was based on wasn't recorded. Treat the size of the difference as unmeasured.
- Example, NTABRT0001 (`bare / brown / green`, from `plans/checks/labels_one_site.R` on 2026-11-01). The script calls `fractional_cover()` with the default `ground_fractional = FALSE`, so these are **not** the project's training labels:
  - 2012-03-19: 18.2 / 33.3 / 48.5
  - 2020-08-01: 25.2 / 33.8 / 41.0
  - **Totals:** `bare`, `brown` and `green` add up to 100% in both NTABRT0001 visits (18.2 + 33.3 + 48.5 and 25.2 + 33.8 + 41.0).
  - **`NA` column:** NTABRT0001's output has no `NA` column, but other sites may have one, so code that reads these labels still needs to handle it.
  - **Change between the two visits:** `bare` rose 7.0 percentage points (18.2 to 25.2), `green` fell 7.5 (48.5 to 41.0) and `brown` rose 0.5 (33.3 to 33.8). This shows that one plot's labels can change between visits, but it's only one site, so it says nothing about how common or how large such changes are.
- `plot_is_100m_by_100m` is TRUE for 1,116 of 1,135 visits.
- `get_ausplots(dictionary=TRUE)` returned HTTP 500 on 1 Nov while the main downloads worked, so the API can be partly down.

## TERN photos

- **Date range:** the latest visit ID is `20211029`. The collection is described as ongoing, so this is how far TERN has published, not the end of the survey.
- **Image counts:** 70,287 frames and 3,009 stitched panoramas for AusPlots.
- **Sequences:** a panorama is a sequence of separate frames, not one image.
  - A sample of 124 sequences from 40 random visits (seed 1) had a median of 23 frames, and most had 11–45.
  - One sequence had a single frame.
  - TERN's method says up to 40 frames, but 5 of the 124 had more.
- **Label frames:** the earliest-captured frame of a sequence is usually a photo of a site label, not the plot.
  - Sample: 646 frames in 30 sequences, using up to 3 random visits per year from 2011–2021 (seed 1) and one random sequence per visit. Frames were viewed as thumbnails, so a small label in a later frame could be missed.
  - The first frame was a handwritten label in 28 sequences and a hand holding a phone in 1. The other sequence (NSTSYB0007, 2015-11-19) had no label frame.
  - No labels were seen later in any sequence.
  - In all 3 sequences of NTABRT0001 (2020-08-01), label frames were 22–38 KB and the 12 other frames sampled averaged 72 KB.
- **Frame order:** sort by `file_created`, not by frame number.
  - `file_created` put the label first in all 29 sequences that had one.
  - `file_created_assumed` was true for all 646 sampled frames and all 58 NTABRT0001 frames. TERN's API spec doesn't define it, so its exact meaning is unknown (`esupport@tern.org.au` could confirm).
  - The dates matched the visit date in all 30 sequences. Some daylight photos are stamped at odd hours, such as 02:01 and 22:23, so don't rely on the time of day (for example, for sun angle).
  - Frame numbers can run forward or backward, jump (48 to 2738) or restart (23 to 1). Two 2021 visits had no frame number that could be parsed from the preview URL.
  - In NTABRT0001 (2020-08-01), each shot is stored as a `.CR2` and `.JPG` pair sharing two numbers, which is why 20 frames reach number 40.
- **Overlapping ends:** the camera turns a full circle, so the first and last views of a sequence nearly match.
- **Missing frames:** NTAFIN0006 (2011-10-19) has a panorama listed, but the frame search returned nothing. The visit counts above use panorama listings, so other visits could also lack individual frames.
- **Stitched panoramas:** about 10,000×1,100 px. The 640-px copy is only 640 px wide, too small to cut up.
- **File access:** 320, 640 and 1920-px previews are public, and a 640-px frame is about 75 KB. Original files (`/file/{id}`) return 403 without a key.
- **Possible change:** the API spec says all endpoints need a key, so TERN could start enforcing this. If requests fail with 401 or 403, generate a key at https://account.tern.org.au/ and send it in the `X-Api-Key` header.
- **Date mismatch:** survey and photo dates can differ. NTABRT0001's 2012-03-19 visit has photos dated 20120320, so don't match on exact dates.
- **Download (2026-11-15):** `src/rangecover/data/photos.py` saved 6,804 photos (378 visits × 18) to `data/photos/<site>_<photo_id>/s<seq>_<k>.jpg`, with `data/photos/manifest.csv` listing each frame's source. Results:
  - No download failed, and every visit has 18 photos. Every file opens as a JPEG.
  - The full run took about 2 minutes at about 57 photos per second (4 parallel requests), so the 4-frame backup was not needed.
  - Sizes: 640×427 px (6,694), 640×480 (90) and 640×426 (20). 23–109 KB, median 67 KB, 450 MB in all.
  - 391 photos are under 40 KB, the size of label frames. The 6 smallest were checked by eye: all show open, bare country, not labels. The other 385 were not checked.

## Coordinates

- **What they mark:** the plot's south-west corner. The centre of a 100 m × 100 m plot aligned to the grid is 50 m east and 50 m north of it. The method is in `docs/decisions.md`.
- **Tag:** every AusPlots visit is tagged `point = SW`.
- **Manual (v1.2.9, 2012):**
  - `100SW` is the south-west corner and the starting point for marking the plot (p. 18).
  - Plot location is recorded at the south-west corner (p. 46).
  - The centre is found by adding 50 m to both values (p. 21).
- **One set per site:** each site has the same coordinates on every visit. For example, both NTABRT0001 visits (2012-03-19 and 2020-08-01) are at latitude -22.2836, longitude 133.2473. If a plot was re-marked in a slightly different place, the data wouldn't show it.
- **Misleading name:** EcoImages stores the same numbers under `centroid_point`, identical to 8 decimal places, even though they mark a corner. Only 2 sites were compared (NTABRT0001 and NTAFIN0009), and neither the manual nor the data explains the name.
- **Soil pit check:** on 2026-11-01, the coordinates were compared with the `pit_marker_*` positions for the 947 visits with a usable position in GDA94 or WGS84. The manual says the pit goes next to the south-west corner.

  | Pit distance from coordinates | Visits |
  |---|---|
  | 40 m or less | 565 |
  | 40–80 m (a centre coordinate would give about 70 m) | 19 |
  | 80–200 m | 354 |
  | Over 200 m | 9 |

  - In the 80–200 m group, 350 of 354 pits lie north, east or north-east of the coordinates, at about 100 m or 141 m. Those are the distances from the south-west corner to the other three corners.
  - The check assumes the `pit_marker_*` fields mean what their names say, and it doesn't cover the other 188 visits.
- **Pit positions:** don't use them to locate a plot. In 2017–2021, 168 of 348 usable visits recorded the pit 80–200 m from the coordinates.
- **Plot shape and alignment:** the site table has no column for which way a plot is turned.

  | `plot_dimensions` | Aligned to grid | Not aligned | Aligned, of the 406 candidates | Not aligned, of the 406 candidates |
  |---|---|---|---|---|
  | 100 x 100 m | 1,070 | 46 | 389 | 14 |
  | 50 x 200 m | 0 | 19 | 0 | 3 |

- **Blank zones:** `pit_marker_mga_zones` is blank for 165 visits, so work out the zone from longitude.

## Sentinel-2

| Collection | Starts | Notes |
|---|---|---|
| Earth Engine `COPERNICUS/S2_SR_HARMONIZED` | 2017-03-28 | Atmospherically corrected |
| Earth Engine `COPERNICUS/S2_HARMONIZED` | 2015-06-27 | Top of atmosphere; can't be mixed with SR |
| Planetary Computer `sentinel-2-l2a` | 2015-06-27 | Processed differently from Earth Engine; don't mix sources in one dataset |

- **Scaling:** reflectance is stored ×10,000, so multiply by `0.0001`.
- **Bands:** Sentinel-2 records 13 bands, and this collection holds 12 (no B10). The project uses 6, so each 10×10 crop holds 600 numbers. The full reasoning is in `docs/decisions.md`.

  | Band | Light | Pixel size | Used? | Why |
  |---|---|---|---|---|
  | B1 | Aerosols | 60 m | No | Atmosphere band; pixels too coarse for a 100 m plot |
  | B2 | Blue | 10 m | Yes | Visible colour of the ground |
  | B3 | Green | 10 m | Yes | Visible colour of the ground |
  | B4 | Red | 10 m | Yes | Living plants absorb it; needed for NDVI |
  | B5 | Red edge 1 | 20 m | No | Judgement call, not tested |
  | B6 | Red edge 2 | 20 m | No | Judgement call, not tested |
  | B7 | Red edge 3 | 20 m | No | Judgement call, not tested |
  | B8 | Near-infrared | 10 m | Yes | Living plants reflect it strongly; needed for NDVI |
  | B8A | Red edge 4 (narrow near-infrared) | 20 m | No | Judgement call, not tested |
  | B9 | Water vapour | 60 m | No | Atmosphere band; pixels too coarse for a 100 m plot |
  | B10 | Not in this collection | n/a | No | Not available |
  | B11 | Shortwave infrared 1 | 20 m | Yes | Helps separate dry plants from bare soil; needed for NDTI |
  | B12 | Shortwave infrared 2 | 20 m | Yes | Helps separate dry plants from bare soil; needed for NDTI |

- **Band resolution:** B11 and B12 are 20 m, so they need a shared 10 m grid to get matching shapes. Neighbouring cells can repeat the same value, so they have less detail than B2, B3, B4 and B8.
- **Cloud fields:**
  - `QA60` is empty from 2022-01-25 to 2024-02-28.
  - `CLOUDY_PIXEL_PERCENTAGE` describes the whole ~100 km tile, not the plot.
- **Clear pixels:** a pixel counts as clear when `cs_cdf` is at least 0.60 and all 6 bands have data. A crop must currently be 100% clear (see `docs/decisions.md`).
- **Test crop:** `plans/checks/earth_engine.py` on 2026-11-02, for NTABRT0001 (2020-08-01):
  - **Images:** 13 within ±30 days, about 5 days apart, and all 100% clear. The chosen image is from the visit date.
  - **Output:** a `(10, 10)` structured array on grid `EPSG:28353`, with its west edge at 319429.4 and north edge at 7534834.5.
  - **Mean reflectance:** B2 0.040, B3 0.066, B4 0.131, B8 0.203, B11 0.305, B12 0.246.
  - **Limit:** this is one dry-season visit, so it doesn't show how often other plots have a fully clear image.
- **Download (2026-11-15):** `src/rangecover/data/sentinel2.py`, for the 378 candidate visits, with a 100% clear rule:

  | Result | Visits |
  |---|---|
  | Candidate visits | 378 |
  | No `S2_SR_HARMONIZED` image within ±30 days | 18 |
  | Images found, but none 100% clear | 2 |
  | **Kept, in `data/sentinel2.npz`** | **358** (336 sites) |

  - **Effect on the dataset:** photos and weather exist for all 378 visits, so these 20 are the only visits lost. Monday's join keeps only visits with all inputs, so the dataset will have **358 visits**.
  - **The 100% clear rule removes 2 visits:** QDACYP0002 (2018-06-07; 3 images, best 18% clear) and SATSTP0001 (2018-08-10; 1 image, 57% clear). 358 is above the plan's 200 limit, so the rule stays at 100%.
  - **The 18 visits with no image** are all on Cape York (QDACYP0004 to QDACYP0024, 9 June to 13 July 2018). This is a gap in the surface-reflectance archive, not cloud. At QDACYP0004, `S2_SR_HARMONIZED` has 0 images from 10 May to 10 July 2018, but the top-of-atmosphere `S2_HARMONIZED` has 12. The SR collection has images there again from November 2018.
  - **Date gap (image to visit):** 48 visits 0 days, 283 visits 1–7 days, 18 visits 8–14 days, 9 visits 15–28 days. The mean is 3.0 days.
  - **Values:** all finite, none masked. Mean reflectance: B2 0.057, B3 0.084, B4 0.124, B8 0.227, B11 0.279, B12 0.218. One B2 pixel is exactly 0 (NSANSS0002, a dark green site).
  - **Tile edges:** where two tiles overlap, the server-side clear score can count an image as 100% clear when part of the plot lies outside it. Those pixels come back as `-inf`. This happened for one visit (SAAKAN0009, tile T53HPA). The script now measures the clear share on the downloaded crop as well, and it takes the next-closest image when the crop fails. For SAAKAN0009 that is the same-day image from the overlapping tile T53HQA.
  - **Plot centre:** computed locally with `pyproj` (GDA94 to MGA). It gives the same grid as the Earth Engine transform in the C3 check (west 319429.4, north 7534834.5).
  - **File contents:** `crops` (358, 6, 10, 10) float32 reflectance in band order B2, B3, B4, B8, B11, B12, and for each visit `site`, `site_unique`, `visit_date`, `image_date`, `image_id`, `date_gap` and `clear_fraction`. Per-visit caches are in `data/sentinel2/`.
- **Sparse early data:** at 5 test points, the first scene was 18 Aug – 24 Nov 2015, and 2016 had only 17–56 scenes per point. Only Sentinel-2A was flying until Sentinel-2B joined in 2017.
- **Offset:** the +1000 offset affects scenes from 2022-01-25 on. It doesn't apply here if windows end by 2021-11-28 (last photo + 30 days).

## SILO

Tested in C1 on 2026-11-02, for the grid cell at -22.30, 133.25 (NTABRT0001), from 2019-08-01 to 2020-07-31. It returned a header and 366 daily rows.

- Returns daily values, which need adding up to monthly.
- Dates are `YYYYMMDD`, and coordinates must be on the 0.05° grid.
- `comment=RXN` requests rain, maximum temperature and minimum temperature.
- SILO monitors request volume, so request each grid cell once and save the result.
- **Download (2026-11-15):** `src/rangecover/data/weather.py`, for the 378 candidate visits. They fall in 285 grid cells, and all 285 downloaded with no failures (daily files in `data/silo/`).
  - `data/weather.csv`: 378 rows, 12 months each of rain, max and min temperature (month rules in `docs/decisions.md`, "Weather months and grid cell"). No missing values. Max temperature is never below min.
  - 12-month rain: median 291 mm, range 26–2,065 mm. Monthly mean max: 1.1–42.9 °C. Monthly mean min: −3.3–27.5 °C. The coldest values are from alpine plots.

## Storage

- `data/` lives in the project folder on Google Drive, ignored by Git, as one file per visit. Its location is set by `DATA_DIR`.
- `.venv` stays off Drive on both machines: `~/.venvs/cv_capstone` on the Mac and `/content/.venv` on Colab.
- About 400 visits × 3 sequences × 6 frames ≈ 7,200 photos ≈ 0.5 GB at 640 px.

## Python version

- Colab runs Python 3.13.18 (checked 2026-11-03), so the project pins 3.13 on both machines.

## Open questions

- ~~How many visits in the final set lack individual frames~~ None of the 378: all have 18 photos (2026-11-15).
- How far apart the default and ground-only labels are, overall and at wooded sites (F9 is decided; see `docs/decisions.md`)
- ~~Final usable visit count after cloud and date filtering~~ 358 (2026-11-15). Photos and weather are complete for all 378 candidates, so the satellite step sets the count. Monday's join drops the 20 visits with no crop. If the join finds other problems, it records them here. **Confirmed 2026-11-16:** the join kept 358 and found no other problems (see "Final dataset").

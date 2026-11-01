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
- **Picked:** `uv`. `pyproject.toml` lists the packages the project needs, `uv sync` installs them into a project-local `.venv`, and `uv.lock` records the exact versions installed. Scripts run with `uv run`.
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
- **If Earth Engine fails:** it hasn't been tested yet (C2 and C3). If we switch to Planetary Computer, every visit moves to it, because the two process images differently and mixing them could make visits look different for reasons unrelated to the land.

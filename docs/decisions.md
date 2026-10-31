# Decisions

One entry per choice: the options, what was picked, and why.

### 2026-10-31: Satellite data source and Earth Engine tier
- **Options:** Google Earth Engine vs Microsoft Planetary Computer; GEE Community tier (150 EECU-h, no billing) vs Contributor (1,000 EECU-h, billing account required).
- **Picked:** Google Earth Engine, academic non-commercial registration, Community tier. Planetary Computer is the backup.
- **Why:** GEE filters by date and cloud and crops on its servers, so each visit returns only a 10×10-pixel Sentinel-2 crop. The expected use is a few EECU-hours, well under 150, and Community needs no billing account. The project can upgrade to Contributor later if needed.

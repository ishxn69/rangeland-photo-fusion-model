"""Download one 10x10 Sentinel-2 crop (6 bands) for each visit, from Earth Engine.

Recipe (tested in plans/checks/earth_engine.py; rules in docs/decisions.md):
  - move the plot's south-west corner 50 m east and north in MGA (zone from longitude);
  - list COPERNICUS/S2_SR_HARMONIZED images within +-30 days of the visit, and score
    each by the share of its 100 plot pixels that are clear (cs_cdf >= 0.60, all bands);
  - pick the closest image whose clear share is at least --min-clear (default 1.0);
  - download B2, B3, B4, B8, B11, B12 on one fixed 10 m grid. Masked pixels hold -1.

Caches (resume: an existing file is not fetched again):
  data/sentinel2/scores/<site_unique>.json    every image in the window, with its clear share
  data/sentinel2/crops/<site_unique>__<image>.npy   the chosen crop
The image choice is made from the cached scores, so a new --min-clear needs no new search.

Output: data/sentinel2.npz with crops (n, 6, 10, 10) float32 and, per visit, site,
site_unique, visit_date, image_date, image_id, date_gap (days) and clear_fraction.
Visits with no passing image are left out. The script prints how many.

Run:  uv run python src/rangecover/data/sentinel2.py [--min-clear 1.0] [--workers 8]
"""
import argparse
import datetime as dt
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import ee
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
CACHE = DATA_DIR / "sentinel2"

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_SCORE = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
REFLECTANCE_SCALE = 0.0001
WINDOW_DAYS = 30
MIN_CLOUD_SCORE = 0.60
PIXEL_METRES = 10
CROP_PIXELS = 10
MASKED_VALUE = -1


def plot_grid(lat: float, lon: float):
    """Return the MGA projection and the west and north edges of the crop centred on the plot."""
    zone = math.floor((lon + 180) / 6) + 1
    crs = f"EPSG:{28300 + zone}"
    # EPSG:4283 is GDA94 latitude and longitude, the datum of the AusPlots coordinates.
    easting, northing = Transformer.from_crs("EPSG:4283", crs, always_xy=True).transform(lon, lat)
    half = CROP_PIXELS * PIXEL_METRES / 2
    centre_e, centre_n = easting + 50, northing + 50
    return crs, centre_e - half, centre_n + half


def score_images(crs: str, west: float, north: float, visit: dt.date) -> list[dict]:
    """List every image within the window, with its clear share over the plot."""
    size = CROP_PIXELS * PIXEL_METRES
    plot = ee.Geometry.Rectangle([west, north - size, west + size, north], crs, False)
    transform = [PIXEL_METRES, 0, west, 0, -PIXEL_METRES, north]
    images = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(plot)
        .filterDate((visit - dt.timedelta(days=WINDOW_DAYS)).isoformat(),
                    (visit + dt.timedelta(days=WINDOW_DAYS + 1)).isoformat())
        .linkCollection(ee.ImageCollection(CLOUD_SCORE), ["cs_cdf"])
    )

    def add_clear(image):
        has_all = image.select(BANDS).mask().reduce(ee.Reducer.min())
        clear = image.select("cs_cdf").gte(MIN_CLOUD_SCORE).And(has_all).unmask(0)
        stats = clear.rename("clear").reduceRegion(
            reducer=ee.Reducer.mean().unweighted(), geometry=plot, crs=crs, crsTransform=transform)
        return image.set("clear_fraction", stats.get("clear"))

    scored = images.map(add_clear)
    table = ee.Dictionary({
        "id": scored.aggregate_array("system:index"),
        "time": scored.aggregate_array("system:time_start"),
        "clear": scored.aggregate_array("clear_fraction"),
    }).getInfo()
    rows = []
    for image_id, time_ms, clear in zip(table["id"], table["time"], table["clear"]):
        day = dt.datetime.fromtimestamp(time_ms / 1000, dt.timezone.utc).date()
        rows.append({"image_id": image_id, "image_date": day.isoformat(),
                     "gap": abs((day - visit).days), "clear": clear or 0.0})
    return rows


def choose(rows: list[dict], min_clear: float) -> dict | None:
    """Closest passing image; on a tie, the clearer one, then the lower ID (fixed order)."""
    passing = [r for r in rows if r["clear"] >= min_clear]
    return min(passing, key=lambda r: (r["gap"], -r["clear"], r["image_id"]), default=None)


def fetch_crop(crs: str, west: float, north: float, image_id: str) -> np.ndarray:
    """Download one image's 6 bands on the fixed grid, as a (6, 10, 10) float32 array."""
    image = ee.Image(f"{COLLECTION}/{image_id}").addBands(
        ee.Image(f"{CLOUD_SCORE}/{image_id}").select("cs_cdf"))
    crop = (image.select(BANDS).updateMask(image.select("cs_cdf").gte(MIN_CLOUD_SCORE))
            .multiply(REFLECTANCE_SCALE).unmask(MASKED_VALUE).toFloat())
    pixels = ee.data.computePixels({
        "expression": crop, "fileFormat": "NUMPY_NDARRAY", "bandIds": BANDS,
        "grid": {"crsCode": crs,
                 "dimensions": {"width": CROP_PIXELS, "height": CROP_PIXELS},
                 "affineTransform": {"scaleX": PIXEL_METRES, "shearX": 0, "translateX": west,
                                     "shearY": 0, "scaleY": -PIXEL_METRES, "translateY": north}},
    })
    if pixels.shape != (CROP_PIXELS, CROP_PIXELS) or list(pixels.dtype.names) != BANDS:
        raise ValueError(f"unexpected crop: shape {pixels.shape}, fields {pixels.dtype.names}")
    crop = np.stack([pixels[b] for b in BANDS]).astype(np.float32)
    # Pixels outside the image footprint come back as -inf; mark them like cloud.
    return np.where(np.isfinite(crop), crop, MASKED_VALUE).astype(np.float32)


def process(visit, min_clear: float) -> dict:
    """Score (or read cached scores), choose an image and fetch (or read) its crop."""
    key = visit.site_unique
    crs, west, north = plot_grid(visit.latitude, visit.longitude)
    score_path = CACHE / "scores" / f"{key}.json"
    if score_path.exists():
        rows = json.loads(score_path.read_text())["images"]
    else:
        rows = score_images(crs, west, north, dt.date.fromisoformat(visit.visit_date))
        score_path.write_text(json.dumps({"crs": crs, "west": west, "north": north,
                                          "images": rows}, indent=1))
    out = {"site_unique": key, "n_images": len(rows), "pick": None, "crop": None}
    # The server score can count a tile-edge image as fully clear when part of the plot lies
    # outside it, so the downloaded crop is measured too. If it fails, its measured share is
    # saved in the scores file and the next-closest image is tried.
    while (pick := choose(rows, min_clear)) is not None:
        crop_path = CACHE / "crops" / f"{key}__{pick['image_id']}.npy"
        if not crop_path.exists():
            np.save(crop_path, fetch_crop(crs, west, north, pick["image_id"]))
        crop = np.load(crop_path)
        measured = float((crop != MASKED_VALUE).all(axis=0).mean())
        if measured >= min_clear:
            out.update(pick=pick, crop=crop)
            return out
        pick["clear"] = measured
        score_path.write_text(json.dumps({"crs": crs, "west": west, "north": north,
                                          "images": rows}, indent=1))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-clear", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    # The high-volume endpoint is meant for many small parallel requests like these.
    ee.Initialize(project=os.environ.get("EE_PROJECT"),
                  opt_url="https://earthengine-highvolume.googleapis.com")
    for sub in ("scores", "crops"):
        (CACHE / sub).mkdir(parents=True, exist_ok=True)

    visits = pd.read_csv(DATA_DIR / "visits.csv").merge(
        pd.read_csv(DATA_DIR / "labels.csv")[["site", "visit_date", "latitude", "longitude"]],
        on=["site", "visit_date"], how="left", validate="one_to_one")
    if visits.latitude.isna().any():
        raise SystemExit("some visits have no coordinates in labels.csv")

    results, failed = {}, []
    with ThreadPoolExecutor(args.workers) as pool:
        jobs = {pool.submit(process, v, args.min_clear): v.site_unique
                for v in visits.itertuples(index=False)}
        for i, job in enumerate(as_completed(jobs), 1):
            try:
                results[jobs[job]] = job.result()
            except Exception as error:  # noqa: BLE001 - report and keep going; rerun retries
                failed.append(jobs[job])
                print(f"FAIL {jobs[job]}: {error}")
            if i % 25 == 0:
                print(f"{i}/{len(jobs)} visits done, {len(failed)} failed", flush=True)

    kept = [v for v in visits.itertuples(index=False)
            if v.site_unique in results and results[v.site_unique]["crop"] is not None]
    no_image = sum(1 for r in results.values() if r["n_images"] == 0)
    no_clear = sum(1 for r in results.values() if r["n_images"] and r["pick"] is None)
    picks = [results[v.site_unique]["pick"] for v in kept]
    np.savez_compressed(
        DATA_DIR / "sentinel2.npz",
        crops=np.stack([results[v.site_unique]["crop"] for v in kept]),
        bands=np.array(BANDS),
        site=np.array([v.site for v in kept]),
        site_unique=np.array([v.site_unique for v in kept]),
        visit_date=np.array([v.visit_date for v in kept]),
        image_date=np.array([p["image_date"] for p in picks]),
        image_id=np.array([p["image_id"] for p in picks]),
        date_gap=np.array([p["gap"] for p in picks], dtype=np.int16),
        clear_fraction=np.array([p["clear"] for p in picks], dtype=np.float32),
        min_clear=np.float32(args.min_clear),
    )
    print(f"\n{len(visits)} visits: {len(kept)} kept (min clear {args.min_clear:.0%}), "
          f"{no_clear} with no image clear enough, {no_image} with no image, "
          f"{len(failed)} failed (rerun to retry)")
    if picks:
        gaps = np.array([p["gap"] for p in picks])
        crops = np.stack([results[v.site_unique]["crop"] for v in kept])
        print(f"date gap: median {np.median(gaps):.0f} days, max {gaps.max()} days; "
              f"masked pixels in kept crops: {int((crops[:, 0] == MASKED_VALUE).sum())}")


if __name__ == "__main__":
    main()

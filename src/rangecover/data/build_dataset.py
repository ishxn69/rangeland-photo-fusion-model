"""Join labels, photos, Sentinel-2 crops and SILO weather into one row per visit.

This is Checkpoint 1 in `analysis/plan-minimum.md`. The script reads the four
downloaded sources, checks each visit and keeps only the visits that have every
input and pass every check. A visit that fails is dropped with a reason; it is
never repaired (see the plan: "Do not try to recover visits with missing data").

Inputs (all in DATA_DIR):
    visits.csv, labels.csv     candidate visits and their cover labels.
    photos/manifest.csv        the 18 chosen frames of each visit.
    sentinel2.npz              one 6-band 10x10 crop per visit that has one.
    sentinel2/scores/*.json    cached image searches, used to explain a missing crop.
    weather.csv                12 visit-relative months of rain and temperature.

Outputs (all in DATA_DIR, none committed):
    dataset.csv          one row per kept visit: IDs, labels, dates, weather.
    dataset_crops.npz    the kept crops, in the same row order as dataset.csv.
    final_visits.csv     the frozen visit list. Only its SHA-256 is recorded in git.
    dropped_visits.csv   each dropped visit and the reason.

Problems with a whole source (duplicate keys, mismatched visit sets) raise an
error instead of dropping rows, because they mean an input file is wrong.

Run:  uv run python src/rangecover/data/build_dataset.py
"""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[3] / "data"))

LABELS = ["green", "dry", "bare"]
LABEL_TOLERANCE = 0.01             # labels must add to 100 within this many points
FIRST_VISIT = pd.Timestamp("2017-03-28")  # start of S2_SR_HARMONIZED
LAST_PHOTO = pd.Timestamp("2021-10-29")   # latest EcoImages visit
OFFSET_START = pd.Timestamp("2022-01-25")  # Sentinel-2 +1000 offset begins
MAX_PHOTO_GAP = 7                  # days, docs/decisions.md "Matching visits to photo dates"
MAX_IMAGE_GAP = 30                 # days, docs/decisions.md "Maximum gap between ..."
MIN_CLEAR = 1.0                    # docs/decisions.md "Clear-pixel threshold"
N_PHOTOS = 18                      # 3 sequences x 6 frames
MASKED_VALUE = -1                  # value sentinel2.py writes for masked pixels
AUSTRALIA = {"lat": (-44.0, -10.0), "lon": (112.0, 154.0)}
WEATHER = [f"{p}_m{k:02d}" for p in ("rain", "tmax", "tmin") for k in range(1, 13)]
FINAL_COLUMNS = ["site", "site_unique", "visit_date", "photo_id", "image_id"]


def load_tables() -> tuple[pd.DataFrame, np.ndarray]:
    """Read every source and join them on the visit.

    Returns:
        A table with one row per candidate visit (missing inputs left as NaN),
        and the crop array indexed by the table's `crop_index` column.

    Raises:
        ValueError: If a source has duplicate keys, if `visits.csv` and
            `labels.csv` list different visits, or if the crop file is
            inconsistent.
    """
    key = ["site", "visit_date"]
    visits = pd.read_csv(DATA_DIR / "visits.csv").rename(columns={"date_gap": "photo_gap"})
    labels = pd.read_csv(DATA_DIR / "labels.csv")
    table = visits.merge(labels, on=key, how="outer", validate="one_to_one", indicator=True)
    if (table.pop("_merge") != "both").any():
        raise ValueError("visits.csv and labels.csv list different visits")

    weather = pd.read_csv(DATA_DIR / "weather.csv")
    table = table.merge(weather, on=key, how="left", validate="one_to_one")

    s2 = np.load(DATA_DIR / "sentinel2.npz")
    crops = s2["crops"]
    satellite = pd.DataFrame({
        "site_unique": s2["site_unique"], "s2_visit_date": s2["visit_date"],
        "image_id": s2["image_id"], "image_date": s2["image_date"],
        "image_gap": s2["date_gap"], "clear_fraction": s2["clear_fraction"],
        "crop_index": np.arange(len(crops)),
    })
    if len(satellite) != len(crops) or list(s2["bands"]) != ["B2", "B3", "B4", "B8", "B11", "B12"]:
        raise ValueError("sentinel2.npz: crop count or band order does not match its metadata")
    table = table.merge(satellite, on="site_unique", how="left", validate="one_to_one")
    has_crop = table["crop_index"].notna()
    if (table.loc[has_crop, "s2_visit_date"] != table.loc[has_crop, "visit_date"]).any():
        raise ValueError("sentinel2.npz: a crop's visit date differs from visits.csv")

    manifest = pd.read_csv(DATA_DIR / "photos" / "manifest.csv", dtype={"photo_id": str})
    photos = manifest.groupby(key + ["photo_id"])["path"].agg(list).rename("photo_paths")
    table["photo_id"] = table["photo_id"].astype(str)
    table = table.merge(photos.reset_index(), on=key + ["photo_id"], how="left",
                        validate="one_to_one")
    return table.drop(columns="s2_visit_date"), crops


def missing_crop_reason(site_unique: str) -> str:
    """Explain why a visit has no crop, from the cached image search.

    Args:
        site_unique: The visit's AusPlots `site_unique` ID.

    Returns:
        A short reason for the drop report.
    """
    path = DATA_DIR / "sentinel2" / "scores" / f"{site_unique}.json"
    if not path.exists():
        return "satellite: never searched"
    if not json.loads(path.read_text())["images"]:
        return f"satellite: no SR image within {MAX_IMAGE_GAP} days"
    return f"satellite: no image {MIN_CLEAR:.0%} clear"


def photos_ok(paths: list[str]) -> bool:
    """Return True if every photo exists, is non-empty and decodes as an image."""
    for rel in paths:
        path = DATA_DIR / "photos" / rel
        if not path.exists() or path.stat().st_size == 0:
            return False
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception:  # noqa: BLE001 - any decode failure means a bad photo
            return False
    return True


def drop_reason(row: pd.Series, crops: np.ndarray) -> str | None:
    """Return the first check a visit fails, or None if it passes them all.

    Missing inputs are checked first, then the values of each input.

    Args:
        row: One visit from `load_tables`.
        crops: The crop array from `load_tables`.

    Returns:
        A short reason such as "labels: do not add to 100", or None.
    """
    # Missing inputs.
    if row[WEATHER].isna().any():
        return "weather: missing"
    if not isinstance(row["photo_paths"], list):
        return "photos: missing"
    if pd.isna(row["crop_index"]):
        return missing_crop_reason(row["site_unique"])

    # Labels.
    values = row[LABELS].astype(float)
    if values.isna().any() or ((values < 0) | (values > 100)).any():
        return "labels: missing or outside 0-100"
    if abs(values.sum() - 100) > LABEL_TOLERANCE:
        return "labels: do not add to 100"

    # Dates.
    visit, photo, image = (pd.to_datetime(row[c], errors="coerce")
                           for c in ("visit_date", "photo_date", "image_date"))
    if pd.isna(visit) or pd.isna(photo) or pd.isna(image):
        return "dates: cannot be read"
    if not FIRST_VISIT <= visit <= LAST_PHOTO:
        return "dates: visit outside 2017-03-28 to 2021-10-29"
    if abs((photo - visit).days) != row["photo_gap"] or row["photo_gap"] > MAX_PHOTO_GAP:
        return "dates: photo gap wrong or over 7 days"
    if abs((image - visit).days) != row["image_gap"] or row["image_gap"] > MAX_IMAGE_GAP:
        return "dates: image gap wrong or over 30 days"
    if image >= OFFSET_START:
        return "dates: image after the +1000 offset change"

    # Coordinates.
    if not (AUSTRALIA["lat"][0] <= row["latitude"] <= AUSTRALIA["lat"][1]
            and AUSTRALIA["lon"][0] <= row["longitude"] <= AUSTRALIA["lon"][1]):
        return "coordinates: outside Australia"

    # Photos.
    if len(row["photo_paths"]) != N_PHOTOS or not photos_ok(row["photo_paths"]):
        return f"photos: fewer than {N_PHOTOS} readable"

    # Satellite.
    crop = crops[int(row["crop_index"])]
    if row["clear_fraction"] < MIN_CLEAR or not np.isfinite(crop).all() or (crop < 0).any():
        return "satellite: masked, non-finite or negative pixels"

    # Weather.
    rain = row[[c for c in WEATHER if c.startswith("rain")]].astype(float)
    tmax = row[[c for c in WEATHER if c.startswith("tmax")]].to_numpy(float)
    tmin = row[[c for c in WEATHER if c.startswith("tmin")]].to_numpy(float)
    if (rain < 0).any() or (tmax < tmin).any():
        return "weather: negative rain or max below min"
    return None


def main() -> None:
    """Build the dataset, write the outputs and print the drop report."""
    table, crops = load_tables()
    print(f"{len(table)} candidate visits; checking photos and values...", flush=True)
    table["drop_reason"] = [drop_reason(row, crops) for _, row in table.iterrows()]

    dropped = table[table["drop_reason"].notna()]
    dropped[["site", "site_unique", "visit_date", "drop_reason"]].to_csv(
        DATA_DIR / "dropped_visits.csv", index=False)

    kept = table[table["drop_reason"].isna()].sort_values("site_unique").reset_index(drop=True)
    kept["photo_dir"] = kept["site"] + "_" + kept["photo_id"]
    np.savez_compressed(DATA_DIR / "dataset_crops.npz",
                        crops=crops[kept["crop_index"].astype(int).to_numpy()],
                        site_unique=kept["site_unique"].to_numpy(str),
                        bands=np.array(["B2", "B3", "B4", "B8", "B11", "B12"]))
    columns = (["site", "site_unique", "visit_date", "latitude", "longitude", *LABELS,
                "na_pct", "photo_id", "photo_date", "photo_gap", "photo_dir",
                "image_id", "image_date", "image_gap", "silo_lat", "silo_lon", *WEATHER])
    kept[columns].to_csv(DATA_DIR / "dataset.csv", index=False)
    final_path = DATA_DIR / "final_visits.csv"
    kept[FINAL_COLUMNS].to_csv(final_path, index=False)

    print(f"\nKept {len(kept)} visits at {kept['site'].nunique()} sites; "
          f"dropped {len(dropped)}:")
    print(dropped["drop_reason"].value_counts().to_string())
    print(f"\nfinal_visits.csv sha256: {hashlib.sha256(final_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

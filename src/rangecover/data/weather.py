"""Download SILO weather and make 12 monthly values before each visit.

For each visit in data/labels.csv:
  - snap the plot point to SILO's 0.05 degree grid (one cell is about 5 km,
    so the 50 m from plot corner to plot centre does not change the cell);
  - "month k" (k = 1..12) is the k-th month back from the visit date, e.g. for a
    visit on 2020-08-15, month 1 is 2020-07-15 .. 2020-08-14. The visit day is
    not included;
  - rain_mKK = total daily rain (mm), tmax_mKK / tmin_mKK = mean daily max / min
    temperature (deg C) in month KK.

SILO asks users to request each grid cell once, so the daily data for each
cell (covering all its visits) is saved to data/silo/<lat>_<lon>.csv.
Resumes: a cell file that exists is not downloaded again.

Output: data/weather.csv, one row per visit: site, visit_date, silo_lat,
silo_lon, then rain_m01..m12, tmax_m01..m12, tmin_m01..m12.

Needs SILO_EMAIL in .env. Run:  uv run python src/rangecover/data/weather.py
"""
import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
API = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/DataDrillDataset.php"
GRID = 0.05
N_MONTHS = 12
COLS = {"daily_rain": "rain", "max_temp": "tmax", "min_temp": "tmin"}


def snap(x: float) -> float:
    """Round a coordinate to the nearest SILO grid point."""
    return round(round(x / GRID) * GRID, 2)


def cell_path(lat: float, lon: float) -> Path:
    return DATA_DIR / "silo" / f"{lat:.2f}_{lon:.2f}.csv"


def fetch_cell(lat, lon, start, finish, email, session, tries=4) -> None:
    """Save daily rain / max / min temperature for one cell. Skips if saved."""
    path = cell_path(lat, lon)
    if path.exists() and path.stat().st_size > 0:
        return
    params = {"lat": f"{lat:.2f}", "lon": f"{lon:.2f}",
              "start": start.strftime("%Y%m%d"), "finish": finish.strftime("%Y%m%d"),
              "format": "csv", "comment": "RXN", "username": email,
              "password": "apirequest"}
    for attempt in range(tries):
        try:
            r = session.get(API, params=params, timeout=120)
            r.raise_for_status()
            if not r.text.startswith("latitude,longitude"):
                raise ValueError(f"not a SILO csv: {r.text[:200]!r}")
            tmp = path.with_suffix(".part")
            tmp.write_text(r.text)
            tmp.replace(path)
            return
        except (requests.RequestException, ValueError):
            if attempt == tries - 1:
                raise
            time.sleep(5 * 2 ** attempt)


def read_cell(lat: float, lon: float) -> pd.DataFrame:
    df = pd.read_csv(cell_path(lat, lon), skipinitialspace=True)
    df["date"] = pd.to_datetime(df["YYYY-MM-DD"])
    return df.set_index("date")[list(COLS)].rename(columns=COLS)


def monthly(daily: pd.DataFrame, visit: pd.Timestamp) -> dict:
    """12 visit-relative months of rain totals and mean temperatures."""
    row = {}
    for k in range(1, N_MONTHS + 1):
        lo = visit - pd.DateOffset(months=k)
        hi = visit - pd.DateOffset(months=k - 1) - pd.Timedelta(days=1)
        d = daily.loc[lo:hi]
        if len(d) != (hi - lo).days + 1 or d.isna().any().any():
            raise ValueError(f"missing days in {lo.date()}..{hi.date()}")
        row[f"rain_m{k:02d}"] = round(d["rain"].sum(), 1)
        row[f"tmax_m{k:02d}"] = round(d["tmax"].mean(), 2)
        row[f"tmin_m{k:02d}"] = round(d["tmin"].mean(), 2)
    return row


def main() -> None:
    load_dotenv(ROOT / ".env")
    email = os.environ.get("SILO_EMAIL")
    if not email:
        sys.exit("SILO_EMAIL is not set in .env")

    v = pd.read_csv(DATA_DIR / "labels.csv", parse_dates=["visit_date"])
    v["silo_lat"], v["silo_lon"] = v["latitude"].map(snap), v["longitude"].map(snap)
    cells = v.groupby(["silo_lat", "silo_lon"])["visit_date"].agg(["min", "max"])
    (DATA_DIR / "silo").mkdir(parents=True, exist_ok=True)
    print(f"{len(v)} visits in {len(cells)} grid cells", flush=True)

    session, failed = requests.Session(), []
    for i, ((lat, lon), r) in enumerate(cells.iterrows(), 1):
        new = not cell_path(lat, lon).exists()
        try:
            fetch_cell(lat, lon, r["min"] - pd.DateOffset(months=N_MONTHS),
                       r["max"] - pd.Timedelta(days=1), email, session)
        except Exception as e:  # keep going; failures are listed at the end
            failed.append((lat, lon, repr(e)))
        if new:
            time.sleep(1)  # be gentle with SILO
        if i % 25 == 0 or i == len(cells):
            print(f"{i}/{len(cells)} cells, {len(failed)} failed", flush=True)
    if failed:
        for f in failed:
            print("FAILED", *f)
        sys.exit(f"{len(failed)} cells failed. Run again to retry.")

    rows = []
    for _, x in v.iterrows():
        rows.append({"site": x["site"], "visit_date": x["visit_date"].date(),
                     "silo_lat": x["silo_lat"], "silo_lon": x["silo_lon"],
                     **monthly(read_cell(x["silo_lat"], x["silo_lon"]), x["visit_date"])})
    out = pd.DataFrame(rows)
    order = ["site", "visit_date", "silo_lat", "silo_lon"] + [
        f"{p}_m{k:02d}" for p in COLS.values() for k in range(1, N_MONTHS + 1)]
    out[order].to_csv(DATA_DIR / "weather.csv", index=False)
    print(f"saved {len(out)} visits to {DATA_DIR / 'weather.csv'}")


if __name__ == "__main__":
    main()

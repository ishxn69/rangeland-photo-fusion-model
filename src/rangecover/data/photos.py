"""Download the ground photos: 6 frames from each of 3 sequences per visit.

Rules (docs/decisions.md, "Choosing 6 frames per photo sequence" and
"Sequences with too few frames"):
  - a sequence is usable if it lists 7 or more frames;
  - use the first 3 usable sequences, by sequence number (visits with 4 use 1-3);
  - sort each sequence by `file_created`, drop the first (label) frame;
  - pick N_FRAMES evenly spaced frames from the rest, at the middle of N_FRAMES
    equal slices, so neither end of the circle is used.

Reads data/visits.csv and the frame listings in data/frames/ (fetched if
missing). Saves 640-px JPEGs to data/photos/<site>_<photo_id>/s<seq>_<k>.jpg
and a list of all chosen frames to data/photos/manifest.csv.
Resumes: a photo file that exists is not downloaded again.

Run:  uv run python src/rangecover/data/photos.py [--frames 6] [--workers 4]
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[3] / "data"))
API = "https://ecoimages.tern.org.au/api/v1.0/search"
MIN_FRAMES = 7   # the first frame is dropped, so 6 remain to pick from
N_SEQ = 3
SIZE = "medium"  # the 640-px preview
JPEG_MAGIC = b"\xff\xd8\xff"


def frame_listing(site: str, photo_id: str, session: requests.Session) -> dict:
    """Read the cached EcoImages frame listing for a visit, or fetch and cache it."""
    path = DATA_DIR / "frames" / f"{site}_{photo_id}.json"
    if not path.exists():
        params = {"image_type": "photopoint", "site_id": "ausplots",
                  "plot": f"ausplots.{site.lower()}", "site_visit_id": photo_id,
                  "page_size": 200}
        r = session.get(API, params=params, timeout=60)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    listing = json.loads(path.read_text())
    if len(listing["hits"]["hits"]) < listing["hits"]["total"]["value"]:
        raise ValueError(f"frame listing truncated: {path}")
    return listing


def pick_indices(n: int, k: int) -> list[int]:
    """k evenly spaced indices into n items: the middle of k equal slices."""
    return [int((i + 0.5) * n / k) for i in range(k)]


def choose_frames(listing: dict, k: int) -> list[dict]:
    """Apply the frame rules. Returns one dict per chosen frame, in order."""
    by_seq = defaultdict(list)
    for hit in listing["hits"]["hits"]:
        src = hit["_source"]
        by_seq[int(src["position"]["value"])].append(src)
    usable = [s for s in sorted(by_seq) if len(by_seq[s]) >= MIN_FRAMES][:N_SEQ]
    if len(usable) < N_SEQ:
        raise ValueError(f"only {len(usable)} usable sequences")
    chosen = []
    for seq in usable:
        frames = sorted(by_seq[seq], key=lambda f: (f["file_created"], f["image_id"]))[1:]
        for j, idx in enumerate(pick_indices(len(frames), k)):
            f = frames[idx]
            url = next(u["url"] for u in f["preview_urls"] if u["size"] == SIZE)
            chosen.append({"seq": seq, "k": j, "n_frames": len(frames) + 1,
                           "image_id": f["image_id"], "file_created": f["file_created"],
                           "url": url})
    return chosen


def download(url: str, dest: Path, session: requests.Session, tries: int = 4) -> str:
    """Save url to dest. Returns 'skip', 'ok' or raises after `tries` failures."""
    if dest.exists() and dest.stat().st_size > 0:
        return "skip"
    tmp = dest.with_suffix(".part")
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
            if not r.content.startswith(JPEG_MAGIC):
                raise ValueError("response is not a JPEG")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return "ok"
        except (requests.RequestException, ValueError):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frames", type=int, default=6, help="frames per sequence")
    ap.add_argument("--workers", type=int, default=4, help="parallel downloads")
    ap.add_argument("--limit", type=int, default=None, help="first N visits only")
    args = ap.parse_args()

    out_dir = DATA_DIR / "photos"
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    with open(DATA_DIR / "visits.csv", newline="") as fh:
        visits = list(csv.DictReader(fh))[: args.limit]

    jobs, manifest = [], []
    for v in visits:
        site, photo_id = v["site"], v["photo_id"]
        for f in choose_frames(frame_listing(site, photo_id, session), args.frames):
            rel = Path(f"{site}_{photo_id}") / f"s{f['seq']}_{f['k']}.jpg"
            manifest.append({"site": site, "visit_date": v["visit_date"],
                             "photo_id": photo_id, "path": rel.as_posix(), **f})
            jobs.append((f["url"], out_dir / rel))
    for d in {dest.parent for _, dest in jobs}:
        d.mkdir(exist_ok=True)
    with open(out_dir / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)

    print(f"{len(visits)} visits, {len(jobs)} photos to check", flush=True)
    counts, failed, start = defaultdict(int), [], time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(download, url, dest, session): (url, dest) for url, dest in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                counts[fut.result()] += 1
            except Exception as e:  # keep going; failures are listed at the end
                url, dest = futures[fut]
                failed.append({"path": dest.relative_to(out_dir).as_posix(),
                               "url": url, "error": repr(e)})
            if i % 200 == 0 or i == len(jobs):
                rate = counts["ok"] / max(time.time() - start, 1e-9)
                print(f"{i}/{len(jobs)} done: {counts['ok']} new, {counts['skip']} "
                      f"skipped, {len(failed)} failed, {rate:.1f} new/s", flush=True)

    fail_path = out_dir / "failed.csv"
    if failed:
        with open(fail_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["path", "url", "error"])
            w.writeheader()
            w.writerows(failed)
        print(f"{len(failed)} failed: see {fail_path}. Run again to retry.")
        sys.exit(1)
    fail_path.unlink(missing_ok=True)
    print("all photos present")


if __name__ == "__main__":
    main()

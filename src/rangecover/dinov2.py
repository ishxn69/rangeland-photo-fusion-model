"""DINOv2 photo features: 768 numbers per photo, then the mean per visit.

Runs in Colab on a GPU (see notebooks/main.ipynb). On the Mac, use only
`--smoke`, which does 2 visits on the CPU and writes to a temporary folder.

Steps:
1. Find the visits that have no features file in DATA_DIR/dinov2/photos/ yet.
   If there are none, steps 2-4 are skipped: no copy, no model, no GPU needed.
2. Copy the 18 photos of only those visits from Drive to the Colab disk
   (`--local`), COPY_WORKERS files at a time. Through the Drive mount each
   file is a separate slow request, so one at a time took about an hour.
3. Load DINOv2 ViT-B/14 at a fixed revision. It is used as-is (no training).
4. For each of those visits, resize its 18 frames to 336 x 224 (the full
   frame, no crop), run them as one batch and keep the CLS output (18 x 768).
   Save one file per visit. Files are written under a temporary name and then
   renamed, so a stopped run never leaves a half-written file.
5. Save the mean of the 18 rows per visit to DATA_DIR/dinov2_visit_mean.npz,
   in the row order of dataset.csv.

Run (Colab):  uv run python -m rangecover.dinov2 --local /content/photos
Run (Mac):    uv run python -m rangecover.dinov2 --smoke [--local <temp folder>]
"""
import argparse
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from transformers import AutoModel

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

MODEL = "facebook/dinov2-base"                         # ViT-B/14, 768 numbers
REVISION = "f9e44c814b77203eaa57a6bdbbd535f21ede1415"  # Hugging Face commit, 2024-01-17
SIZE = (336, 224)          # width, height: 24 x 16 patches of 14 px; frames are 3:2
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)   # ImageNet, as DINOv2 was trained
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
FRAMES = [f"s{seq}_{k}.jpg" for seq in (1, 2, 3) for k in range(6)]   # docs/decisions.md
N_FEATURES = 768
COPY_WORKERS = 16          # files copied at the same time; the copy waits on Drive, not the CPU
SMOKE_DIR = Path(tempfile.gettempdir()) / "dinov2_smoke"   # fixed, so a 2nd smoke run resumes


def missing_visits(table: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Return the visits that have no features file in `out_dir` yet."""
    done = [(out_dir / f"{s}.npy").exists() for s in table["site_unique"]]
    return table[~np.array(done, dtype=bool)]


def copy_one(source: Path, target: Path) -> None:
    """Copy one file unless it exists. Copy to `.part`, then rename.

    The rename is one step, so a stopped copy leaves only a `.part` file. The
    real name then does not exist, and the next run copies that photo again.
    """
    if target.exists():
        return
    part = target.with_name(target.name + ".part")
    shutil.copyfile(source, part)
    part.replace(target)


def copy_photos(table: pd.DataFrame, source: Path, target: Path,
                workers: int = COPY_WORKERS) -> None:
    """Copy the 18 frames of each visit in `table` to `target`, with progress.

    Threads are enough here: each copy waits on the network, and Python lets
    other threads run while one waits.
    """
    pairs = [(source / d / n, target / d / n) for d in table["photo_dir"] for n in FRAMES]
    for photo_dir in table["photo_dir"]:
        (target / photo_dir).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, _ in enumerate(pool.map(lambda p: copy_one(*p), pairs), 1):
            if i % 500 == 0 or i == len(pairs):
                print(f"copied {i}/{len(pairs)} photos", flush=True)


def load_frames(folder: Path) -> torch.Tensor:
    """Read a visit's 18 frames as one batch, shape (18, 3, 224, 336).

    `convert("RGB")` decodes every pixel, so a cut or broken JPEG fails here
    with its path, instead of passing as it can in the join's `verify()` check.
    """
    arrays = []
    for name in FRAMES:
        with Image.open(folder / name) as image:
            rgb = image.convert("RGB").resize(SIZE, Image.Resampling.BICUBIC)
        arrays.append((np.asarray(rgb, dtype=np.float32) / 255 - MEAN) / STD)
    return torch.from_numpy(np.stack(arrays)).permute(0, 3, 1, 2)


def load_model(device: torch.device) -> torch.nn.Module:
    """Load DINOv2 at the fixed revision, in evaluation mode."""
    model = AutoModel.from_pretrained(MODEL, revision=REVISION)
    return model.to(device).eval()


@torch.inference_mode()
def embed(model: torch.nn.Module, batch: torch.Tensor, device: torch.device) -> np.ndarray:
    """Run one batch and return the CLS output, shape (n, 768), float32.

    On a GPU, autocast runs the model in half precision (faster on a T4).
    The CLS output is the first token of the last layer, after the final norm.
    """
    with torch.autocast(device_type=device.type, dtype=torch.float16,
                        enabled=device.type == "cuda"):
        out = model(pixel_values=batch.to(device))
    return out.last_hidden_state[:, 0].float().cpu().numpy()


def save_atomic(path: Path, array: np.ndarray) -> None:
    """Write to a temporary name, then rename, so a half-written file never exists."""
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, array)
    tmp.replace(path)


def run(table: pd.DataFrame, photo_root: Path, out_dir: Path, device: torch.device) -> np.ndarray:
    """Make or reuse the per-visit features and return the visit means.

    Args:
        table: Visits in model row order, with `site_unique` and `photo_dir`.
        photo_root: Folder that holds one photo folder per visit.
        out_dir: Folder for the per-visit files.
        device: Where the model runs.

    Returns:
        Array of shape (len(table), 768), one mean row per visit.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    model = None   # loaded only if a visit still needs it
    means = []
    for i, row in enumerate(table.itertuples(), 1):
        path = out_dir / f"{row.site_unique}.npy"
        if not path.exists():
            model = model or load_model(device)
            save_atomic(path, embed(model, load_frames(photo_root / row.photo_dir), device))
        features = np.load(path)
        if features.shape != (len(FRAMES), N_FEATURES) or not np.isfinite(features).all():
            raise ValueError(f"{path}: bad features {features.shape}")
        means.append(features.mean(axis=0))
        if i % 50 == 0 or i == len(table):
            print(f"{i}/{len(table)} visits", flush=True)
    return np.stack(means)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--local", type=Path, help="copy photos here first (Colab disk)")
    parser.add_argument("--smoke", action="store_true", help="2 visits, CPU, temp output")
    args = parser.parse_args()

    torch.manual_seed(0)
    table = pd.read_csv(DATA_DIR / "dataset.csv")
    frozen = pd.read_csv(DATA_DIR / "final_visits.csv")
    if list(table["site_unique"]) != list(frozen["site_unique"]):
        raise ValueError("dataset.csv and final_visits.csv list different visits")

    if args.smoke:
        table, out_root = table.head(2), SMOKE_DIR
    else:
        out_root = DATA_DIR
    out_dir = out_root / "dinov2" / "photos"

    # Check the finished work first: only the missing visits need a copy and a GPU.
    todo = missing_visits(table, out_dir)
    print(f"{len(table) - len(todo)}/{len(table)} visits already have features; "
          f"{len(todo)} to do", flush=True)
    if args.smoke or todo.empty:
        device = torch.device("cpu")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        raise SystemExit("No GPU. In Colab: Runtime > Change runtime type > T4 GPU. "
                         "On the Mac, use --smoke.")

    photo_root = DATA_DIR / "photos"
    if args.local and not todo.empty:
        print(f"Copying the photos of {len(todo)} visits to {args.local} ...", flush=True)
        copy_photos(todo, photo_root, args.local)
        photo_root = args.local

    means = run(table, photo_root, out_dir, device)
    out = out_root / "dinov2_visit_mean.npz"
    np.savez_compressed(out, features=means.astype(np.float32),
                        site_unique=table["site_unique"].to_numpy(str),
                        model=MODEL, revision=REVISION)
    print(f"Saved {means.shape} to {out} (device: {device})")


if __name__ == "__main__":
    main()

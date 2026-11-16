"""The 15 site-grouped test runs: 5 location groups x 3 random groupings.

Nearby sites look alike, so a test site next to a training site would make the
error look too good. The script therefore never splits single visits. It:

1. takes one point per site (all visits of a site stay together);
2. cuts the sites into N_BLOCKS small location blocks with k-means (fixed seed);
3. for each seed in SEEDS, shuffles the blocks and deals them in that order
   into N_GROUPS groups, each block to the group with the fewest visits;
4. makes one test run per group: train on the other 4 groups, test on it.

Why blocks and not k-means with 5 clusters: on this data, 5-cluster k-means
gives the same grouping for every seed (one cluster holds 157 of 336 sites), so
the "3 random groupings" would be one grouping counted 3 times. See
docs/decisions.md "Test runs: location blocks dealt into 5 groups".

Run (prints the group sizes):  uv run python -m rangecover.splits
"""
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

N_BLOCKS = 30        # location blocks; about 11 sites each on average
N_GROUPS = 5         # test groups per grouping
SEEDS = (0, 1, 2)    # one random grouping per seed
BLOCK_SEED = 0       # the blocks themselves are fixed


@dataclass(frozen=True)
class TestRun:
    """One test run. `train` and `test` are row positions in the visit table."""
    run: int          # 0-14
    seed: int         # which grouping
    group: int        # which group is the test group
    train: np.ndarray
    test: np.ndarray


def unit_vectors(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Turn latitude and longitude (degrees) into points on a unit sphere.

    k-means measures straight-line distance. One degree of longitude is shorter
    than one degree of latitude away from the equator, so raw degrees would
    stretch the map east-west. On the sphere, distance follows real distance.
    """
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def site_blocks(table: pd.DataFrame, n_blocks: int = N_BLOCKS) -> pd.Series:
    """Give each site a location block number.

    Args:
        table: Visits with `site`, `latitude` and `longitude` columns.
        n_blocks: How many blocks to make.

    Returns:
        A Series indexed by site, holding the block number.
    """
    sites = table.groupby("site")[["latitude", "longitude"]].mean()
    points = unit_vectors(sites["latitude"].to_numpy(), sites["longitude"].to_numpy())
    labels = KMeans(n_clusters=n_blocks, random_state=BLOCK_SEED, n_init=10).fit_predict(points)
    return pd.Series(labels, index=sites.index, name="block")


def deal_blocks(block_sizes: pd.Series, seed: int, n_groups: int = N_GROUPS) -> dict[int, int]:
    """Deal the blocks into groups of about equal visit count.

    The blocks are shuffled with `seed`. In that order, each block goes to the
    group that has the fewest visits so far. Different seeds give different
    groupings, while the group sizes stay close. (Sorting the blocks largest
    first would balance sizes better, but then every seed gives almost the
    same grouping.)

    Args:
        block_sizes: Number of visits in each block, indexed by block.
        seed: Seed for the shuffle.
        n_groups: How many groups to make.

    Returns:
        A map from block number to group number.
    """
    rng = np.random.default_rng(seed)
    shuffled = block_sizes.loc[rng.permutation(block_sizes.index.to_numpy())]
    totals = np.zeros(n_groups, dtype=int)
    group_of = {}
    for block, size in shuffled.items():
        # Random tie-break, so equal totals do not always favour group 0.
        smallest = np.flatnonzero(totals == totals.min())
        group = int(rng.choice(smallest))
        group_of[int(block)] = group
        totals[group] += size
    return group_of


def make_test_runs(table: pd.DataFrame, seeds=SEEDS, n_groups: int = N_GROUPS,
                   n_blocks: int = N_BLOCKS) -> list[TestRun]:
    """Make the test runs for a visit table.

    Args:
        table: Visits with `site`, `latitude` and `longitude`, in model row order.
        seeds: One grouping per seed.
        n_groups: Test groups per grouping.
        n_blocks: Location blocks.

    Returns:
        len(seeds) * n_groups test runs, in order seed by seed.
    """
    block_of_site = site_blocks(table, n_blocks)
    visit_block = table["site"].map(block_of_site).to_numpy()
    block_sizes = pd.Series(visit_block).value_counts().sort_index()
    runs = []
    for seed in seeds:
        group_of = deal_blocks(block_sizes, seed, n_groups)
        visit_group = np.array([group_of[b] for b in visit_block])
        for group in range(n_groups):
            runs.append(TestRun(run=len(runs), seed=seed, group=group,
                                train=np.flatnonzero(visit_group != group),
                                test=np.flatnonzero(visit_group == group)))
    return runs


def load_visits() -> pd.DataFrame:
    """Read the frozen dataset in its saved row order (sorted by site_unique)."""
    return pd.read_csv(DATA_DIR / "dataset.csv")


def main() -> None:
    """Print the size of each test group, so it can be recorded."""
    table = load_visits()
    runs = make_test_runs(table)
    print(f"{len(table)} visits, {table['site'].nunique()} sites, {N_BLOCKS} blocks")
    for run in runs:
        print(f"run {run.run:2d}  seed {run.seed}  group {run.group}  "
              f"test {len(run.test):3d} visits / {table['site'].iloc[run.test].nunique():3d} sites  "
              f"train {len(run.train):3d}")


if __name__ == "__main__":
    main()

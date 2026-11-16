"""Safe file writes shared by the Step 4 and Step 5 scripts."""
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_path(path: Path) -> Iterator[Path]:
    """Yield a temporary path next to `path`; rename it to `path` on success.

    A rename is one step, so a stopped run leaves only the temporary file and
    never a half-written file under the real name. If the body raises, the
    temporary file is removed and `path` is not touched.

    Example:
        with atomic_path(out / "table.csv") as tmp:
            table.to_csv(tmp, index=False)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}.tmp{path.suffix}")   # keep the suffix for savefig
    try:
        yield tmp
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)

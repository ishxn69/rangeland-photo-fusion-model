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

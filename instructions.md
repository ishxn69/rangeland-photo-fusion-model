# Colab notebook instructions

Every notebook needs these three things.

## 1. Setup cell at the top

Run this first, and again after any runtime disconnect or restart.

```python
import os
from google.colab import drive
drive.mount('/content/drive')

os.environ['DATA_DIR'] = '/content/drive/MyDrive/cv_capstone_project/data'
os.environ['UV_PROJECT_ENVIRONMENT'] = '/content/.venv'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

%cd /content/drive/MyDrive/cv_capstone_project
!pip install -q uv
!uv sync --frozen
```

## 2. Run scripts through uv

The notebook's own Python won't see the locked packages.

```python
!uv run --frozen python scripts/your_script.py
```

## 3. Flush at the end

Make this the last cell, so all writes reach Drive.

```python
drive.flush_and_unmount()
```

## Git

Run git only on the Mac. `.git` in the project is a pointer file to a repo outside Drive.

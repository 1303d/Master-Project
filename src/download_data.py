"""Download the LinkedIn job postings dataset from Kaggle into data/raw/linkedin/."""
import shutil
from pathlib import Path

import kagglehub

DATASET = "arshkon/linkedin-job-postings"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "linkedin"


def main():
    # kagglehub downloads to its own cache folder and returns that path
    cache_path = Path(kagglehub.dataset_download(DATASET))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(cache_path, RAW_DIR, dirs_exist_ok=True)

    print(f"Saved to {RAW_DIR}")
    for f in sorted(RAW_DIR.rglob("*.csv")):
        print(f"  {f.relative_to(RAW_DIR)}  ({f.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

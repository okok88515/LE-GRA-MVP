"""Prepare and verify LE-GRA research data after cloning the repository.

Default behavior:
1. Hydrate the three real Simu5G radio CSV files through Git LFS.
2. Verify every recovered radio and mobility file against the committed
   recovery manifest.
3. Rebuild and validate the reproducible fair-input benchmark when missing.

Run from any directory with:
    python path/to/LE-GRA-MVP/prepare_project_data.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "real_simu5g_data"
MANIFEST_PATH = DATA_DIR / "recovery_manifest.json"
FAIR_DATASET_DIR = REPO_ROOT / "fair_input_dataset_v1"
LFS_FILES = (
    "real_simu5g_data/raw_radio.csv",
    "real_simu5g_data/mid_raw_radio.csv",
    "real_simu5g_data/high_raw_radio.csv",
    "real_simu5g_multiseed_data/**",
)


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def hydrate_lfs() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("Git is not installed or is not available on PATH.")

    try:
        subprocess.run(
            ["git", "lfs", "version"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Git LFS is required. Install it from https://git-lfs.com, then rerun."
        ) from exc

    run(["git", "lfs", "install", "--local"])
    run(["git", "lfs", "pull", "--include=" + ",".join(LFS_FILES)])


def verify_real_data() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    print("\nVerifying real Simu5G files (about 600 MB total)...", flush=True)
    for dispersion, entry in manifest["outputs"].items():
        for kind in ("radio", "mobility"):
            path = DATA_DIR / entry[f"{kind}_file"]
            expected = entry[f"{kind}_sha256"].upper()
            if not path.is_file():
                failures.append(f"{dispersion}/{kind}: missing {path}")
                continue

            actual = sha256_file(path)
            status = "OK" if actual == expected else "FAIL"
            print(f"  {status:4} {path.relative_to(REPO_ROOT)}")
            if actual != expected:
                failures.append(
                    f"{dispersion}/{kind}: expected {expected}, got {actual}"
                )

    if failures:
        raise RuntimeError("Real-data verification failed:\n- " + "\n- ".join(failures))


def prepare_fair_dataset(force: bool) -> None:
    manifest = FAIR_DATASET_DIR / "manifest.json"
    if force or not manifest.is_file():
        run([sys.executable, "build_fair_input_dataset.py"])
    else:
        print("\nFair-input dataset already exists; skipping rebuild.")
    run([sys.executable, "validate_fair_input_dataset.py", str(FAIR_DATASET_DIR)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-lfs",
        action="store_true",
        help="Do not run git lfs pull; only verify files already present.",
    )
    parser.add_argument(
        "--skip-fair",
        action="store_true",
        help="Verify real data only; do not build or validate fair_input_dataset_v1.",
    )
    parser.add_argument(
        "--rebuild-fair",
        action="store_true",
        help="Rebuild fair_input_dataset_v1 even when its manifest exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_lfs:
        hydrate_lfs()
    verify_real_data()
    if not args.skip_fair:
        prepare_fair_dataset(force=args.rebuild_fair)
    print("\nDATA_READY: real Simu5G inputs verified and requested datasets prepared.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

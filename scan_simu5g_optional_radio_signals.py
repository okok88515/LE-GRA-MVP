"""Scan Simu5G / INET / Veins sources for optional radio-diagnostic hooks.

Use this before extending the recorder so we do not patch blind.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


PATTERNS = {
    "sinr": re.compile(r"\bsinr\b", re.IGNORECASE),
    "rsrp": re.compile(r"\brsrp\b", re.IGNORECASE),
    "rsrq": re.compile(r"\brsrq\b", re.IGNORECASE),
    "mcs": re.compile(r"\bmcs\b", re.IGNORECASE),
    "cqi": re.compile(r"\bcqi\b", re.IGNORECASE),
    "feedback": re.compile(r"\bfeedback\b", re.IGNORECASE),
}

SOURCE_EXTENSIONS = {".cc", ".cpp", ".cxx", ".h", ".hpp", ".msg", ".ned"}


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            yield path


def scan_root(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in _iter_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            matches = [name for name, pattern in PATTERNS.items() if pattern.search(line)]
            if not matches:
                continue
            rows.append(
                {
                    "root": str(root),
                    "file": str(path),
                    "line": str(lineno),
                    "signals": "|".join(matches),
                    "content": line.strip(),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--summary-txt", type=Path, default=None)
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for root in args.roots:
        if not root.exists():
            rows.append(
                {
                    "root": str(root),
                    "file": "",
                    "line": "",
                    "signals": "missing_root",
                    "content": "",
                }
            )
            continue
        rows.extend(scan_root(root))

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["root", "file", "line", "signals", "content"])
        writer.writeheader()
        writer.writerows(rows)

    summary_lines = []
    summary_lines.append("Optional radio signal scan summary")
    summary_lines.append(f"roots={', '.join(str(root) for root in args.roots)}")
    for signal in sorted({*PATTERNS.keys(), "missing_root"}):
        count = sum(1 for row in rows if signal in row["signals"].split("|"))
        summary_lines.append(f"{signal}: {count}")
    if args.summary_txt is not None:
        args.summary_txt.parent.mkdir(parents=True, exist_ok=True)
        args.summary_txt.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("\n".join(summary_lines))


if __name__ == "__main__":
    main()

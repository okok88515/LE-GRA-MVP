"""Run a resumable low/mid/high real Simu5G multi-seed batch in WSL."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
RUNNER_WINDOWS = REPO_ROOT / "real_simu5g_data" / "run_p3_7_multiseed_batch.sh"
DEFAULT_OUTPUT_ROOT = "/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs"


def windows_to_wsl(path: Path) -> str:
    """Convert an absolute Windows path for this opp_env image's /c mount."""

    resolved = path.resolve()
    if not resolved.drive:
        raise ValueError(f"expected an absolute Windows path: {resolved}")
    drive = resolved.drive.rstrip(":").lower()
    return f"/{drive}/" + "/".join(resolved.parts[1:])


def parse_seed_spec(spec: str) -> list[int]:
    seeds: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"descending seed range is invalid: {part}")
            seeds.update(range(start, end + 1))
        else:
            seeds.add(int(part))
    if not seeds or min(seeds) < 0:
        raise ValueError("at least one non-negative seed is required")
    return sorted(seeds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="1-10", help="Example: 1-10 or 1,3,8")
    parser.add_argument(
        "--dispersions",
        default="low,mid,high",
        help="Comma-separated subset of low,mid,high",
    )
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--distro", default="LE-GRA-opp-env")
    parser.add_argument(
        "--scenario-root", default=None,
        help="Override P3_7_SCENARIO_ROOT (WSL-native path), e.g. for a differently-scaled scenario",
    )
    parser.add_argument(
        "--omnetpp-config", default=None,
        help="Override P3_7_OMNETPP_CONFIG (defaults to P3_7_Clean_DL if unset)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seeds = parse_seed_spec(args.seeds)
    dispersions = [item.strip() for item in args.dispersions.split(",") if item.strip()]
    invalid = set(dispersions) - {"low", "mid", "high"}
    if invalid:
        raise SystemExit(f"invalid dispersions: {sorted(invalid)}")

    runner_wsl = windows_to_wsl(RUNNER_WINDOWS)
    total = len(seeds) * len(dispersions)
    print(
        f"Starting/resuming {total} runs: dispersions={dispersions}, seeds={seeds}",
        flush=True,
    )
    env_prefix: list[str] = []
    if args.scenario_root:
        env_prefix.append(f"P3_7_SCENARIO_ROOT={args.scenario_root}")
    if args.omnetpp_config:
        env_prefix.append(f"P3_7_OMNETPP_CONFIG={args.omnetpp_config}")
    command = (["env", *env_prefix] if env_prefix else []) + [
        "bash", "--noprofile", "--norc",
        runner_wsl,
        ",".join(str(seed) for seed in seeds),
        ",".join(dispersions),
        args.output_root,
    ]
    subprocess.run(
        ["wsl", "-d", args.distro, "--", *command],
        cwd=REPO_ROOT,
        check=True,
    )
    print(f"\nP3_7_MULTISEED_BATCH_COMPLETE runs={total}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

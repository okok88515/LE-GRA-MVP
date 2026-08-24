#!/usr/bin/env bash
# Run a resumable set of P3.7 protocol-v3 seeds in one opp_env shell.
# Usage: bash run_p3_7_multiseed_batch.sh SEED_CSV DISPERSION_CSV [OUTPUT_ROOT]

set -euo pipefail

seed_csv="${1:-1,2,3,4,5,6,7,8,9,10}"
dispersion_csv="${2:-low,mid,high}"
output_root="${3:-/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs}"
script_dir="$(cd "$(dirname "$0")" && pwd)"

if test -z "${IN_NIX_SHELL:-}"; then
  runner_path="$(realpath "$0")"
  printf -v runner_command '%q ' bash "$runner_path" "$@"
  set +u
  source /home/opp_env/.venv/bin/activate
  source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
  set -u
  cd /home/opp_env/p3_5_workspace
  printf '%s\nexit\n' "$runner_command" \
    | opp_env shell -w /home/opp_env/p3_5_workspace --no-chdir -q
  exit "${PIPESTATUS[1]}"
fi

IFS=',' read -r -a seeds <<< "$seed_csv"
IFS=',' read -r -a dispersions <<< "$dispersion_csv"
total=$((${#seeds[@]} * ${#dispersions[@]}))
current=0

for seed in "${seeds[@]}"; do
  case "$seed" in
    ''|*[!0-9]*) echo "invalid seed: $seed" >&2; exit 2 ;;
  esac
  for dispersion in "${dispersions[@]}"; do
    case "$dispersion" in
      low|mid|high) ;;
      *) echo "invalid dispersion: $dispersion" >&2; exit 2 ;;
    esac
    current=$((current + 1))
    echo "P3_7_BATCH_PROGRESS current=$current total=$total dispersion=$dispersion seed=$seed"
    bash "$script_dir/run_p3_7_seed.sh" "$dispersion" "$seed" "$output_root"
  done
done

echo "P3_7_MULTISEED_BATCH_COMPLETE runs=$total output_root=$output_root"

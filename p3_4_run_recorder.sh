#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace=/home/opp_env/default_workspace
raw_dir="$script_dir/p3_4_actual_radio"
raw_csv="$raw_dir/raw_radio.csv"
raw_diag_csv="$raw_dir/raw_radio_diag.csv"

mkdir -p "$raw_dir"
rm -f "$raw_csv" "$raw_diag_csv"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
cd "$workspace"

export LEGRA_RADIO_RAW_CSV="$raw_csv"
export LEGRA_RADIO_DIAG_RAW_CSV="$raw_diag_csv"
opp_env run simu5g-1.4.3 --no-isolated -c '
  cd /home/opp_env/default_workspace/simu5g-1.4.3/tutorials/nr
  simu5g -u Cmdenv -c Single-UE --sim-time-limit=2s --warmup-period=0s
'

test -s "$raw_csv"
echo P3_4_RAW_RADIO_OK
test -s "$raw_diag_csv" && echo P3_4_RAW_RADIO_DIAG_OK || true
wc -l "$raw_csv"

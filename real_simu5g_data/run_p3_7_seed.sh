#!/usr/bin/env bash
# Run one independently seeded P3.7 Simu5G+SUMO+Veins scenario.
#
# Usage inside LE-GRA-opp-env:
#   bash run_p3_7_seed.sh DISPERSION SEED [OUTPUT_ROOT]
#
# The runner never overwrites a completed run. It writes to a unique scratch
# directory, validates and compresses the raw CSV files, then atomically moves
# the directory into DISPERSION/seed_NNNN.

set -euo pipefail

# The official OMNeT++ binaries installed by opp_env refuse to run outside
# their Nix development shell. Re-enter this script once through that shell
# when invoked directly from WSL/PowerShell.
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

dispersion="${1:?dispersion must be low, mid, or high}"
seed="${2:?seed must be a non-negative integer}"
output_root="${3:-/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs}"
scenario_root="${P3_7_SCENARIO_ROOT:-/home/opp_env/p3_5_workspace/p3_7_recovery/scenarios}"
omnetpp_config="${P3_7_OMNETPP_CONFIG:-P3_7_Clean_DL}"
script_dir="$(cd "$(dirname "$0")" && pwd)"

case "$dispersion" in
  low|mid|high) ;;
  *) echo "invalid dispersion: $dispersion" >&2; exit 2 ;;
esac
case "$seed" in
  ''|*[!0-9]*) echo "seed must be a non-negative integer: $seed" >&2; exit 2 ;;
esac

export VEINS_ROOT=/home/opp_env/p3_5_workspace/veins-5.3.1
export SIMU5G_ROOT=/home/opp_env/p3_5_workspace/simu5g-1.4.3
export INET_ROOT=/home/opp_env/p3_5_workspace/inet-4.6.0
export OMNETPP_ROOT=/home/opp_env/p3_5_workspace/omnetpp-6.3.0
export PATH="$VEINS_ROOT/bin:$PATH"

seed_label="$(printf '%04d' "$seed")"
source_scenario="$scenario_root/$dispersion"
final_dir="$output_root/$dispersion/seed_$seed_label"
mkdir -p "$output_root/$dispersion" "$output_root/.scratch"

if test -s "$final_dir/run_manifest.json" \
    && test -s "$final_dir/raw_radio.csv.gz" \
    && test -s "$final_dir/raw_mobility.csv.gz"; then
  echo "P3_7_SEED_ALREADY_COMPLETE dispersion=$dispersion seed=$seed dir=$final_dir"
  exit 0
fi
if test -e "$final_dir"; then
  echo "refusing to overwrite incomplete final directory: $final_dir" >&2
  exit 3
fi
for required in omnetpp.ini heterogeneous.launchd.xml heterogeneous.net.xml \
                heterogeneous.rou.xml heterogeneous.sumocfg gui-settings.xml; do
  test -s "$source_scenario/$required" || {
    echo "missing scenario input: $source_scenario/$required" >&2
    exit 4
  }
done

scratch_dir="$(mktemp -d "$output_root/.scratch/${dispersion}_seed_${seed_label}.XXXXXX")"
scenario="$scratch_dir/scenario"
output="$scratch_dir/output"
mkdir -p "$scenario" "$output"
cp "$source_scenario"/* "$scenario/"

# The coupled SUMO launcher produced byte-identical mobility even when its
# internal seed and a stochastic vType distribution changed. Generate explicit
# per-vehicle speed factors from the recorded seed instead; this is auditable,
# reproducible, and identical across low/mid/high for a given seed.
python3 "$script_dir/generate_seeded_route.py" \
  --input "$scenario/heterogeneous.rou.xml" \
  --output "$scenario/heterogeneous.rou.xml" \
  --metadata "$scenario/mobility_seed.json" \
  --seed "$seed"

# Pin SUMO randomness explicitly.
sed -i "/<\/configuration>/i\  <random_number>\n    <seed value=\"$seed\"/>\n  </random_number>" \
  "$scenario/heterogeneous.sumocfg"

# Pin OMNeT++/INET/Simu5G RNGs to the same recorded seed. The custom raw CSV
# recorders are independent of OMNeT++ scalar/vector recording, so disable the
# large .vec/.sca payloads.
{
  echo
  echo "# Multi-seed reproducibility overrides"
  echo "seed-set = $seed"
  echo "**.scalar-recording = false"
  echo "**.vector-recording = false"
} >> "$scenario/omnetpp.ini"

cd "$SIMU5G_ROOT"
opp_featuretool enable Simu5G_Cars >/dev/null
export LEGRA_RADIO_RAW_CSV="$output/raw_radio.csv"
export LEGRA_RADIO_DIAG_RAW_CSV="$output/raw_radio_diag.csv"
export LEGRA_MOBILITY_RAW_CSV="$output/raw_mobility.csv"
export OMNETPP_NED_PACKAGE_EXCLUSIONS="$(tr '\n' ';' < "$INET_ROOT/.nedexclusions")"

pkill -9 -f veins_launchd 2>/dev/null || true
sleep 1
veins_launchd -d -vv -k -L "$output/launchd.log" -P "$output/launchd.pid"
cleanup_launchd() {
  if test -s "$output/launchd.pid"; then
    kill -9 "$(cat "$output/launchd.pid")" 2>/dev/null || true
  fi
}
trap cleanup_launchd EXIT
for _ in $(seq 1 30); do
  test -s "$output/launchd.pid" && break
  sleep 0.1
done
test -s "$output/launchd.pid"

started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
started_epoch="$(date +%s)"
opp_run -u Cmdenv -f "$scenario/omnetpp.ini" -c "$omnetpp_config" \
  --output-scalar-file="$output/coupled.sca" \
  --output-vector-file="$output/coupled.vec" \
  -l "$INET_ROOT/src/INET" \
  -l "$VEINS_ROOT/src/veins" \
  -l "$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" \
  -l "$SIMU5G_ROOT/src/simu5g" \
  -n "$scenario:$SIMU5G_ROOT/simulations:$SIMU5G_ROOT/emulation:$SIMU5G_ROOT/src:$INET_ROOT/src:$VEINS_ROOT/src/veins:$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" \
  >"$output/opp_run.log" 2>&1
ended_epoch="$(date +%s)"
ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test -s "$output/raw_radio.csv"
test -s "$output/raw_mobility.csv"
radio_rows="$(wc -l < "$output/raw_radio.csv")"
mobility_rows="$(wc -l < "$output/raw_mobility.csv")"
radio_bytes="$(stat -c %s "$output/raw_radio.csv")"
mobility_bytes="$(stat -c %s "$output/raw_mobility.csv")"
radio_sha256="$(sha256sum "$output/raw_radio.csv" | cut -d' ' -f1)"
mobility_sha256="$(sha256sum "$output/raw_mobility.csv" | cut -d' ' -f1)"

gzip -9 "$output/raw_radio.csv" "$output/raw_mobility.csv"
radio_gzip_sha256="$(sha256sum "$output/raw_radio.csv.gz" | cut -d' ' -f1)"
mobility_gzip_sha256="$(sha256sum "$output/raw_mobility.csv.gz" | cut -d' ' -f1)"

mv "$scenario" "$output/scenario"
cat > "$output/run_manifest.json" <<EOF
{
  "status": "complete",
  "dispersion": "$dispersion",
  "seed": $seed,
  "omnetpp_seed_set": $seed,
  "sumo_seed": $seed,
  "protocol_version": "3.0",
  "mobility_randomization": {
    "parameter": "explicit per-vehicle desired-speed factor",
    "distribution": "seeded clipped normal(mean=1.0,std=0.08,min=0.85,max=1.15)",
    "metadata_file": "scenario/mobility_seed.json",
    "shared_across_dispersions_for_same_seed": true
  },
  "started_utc": "$started_utc",
  "ended_utc": "$ended_utc",
  "duration_s": $((ended_epoch - started_epoch)),
  "simulation_time_limit_s": 90,
  "radio": {
    "file": "raw_radio.csv.gz",
    "rows_including_header": $radio_rows,
    "uncompressed_bytes": $radio_bytes,
    "uncompressed_sha256": "$radio_sha256",
    "gzip_sha256": "$radio_gzip_sha256"
  },
  "mobility": {
    "file": "raw_mobility.csv.gz",
    "rows_including_header": $mobility_rows,
    "uncompressed_bytes": $mobility_bytes,
    "uncompressed_sha256": "$mobility_sha256",
    "gzip_sha256": "$mobility_gzip_sha256"
  },
  "environment": {
    "wsl_distribution": "LE-GRA-opp-env",
    "omnetpp": "6.3.0",
    "inet": "4.6.0",
    "simu5g": "1.4.3",
    "veins": "5.3.1"
  }
}
EOF

trap - EXIT
cleanup_launchd
rm -f "$output/launchd.pid"
mv "$output" "$final_dir"
rmdir "$scratch_dir"
echo "P3_7_SEED_COMPLETE dispersion=$dispersion seed=$seed duration_s=$((ended_epoch - started_epoch)) dir=$final_dir"

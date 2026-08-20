#!/usr/bin/env bash
set -euo pipefail
export VEINS_ROOT=/home/opp_env/p3_5_workspace/veins-5.3.1
export SIMU5G_ROOT=/home/opp_env/p3_5_workspace/simu5g-1.4.3
export INET_ROOT=/home/opp_env/p3_5_workspace/inet-4.6.0
export OMNETPP_ROOT=/home/opp_env/p3_5_workspace/omnetpp-6.3.0
output="${1:-/home/opp_env/p3_5_workspace/p3_7_clean_validation_output}"
scenario="${2:-/home/opp_env/p3_5_workspace/p3_7_clean_validation_scenario}"

cd "$SIMU5G_ROOT"
opp_featuretool enable Simu5G_Cars

export LEGRA_RADIO_RAW_CSV="$output/raw_radio.csv"
export LEGRA_RADIO_DIAG_RAW_CSV="$output/raw_radio_diag.csv"
export LEGRA_MOBILITY_RAW_CSV="$output/raw_mobility.csv"
export OMNETPP_NED_PACKAGE_EXCLUSIONS="$(tr '\n' ';' < "$INET_ROOT/.nedexclusions")"

pkill -9 -f veins_launchd || true
sleep 1
rm -f "$output/launchd.pid"

veins_launchd -d -vv -k -L "$output/launchd.log" -P "$output/launchd.pid"
cleanup_launchd() {
  if test -s "$output/launchd.pid"; then
    pid="$(cat "$output/launchd.pid")"
    kill -9 "$pid" 2>/dev/null || true
  fi
}
trap cleanup_launchd EXIT

for _ in $(seq 1 30); do
  test -s "$output/launchd.pid" && break
  sleep 0.1
done
test -s "$output/launchd.pid"

opp_run -u Cmdenv -f "$scenario/omnetpp.ini" -c P3_7_Clean_DL \
  --output-scalar-file="$output/coupled.sca" \
  --output-vector-file="$output/coupled.vec" \
  -l "$INET_ROOT/src/INET" \
  -l "$VEINS_ROOT/src/veins" \
  -l "$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" \
  -l "$SIMU5G_ROOT/src/simu5g" \
  -n "$scenario:$SIMU5G_ROOT/simulations:$SIMU5G_ROOT/emulation:$SIMU5G_ROOT/src:$INET_ROOT/src:$VEINS_ROOT/src/veins:$VEINS_ROOT/subprojects/veins_inet/src/veins_inet"

test -s "$output/raw_radio.csv"
test -s "$output/raw_mobility.csv"
echo P3_7_CLEAN_SIMULATION_OK

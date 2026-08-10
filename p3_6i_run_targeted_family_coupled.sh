#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "bash" ]]; then
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  script_dir="$(pwd)"
fi
workspace=/home/opp_env/p3_5_workspace
sim_root="$workspace/simu5g-1.4.3/simulations/nr/cars"
runtime_output="$workspace/p3_6i_coupled_output"
repo_output="$script_dir/p3_6i_coupled_output"
runtime_scenario="$workspace/p3_6i_runtime_scenario"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

mkdir -p "$runtime_output" "$repo_output"
rm -rf "$runtime_scenario"
mkdir -p "$runtime_scenario"
rm -f "$runtime_output/raw_radio.csv" \
      "$runtime_output/raw_radio_diag.csv" \
      "$runtime_output/raw_mobility.csv" \
      "$runtime_output/launchd.log" \
      "$runtime_output/launchd.pid" \
      "$runtime_output/coupled.sca" \
      "$runtime_output/coupled.vec" \
      "$runtime_output/coupled.vci"

cp "$sim_root/heterogeneous.net.xml" "$runtime_scenario/heterogeneous.net.xml"
cp "$sim_root/gui-settings.xml" "$runtime_scenario/gui-settings.xml"
cp "$sim_root/demo.xml" "$runtime_scenario/demo.xml"
cp "$script_dir/p3_6i_coupled_scenario/targeted_family.launchd.xml" "$runtime_scenario/targeted_family.launchd.xml"
cp "$script_dir/p3_6i_coupled_scenario/targeted_family.sumocfg" "$runtime_scenario/targeted_family.sumocfg"
cp "$script_dir/p3_6i_coupled_scenario/targeted_family.rou.xml" "$runtime_scenario/targeted_family.rou.xml"
cp "$script_dir/p3_6i_coupled_scenario/omnetpp.ini" "$runtime_scenario/omnetpp.ini"

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 veins-5.3.1 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    set -euo pipefail
    output=/home/opp_env/p3_5_workspace/p3_6i_coupled_output
    scenario=/home/opp_env/p3_5_workspace/p3_6i_runtime_scenario

    cd "$SIMU5G_ROOT"
    opp_featuretool enable Simu5G_Cars

    export LEGRA_RADIO_RAW_CSV="$output/raw_radio.csv"
    export LEGRA_RADIO_DIAG_RAW_CSV="$output/raw_radio_diag.csv"
    export LEGRA_MOBILITY_RAW_CSV="$output/raw_mobility.csv"
    export OMNETPP_NED_PACKAGE_EXCLUSIONS="$(tr "\n" ";" < "$INET_ROOT/.nedexclusions")"

    if test -s "$output/launchd.pid"; then
      stale_pid="$(cat "$output/launchd.pid")"
      if kill -0 "$stale_pid" 2>/dev/null; then
        kill "$stale_pid" || true
        wait "$stale_pid" 2>/dev/null || true
      fi
    fi
    rm -f "$output/launchd.pid"

    veins_launchd -d -vv -k \
      -L "$output/launchd.log" \
      -P "$output/launchd.pid"

    cleanup_launchd() {
      if test -s "$output/launchd.pid"; then
        pid="$(cat "$output/launchd.pid")"
        if kill -0 "$pid" 2>/dev/null; then
          kill "$pid"
          wait "$pid" 2>/dev/null || true
        fi
      fi
    }
    trap cleanup_launchd EXIT

    for _ in $(seq 1 30); do
      test -s "$output/launchd.pid" && break
      sleep 0.1
    done
    test -s "$output/launchd.pid"

    opp_run -u Cmdenv -f "$scenario/omnetpp.ini" -c P3_6I_TargetedFamily_DL \
      --output-scalar-file="$output/coupled.sca" \
      --output-vector-file="$output/coupled.vec" \
      -l "$INET_ROOT/src/INET" \
      -l "$VEINS_ROOT/src/veins" \
      -l "$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" \
      -l "$SIMU5G_ROOT/src/simu5g" \
      -n "$scenario:$SIMU5G_ROOT/simulations:$SIMU5G_ROOT/emulation:$SIMU5G_ROOT/src:$INET_ROOT/src:$VEINS_ROOT/src/veins:$VEINS_ROOT/subprojects/veins_inet/src/veins_inet"

    test -s "$output/raw_radio.csv"
    test -s "$output/raw_radio_diag.csv"
    test -s "$output/raw_mobility.csv"
    test -s "$output/coupled.sca"
    echo P3_6I_COUPLED_SIMULATION_OK
  '

cp -f "$runtime_output/raw_radio.csv" "$repo_output/raw_radio.csv"
cp -f "$runtime_output/raw_radio_diag.csv" "$repo_output/raw_radio_diag.csv"
cp -f "$runtime_output/raw_mobility.csv" "$repo_output/raw_mobility.csv"
cp -f "$runtime_output/launchd.log" "$repo_output/launchd.log"
echo P3_6I_COUPLED_OUTPUT_COPIED
wc -l "$repo_output/raw_radio.csv" "$repo_output/raw_radio_diag.csv" "$repo_output/raw_mobility.csv"

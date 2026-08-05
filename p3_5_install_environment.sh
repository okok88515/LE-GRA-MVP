#!/usr/bin/env bash
set -euo pipefail

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

workspace=/home/opp_env/p3_5_workspace
opp_env install --init --workspace "$workspace" \
  --build-modes release \
  omnetpp-6.3.0 inet-4.6.0 veins-5.3.1 simu5g-1.4.3

opp_env run --workspace "$workspace" simu5g-1.4.3 veins-5.3.1 \
  --no-isolated -c '
    command -v sumo
    command -v python3
    test -s "$VEINS_ROOT/src/libveins.so"
    test -s "$VEINS_ROOT/subprojects/veins_inet/src/libveins_inet.so"
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    echo P3_5_ENVIRONMENT_OK
  '

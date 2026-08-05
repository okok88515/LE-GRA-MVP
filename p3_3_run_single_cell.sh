#!/usr/bin/env bash
set -euo pipefail

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
cd /home/opp_env/default_workspace

opp_env run simu5g-1.4.3 --no-isolated -c '
  cd /home/opp_env/default_workspace/simu5g-1.4.3/tutorials/nr
  rm -rf results/Single-UE
  simu5g -u Cmdenv -c Single-UE
  test -s results/Single-UE/0.sca
  test -s results/Single-UE/0.vec
  echo P3_3_SINGLE_CELL_OK
'

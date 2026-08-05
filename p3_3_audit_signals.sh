#!/usr/bin/env bash
set -euo pipefail

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
cd /home/opp_env/default_workspace

opp_env run simu5g-1.4.3 --no-isolated -c '
  cd /home/opp_env/default_workspace/simu5g-1.4.3
  result_dir=tutorials/nr/results/Single-UE

  echo "P3_3_RELEVANT_UNIQUE_VECTORS_BEGIN"
  opp_scavetool query -n -T v "$result_dir/0.vec" \
    | grep -Ei "cqi|sinr|snir|servedblock|throughput|harq" \
    | sort -u || true
  echo "P3_3_RELEVANT_UNIQUE_VECTORS_END"

  echo "P3_3_CQI_RESULT_COUNT"
  opp_scavetool query -e -T v "$result_dir/0.vec" | grep -Eic "cqi" || true

  echo "P3_3_SOURCE_DECLARATIONS_BEGIN"
  grep -RniE "@statistic.*(cqi|sinr|servedblock)|registerSignal.*(cqi|sinr|servedblock)" src \
    | head -120 || true
  echo "P3_3_SOURCE_DECLARATIONS_END"
'

#!/usr/bin/env bash
set -euo pipefail

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
cd /home/opp_env/default_workspace

opp_env run simu5g-1.4.3 --no-isolated -c '
  cd /home/opp_env/default_workspace/simu5g-1.4.3/tutorials/nr
  result_dir=results/Single-UE

  ls -lh "$result_dir/0.sca" "$result_dir/0.vec" "$result_dir/0.vci"
  echo "P3_3_VECTOR_NAMES_BEGIN"
  opp_scavetool query -e -T v "$result_dir/0.vec" \
    | grep -Ei "cqi|sinr|snir|rb|resource|throughput|bitrate|packet|serving|cell|harq" \
    | head -200 || true
  echo "P3_3_VECTOR_NAMES_END"

  echo "P3_3_SCALAR_NAMES_BEGIN"
  opp_scavetool query -e -T s "$result_dir/0.sca" \
    | grep -Ei "cqi|sinr|snir|rb|resource|throughput|bitrate|packet|serving|cell|harq" \
    | head -200 || true
  echo "P3_3_SCALAR_NAMES_END"
'

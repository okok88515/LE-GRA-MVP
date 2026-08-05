#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace=/home/opp_env/default_workspace
simu5g_root="$workspace/simu5g-1.4.3"
target="$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

if grep -q 'recordLeGraDlBandState' "$target"; then
  echo P3_4_PATCH_ALREADY_APPLIED
else
  git -C "$simu5g_root" apply "$script_dir/simu5g_p3_4_radio_recorder.patch"
  echo P3_4_PATCH_APPLIED
fi

cd "$workspace"
opp_env run simu5g-1.4.3 --no-isolated -c '
  cd /home/opp_env/default_workspace/simu5g-1.4.3/src
  make MODE=release -j2
  test -s libsimu5g.so
  echo P3_4_BUILD_OK
'

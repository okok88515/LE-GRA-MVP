#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"
veins_root="$workspace/veins-5.3.1"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

if grep -q 'ue_module_path,band_index' "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc"; then
  echo P3_5_SIMU5G_PATCH_ALREADY_APPLIED
else
  git -C "$simu5g_root" apply "$script_dir/simu5g_p3_5_module_path.patch"
  echo P3_5_SIMU5G_PATCH_APPLIED
fi

if grep -q 'const char \*ueModulePath = binder_' "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc"; then
  git -C "$simu5g_root" apply "$script_dir/simu5g_p3_5_lifetime_fix.patch"
  echo P3_5_SIMU5G_LIFETIME_FIX_APPLIED
fi

if grep -q 'recordLeGraSumoMobility' "$veins_root/subprojects/veins_inet/src/veins_inet/VeinsInetMobility.cc"; then
  echo P3_5_VEINS_PATCH_ALREADY_APPLIED
else
  git -C "$veins_root" apply "$script_dir/veins_p3_5_mobility_recorder.patch"
  echo P3_5_VEINS_PATCH_APPLIED
fi

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 veins-5.3.1 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    cd "$SIMU5G_ROOT/src"
    make MODE=release -j2
    cd "$VEINS_ROOT/subprojects/veins_inet/src"
    make MODE=release -j2
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    test -s "$VEINS_ROOT/subprojects/veins_inet/src/libveins_inet.so"
    echo P3_5_RECORDERS_BUILD_OK
  '

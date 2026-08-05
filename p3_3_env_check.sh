#!/usr/bin/env bash
set -euo pipefail

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
cd /home/opp_env/default_workspace

opp_env run simu5g-1.4.3 --no-isolated -c '
  printenv OMNETPP_ROOT
  printenv INET_ROOT
  printenv SIMU5G_ROOT
  command -v opp_run || true
  command -v simu5g || true
  test -x /home/opp_env/default_workspace/omnetpp-6.4.0/bin/opp_run && echo OMNETPP_BINARY_OK
  test -s /home/opp_env/default_workspace/inet-4.6.0/out/clang-release/src/libINET.so && echo INET_LIBRARY_OK
  test -s /home/opp_env/default_workspace/simu5g-1.4.3/src/libsimu5g.so && echo SIMU5G_LIBRARY_OK
  test -x /home/opp_env/default_workspace/simu5g-1.4.3/bin/simu5g && echo SIMU5G_BINARY_OK
'

#!/usr/bin/env bash
set -euo pipefail

workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

python3 - "$simu5g_root/src/simu5g/stack/phy/LtePhyEnb.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

include_anchor = '#include <inet/networklayer/common/NetworkInterface.h>\n'
include_block = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <string>\n#include <vector>\n\n#include <inet/networklayer/common/NetworkInterface.h>\n'
if '#include <cstdlib>' not in text:
    if include_anchor not in text:
        raise SystemExit("P3_6Q29_INCLUDE_ANCHOR_MISSING")
    text = text.replace(include_anchor, include_block, 1)

namespace_anchor = 'using namespace omnetpp;\nusing namespace inet;\n\n'
helper_block = """using namespace omnetpp;\nusing namespace inet;\n\nnamespace {\n\nvoid recordLeGraDlRadioDiagnostics(simtime_t timestamp, MacNodeId ueId,\n        MacNodeId gnbId, const std::vector<double>& sinr,\n        const std::vector<double>& rsrp)\n{\n    const char *outputPath = std::getenv(\"LEGRA_RADIO_DIAG_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n    if (sinr.empty() || rsrp.empty())\n        return;\n    if (sinr.size() != rsrp.size())\n        throw cRuntimeError(\"LEGRA radio diag size mismatch: sinr=%zu rsrp=%zu\",\n                sinr.size(), rsrp.size());\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw cRuntimeError(\"Cannot open LE-GRA radio diag output: %s\", outputPath);\n        output << \"timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw cRuntimeError(\"LEGRA_RADIO_DIAG_RAW_CSV changed during the simulation\");\n    }\n\n    double meanSinr = 0.0;\n    double meanRsrp = 0.0;\n    for (size_t i = 0; i < sinr.size(); ++i) {\n        meanSinr += sinr[i];\n        meanRsrp += rsrp[i];\n    }\n    meanSinr /= sinr.size();\n    meanRsrp /= rsrp.size();\n\n    for (size_t band = 0; band < sinr.size(); ++band) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << band << ','\n               << sinr[band] << ','\n               << meanSinr << ','\n               << meanRsrp << '\\n';\n    }\n    output.flush();\n}\n\n} // namespace\n\n"""
if "recordLeGraDlRadioDiagnostics" not in text:
    if namespace_anchor not in text:
        raise SystemExit("P3_6Q29_NAMESPACE_ANCHOR_MISSING")
    text = text.replace(namespace_anchor, helper_block, 1)

old_dl_block = """            //Get snr for DL direction
            if (channelModel != nullptr)
                snr = channelModel->getSINR(frame, lteinfo);
            else
                throw cRuntimeError("LtePhyEnbD2D::requestFeedback - channelModel is a null pointer");
        }
        else
            header->setLteFeedbackDoubleVectorDl(fb);
"""
new_dl_block = """            //Get snr for DL direction
            if (channelModel != nullptr)
                snr = channelModel->getSINR(frame, lteinfo);
            else
                throw cRuntimeError("LtePhyEnbD2D::requestFeedback - channelModel is a null pointer");
        }
        else {
            std::vector<double> rsrp;
            if (channelModel != nullptr)
                rsrp = channelModel->getRSRP(frame, lteinfo);
            else
                throw cRuntimeError("LtePhyEnbD2D::requestFeedback - channelModel is a null pointer");
            recordLeGraDlRadioDiagnostics(simTime(), lteinfo->getSourceId(),
                    nodeId_, snr, rsrp);
            header->setLteFeedbackDoubleVectorDl(fb);
        }
"""
if old_dl_block in text:
    text = text.replace(old_dl_block, new_dl_block, 1)

if "LEGRA_RADIO_DIAG_RAW_CSV" not in text:
    raise SystemExit("P3_6Q29_PATCH_FAILED")

path.write_text(text)
PY

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    cd "$SIMU5G_ROOT/src"
    make MODE=release -j2
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    echo P3_6Q29_PHY_RADIO_DIAG_RECORDER_OK
  '

#!/usr/bin/env bash
set -euo pipefail

workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

python3 - "$simu5g_root/src/simu5g/stack/phy/LtePhyUe.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

include_anchor = '#include "simu5g/common/LteControlInfoTags_m.h"\n'
include_block = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <string>\n#include <vector>\n\n#include "simu5g/common/LteControlInfoTags_m.h"\n'
if '#include <cstdlib>' not in text:
    if include_anchor not in text:
        raise SystemExit("P3_6Q30_INCLUDE_ANCHOR_MISSING")
    text = text.replace(include_anchor, include_block, 1)

namespace_anchor = 'using namespace inet;\n\n'
helper_block = """using namespace inet;\n\nnamespace {\n\nvoid recordLeGraUeDlRadioDiagnostics(simtime_t timestamp, MacNodeId ueId,\n        MacNodeId gnbId, const std::vector<double>& sinr,\n        const std::vector<double>& rsrp, int frameType)\n{\n    const char *outputPath = std::getenv(\"LEGRA_RADIO_DIAG_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw cRuntimeError(\"Cannot open LE-GRA UE radio diag output: %s\", outputPath);\n        output << \"timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm,frame_type\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw cRuntimeError(\"LEGRA_RADIO_DIAG_RAW_CSV changed during the simulation\");\n    }\n\n    if (sinr.empty() || rsrp.empty()) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << -1 << ','\n               << \"nan,nan,nan,\" << frameType << '\\n';\n        output.flush();\n        return;\n    }\n    if (sinr.size() != rsrp.size())\n        throw cRuntimeError(\"LEGRA UE radio diag size mismatch: sinr=%zu rsrp=%zu\",\n                sinr.size(), rsrp.size());\n\n    double meanSinr = 0.0;\n    double meanRsrp = 0.0;\n    for (size_t i = 0; i < sinr.size(); ++i) {\n        meanSinr += sinr[i];\n        meanRsrp += rsrp[i];\n    }\n    meanSinr /= sinr.size();\n    meanRsrp /= rsrp.size();\n\n    for (size_t band = 0; band < sinr.size(); ++band) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << band << ','\n               << sinr[band] << ','\n               << meanSinr << ','\n               << meanRsrp << ','\n               << frameType << '\\n';\n    }\n    output.flush();\n}\n\n} // namespace\n\n"""
if "recordLeGraUeDlRadioDiagnostics" not in text:
    if namespace_anchor not in text:
        raise SystemExit("P3_6Q30_NAMESPACE_ANCHOR_MISSING")
    text = text.replace(namespace_anchor, helper_block, 1)

early_anchor = """    // check if the air frame was sent on a correct carrier frequency
    GHz carrierFreq = lteInfo->getCarrierFrequency();
    LteChannelModel *channelModel = getChannelModel(carrierFreq);
    if (channelModel == nullptr) {
        EV << "Received packet on carrier frequency not supported by this node. Delete it." << endl;
        delete lteInfo;
        delete frame;
        return;
    }

    //Update coordinates of this user
"""
early_replacement = """    // check if the air frame was sent on a correct carrier frequency
    GHz carrierFreq = lteInfo->getCarrierFrequency();
    LteChannelModel *channelModel = getChannelModel(carrierFreq);
    if (channelModel == nullptr) {
        EV << "Received packet on carrier frequency not supported by this node. Delete it." << endl;
        delete lteInfo;
        delete frame;
        return;
    }

    std::vector<double> legraProbeSinr = channelModel->getSINR(frame, lteInfo);
    std::vector<double> legraProbeRsrp = channelModel->getRSRP(frame, lteInfo);
    recordLeGraUeDlRadioDiagnostics(simTime(), nodeId_, lteInfo->getSourceId(),
            legraProbeSinr, legraProbeRsrp, lteInfo->getFrameType());

    //Update coordinates of this user
"""
if "std::vector<double> legraProbeSinr = channelModel->getSINR(frame, lteInfo);" not in text:
    if early_anchor not in text:
        raise SystemExit("P3_6Q30_EARLY_PROBE_ANCHOR_MISSING")
    text = text.replace(early_anchor, early_replacement, 1)

text = text.replace(
    "    if (lteInfo->getFrameType() == DATAPKT) {\n        std::vector<double> sinr = channelModel->getSINR(frame, lteInfo);\n        std::vector<double> rsrp = channelModel->getRSRP(frame, lteInfo);\n        recordLeGraUeDlRadioDiagnostics(simTime(), nodeId_, lteInfo->getSourceId(),\n                sinr, rsrp);\n    }\n\n",
    "",
)
text = text.replace(
    "    std::vector<double> sinr = channelModel->getSINR(frame, lteInfo);\n    std::vector<double> rsrp = channelModel->getRSRP(frame, lteInfo);\n    recordLeGraUeDlRadioDiagnostics(simTime(), nodeId_, lteInfo->getSourceId(),\n            sinr, rsrp, lteInfo->getFrameType());\n\n",
    "",
)

if "LEGRA_RADIO_DIAG_RAW_CSV" not in text or "recordLeGraUeDlRadioDiagnostics" not in text:
    raise SystemExit("P3_6Q30_PATCH_FAILED")

path.write_text(text)
PY

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    cd "$SIMU5G_ROOT/src"
    make MODE=release -j2
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    echo P3_6Q30_UE_AIRFRAME_DIAG_RECORDER_OK
  '

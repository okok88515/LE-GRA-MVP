#!/usr/bin/env bash
set -euo pipefail

workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

python3 - "$simu5g_root/src/simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

include_anchor = '#include <fstream>\n'
include_block = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <string>\n#include <vector>\n'
if '#include <cstdlib>' not in text:
    if include_anchor not in text:
        raise SystemExit("P3_6Q31_INCLUDE_ANCHOR_MISSING")
    text = text.replace(include_anchor, include_block, 1)

namespace_anchor = 'using namespace inet;\nusing namespace omnetpp;\nDefine_Module(LteRealisticChannelModel);\n\n'
helper_block = """using namespace inet;\nusing namespace omnetpp;\nDefine_Module(LteRealisticChannelModel);\n\nnamespace {\n\nvoid recordLeGraChannelModelDiag(simtime_t timestamp, MacNodeId ueId,\n        MacNodeId gnbId, const std::vector<double>& sinr,\n        const std::vector<double>& rsrp, Direction dir, LtePhyFrameType frameType)\n{\n    const char *outputPath = std::getenv(\"LEGRA_RADIO_DIAG_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n    if (sinr.size() != rsrp.size())\n        throw cRuntimeError(\"LEGRA channelmodel diag size mismatch: sinr=%zu rsrp=%zu\",\n                sinr.size(), rsrp.size());\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw cRuntimeError(\"Cannot open LE-GRA channelmodel diag output: %s\", outputPath);\n        output << \"timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm,frame_type,direction\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw cRuntimeError(\"LEGRA_RADIO_DIAG_RAW_CSV changed during the simulation\");\n    }\n\n    if (sinr.empty()) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << -1 << ','\n               << \"nan,nan,nan,\"\n               << static_cast<int>(frameType) << ','\n               << static_cast<int>(dir) << '\\n';\n        output.flush();\n        return;\n    }\n\n    double meanSinr = 0.0;\n    double meanRsrp = 0.0;\n    for (size_t i = 0; i < sinr.size(); ++i) {\n        meanSinr += sinr[i];\n        meanRsrp += rsrp[i];\n    }\n    meanSinr /= sinr.size();\n    meanRsrp /= rsrp.size();\n\n    for (size_t band = 0; band < sinr.size(); ++band) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << band << ','\n               << sinr[band] << ','\n               << meanSinr << ','\n               << rsrp[band] << ','\n               << static_cast<int>(frameType) << ','\n               << static_cast<int>(dir) << '\\n';\n    }\n    output.flush();\n}\n\n} // namespace\n\n"""
if "recordLeGraChannelModelDiag" not in text:
    if namespace_anchor not in text:
        raise SystemExit("P3_6Q31_NAMESPACE_ANCHOR_MISSING")
    text = text.replace(namespace_anchor, helper_block, 1)

insert_anchor = """    //===================== SINR COMPUTATION ========================
    // compute and linearize total noise
    double totN = dBmToLinear(thermalNoise_ + noiseFigure);
"""
insert_replacement = """    std::vector<double> rsrpVector = snrVector;

    //===================== SINR COMPUTATION ========================
    // compute and linearize total noise
    double totN = dBmToLinear(thermalNoise_ + noiseFigure);
"""
if "std::vector<double> rsrpVector = snrVector;" not in text:
    if insert_anchor not in text:
        raise SystemExit("P3_6Q31_RSRP_COPY_ANCHOR_MISSING")
    text = text.replace(insert_anchor, insert_replacement, 1)

return_anchor = """    // sender is a UE
    else
        updatePositionHistory(ueId, coord);
    return snrVector;
}
"""
return_replacement = """    // sender is a UE
    else
        updatePositionHistory(ueId, coord);

    recordLeGraChannelModelDiag(simTime(), ueId, eNbId, snrVector, rsrpVector,
            dir, static_cast<LtePhyFrameType>(lteInfo->getFrameType()));
    return snrVector;
}
"""
if "recordLeGraChannelModelDiag(simTime(), ueId, eNbId, snrVector, rsrpVector," not in text:
    if return_anchor not in text:
        raise SystemExit("P3_6Q31_RECORD_ANCHOR_MISSING")
    text = text.replace(return_anchor, return_replacement, 1)

if "LEGRA_RADIO_DIAG_RAW_CSV" not in text or "recordLeGraChannelModelDiag" not in text:
    raise SystemExit("P3_6Q31_PATCH_FAILED")

path.write_text(text)
PY

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    cd "$SIMU5G_ROOT/src"
    make MODE=release -j2
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    echo P3_6Q31_CHANNELMODEL_DIAG_RECORDER_OK
  '

#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "bash" ]]; then
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
else
  script_dir="$(pwd)"
fi
workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"
veins_root="$workspace/veins-5.3.1"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

if grep -q 'ue_module_path,band_index' "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc"; then
  echo P3_5_SIMU5G_PATCH_ALREADY_APPLIED
else
  python3 - "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old_includes = '#include <string>\n'
new_includes = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <string>\n'
if old_includes not in text:
    raise SystemExit("P3_5_SIMU5G_INCLUDE_ANCHOR_MISSING")
text = text.replace(old_includes, new_includes, 1)

anchor = 'using namespace omnetpp;\n\n'
helper = """using namespace omnetpp;\n\nnamespace {\n\nvoid recordLeGraDlBandState(simtime_t timestamp, MacNodeId ueId,\n        MacNodeId gnbId, const char *ueModulePath, GHz carrierFrequency,\n        const LteFeedback& feedback, const CqiVector& bandCqi, LteAmc *amc)\n{\n    const char *outputPath = std::getenv(\"LEGRA_RADIO_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw cRuntimeError(\"Cannot open LE-GRA radio recorder output: %s\", outputPath);\n        output << \"timestamp_s,ue_node_id,gnb_node_id,ue_module_path,band_index,cqi,tbs_bits_per_slot,total_bands,wideband_cqi,itbs\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw cRuntimeError(\"LEGRA_RADIO_RAW_CSV changed during the simulation\");\n    }\n\n    double wbCqiValue = 0.0;\n    if (feedback.hasWbCqi()) {\n        auto wb = feedback.getWbCqi();\n        if (!wb.empty())\n            wbCqiValue = wb.front();\n    }\n    else if (!bandCqi.empty()) {\n        for (const auto& value : bandCqi)\n            wbCqiValue += value;\n        wbCqiValue /= bandCqi.size();\n    }\n\n    for (Band band = 0; band < bandCqi.size(); ++band) {\n        Cqi cqi = bandCqi[band];\n        unsigned int bitsPerSlot = amc->computeBitsPerRbBackground(\n                cqi, DL, carrierFrequency);\n        unsigned int itbs = amc->getItbsPerCqi(cqi, DL);\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << ueModulePath << ','\n               << band << ','\n               << cqi << ','\n               << bitsPerSlot << ','\n               << bandCqi.size() << ','\n               << wbCqiValue << ','\n               << itbs << '\\n';\n    }\n    output.flush();\n}\n\n} // namespace\n\n"""
if anchor not in text:
    raise SystemExit("P3_5_SIMU5G_NAMESPACE_ANCHOR_MISSING")
text = text.replace(anchor, helper, 1)

old_block = """    for (auto& fbv : fbMapUl) {\n        for (auto& fb : fbv) {\n            if (!fb.isEmptyFeedback())\n                amc_->pushFeedback(srcNodeId, UL, fb, lteInfo->getCarrierFrequency());\n        }\n    }\n"""
new_block = """    for (const auto& fbv : fbMapDl) {\n        bool recorded = false;\n        for (const auto& fb : fbv) {\n            if (!fb.isEmptyFeedback() && fb.hasBandCqi()) {\n                const auto& codewords = fb.getBandCqi();\n                if (!codewords.empty() && !codewords.front().empty()) {\n                    std::string ueModulePath = binder_->getModuleByMacNodeId(\n                            srcNodeId)->getFullPath();\n                    recordLeGraDlBandState(simTime(), srcNodeId, nodeId_,\n                            ueModulePath.c_str(), lteInfo->getCarrierFrequency(),\n                            fb, codewords.front(), amc_);\n                    recorded = true;\n                    break;\n                }\n            }\n        }\n        if (recorded)\n            break;\n    }\n    for (auto& fbv : fbMapUl) {\n        for (auto& fb : fbv) {\n            if (!fb.isEmptyFeedback())\n                amc_->pushFeedback(srcNodeId, UL, fb, lteInfo->getCarrierFrequency());\n        }\n    }\n"""
if old_block not in text:
    raise SystemExit("P3_5_SIMU5G_MAC_BLOCK_ANCHOR_MISSING")
text = text.replace(old_block, new_block, 1)

path.write_text(text)
PY
  echo P3_5_SIMU5G_PATCH_APPLIED
fi

if grep -q 'const char \*ueModulePath = binder_' "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc"; then
  git -C "$simu5g_root" apply "$script_dir/simu5g_p3_5_lifetime_fix.patch"
  echo P3_5_SIMU5G_LIFETIME_FIX_APPLIED
fi

if grep -q 'timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm,frame_type,direction' \
    "$simu5g_root/src/simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc"; then
  echo P3_5_SIMU5G_DIAG_PATCH_ALREADY_APPLIED
else
  python3 - "$simu5g_root/src/simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

include_anchor = '#include <fstream>\n'
include_block = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <string>\n#include <vector>\n'
if '#include <cstdlib>' not in text:
    if include_anchor not in text:
        raise SystemExit("P3_5_SIMU5G_DIAG_INCLUDE_ANCHOR_MISSING")
    text = text.replace(include_anchor, include_block, 1)

namespace_anchor = 'using namespace inet;\nusing namespace omnetpp;\nDefine_Module(LteRealisticChannelModel);\n\n'
helper_block = """using namespace inet;\nusing namespace omnetpp;\nDefine_Module(LteRealisticChannelModel);\n\nnamespace {\n\nvoid recordLeGraChannelModelDiag(simtime_t timestamp, MacNodeId ueId,\n        MacNodeId gnbId, const std::vector<double>& sinr,\n        const std::vector<double>& rsrp, Direction dir, LtePhyFrameType frameType)\n{\n    const char *outputPath = std::getenv(\"LEGRA_RADIO_DIAG_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n    if (sinr.size() != rsrp.size())\n        throw cRuntimeError(\"LEGRA channelmodel diag size mismatch: sinr=%zu rsrp=%zu\",\n                sinr.size(), rsrp.size());\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw cRuntimeError(\"Cannot open LE-GRA channelmodel diag output: %s\", outputPath);\n        output << \"timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm,frame_type,direction\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw cRuntimeError(\"LEGRA_RADIO_DIAG_RAW_CSV changed during the simulation\");\n    }\n\n    if (sinr.empty()) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << -1 << ','\n               << \"nan,nan,nan,\"\n               << static_cast<int>(frameType) << ','\n               << static_cast<int>(dir) << '\\n';\n        output.flush();\n        return;\n    }\n\n    double meanSinr = 0.0;\n    for (size_t i = 0; i < sinr.size(); ++i)\n        meanSinr += sinr[i];\n    meanSinr /= sinr.size();\n\n    for (size_t band = 0; band < sinr.size(); ++band) {\n        output << timestamp.dbl() << ','\n               << ueId << ','\n               << gnbId << ','\n               << band << ','\n               << sinr[band] << ','\n               << meanSinr << ','\n               << rsrp[band] << ','\n               << static_cast<int>(frameType) << ','\n               << static_cast<int>(dir) << '\\n';\n    }\n    output.flush();\n}\n\n} // namespace\n\n"""
if "recordLeGraChannelModelDiag" not in text:
    if namespace_anchor not in text:
        raise SystemExit("P3_5_SIMU5G_DIAG_NAMESPACE_ANCHOR_MISSING")
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
        raise SystemExit("P3_5_SIMU5G_DIAG_RSRP_COPY_ANCHOR_MISSING")
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
        raise SystemExit("P3_5_SIMU5G_DIAG_RECORD_ANCHOR_MISSING")
    text = text.replace(return_anchor, return_replacement, 1)

path.write_text(text)
PY
  echo P3_5_SIMU5G_DIAG_PATCH_APPLIED
fi

if grep -q 'recordLeGraSumoMobility' "$veins_root/subprojects/veins_inet/src/veins_inet/VeinsInetMobility.cc"; then
  echo P3_5_VEINS_PATCH_ALREADY_APPLIED
else
  python3 - "$veins_root/subprojects/veins_inet/src/veins_inet/VeinsInetMobility.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old_include = '#include "veins_inet/VeinsInetMobility.h"\n'
new_include = '#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n\n#include "veins_inet/VeinsInetMobility.h"\n'
if old_include not in text:
    raise SystemExit("P3_5_VEINS_INCLUDE_ANCHOR_MISSING")
text = text.replace(old_include, new_include, 1)

anchor = 'using namespace inet::units::values;\n\n'
helper = """using namespace inet::units::values;\n\nnamespace {\n\nvoid recordLeGraSumoMobility(omnetpp::simtime_t timestamp,\n        const std::string& externalId, const char *modulePath,\n        const inet::Coord& position, double speed)\n{\n    const char *outputPath = std::getenv(\"LEGRA_MOBILITY_RAW_CSV\");\n    if (outputPath == nullptr || outputPath[0] == '\\0')\n        return;\n    if (externalId.find(',') != std::string::npos)\n        throw omnetpp::cRuntimeError(\"SUMO vehicle ID contains a comma: %s\",\n                externalId.c_str());\n\n    static std::ofstream output;\n    static std::string activePath;\n    if (!output.is_open()) {\n        activePath = outputPath;\n        output.open(activePath, std::ios::out | std::ios::trunc);\n        if (!output)\n            throw omnetpp::cRuntimeError(\n                    \"Cannot open LE-GRA mobility recorder output: %s\",\n                    outputPath);\n        output << \"timestamp_s,sumo_vehicle_id,ue_module_path,x_m,y_m,speed_mps\\n\";\n        output << std::setprecision(15);\n    }\n    else if (activePath != outputPath) {\n        throw omnetpp::cRuntimeError(\n                \"LEGRA_MOBILITY_RAW_CSV changed during the simulation\");\n    }\n\n    output << timestamp.dbl() << ','\n           << externalId << ','\n           << modulePath << ','\n           << position.x << ','\n           << position.y << ','\n           << speed << '\\n';\n    output.flush();\n}\n\n} // namespace\n\n"""
if anchor not in text:
    raise SystemExit("P3_5_VEINS_NAMESPACE_ANCHOR_MISSING")
text = text.replace(anchor, helper, 1)

old_block = """    lastPosition = position;\n    lastVelocity = inet::Coord(cos(angle), -sin(angle)) * speed;\n    lastOrientation = inet::Quaternion(inet::EulerAngles(rad(-angle), rad(0.0), rad(0.0)));\n\n    // Update display string to show node is getting updates\n"""
new_block = """    lastPosition = position;\n    lastVelocity = inet::Coord(cos(angle), -sin(angle)) * speed;\n    lastOrientation = inet::Quaternion(inet::EulerAngles(rad(-angle), rad(0.0), rad(0.0)));\n\n    recordLeGraSumoMobility(simTime(), external_id,\n            getParentModule()->getFullPath().c_str(), position, speed);\n\n    // Update display string to show node is getting updates\n"""
if old_block not in text:
    raise SystemExit("P3_5_VEINS_POSITION_BLOCK_ANCHOR_MISSING")
text = text.replace(old_block, new_block, 1)

path.write_text(text)
PY
  echo P3_5_VEINS_PATCH_APPLIED
fi

python3 - "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc" \
          "$veins_root/subprojects/veins_inet/src/veins_inet/VeinsInetMobility.cc" <<'PY'
from pathlib import Path
import sys

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    text = path.read_text()
    text = text.replace('total_bands,wideband_cqi,itbs\\\\n";', 'total_bands,wideband_cqi,itbs\\n";')
    text = text.replace('total_bands\\\\n";', 'total_bands\\n";')
    text = text.replace('speed_mps\\\\n";', 'speed_mps\\n";')
    path.write_text(text)
PY
echo P3_5_RECORDER_HEADER_NORMALIZED

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

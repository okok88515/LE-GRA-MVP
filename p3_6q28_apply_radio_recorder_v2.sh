#!/usr/bin/env bash
set -euo pipefail

workspace=/home/opp_env/p3_5_workspace
simu5g_root="$workspace/simu5g-1.4.3"

source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh

python3 - "$simu5g_root/src/simu5g/stack/mac/LteMacEnb.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

replacements = [
    (
        """void recordLeGraDlBandState(simtime_t timestamp, MacNodeId ueId,
        MacNodeId gnbId, const char *ueModulePath, GHz carrierFrequency,
        const CqiVector& bandCqi, LteAmc *amc)
""",
        """void recordLeGraDlBandState(simtime_t timestamp, MacNodeId ueId,
        MacNodeId gnbId, const char *ueModulePath, GHz carrierFrequency,
        const LteFeedback& feedback, const CqiVector& bandCqi, LteAmc *amc)
""",
    ),
    (
        '        output << "timestamp_s,ue_node_id,gnb_node_id,ue_module_path,band_index,cqi,tbs_bits_per_slot,total_bands\\n";\n',
        '        output << "timestamp_s,ue_node_id,gnb_node_id,ue_module_path,band_index,cqi,tbs_bits_per_slot,total_bands,wideband_cqi,itbs\\n";\n',
    ),
    (
        """    for (Band band = 0; band < bandCqi.size(); ++band) {
        Cqi cqi = bandCqi[band];
        unsigned int bitsPerSlot = amc->computeBitsPerRbBackground(
                cqi, DL, carrierFrequency);
        output << timestamp.dbl() << ','
               << ueId << ','
               << gnbId << ','
               << ueModulePath << ','
               << band << ','
               << cqi << ','
               << bitsPerSlot << ','
               << bandCqi.size() << '\\n';
    }
""",
        """    double wbCqiValue = 0.0;
    if (feedback.hasWbCqi()) {
        auto wb = feedback.getWbCqi();
        if (!wb.empty())
            wbCqiValue = wb.front();
    }
    else if (!bandCqi.empty()) {
        for (const auto& value : bandCqi)
            wbCqiValue += value;
        wbCqiValue /= bandCqi.size();
    }

    for (Band band = 0; band < bandCqi.size(); ++band) {
        Cqi cqi = bandCqi[band];
        unsigned int bitsPerSlot = amc->computeBitsPerRbBackground(
                cqi, DL, carrierFrequency);
        unsigned int itbs = amc->getItbsPerCqi(cqi, DL);
        output << timestamp.dbl() << ','
               << ueId << ','
               << gnbId << ','
               << ueModulePath << ','
               << band << ','
               << cqi << ','
               << bitsPerSlot << ','
               << bandCqi.size() << ','
               << wbCqiValue << ','
               << itbs << '\\n';
    }
""",
    ),
    (
        """                    recordLeGraDlBandState(simTime(), srcNodeId, nodeId_,
                            ueModulePath.c_str(), lteInfo->getCarrierFrequency(),
                            codewords.front(), amc_);
""",
        """                    recordLeGraDlBandState(simTime(), srcNodeId, nodeId_,
                            ueModulePath.c_str(), lteInfo->getCarrierFrequency(),
                            fb, codewords.front(), amc_);
""",
    ),
]

for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)

if "wideband_cqi,itbs" not in text:
    raise SystemExit("P3_6Q28_UPGRADE_FAILED")

path.write_text(text)
PY

opp_env run --workspace "$workspace" \
  simu5g-1.4.3 inet-4.6.0 omnetpp-6.3.0 \
  --no-isolated -c '
    cd "$SIMU5G_ROOT/src"
    make MODE=release -j2
    test -s "$SIMU5G_ROOT/src/libsimu5g.so"
    echo P3_6Q28_RADIO_RECORDER_V2_OK
  '

"""Turn validated tool calls into an Opentrons Python protocol (API v2).

The output is plain Python that can be run with `opentrons_simulate protocol.py`
(no robot needed) or, after review, uploaded to the Opentrons app for a Flex robot.
"""

from .deck import REAGENTS, pipette_for
from .validator import _norm_wells

HEADER = '''from opentrons import protocol_api

metadata = {
    "protocolName": "LLM-generated protocol (labbot demo)",
    "author": "labbot",
}

requirements = {"robotType": "Flex", "apiLevel": "2.19"}


def run(protocol: protocol_api.ProtocolContext):
    plate = protocol.load_labware("corning_96_wellplate_360ul_flat", "B1")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "B2")
    tips50 = protocol.load_labware("opentrons_flex_96_tiprack_50ul", "C1")
    tips1000 = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "C2")
    p50 = protocol.load_instrument("flex_1channel_50", "left", tip_racks=[tips50])
    p1000 = protocol.load_instrument("flex_1channel_1000", "right", tip_racks=[tips1000])
    pipettes = {"p1000": p1000, "p50": p50}
    trash = protocol.load_trash_bin("A3")  # Flex needs a trash bin declared for used tips
    labware = {"plate": plate, "reservoir": reservoir}
'''


def generate_protocol(calls):
    """Return protocol source for already-validated calls."""
    lines = [HEADER]
    for n, call in enumerate(calls, start=1):
        tool = call["tool"]
        lines.append(f"    # step {n}: {tool}")
        if tool == "transfer":
            sw, dw = _norm_wells(call["source_wells"]), _norm_wells(call["dest_wells"])
            pairs = list(zip(sw, dw)) if len(sw) == len(dw) else [(sw[0], d) for d in dw]
            vol = call["volume_ul"]
            pip = pipette_for(vol)
            for s, d in pairs:
                lines.append(
                    f'    pipettes["{pip}"].transfer({vol!r}, labware["{call["source_labware"]}"]["{s}"], '
                    f'labware["{call["dest_labware"]}"]["{d}"], new_tip="always")'
                )
        elif tool == "add_reagent":
            wells = _norm_wells(call["dest_wells"])
            vol = call["volume_ul"]
            pip = pipette_for(vol)
            dests = ", ".join(f'plate["{w}"]' for w in wells)
            lines.append(
                f'    pipettes["{pip}"].transfer({vol!r}, reservoir["{REAGENTS[call["reagent"]]}"], '
                f'[{dests}], new_tip="once")'
            )
        elif tool == "mix":
            vol = call["volume_ul"]
            pip = pipette_for(vol)
            for w in _norm_wells(call["wells"]):
                lines.append(f'    pipettes["{pip}"].pick_up_tip()')
                lines.append(f'    pipettes["{pip}"].mix({call["repetitions"]}, {vol!r}, plate["{w}"])')
                lines.append(f'    pipettes["{pip}"].drop_tip()')
        else:
            raise ValueError(f"cannot generate code for tool '{tool}'")
    return "\n".join(lines) + "\n"

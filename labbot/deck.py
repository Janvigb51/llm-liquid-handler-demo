"""Fixed virtual deck used by the demo.

Opentrons Flex deck (slots A1-D3):
Slot B1: Corning 96-well plate (360 uL wells) - column 1 starts with 200 uL of sample
Slot B2: NEST 12-well reservoir - A1 = buffer, A2 = diluent (15 mL each)
Slot C1: 50 uL tip rack (Flex 1-channel 50 uL pipette, left mount, 1-50 uL)
Slot C2: 1000 uL tip rack (Flex 1-channel 1000 uL pipette, right mount, 5-1000 uL)
Slot A3: trash bin (used tips are dropped here)

Keeping the deck fixed keeps the problem small: the interesting question is how
reliably an LLM turns natural language into valid, correct liquid-handling steps.
"""

ROWS = "ABCDEFGH"
PLATE_WELLS = [f"{r}{c}" for c in range(1, 13) for r in ROWS]
RESERVOIR_WELLS = [f"A{c}" for c in range(1, 13)]

LABWARE_WELLS = {"plate": set(PLATE_WELLS), "reservoir": set(RESERVOIR_WELLS)}

REAGENTS = {"buffer": "A1", "diluent": "A2"}

PLATE_MAX_UL = 360.0
RESERVOIR_INITIAL_UL = 15000.0
SAMPLE_UL = 200.0  # loaded into plate column 1 (A1-H1) before the run

# name -> (min_uL, max_uL)
PIPETTES = {"p50": (1.0, 50.0), "p1000": (5.0, 1000.0)}
TIPS_PER_RACK = 96

MIN_VOLUME_UL = 1.0
MAX_VOLUME_UL = 300.0


def initial_state():
    """Liquid volume (uL) per (labware, well)."""
    state = {("plate", w): 0.0 for w in PLATE_WELLS}
    for r in ROWS:
        state[("plate", f"{r}1")] = SAMPLE_UL
    for w in RESERVOIR_WELLS:
        state[("reservoir", w)] = 0.0
    for well in REAGENTS.values():
        state[("reservoir", well)] = RESERVOIR_INITIAL_UL
    return state


def pipette_for(volume_ul):
    """p50 for volumes up to 50 uL, otherwise p1000."""
    return "p50" if volume_ul <= 50.0 else "p1000"

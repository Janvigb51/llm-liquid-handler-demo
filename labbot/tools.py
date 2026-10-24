"""Tool definitions exposed to the LLM (Anthropic tool-use format).

The LLM never writes robot code. It can only call these three functions, and
every call is checked by validator.py before a protocol is generated.
"""

SYSTEM_PROMPT = """You control a liquid-handling robot by calling tools.

Deck:
- 'plate': 96-well plate, wells A1-H12 (rows A-H, columns 1-12), 360 uL max per well.
  Column 1 (A1-H1) already contains 200 uL of sample per well; all other wells are empty.
- 'reservoir': 12-well reservoir. Well A1 holds 'buffer', well A2 holds 'diluent' (plenty of both).

Rules:
- Volumes are in microlitres (uL), between 1 and 300 per transfer.
- Expand ranges such as 'column 3' or 'row B' into explicit well lists (e.g. column 3 = A3..H3).
- Use only the tools provided. Do not invent labware, reagents or wells.
- Make every tool call needed for the whole request in this one reply, in the order the steps happen. Later steps can assume earlier steps are done; do not wait for results.
- If the request is ambiguous, missing a volume or location, or cannot be done on this deck,
  do NOT guess: reply in plain text explaining what is missing and make no tool calls.
"""

WELL_LIST = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "description": "Explicit well names such as ['A1','B1']",
}

TOOLS = [
    {
        "name": "transfer",
        "description": (
            "Transfer liquid between wells using a fresh tip for every pair. "
            "source_wells and dest_wells must be the same length (paired in order) "
            "or source_wells must have exactly one well (one source to many destinations)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_labware": {"type": "string", "enum": ["plate", "reservoir"]},
                "source_wells": WELL_LIST,
                "dest_labware": {"type": "string", "enum": ["plate", "reservoir"]},
                "dest_wells": WELL_LIST,
                "volume_ul": {"type": "number", "description": "Volume per transfer in uL"},
            },
            "required": ["source_labware", "source_wells", "dest_labware", "dest_wells", "volume_ul"],
        },
    },
    {
        "name": "add_reagent",
        "description": "Dispense a reagent ('buffer' or 'diluent') from the reservoir into plate wells, one tip per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reagent": {"type": "string", "enum": ["buffer", "diluent"]},
                "dest_wells": WELL_LIST,
                "volume_ul": {"type": "number", "description": "Volume per well in uL"},
            },
            "required": ["reagent", "dest_wells", "volume_ul"],
        },
    },
    {
        "name": "mix",
        "description": "Mix the liquid in plate wells by repeated aspirate/dispense, using a fresh tip per well.",
        "input_schema": {
            "type": "object",
            "properties": {
                "wells": WELL_LIST,
                "repetitions": {"type": "integer", "description": "Number of mix cycles (1-20)"},
                "volume_ul": {"type": "number", "description": "Mix volume in uL"},
            },
            "required": ["wells", "repetitions", "volume_ul"],
        },
    },
]

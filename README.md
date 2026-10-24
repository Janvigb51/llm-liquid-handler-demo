# labbot: natural language to a simulated liquid-handling protocol

A small proof of concept that connects a large language model (LLM) to a laboratory liquid handler
(an Opentrons Flex robot, **simulated only**) and measures how reliable the approach is.

```
"Add 50 uL of diluent to every well in column 2"
        |
        v
LLM with tool calling  ->  [{"tool": "add_reagent", "reagent": "diluent", "dest_wells": [A2..H2], "volume_ul": 50}]
        |
        v
Validator (plain Python, replays the steps on a virtual deck)
        |  rejects: unknown wells, bad volumes, empty sources, plate overflow, out of tips ...
        v
Protocol generator  ->  Opentrons Python protocol (API v2)
        |
        v
Opentrons simulator  (opentrons_simulate)
```

## Design choices

- **The LLM never writes robot code.** It can only call three tools (`transfer`, `add_reagent`, `mix`),
  so its output is structured data that can be checked. Free-form code generation would be harder to verify.
- **A deterministic validator sits between the LLM and the robot.** The Opentrons simulator checks that a
  protocol *runs*, but it does not know how much liquid is in each well. The validator tracks volumes
  per well, so it catches things the simulator cannot (pipetting from an empty well, overfilling a well).
- **The deck is fixed and small** (one 96-well plate, one reservoir with buffer and diluent, two tip racks),
  which keeps the focus on the language-to-protocol step. See `labbot/deck.py`.
- **The model is told to decline** ambiguous or impossible requests instead of guessing. Whether it does
  is part of what the evaluation measures.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # needed for the LLM backend only
```

The model defaults to `claude-sonnet-5-5` and can be changed with `LABBOT_MODEL`
(`labbot/llm.py`).

## Run it

```bash
# unit tests (no API key, no opentrons needed)
python -m unittest discover -s tests

# harness sanity check: replays hand-written reference calls, does NOT test the LLM
python run_eval.py --backend reference

# real evaluation: 26 instructions through the LLM (+ the Opentrons simulator)
python run_eval.py --backend llm --simulate
```

Results are written to `results/` (full records in JSON, summary in Markdown).

## Evaluation

`data/instructions.json` has 26 instructions:

- **16 executable requests** from single transfers to a 4-step serial dilution, including column and row
  operations, small (50 uL pipette) and large (1000 uL pipette) volumes, and cross-labware moves. Each has a hand-written
  reference solution. *Accuracy* means the final virtual deck state (volume in every well) matches the
  reference, so different valid ways of reaching the same outcome all count as correct.
- **10 requests that should not run**: ambiguous or incomplete instructions, non-existent wells,
  volumes outside the pipette range, pipetting from an empty well, overflowing a well, an unknown reagent,
  and an action the robot cannot do (heating). Success means the model made no tool calls, or the validator
  blocked them. Calls that pass validation for these requests count as failures.

### Results

> Fill in after running `python run_eval.py --backend llm --simulate`. Report the model name and date.

| Metric | Result |
|---|---|
| Executable requests: calls pass validation | _/16 |
| Executable requests: correct final deck state | _/16 |
| Executable requests: simulated without errors | _/16 |
| Impossible/ambiguous requests handled safely | _/10 |
| - of which blocked only by the validator | _ |

Observed failure modes and what they suggest: _(write 3-5 sentences after looking at `results/results_llm.json`)_

## Limitations

- **Simulation only.** Nothing here has been run on a physical robot. Real deployment would need
  calibrated labware definitions, tip and liquid-handling parameters (aspirate/dispense speeds,
  liquid classes), error recovery, and human review of every generated protocol.
- **Tiny fixed deck and three operations.** Real laboratory workflows involve many more instruments,
  plate formats and timing/incubation steps.
- **Small test set (26 instructions).** Enough to show failure modes, not enough for statistical claims.
  LLM output varies between runs; re-run the evaluation several times to see the spread.
- **The validator encodes the rules I thought of.** Anything it does not check can still slip through.
- **Volumes are idealised.** No evaporation, dead volume or pipetting error is modelled.

## Ideas for extending it

- Add more tools (incubate, shake, centrifuge) and labware, and let the LLM choose the deck layout.
- Ask the LLM to explain its plan back to the user and require confirmation before generating a protocol.
- Compare several models or prompts on the same test set.
- Connect to a real instrument API behind a human-approval step.

## Layout

```
labbot/deck.py        fixed virtual deck, pipette limits
labbot/tools.py       system prompt and tool schemas given to the LLM
labbot/llm.py         natural language -> tool calls (Anthropic tool use)
labbot/validator.py   replays calls on the virtual deck and reports problems
labbot/generator.py   validated calls -> Opentrons Python protocol
labbot/simulate.py    runs a protocol in the Opentrons simulator
run_eval.py           evaluation harness
data/instructions.json  26 test instructions with reference solutions
tests/                unit tests
```

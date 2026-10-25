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
        |  (optional: send its errors back to the model for one retry)
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
export ANTHROPIC_API_KEY=...        # needed for the LLM backend only; never commit it
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

# harder set (15 instructions), another model, and the retry option
LABBOT_MODEL=claude-haiku-5-5 python run_eval.py --backend llm --simulate \
    --cases data/instructions_hard.json --retry --out results_example
```

Each run writes full records (`results_llm.json`) and a summary (`summary_llm.md`) to its output folder.

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

`data/instructions_hard.json` has 15 harder instructions (8 executable, 7 that should be refused): relative
volumes, "the same for column 7", mL instead of uL, the 50/51 uL pipette boundary, every other well,
overflow that only appears over several steps, a well that runs dry, a contradiction, "same as before"
with no earlier context, a partly unsupported request, and a well range that runs off the plate.

### Results

Models: `claude-sonnet-5-5` and `claude-haiku-5-5`, October 2026. Everything is simulated. "Safe" means the
model declined or the validator blocked the request. All executable requests that passed validation also
ran in the Opentrons simulator without errors.

**Original set (26 instructions)**

| Setup | Runs | Executable: correct | Bad requests: safe | Blocked only by validator |
|---|---|---|---|---|
| Sonnet, first prompt | 1 | 15/16 | 10/10 | 0 |
| Sonnet, prompt + "make all tool calls in one reply" | 3 | 16/16 in each run | 10/10 in each run | 2 per run (r05, r10) |
| Haiku, same prompt | 1 | 16/16 | 10/10 | 0 |

**Harder set (15 instructions)**

| Setup | Runs | Executable: correct | Bad requests: safe | Blocked only by validator |
|---|---|---|---|---|
| Sonnet | 3 | 8/8 in each run | 7/7 in each run | 0 |
| Haiku | 3 | 8/8 in each run | 7/7 in each run | 1, 2, 2 (h09 in 3/3 runs, h10 in 2/3) |
| Haiku + retry with validator feedback | 3 | 8/8 in each run | 7/7 in each run | 0 (first attempt rejected and retried: 1, 1, 2) |

### What I found

1. **The first failure was a prompt problem, not a model problem.** In the first run the model made only the
   first tool call of a multi-step request and waited for a result. One added line in the system prompt
   ("make every tool call needed for the whole request in this one reply") fixed it in all later runs.
2. **That fix had a side effect.** The model became more willing to act, and attempted two requests that
   cannot work physically (r05, r10). The validator blocked them in all three runs. Fixing one failure
   can expose another, which is why the checks sit outside the model.
3. **The failures that remain are state-tracking failures.** The smaller model never missed a visible problem
   (wrong unit, contradiction, missing context, unsupported action, non-existent well). It missed requests
   where every step looks fine alone and only the running volume in a well is the problem: three 100 uL
   additions to a well that already holds 200 uL (h09), and three 100 uL transfers out of it (h10). The
   larger model reasoned through both correctly in every run.
4. **The validator is a backstop, not the main safeguard, with a strong model.** On the harder set the larger
   model needed it zero times. With the smaller model it caught 1-2 cases per run.
5. **Sending the validator's errors back for one retry worked on every case it was tried on.** In 4 of 4
   rejected first attempts the model declined correctly after seeing the error, and explained the
   arithmetic. If the model had instead quietly shortened the request, the harness would count that as
   a failure; that did not happen.

### How far to trust this

The test sets are small and written by me, each setup was run 1-3 times, and the retry result is 4 cases
from one model on one test set. These are observations about failure modes, not statistics, and runs are
not paired (the with-retry and without-retry numbers come from separate runs). The first-prompt baseline
is a single run.

## Limitations

- **Simulation only.** Nothing here has been run on a physical robot. Real deployment would need
  calibrated labware definitions, tip and liquid-handling parameters (aspirate/dispense speeds,
  liquid classes), error recovery, and human review of every generated protocol.
- **Tiny fixed deck and three operations.** Real laboratory workflows involve many more instruments,
  plate formats and timing/incubation steps.
- **Small test sets and few repeats.** Enough to show failure modes, not enough for statistical claims.
  LLM output varies between runs.
- **The validator encodes the rules I thought of.** Anything it does not check can still slip through.
- **Error messages for one-to-many transfers** report the step but not which destination well failed.
- **Volumes are idealised.** No evaporation, dead volume or pipetting error is modelled.

## Ideas for extending it

- Add more tools (incubate, shake, centrifuge) and labware, and let the LLM choose the deck layout.
- Ask the LLM to explain its plan back to the user and require confirmation before generating a protocol.
- Test the retry on the original set and on more models, with more repeats.
- Write harder multi-step cases where the validator, not the model, has to carry the load.
- Connect to a real instrument API behind a human-approval step.

## Layout

```
labbot/deck.py        fixed virtual deck, pipette limits
labbot/tools.py       system prompt and tool schemas given to the LLM
labbot/llm.py         natural language -> tool calls (Anthropic tool use), retry with feedback
labbot/validator.py   replays calls on the virtual deck and reports problems
labbot/generator.py   validated calls -> Opentrons Python protocol
labbot/simulate.py    runs a protocol in the Opentrons simulator
run_eval.py           evaluation harness
data/                 test instructions with reference solutions (original and harder set)
results*/             raw records and summaries for every run reported above
FINDINGS.md           short written summary of the experiments
tests/                unit tests
```

# Findings

All results are from simulation (Opentrons simulator), not a physical robot. Models: claude-sonnet-5-5 and claude-haiku-5-5, October 2026. Test sets are small (26 and 15 instructions), and each configuration was run 1-3 times, so treat these as observations, not statistics.

## Original set (26 instructions: 16 executable, 10 that should be refused)
- Baseline prompt, Sonnet, 1 run: 15/16 executable correct; all 10 bad requests declined. One failure: the model made only the first tool call of a multi-step request and stopped.
- After adding one prompt rule (make every tool call for the whole request in one reply), Sonnet, 3 runs: 16/16 correct each time. The model now also attempted two requests that cannot work physically (r05, r10), and the validator blocked both in all 3 runs.
- Haiku, 1 run: 16/16 correct, 10/10 declined.

## Harder set (15 instructions: 8 executable, 7 that should be refused)
- Sonnet, 3 runs: identical each time. 8/8 correct, 7/7 declined, validator blocked nothing. Declines gave correct, specific reasons (arithmetic, wrong units, contradiction, missing context, unsupported action).
- Haiku, 3 runs: 8/8 correct each time. It declined 5-6 of 7; the validator blocked the rest: h09 (three 100 uL additions to a well already holding 200 uL) in 3/3 runs and h10 (three 100 uL transfers out of that well) in 2/3 runs.

## Retry with validator feedback
- When the validator rejected the first attempt, its error text was sent back to the model once. Haiku, hard set, 3 runs: first attempts rejected 1, 1, 2 times; all 4 ended as a correct decline on the second try.

## What this suggests
- Failures cluster in multi-step requests where each step is fine alone but the running volume in a well is not.
- A deterministic validator that tracks per-well volume catches these; the simulator alone does not know liquid volumes.
- Feeding the validator's errors back to the model fixed every case it was tried on (4 of 4, small sample).

## Limitations
- Simulation only; small test sets; few repeats; one fixed deck and three tools.
- The validator only checks the rules I thought of.
- Error messages for one-to-many transfers do not say which destination failed.

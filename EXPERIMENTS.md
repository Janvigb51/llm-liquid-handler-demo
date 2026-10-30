# Experiment log

Chronological record of evaluation runs. Models: claude-sonnet-5-5 and claude-haiku-5-5.
Everything is simulated. Test sets: data/instructions.json (26: 16 executable, 10 to refuse)
and data/instructions_hard.json (15: 8 executable, 7 to refuse).

## 2026-10-24 - Reference run (harness check)
- Replays hand-written reference calls through the validator, generator and simulator.
- 16/16 executable correct, 10/10 safe. This tests the harness, not the LLM.

## 2026-10-24 - Sonnet, first prompt, original set (1 run)
- 15/16 executable correct, 10/10 safe, 0 blocked only by the validator.
- Failure: v13 (4-step serial dilution). The model made only the first tool call and stopped.

## 2026-10-24 - Sonnet, prompt changed, original set (3 runs)
- Added a line to the system prompt: make every tool call needed for the whole request in one reply.
- 16/16 executable correct and 10/10 safe in each run.
- Validator blocked 2 cases per run (r05, r10): the model attempted requests that cannot work
  physically (empty source well, volume more than the well holds).

## 2026-10-24 - Sonnet, hard set (3 runs)
- 8/8 executable correct and 7/7 safe in each run; validator blocked 0.

## 2026-10-25 - Haiku, same prompt, original and hard sets
- Original set (1 run): 16/16 executable correct, 10/10 safe, 0 blocked by the validator.
- Hard set (3 runs): 8/8 executable correct and 7/7 safe in each run.
- Validator blocked 1, 2, 2 cases per run: h09 in 3/3 runs, h10 in 2/3.
- Both are state-tracking mistakes: h09 adds 100 uL three times to a well that already holds 200 uL
  (max 360); h10 takes 100 uL three times from a well that holds 200 uL.

## 2026-10-25 - Added --retry option (validator errors sent back to the model once)
- Implemented in the harness; normal runs are unchanged without the flag.

## 2026-10-25 - Haiku with --retry, hard set (3 runs)
- 8/8 executable correct and 7/7 safe in each run; validator blocked 0.
- First attempt rejected and retried: 1, 1, 2. All 4 ended as a correct decline on the second try.
- Caveat: 4 cases, one model, one test set. Retry and no-retry runs are separate samples.

## 2026-10-27 - Haiku with --retry, original set (3 runs)
- Executable correct: 16/16, 16/16, 15/16. Bad requests safe: 10/10 in each run.
- Validator blocked 0 in the final results. First attempt retried: 0, 1, 0.
- The retried case was r05 (run 2): the first attempt took 50 uL from empty well C4 and was
  rejected; after seeing the error the model declined and explained that only column 1 holds sample.
- Run 3, v13: the model made only the first tool call (add diluent to A2-A4) and none of the
  transfer/mix steps, with no text reply. The partial plan passed the validator and simulated
  without errors, but the final well volumes did not match the reference.
- Observation: v13 is the same case that stopped after the first step in the first Sonnet run
  (2026-10-24), before the prompt change. The validator checks each step is possible, not that the
  plan is complete, so it cannot catch this. Retry only triggers on a validator rejection.

## 2026-10-30 - Haiku, original set, no retry (3 more runs)
- Executable correct: 15/16, 13/16, 16/16. Bad requests safe: 10/10 in each run. Validator blocked 0.
- Run 1: v13 stopped after 1 tool call of 6.
- Run 2: v13 stopped after 2 of 6 calls; v08 made only the first of two steps (the transfer, not
  the diluent addition); v16 ("Mix wells A1 and B1...") got no tool calls: the model said B1 was
  empty and offered options, although B1 is in column 1, which holds sample.
- Run 3: 16/16.
- v13 over the 7 Haiku runs on the original set so far: stopped early in 3 (1, 1 and 2 calls of 6),
  correct in 4. Sonnet got v13 right in every run after the prompt change.
- Earlier Haiku baseline (1 run, 16/16) was not representative; across 4 plain runs the score
  ranged 13/16 to 16/16.

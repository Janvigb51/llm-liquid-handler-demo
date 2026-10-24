"""Evaluate how reliably instructions become valid, correct protocols.

Backends:
  --backend llm        ask the LLM (needs ANTHROPIC_API_KEY and `pip install anthropic`)
  --backend reference  replay the hand-written reference calls (harness sanity check; scores
                       100% on 'execute' cases by construction and says nothing about the LLM)

Per case we record:
  parsed       the model returned tool calls (not just text)
  valid        the calls passed validator.validate()
  state_match  the final virtual deck matches the reference outcome (accuracy)
  simulated    the generated protocol ran in the Opentrons simulator (with --simulate)
For 'reject' cases (ambiguous / impossible requests) success means the model made no calls or
the validator blocked them. A model that makes calls the validator accepts has failed.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from labbot.deck import initial_state
from labbot.generator import generate_protocol
from labbot.simulate import simulate_protocol
from labbot.validator import validate

ROOT = Path(__file__).parent


def states_match(a, b, tol=1e-6):
    return all(abs(a[k] - b[k]) <= tol for k in a) and a.keys() == b.keys()


def reference_state(case):
    return validate(case["reference_calls"]).final_state if case["reference_calls"] else initial_state()


def run_case(case, backend, simulate, model):
    rec = {"id": case["id"], "category": case["category"], "expected": case["expected"],
           "instruction": case["instruction"]}
    if backend == "llm":
        from labbot.llm import instruction_to_calls
        calls, text = instruction_to_calls(case["instruction"], model=model)
    else:
        calls, text = case["reference_calls"], ""
    rec.update(calls=calls, llm_text=text, parsed=bool(calls))

    if not calls:
        rec.update(valid=None, errors=[], state_match=None, simulated=None)
        rec["success"] = case["expected"] == "reject"
        rec["outcome"] = "declined" if case["expected"] == "reject" else "no tool calls"
        return rec

    result = validate(calls)
    rec.update(valid=result.ok, errors=result.errors)
    if case["expected"] == "reject":
        rec.update(state_match=None, simulated=None)
        rec["success"] = not result.ok
        rec["outcome"] = "blocked by validator" if not result.ok else "ACCEPTED A REQUEST IT SHOULD REJECT"
        return rec

    if not result.ok:
        rec.update(state_match=False, simulated=None, success=False, outcome="invalid calls")
        return rec

    rec["state_match"] = states_match(result.final_state, reference_state(case))
    rec["simulated"] = None
    if simulate:
        status, output = simulate_protocol(generate_protocol(calls))
        rec["simulated"] = status
        if status != "ok":
            rec["simulator_output"] = output[-1500:]
    rec["success"] = rec["state_match"] and rec["simulated"] in (None, "ok")
    if rec["simulated"] not in (None, "ok"):
        rec["outcome"] = f"simulator problem ({rec['simulated']})"
    else:
        rec["outcome"] = "correct" if rec["success"] else "valid but wrong outcome"
    return rec


def summarise(records):
    execute = [r for r in records if r["expected"] == "execute"]
    reject = [r for r in records if r["expected"] == "reject"]
    pct = lambda n, d: f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"
    lines = [
        "| Metric | Result |",
        "|---|---|",
        f"| Executable requests: calls pass validation | {pct(sum(bool(r['valid']) for r in execute), len(execute))} |",
        f"| Executable requests: correct final deck state | {pct(sum(bool(r['state_match']) for r in execute), len(execute))} |",
        f"| Impossible/ambiguous requests handled safely | {pct(sum(r['success'] for r in reject), len(reject))} |",
        f"| - of which blocked only by the validator | {sum(r['outcome'] == 'blocked by validator' for r in reject)} |",
    ]
    if any(r["simulated"] for r in records):
        ran = [r for r in execute if r["simulated"]]
        lines.append(f"| Executable requests: simulated without errors | {pct(sum(r['simulated'] == 'ok' for r in ran), len(ran))} |")
    lines += ["", "Failure/outcome breakdown:", ""]
    for outcome, n in Counter(r["outcome"] for r in records).most_common():
        lines.append(f"- {outcome}: {n}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["llm", "reference"], default="llm")
    ap.add_argument("--simulate", action="store_true", help="also run the Opentrons simulator")
    ap.add_argument("--model", default=None)
    ap.add_argument("--cases", default=str(ROOT / "data" / "instructions.json"))
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()

    cases = json.loads(Path(args.cases).read_text())
    records = [run_case(c, args.backend, args.simulate, args.model) for c in cases]

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    (out / f"results_{args.backend}.json").write_text(json.dumps(records, indent=1, ensure_ascii=False))
    summary = summarise(records)
    (out / f"summary_{args.backend}.md").write_text(summary + "\n")
    print(summary)
    for r in records:
        if not r["success"]:
            print(f"\n[{r['id']}] {r['outcome']}: {r['instruction']}")
            for e in r["errors"]:
                print("   -", e)
            if r.get("simulator_output"):
                print("   simulator said:", r["simulator_output"][-600:])


if __name__ == "__main__":
    main()

"""Deterministic checks between the LLM's tool calls and the robot.

validate() replays the calls against a virtual copy of the deck and collects
every problem it finds: unknown wells, bad volumes, pipetting from empty wells,
overflowing the plate, running out of tips, and so on. Nothing the LLM says
reaches the protocol generator unless it passes.
"""

from dataclasses import dataclass, field

from .deck import (
    LABWARE_WELLS,
    MAX_VOLUME_UL,
    MIN_VOLUME_UL,
    PLATE_MAX_UL,
    REAGENTS,
    TIPS_PER_RACK,
    initial_state,
    pipette_for,
)

TOOL_NAMES = {"transfer", "add_reagent", "mix"}
EPS = 1e-9


@dataclass
class ValidationResult:
    ok: bool
    errors: list = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    tips_used: dict = field(default_factory=dict)


def _norm_wells(value):
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(w, str) for w in value):
        return None
    return [w.strip().upper() for w in value]


def _check_volume(v, label, errors, step):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        errors.append(f"step {step}: {label} must be a number")
        return False
    if not (MIN_VOLUME_UL <= v <= MAX_VOLUME_UL):
        errors.append(
            f"step {step}: {label} {v} uL is outside {MIN_VOLUME_UL:g}-{MAX_VOLUME_UL:g} uL"
        )
        return False
    return True


def _check_wells(labware, wells, label, errors, step):
    if labware not in LABWARE_WELLS:
        errors.append(f"step {step}: unknown labware '{labware}'")
        return False
    if wells is None:
        errors.append(f"step {step}: {label} must be a non-empty list of well names")
        return False
    bad = [w for w in wells if w not in LABWARE_WELLS[labware]]
    if bad:
        errors.append(f"step {step}: well(s) {bad} do not exist on '{labware}'")
        return False
    if len(set(wells)) != len(wells):
        errors.append(f"step {step}: {label} contains duplicate wells")
        return False
    return True


def validate(calls, state=None):
    """Validate a list of {'tool': name, ...args} dicts."""
    state = dict(initial_state() if state is None else state)
    errors = []
    tips = {"p50": 0, "p1000": 0}

    if not isinstance(calls, list) or not calls:
        return ValidationResult(False, ["no tool calls to run"], state, tips)

    def use_tips(pip, n, step):
        tips[pip] += n
        if tips[pip] > TIPS_PER_RACK:
            errors.append(f"step {step}: out of {pip} tips (limit {TIPS_PER_RACK} per rack)")

    for i, call in enumerate(calls, start=1):
        name = call.get("tool") if isinstance(call, dict) else None
        if name not in TOOL_NAMES:
            errors.append(f"step {i}: unknown tool '{name}'")
            continue

        if name == "transfer":
            sl, dl = call.get("source_labware"), call.get("dest_labware")
            sw, dw = _norm_wells(call.get("source_wells")), _norm_wells(call.get("dest_wells"))
            vol = call.get("volume_ul")
            ok = _check_volume(vol, "volume", errors, i)
            ok &= _check_wells(sl, sw, "source_wells", errors, i)
            ok &= _check_wells(dl, dw, "dest_wells", errors, i)
            if not ok:
                continue
            if len(sw) == len(dw):
                pairs = list(zip(sw, dw))
            elif len(sw) == 1:
                pairs = [(sw[0], d) for d in dw]
            else:
                errors.append(
                    f"step {i}: {len(sw)} source wells cannot be paired with {len(dw)} destination wells"
                )
                continue
            use_tips(pipette_for(vol), len(pairs), i)
            for s, d in pairs:
                if (sl, s) == (dl, d):
                    errors.append(f"step {i}: source and destination are both {sl} {s}")
                    continue
                if state[(sl, s)] + EPS < vol:
                    errors.append(
                        f"step {i}: {sl} {s} holds {state[(sl, s)]:g} uL, cannot take {vol:g} uL"
                    )
                    continue
                state[(sl, s)] -= vol
                state[(dl, d)] += vol
                if dl == "plate" and state[(dl, d)] > PLATE_MAX_UL + EPS:
                    errors.append(
                        f"step {i}: plate {d} would hold {state[(dl, d)]:g} uL (max {PLATE_MAX_UL:g})"
                    )

        elif name == "add_reagent":
            reagent = call.get("reagent")
            dw = _norm_wells(call.get("dest_wells"))
            vol = call.get("volume_ul")
            if reagent not in REAGENTS:
                errors.append(f"step {i}: unknown reagent '{reagent}' (use {sorted(REAGENTS)})")
                continue
            ok = _check_volume(vol, "volume", errors, i)
            ok &= _check_wells("plate", dw, "dest_wells", errors, i)
            if not ok:
                continue
            use_tips(pipette_for(vol), 1, i)
            src = ("reservoir", REAGENTS[reagent])
            for d in dw:
                if state[src] + EPS < vol:
                    errors.append(f"step {i}: reservoir ran out of {reagent}")
                    break
                state[src] -= vol
                state[("plate", d)] += vol
                if state[("plate", d)] > PLATE_MAX_UL + EPS:
                    errors.append(
                        f"step {i}: plate {d} would hold {state[('plate', d)]:g} uL (max {PLATE_MAX_UL:g})"
                    )

        else:  # mix
            wells = _norm_wells(call.get("wells"))
            reps, vol = call.get("repetitions"), call.get("volume_ul")
            ok = _check_volume(vol, "mix volume", errors, i)
            ok &= _check_wells("plate", wells, "wells", errors, i)
            if isinstance(reps, bool) or not isinstance(reps, int) or not (1 <= reps <= 20):
                errors.append(f"step {i}: repetitions must be an integer from 1 to 20")
                ok = False
            if not ok:
                continue
            use_tips(pipette_for(vol), len(wells), i)
            for w in wells:
                if state[("plate", w)] + EPS < vol:
                    errors.append(
                        f"step {i}: plate {w} holds {state[('plate', w)]:g} uL, cannot mix {vol:g} uL"
                    )

    return ValidationResult(not errors, errors, state, tips)

import ast
import json
import unittest
from pathlib import Path

from labbot.deck import initial_state
from labbot.generator import generate_protocol
from labbot.validator import validate

CASES = json.loads((Path(__file__).parent.parent / "data" / "instructions.json").read_text())


def T(sl, sw, dl, dw, v):
    return {"tool": "transfer", "source_labware": sl, "source_wells": sw,
            "dest_labware": dl, "dest_wells": dw, "volume_ul": v}


class ValidatorTests(unittest.TestCase):
    def test_simple_transfer_updates_volumes(self):
        r = validate([T("plate", ["A1"], "plate", ["A2"], 50)])
        self.assertTrue(r.ok, r.errors)
        self.assertEqual(r.final_state[("plate", "A1")], 150)
        self.assertEqual(r.final_state[("plate", "A2")], 50)

    def test_unknown_well(self):
        r = validate([{"tool": "add_reagent", "reagent": "buffer", "dest_wells": ["A13"], "volume_ul": 50}])
        self.assertFalse(r.ok)

    def test_empty_source(self):
        self.assertFalse(validate([T("plate", ["C4"], "plate", ["D4"], 50)]).ok)

    def test_plate_overflow(self):
        r = validate([{"tool": "add_reagent", "reagent": "buffer", "dest_wells": ["A1"], "volume_ul": 300}])
        self.assertFalse(r.ok)

    def test_volume_limits(self):
        self.assertFalse(validate([T("plate", ["A1"], "plate", ["B1"], 0.2)]).ok)
        self.assertFalse(validate([T("plate", ["A1"], "plate", ["B1"], 500)]).ok)

    def test_unknown_reagent_and_tool(self):
        self.assertFalse(validate([{"tool": "add_reagent", "reagent": "ethanol", "dest_wells": ["B2"], "volume_ul": 50}]).ok)
        self.assertFalse(validate([{"tool": "heat", "temperature": 37}]).ok)

    def test_pairing_rules(self):
        self.assertFalse(validate([T("plate", ["A1", "B1"], "plate", ["A2", "B2", "C2"], 10)]).ok)
        self.assertTrue(validate([T("plate", ["A1"], "plate", ["A2", "B2", "C2"], 10)]).ok)

    def test_empty_call_list(self):
        self.assertFalse(validate([]).ok)

    def test_tip_limit(self):
        # 97 single-tip transfers of 50 uL (p50) exceed the 96 tips in one rack
        wells = [f"{r}{c}" for c in range(2, 13) for r in "ABCDEFGH"]  # 88 wells
        calls = [T("reservoir", ["A1"], "plate", [w], 50) for w in wells]
        calls += [T("reservoir", ["A1"], "plate", [w], 10 + 40) for w in wells[:9]]  # 97 in total
        self.assertTrue(any("tips" in e for e in validate(calls).errors))
        self.assertFalse(any("tips" in e for e in validate(calls[:96]).errors))

    def test_does_not_mutate_initial_state(self):
        validate([T("plate", ["A1"], "plate", ["A2"], 50)])
        self.assertEqual(initial_state()[("plate", "A1")], 200)


class ReferenceCaseTests(unittest.TestCase):
    def test_reference_calls_are_valid_and_generate_parseable_code(self):
        for case in CASES:
            if case["expected"] != "execute":
                continue
            with self.subTest(case=case["id"]):
                r = validate(case["reference_calls"])
                self.assertTrue(r.ok, r.errors)
                code = generate_protocol(case["reference_calls"])
                ast.parse(code)
                self.assertIn("def run(protocol", code)

    def test_every_reject_case_has_no_reference_calls(self):
        for case in CASES:
            if case["expected"] == "reject":
                self.assertEqual(case["reference_calls"], [])

    def test_rejected_requests_fail_validation_when_attempted_literally(self):
        attempts = {
            "r03": [{"tool": "add_reagent", "reagent": "buffer", "dest_wells": ["A13"], "volume_ul": 50}],
            "r04": [T("plate", ["A1"], "plate", ["B1"], 500)],
            "r05": [T("plate", ["C4"], "plate", ["D4"], 50)],
            "r07": [{"tool": "add_reagent", "reagent": "buffer", "dest_wells": ["A1"], "volume_ul": 300}],
            "r09": [T("plate", ["A1"], "plate", ["B1"], 0.2)],
            "r10": [T("plate", ["A1"], "plate", ["B2", "C2", "D2"], 150)],
        }
        for cid, calls in attempts.items():
            with self.subTest(case=cid):
                self.assertFalse(validate(calls).ok)


class GeneratorTests(unittest.TestCase):
    def test_small_volume_uses_p50_and_large_uses_p1000(self):
        code = generate_protocol([T("plate", ["A1"], "plate", ["A2"], 10), T("plate", ["A1"], "plate", ["A3"], 100)])
        self.assertIn('pipettes["p50"].transfer(10', code)
        self.assertIn('pipettes["p1000"].transfer(100', code)
        self.assertIn('robotType": "Flex"', code)
        self.assertNotIn("OT-2", code)
        self.assertIn("load_trash_bin", code)


if __name__ == "__main__":
    unittest.main()

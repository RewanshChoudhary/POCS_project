"""Unit tests for Priority 3: Minimum-Cost Repair Engine."""

import unittest
from automaton import build_automaton
from grammar_inference import infer_grammar
from repair import RepairEngine, RepairOperation, repair_session


class TestPriority3RepairEngine(unittest.TestCase):
    def setUp(self):
        # A simple, clean grammar:
        # LOGIN -> (VIEW | EDIT)* -> LOGOUT
        self.train_seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
            ["LOGIN", "VIEW", "EDIT", "LOGOUT"],
            ["LOGIN", "LOGOUT"],
        ]
        self.grammar = infer_grammar(self.train_seqs, threshold=0.70, min_support=1)
        self.automaton = build_automaton(self.grammar)

    def test_already_valid_sequence(self):
        """Valid sequences return zero-cost repair immediately."""
        seq = ["LOGIN", "VIEW", "LOGOUT"]
        res = repair_session(seq, self.grammar)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 0)
        self.assertEqual(res.operations, [])
        self.assertEqual(res.repaired_sequence, seq)
        self.assertEqual(res.reason, "already_valid")

    def test_single_insertion(self):
        """Repair via single insertion when end event is missing."""
        seq = ["LOGIN", "VIEW"]
        # With default costs: append LOGOUT is 1 insertion
        engine = RepairEngine(
            self.grammar,
            costs={"insert": 1, "delete": 5, "substitute": 5},
            max_repair_cost=2,
        )
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 1)
        self.assertEqual(len(res.operations), 1)
        self.assertEqual(res.operations[0].operation, "insert")
        self.assertEqual(res.operations[0].new_token, "LOGOUT")
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_single_deletion(self):
        """Repair via single deletion when rogue event is inserted."""
        seq = ["LOGIN", "LOGOUT", "ROGUE"]
        engine = RepairEngine(
            self.grammar,
            costs={"insert": 5, "delete": 1, "substitute": 5},
            max_repair_cost=2,
        )
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 1)
        self.assertEqual(len(res.operations), 1)
        self.assertEqual(res.operations[0].operation, "delete")
        self.assertEqual(res.operations[0].old_token, "ROGUE")
        self.assertEqual(res.operations[0].index, 2)
        self.assertEqual(res.repaired_sequence, ["LOGIN", "LOGOUT"])
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_single_substitution(self):
        """Repair via single substitution."""
        seq = ["WRONG_START", "VIEW", "LOGOUT"]
        engine = RepairEngine(
            self.grammar,
            costs={"insert": 5, "delete": 5, "substitute": 1},
            max_repair_cost=2,
        )
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 1)
        self.assertEqual(len(res.operations), 1)
        self.assertEqual(res.operations[0].operation, "substitute")
        self.assertEqual(res.operations[0].new_token, "LOGIN")
        self.assertEqual(res.operations[0].index, 0)
        self.assertEqual(res.repaired_sequence, ["LOGIN", "VIEW", "LOGOUT"])
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_minimum_cost_selection(self):
        """Uniform-Cost Search strictly chooses the minimum-cost edit."""
        seq = ["VIEW", "LOGOUT"]
        # Can insert LOGIN (cost 10) or substitute VIEW with LOGIN (cost 2)
        engine = RepairEngine(
            self.grammar,
            costs={"insert": 10, "delete": 10, "substitute": 2},
            max_repair_cost=15,
        )
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 2)
        self.assertEqual(res.operations[0].operation, "substitute")

    def test_multiple_edit_repairs(self):
        """Repair requiring 2 edits when max_repair_cost=2."""
        # Missing LOGIN at start and missing LOGOUT at end
        seq = ["VIEW", "EDIT"]
        engine = RepairEngine(self.grammar, max_repair_cost=2)
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 2)
        self.assertEqual(len(res.operations), 2)
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_no_repair_within_budget(self):
        """Terminates cleanly when repair requires more than max_repair_cost."""
        # 3 errors away from valid
        seq = ["A", "B", "C", "D"]
        engine = RepairEngine(self.grammar, max_repair_cost=1)
        res = engine.repair(seq)
        self.assertFalse(res.found)
        self.assertIsNone(res.repaired_sequence)
        self.assertIn("No repair found within search budget", res.reason)

    def test_candidate_limits(self):
        """Search terminates cleanly when max_candidates is reached."""
        seq = ["A", "B", "C", "D"]
        engine = RepairEngine(self.grammar, max_candidates=5, max_repair_cost=5)
        res = engine.repair(seq)
        self.assertFalse(res.found)
        self.assertIn("Candidate search limit reached", res.reason)

    def test_empty_sequences(self):
        """Empty sequence can be repaired by inserting valid start and end events."""
        engine = RepairEngine(self.grammar, max_repair_cost=2)
        res = engine.repair([])
        self.assertTrue(res.found)
        self.assertEqual(res.total_cost, 2)
        self.assertEqual(res.repaired_sequence, ["LOGIN", "LOGOUT"])
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_unknown_events_in_input(self):
        """Unknown input events are cleanly processed and repaired."""
        seq = ["FOO", "BAR"]
        engine = RepairEngine(self.grammar, max_repair_cost=2)
        res = engine.repair(seq)
        self.assertTrue(res.found)
        self.assertTrue(self.automaton.accepts(res.repaired_sequence))

    def test_validation_of_returned_repairs(self):
        """Every returned repair must validate against the automaton."""
        test_inputs = [
            ["VIEW", "EDIT", "LOGOUT"],
            ["LOGIN", "VIEW"],
            ["LOGIN", "VIEW", "LOGOUT", "LOGOUT"],
            ["LOGIN", "LOGOUT", "VIEW"],
        ]
        engine = RepairEngine(self.grammar, max_repair_cost=2)
        for seq in test_inputs:
            res = engine.repair(seq)
            if res.found:
                self.assertTrue(
                    self.automaton.accepts(res.repaired_sequence),
                    f"Repaired sequence {res.repaired_sequence} did not validate!"
                )


if __name__ == "__main__":
    unittest.main()

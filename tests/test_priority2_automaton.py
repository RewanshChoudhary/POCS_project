"""Unit tests for Priority 2: Finite Automaton Representation."""

import unittest
from automaton import Automaton, START_STATE, build_automaton
from grammar_inference import infer_grammar
from validator import validate_session


class TestPriority2Automaton(unittest.TestCase):
    def setUp(self):
        # Deterministic training sequences for testing
        self.train_seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "EDIT", "LOGOUT"],
            ["LOGIN", "DELETE", "LOGOUT"],
            ["LOGIN", "DELETE", "LOGOUT"],
        ]
        self.grammar = infer_grammar(self.train_seqs, threshold=0.70, min_support=1)
        self.automaton = build_automaton(self.grammar)

    def test_automaton_construction(self):
        """Verify automaton fields, states, and alphabet initialized correctly."""
        self.assertEqual(self.automaton.initial_state, START_STATE)
        self.assertIn("LOGIN", self.automaton.alphabet)
        self.assertIn("LOGOUT", self.automaton.alphabet)
        self.assertIn("VIEW", self.automaton.alphabet)
        self.assertIn("DELETE", self.automaton.alphabet)

    def test_initial_state_handling(self):
        """Verify transitions out of initial state only accept allowed start events."""
        self.assertEqual(self.automaton.allowed_events(START_STATE), ["LOGIN"])
        next_s = self.automaton.next_state(START_STATE, "LOGIN")
        self.assertEqual(next_s, ("LOGIN",))

        # Invalid start event yields None
        self.assertIsNone(self.automaton.next_state(START_STATE, "VIEW"))
        self.assertIsNone(self.automaton.next_state(START_STATE, "LOGOUT"))

    def test_valid_training_sessions(self):
        """Verify all valid training sessions are accepted by automaton."""
        for seq in self.train_seqs:
            self.assertTrue(self.automaton.accepts(seq), f"Expected {seq} to be accepted")
            val = self.automaton.validate(seq)
            self.assertTrue(val.valid, f"Expected {seq} validation to be True")

    def test_terminal_states_and_events_after_logout(self):
        """Terminal states have no outgoing transitions and reject actions after LOGOUT."""
        # State ending in LOGOUT is terminal
        term_state = ("VIEW", "LOGOUT")
        self.assertTrue(self.automaton.is_terminal(term_state))
        self.assertTrue(self.automaton.is_accepting(term_state))
        self.assertEqual(self.automaton.allowed_events(term_state), [])
        self.assertIsNone(self.automaton.next_state(term_state, "VIEW"))

        # Test session with action after LOGOUT
        seq = ["LOGIN", "LOGOUT", "VIEW"]
        self.assertFalse(self.automaton.accepts(seq))
        val = self.automaton.validate(seq)
        self.assertFalse(val.valid)
        self.assertEqual(val.rule_type, "terminal")
        self.assertEqual(val.failure_index, 2)
        self.assertEqual(val.failure_token, "VIEW")

    def test_double_logout(self):
        """Verify double LOGOUT is rejected as terminal rule violation."""
        seq = ["LOGIN", "VIEW", "LOGOUT", "LOGOUT"]
        self.assertFalse(self.automaton.accepts(seq))
        val = self.automaton.validate(seq)
        self.assertFalse(val.valid)
        self.assertEqual(val.rule_type, "terminal")
        self.assertEqual(val.failure_index, 3)
        self.assertEqual(val.failure_token, "LOGOUT")

    def test_missing_login(self):
        """Verify missing LOGIN rejected at position 0."""
        seq = ["VIEW", "LOGOUT"]
        self.assertFalse(self.automaton.accepts(seq))
        val = self.automaton.validate(seq)
        self.assertFalse(val.valid)
        self.assertEqual(val.rule_type, "start")
        self.assertEqual(val.failure_index, 0)
        self.assertEqual(val.failure_token, "VIEW")

    def test_truncated_sessions(self):
        """Verify sessions not reaching an accepting state are rejected as truncated."""
        seq = ["LOGIN", "VIEW"]
        self.assertFalse(self.automaton.accepts(seq))
        val = self.automaton.validate(seq)
        self.assertFalse(val.valid)
        self.assertEqual(val.rule_type, "end")
        self.assertEqual(val.failure_index, 1)
        self.assertEqual(val.failure_token, "VIEW")

    def test_empty_sessions(self):
        """Verify empty sessions are rejected."""
        self.assertFalse(self.automaton.accepts([]))
        val = self.automaton.validate([])
        self.assertFalse(val.valid)
        self.assertEqual(val.rule_type, "empty")

    def test_unknown_events(self):
        """Verify unknown events are handled properly at start and inside session."""
        # Unknown start
        self.assertFalse(self.automaton.accepts(["UNKNOWN_EVENT", "LOGOUT"]))
        # Unknown event after DELETE (where DELETE requires LOGOUT at >= 70%)
        seq = ["LOGIN", "DELETE", "UNKNOWN_ACTION", "LOGOUT"]
        self.assertFalse(self.automaton.accepts(seq))
        val = self.automaton.validate(seq)
        self.assertFalse(val.valid)
        self.assertEqual(val.failure_token, "UNKNOWN_ACTION")

    def test_trigram_context_transitions(self):
        """Verify 2-event context transitions in the automaton."""
        # In training, ('LOGIN', 'DELETE') is followed by LOGOUT in 2/2 = 100%
        # Next state from ('LOGIN', 'DELETE') on 'LOGOUT' is ('DELETE', 'LOGOUT')
        s0 = self.automaton.next_state(START_STATE, "LOGIN")
        s1 = self.automaton.next_state(s0, "DELETE")
        self.assertEqual(s1, ("LOGIN", "DELETE"))
        s2 = self.automaton.next_state(s1, "LOGOUT")
        self.assertEqual(s2, ("DELETE", "LOGOUT"))
        self.assertTrue(self.automaton.is_accepting(s2))

        # But on 'VIEW', transition is invalid
        self.assertIsNone(self.automaton.next_state(s1, "VIEW"))

    def test_consistency_between_automaton_and_validator(self):
        """Verify that automaton.accepts(seq) matches validate_session(seq, grammar).valid."""
        test_cases = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
            ["VIEW", "EDIT", "LOGOUT"],
            ["LOGIN", "VIEW"],
            ["LOGIN", "VIEW", "LOGOUT", "LOGOUT"],
            ["LOGIN", "DELETE", "VIEW", "LOGOUT"],
            ["LOGIN", "DELETE", "LOGOUT"],
            ["LOGOUT"],
            [],
        ]
        for seq in test_cases:
            aut_acc = self.automaton.accepts(seq)
            val_res = validate_session(seq, self.grammar)
            self.assertEqual(
                aut_acc,
                val_res.valid,
                f"Mismatch for {seq}: automaton={aut_acc}, validator={val_res.valid}"
            )


if __name__ == "__main__":
    unittest.main()

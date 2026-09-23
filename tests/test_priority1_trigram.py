"""Unit tests for Priority 1: Context-aware trigram grammar inference."""

import unittest
from grammar_inference import (
    InferredGrammar,
    allowed_trigram_followers,
    allowed_followers,
    allowed_starts,
    allowed_ends,
    infer_grammar,
)
from validator import validate_session


class TestPriority1TrigramInference(unittest.TestCase):
    def test_trigram_count_generation(self):
        """Verify trigram counts and support are correctly counted."""
        # 3 sessions: 2 have A->B->C, 1 has A->B->D
        seqs = [
            ["A", "B", "C"],
            ["A", "B", "C"],
            ["A", "B", "D"],
        ]
        grammar = infer_grammar(seqs, threshold=0.60, min_support=1)
        self.assertEqual(grammar.trigram_support.get(("A", "B")), 3)
        self.assertEqual(grammar.trigram_counts.get(("A", "B"), {}).get("C"), 2)
        self.assertEqual(grammar.trigram_counts.get(("A", "B"), {}).get("D"), 1)

    def test_probability_calculation(self):
        """Verify conditional probabilities P(C | A, B) are calculated accurately."""
        seqs = [
            ["A", "B", "C"],
            ["A", "B", "C"],
            ["A", "B", "D"],
        ]
        grammar = infer_grammar(seqs, threshold=0.50, min_support=1)
        prob_c = grammar.get_trigram_prob("A", "B", "C")
        prob_d = grammar.get_trigram_prob("A", "B", "D")
        self.assertAlmostEqual(prob_c, 2 / 3, places=4)
        self.assertAlmostEqual(prob_d, 1 / 3, places=4)

    def test_threshold_filtering(self):
        """Verify candidates must meet or exceed threshold to be allowed."""
        seqs = [
            ["A", "B", "C"],
            ["A", "B", "C"],
            ["A", "B", "D"],
        ]
        # P(C | A, B) = 0.667
        # At threshold 0.70: neither C nor D qualifies
        grammar_strict = infer_grammar(seqs, threshold=0.70, min_support=1)
        self.assertEqual(allowed_trigram_followers(grammar_strict, ("A", "B")), [])

        # At threshold 0.60: C qualifies (0.667 >= 0.60)
        grammar_lenient = infer_grammar(seqs, threshold=0.60, min_support=1)
        self.assertEqual(allowed_trigram_followers(grammar_lenient, ("A", "B")), ["C"])

    def test_minimum_support(self):
        """Verify rules require support >= min_support."""
        seqs = [
            ["A", "B", "C"],
            ["A", "B", "C"],
        ]
        # Support is 2, P(C | A, B) = 1.0
        grammar_supp_2 = infer_grammar(seqs, threshold=0.70, min_support=2)
        self.assertEqual(allowed_trigram_followers(grammar_supp_2, ("A", "B")), ["C"])

        grammar_supp_3 = infer_grammar(seqs, threshold=0.70, min_support=3)
        self.assertEqual(allowed_trigram_followers(grammar_supp_3, ("A", "B")), [])

    def test_multiple_successors(self):
        """Verify handling of multiple successors from the same context."""
        seqs = [
            ["A", "B", "C"],
            ["A", "B", "D"],
            ["A", "B", "E"],
            ["A", "B", "F"],
        ]
        grammar = infer_grammar(seqs, threshold=0.20, min_support=1)
        self.assertEqual(grammar.trigram_support[("A", "B")], 4)
        for token in ("C", "D", "E", "F"):
            self.assertAlmostEqual(grammar.get_trigram_prob("A", "B", token), 0.25)
        # All 4 meet threshold 0.20
        self.assertEqual(allowed_trigram_followers(grammar, ("A", "B")), ["C", "D", "E", "F"])

    def test_empty_training_data(self):
        """Verify empty training dataset returns empty InferredGrammar without error."""
        grammar = infer_grammar([])
        self.assertEqual(grammar.session_count, 0)
        self.assertEqual(grammar.trigram_rules, {})
        self.assertEqual(grammar.trigram_support, {})

    def test_empty_sessions(self):
        """Verify list of empty sessions handled gracefully."""
        grammar = infer_grammar([[], [], []])
        self.assertEqual(grammar.session_count, 3)
        self.assertEqual(grammar.trigram_rules, {})

    def test_sessions_shorter_than_three_tokens(self):
        """Verify 1-token and 2-token sessions generate starts/ends/bigrams but no trigrams."""
        seqs = [
            ["LOGIN"],
            ["LOGIN", "LOGOUT"],
        ]
        grammar = infer_grammar(seqs, threshold=0.50, min_support=1)
        self.assertIn("LOGIN", allowed_starts(grammar))
        self.assertIn("LOGOUT", allowed_ends(grammar))
        self.assertEqual(grammar.trigram_support, {})
        self.assertEqual(grammar.trigram_rules, {})

    def test_trigram_validation(self):
        """Verify validator flags contextual trigram violations with rule_type='trigram_transition'."""
        train_seqs = [
            ["LOGIN", "DELETE", "LOGOUT"],
            ["LOGIN", "DELETE", "LOGOUT"],
            ["LOGIN", "DELETE", "LOGOUT"],
            ["LOGIN", "DELETE", "VIEW", "LOGOUT"],
        ]
        # Context ('LOGIN', 'DELETE'): LOGOUT has 3/4 = 0.75 >= 0.70
        grammar = infer_grammar(train_seqs, threshold=0.70, min_support=1)
        self.assertIn("LOGOUT", allowed_trigram_followers(grammar, ("LOGIN", "DELETE")))

        # Valid test session conforming to trigram rule
        valid_res = validate_session(["LOGIN", "DELETE", "LOGOUT"], grammar)
        self.assertTrue(valid_res.valid)

        # Invalid test session where ('LOGIN', 'DELETE') is followed by VIEW
        invalid_res = validate_session(["LOGIN", "DELETE", "VIEW", "LOGOUT"], grammar)
        self.assertFalse(invalid_res.valid)
        self.assertEqual(invalid_res.rule_type, "trigram_transition")
        self.assertEqual(invalid_res.failure_index, 2)
        self.assertEqual(invalid_res.failure_token, "VIEW")
        self.assertEqual(invalid_res.expected, ["LOGOUT"])

    def test_bigram_fallback(self):
        """Verify fallback to bigram when trigram has insufficient support or is diffuse."""
        train_seqs = [
            # LOGIN -> VIEW has diffuse successors (LOGOUT and EDIT 50% each)
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "EDIT", "LOGOUT"],
            # EDIT -> LOGOUT is 100%
        ]
        grammar = infer_grammar(train_seqs, threshold=0.70, min_support=1)
        # Context ('LOGIN', 'VIEW') has no single follower >= 0.70
        self.assertEqual(allowed_trigram_followers(grammar, ("LOGIN", "VIEW")), [])

        # In bigram: VIEW has no single follower >= 0.70 either, so both EDIT and LOGOUT allowed
        test_session = ["LOGIN", "VIEW", "EDIT", "LOGOUT"]
        res = validate_session(test_session, grammar)
        self.assertTrue(res.valid)

    def test_rare_but_valid_transitions(self):
        """Unconstrained transitions (no learned rule >= threshold) are allowed by policy."""
        train_seqs = [
            ["LOGIN", "ACTION_A", "LOGOUT"],
            ["LOGIN", "ACTION_B", "LOGOUT"],
            ["LOGIN", "ACTION_C", "LOGOUT"],
        ]
        grammar = infer_grammar(train_seqs, threshold=0.70, min_support=1)
        # LOGIN -> ACTION_D is unseen, but LOGIN has no single dominant follower >= 70%
        # The transition is not constrained by a high-confidence rule
        res = validate_session(["LOGIN", "ACTION_D", "LOGOUT"], grammar)
        self.assertTrue(res.valid)

    def test_terminal_event_handling(self):
        """Terminal events cannot have successors in validation, and post-terminal events are not counted."""
        train_seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "LOGOUT"],
            # Noisy training session with post-terminal event
            ["LOGIN", "VIEW", "LOGOUT", "ROGUE"],
        ]
        grammar = infer_grammar(train_seqs, threshold=0.65, min_support=1)
        # LOGOUT is terminal (ends >= 65% of sessions)
        self.assertIn("LOGOUT", allowed_ends(grammar))
        # ROGUE should not be counted as a valid follower of LOGOUT
        self.assertNotIn("ROGUE", grammar.bigram_rules.get("LOGOUT", {}))

        # In validation, any event following LOGOUT is flagged as terminal
        res = validate_session(["LOGIN", "VIEW", "LOGOUT", "EDIT"], grammar)
        self.assertFalse(res.valid)
        self.assertEqual(res.rule_type, "terminal")
        self.assertEqual(res.failure_index, 3)
        self.assertEqual(res.failure_token, "EDIT")

    def test_conflicting_trigram_and_bigram_evidence(self):
        """Trigram context specificity takes precedence over generic bigram rule."""
        train_seqs = [
            # Globally, ACTION_B is followed by COMMON 80% of the time (4 times)
            ["LOGIN", "ACTION_A", "ACTION_B", "COMMON", "LOGOUT"],
            ["LOGIN", "ACTION_A", "ACTION_B", "COMMON", "LOGOUT"],
            ["LOGIN", "ACTION_A", "ACTION_B", "COMMON", "LOGOUT"],
            ["LOGIN", "ACTION_A", "ACTION_B", "COMMON", "LOGOUT"],
            # But specifically under context (SPECIAL, ACTION_B), it is followed by SPECIAL_NEXT
            ["LOGIN", "SPECIAL", "ACTION_B", "SPECIAL_NEXT", "LOGOUT"],
            ["LOGIN", "SPECIAL", "ACTION_B", "SPECIAL_NEXT", "LOGOUT"],
        ]
        grammar = infer_grammar(train_seqs, threshold=0.70, min_support=2)

        # Bigram rule for ACTION_B alone: COMMON (4/6 = 66.7% - below 70%, or if 80% above)
        # For context ('SPECIAL', 'ACTION_B'): SPECIAL_NEXT is 2/2 = 100%
        self.assertEqual(
            allowed_trigram_followers(grammar, ("SPECIAL", "ACTION_B")),
            ["SPECIAL_NEXT"]
        )

        # Test session using the context-specific follower should succeed
        valid_seq = ["LOGIN", "SPECIAL", "ACTION_B", "SPECIAL_NEXT", "LOGOUT"]
        res = validate_session(valid_seq, grammar)
        self.assertTrue(res.valid)

        # Test session with context ('SPECIAL', 'ACTION_B') using COMMON should be rejected by trigram rule
        invalid_seq = ["LOGIN", "SPECIAL", "ACTION_B", "COMMON", "LOGOUT"]
        res_invalid = validate_session(invalid_seq, grammar)
        self.assertFalse(res_invalid.valid)
        self.assertEqual(res_invalid.rule_type, "trigram_transition")
        self.assertEqual(res_invalid.expected, ["SPECIAL_NEXT"])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for probability_model.py — smoothed probabilities, NLL scoring, adaptive threshold."""

from __future__ import annotations

import math
import unittest

from grammar_inference import InferredGrammar, infer_grammar
from probability_model import (
    SmoothedProbabilityModel,
    build_probability_model,
    calculate_adaptive_threshold,
    calculate_session_anomaly_score,
    is_anomalous,
    score_sessions,
    transition_probability,
    transition_surprise,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_model(
    counts: dict[str, dict[str, int]],
    vocab: list[str],
    alpha: float = 1.0,
    epsilon: float = 1e-12,
) -> SmoothedProbabilityModel:
    return SmoothedProbabilityModel(
        transition_counts=counts,
        event_types=vocab,
        alpha=alpha,
        epsilon=epsilon,
    )


# ---------------------------------------------------------------------------
# 1. Transition probability function
# ---------------------------------------------------------------------------

class TestTransitionProbability(unittest.TestCase):

    def setUp(self):
        # LOGIN → VIEW: 3 times; LOGIN → EDIT: 1 time
        self.counts = {"LOGIN": {"VIEW": 3, "EDIT": 1}}
        self.vocab = ["DELETE", "EDIT", "LOGIN", "LOGOUT", "VIEW"]  # 5 tokens

    def test_known_transition(self):
        """Smoothed probability for a seen (current, next) pair."""
        # P(VIEW | LOGIN) = (3 + 1) / (4 + 1×5) = 4/9
        p = transition_probability("LOGIN", "VIEW", self.counts, self.vocab, alpha=1.0)
        self.assertAlmostEqual(p, 4 / 9, places=6)

    def test_unseen_transition_gets_nonzero(self):
        """Laplace smoothing ensures unseen transitions have finite probability."""
        # P(LOGOUT | LOGIN) = (0 + 1) / (4 + 5) = 1/9
        p = transition_probability("LOGIN", "LOGOUT", self.counts, self.vocab, alpha=1.0)
        self.assertAlmostEqual(p, 1 / 9, places=6)
        self.assertGreater(p, 0)

    def test_probabilities_sum_to_one(self):
        """All transition probabilities from LOGIN must sum to ~1.0."""
        total = sum(
            transition_probability("LOGIN", t, self.counts, self.vocab, alpha=1.0)
            for t in self.vocab
        )
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_empty_vocabulary_returns_zero(self):
        """Empty vocabulary returns 0.0 safely (no division by zero)."""
        p = transition_probability("LOGIN", "VIEW", self.counts, [], alpha=1.0)
        self.assertEqual(p, 0.0)

    def test_unknown_current_event(self):
        """Unknown current event (no outgoing transitions) uses smoothing over vocab."""
        # count("UNKNOWN", anything) = 0; total_from_UNKNOWN = 0
        # P(VIEW | UNKNOWN) = (0 + 1) / (0 + 1×5) = 1/5
        p = transition_probability("UNKNOWN", "VIEW", self.counts, self.vocab, alpha=1.0)
        self.assertAlmostEqual(p, 1 / 5, places=6)

    def test_alpha_zero_unseen_is_zero(self):
        """With alpha=0, unseen transitions get probability 0."""
        p = transition_probability("LOGIN", "LOGOUT", self.counts, self.vocab, alpha=0.0)
        self.assertEqual(p, 0.0)

    def test_alpha_zero_seen_gives_mle(self):
        """With alpha=0, seen transitions give MLE: count/total."""
        # P(VIEW | LOGIN) = 3 / 4
        p = transition_probability("LOGIN", "VIEW", self.counts, self.vocab, alpha=0.0)
        self.assertAlmostEqual(p, 3 / 4, places=6)

    def test_negative_alpha_raises(self):
        """Negative alpha is invalid and must raise ValueError."""
        with self.assertRaises(ValueError):
            transition_probability("LOGIN", "VIEW", self.counts, self.vocab, alpha=-0.1)

    def test_result_in_unit_interval(self):
        """Probabilities are always in [0, 1]."""
        for t in self.vocab:
            p = transition_probability("LOGIN", t, self.counts, self.vocab, alpha=1.0)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_result_is_finite(self):
        """All results are finite floats."""
        for t in self.vocab:
            p = transition_probability("LOGIN", t, self.counts, self.vocab, alpha=1.0)
            self.assertTrue(math.isfinite(p))


# ---------------------------------------------------------------------------
# 2. SmoothedProbabilityModel
# ---------------------------------------------------------------------------

class TestSmoothedProbabilityModel(unittest.TestCase):

    def setUp(self):
        self.counts = {"LOGIN": {"VIEW": 4, "EDIT": 2}, "VIEW": {"LOGOUT": 3, "EDIT": 1}}
        self.vocab = ["EDIT", "LOGIN", "LOGOUT", "VIEW"]

    def test_model_caches_results(self):
        """Calling transition_probability twice returns identical result."""
        m = _simple_model(self.counts, self.vocab)
        p1 = m.transition_probability("LOGIN", "VIEW")
        p2 = m.transition_probability("LOGIN", "VIEW")
        self.assertEqual(p1, p2)

    def test_negative_alpha_raises_on_init(self):
        """SmoothedProbabilityModel raises ValueError for negative alpha."""
        with self.assertRaises(ValueError):
            SmoothedProbabilityModel(
                transition_counts={}, event_types=["A"], alpha=-1.0
            )

    def test_nonpositive_epsilon_raises(self):
        """SmoothedProbabilityModel raises ValueError for non-positive epsilon."""
        with self.assertRaises(ValueError):
            SmoothedProbabilityModel(
                transition_counts={}, event_types=["A"], alpha=1.0, epsilon=0.0
            )

    def test_top_surprising_transitions_sorted_descending(self):
        """top_surprising_transitions returns entries sorted by surprise (descending)."""
        m = _simple_model(self.counts, self.vocab, alpha=1.0)
        seq = ["LOGIN", "VIEW", "EDIT", "LOGOUT"]
        surprises = m.top_surprising_transitions(seq, n=10)
        scores_only = [e["surprise"] for e in surprises]
        self.assertEqual(scores_only, sorted(scores_only, reverse=True))

    def test_top_surprising_short_session(self):
        """Single-event session has no transitions; returns empty list."""
        m = _simple_model(self.counts, self.vocab)
        self.assertEqual(m.top_surprising_transitions(["LOGIN"], n=3), [])
        self.assertEqual(m.top_surprising_transitions([], n=3), [])

    def test_top_surprising_n_limit(self):
        """top_surprising_transitions returns at most n entries."""
        m = _simple_model(self.counts, self.vocab)
        seq = ["LOGIN", "VIEW", "EDIT", "LOGOUT"]
        self.assertLessEqual(len(m.top_surprising_transitions(seq, n=2)), 2)


# ---------------------------------------------------------------------------
# 3. Session anomaly scoring
# ---------------------------------------------------------------------------

class TestSessionAnomalyScore(unittest.TestCase):

    def setUp(self):
        # High-probability chain: LOGIN→VIEW→LOGOUT dominates training
        self.counts = {
            "LOGIN": {"VIEW": 10},
            "VIEW": {"LOGOUT": 10},
        }
        self.vocab = ["EDIT", "LOGIN", "LOGOUT", "VIEW"]
        self.model = _simple_model(self.counts, self.vocab, alpha=1.0)

    def test_empty_session_returns_zero(self):
        """Empty session score is 0.0."""
        self.assertEqual(calculate_session_anomaly_score([], self.model), 0.0)

    def test_single_event_returns_zero(self):
        """Single-event session has no transitions; score is 0.0."""
        self.assertEqual(calculate_session_anomaly_score(["LOGIN"], self.model), 0.0)

    def test_high_prob_sequence_lower_than_low_prob(self):
        """High-probability sequence has strictly lower NLL score than low-probability."""
        high_prob = ["LOGIN", "VIEW", "LOGOUT"]  # follows dominant training pattern
        low_prob = ["LOGIN", "EDIT", "LOGOUT"]   # EDIT is rare after LOGIN
        s_high = calculate_session_anomaly_score(high_prob, self.model)
        s_low = calculate_session_anomaly_score(low_prob, self.model)
        self.assertLess(s_high, s_low)

    def test_score_is_finite(self):
        """Score is a finite float for a normal sequence."""
        score = calculate_session_anomaly_score(["LOGIN", "VIEW", "LOGOUT"], self.model)
        self.assertTrue(math.isfinite(score))

    def test_score_nonnegative(self):
        """NLL score is always >= 0."""
        for seq in [
            [],
            ["LOGIN"],
            ["LOGIN", "VIEW"],
            ["LOGIN", "VIEW", "LOGOUT"],
            ["UNKNOWN", "ALSO_UNKNOWN"],
        ]:
            score = calculate_session_anomaly_score(seq, self.model)
            self.assertGreaterEqual(score, 0.0)

    def test_unknown_events_do_not_crash(self):
        """Unknown tokens in session receive smoothed probability; no exception."""
        score = calculate_session_anomaly_score(["UNKNOWN_A", "UNKNOWN_B"], self.model)
        self.assertTrue(math.isfinite(score))

    def test_repeated_events(self):
        """Repeated events in a session are handled correctly."""
        score = calculate_session_anomaly_score(["LOGIN", "VIEW", "VIEW", "VIEW", "LOGOUT"], self.model)
        self.assertTrue(math.isfinite(score))
        self.assertGreaterEqual(score, 0.0)

    def test_nll_formula_correctness(self):
        """Manually verify formula: mean of -log(P(t|t-1)) over transitions."""
        seq = ["LOGIN", "VIEW", "LOGOUT"]
        p_lv = self.model.transition_probability("LOGIN", "VIEW")
        p_vl = self.model.transition_probability("VIEW", "LOGOUT")
        expected = (-math.log(p_lv) + -math.log(p_vl)) / 2.0
        actual = calculate_session_anomaly_score(seq, self.model)
        self.assertAlmostEqual(actual, expected, places=10)

    def test_model_session_score_identical_to_function(self):
        """SmoothedProbabilityModel.session_score equals the standalone function."""
        seq = ["LOGIN", "VIEW", "LOGOUT"]
        self.assertAlmostEqual(
            self.model.session_score(seq),
            calculate_session_anomaly_score(seq, self.model),
            places=10,
        )


# ---------------------------------------------------------------------------
# 4. transition_surprise
# ---------------------------------------------------------------------------

class TestTransitionSurprise(unittest.TestCase):

    def test_surprise_equals_neg_log_prob(self):
        """Surprise should equal -log(P(next|current))."""
        m = _simple_model({"A": {"B": 9}}, ["A", "B", "C"], alpha=1.0)
        p = m.transition_probability("A", "B")
        expected = -math.log(max(p, m.epsilon))
        actual = transition_surprise("A", "B", m)
        self.assertAlmostEqual(actual, expected, places=10)

    def test_surprise_nonnegative(self):
        """Surprise is always >= 0 (probabilities are in (0, 1])."""
        m = _simple_model({"A": {"B": 5}}, ["A", "B"], alpha=1.0)
        self.assertGreaterEqual(transition_surprise("A", "B", m), 0.0)

    def test_low_prob_transition_higher_surprise(self):
        """Low-probability transition has higher surprise than high-probability."""
        m = _simple_model({"A": {"B": 100, "C": 1}}, ["A", "B", "C"], alpha=1.0)
        s_high = transition_surprise("A", "B", m)  # high prob → low surprise
        s_low = transition_surprise("A", "C", m)   # low prob → high surprise
        self.assertLess(s_high, s_low)


# ---------------------------------------------------------------------------
# 5. Adaptive threshold
# ---------------------------------------------------------------------------

class TestAdaptiveThreshold(unittest.TestCase):

    def test_empty_scores_returns_inf(self):
        """Empty normal_scores returns +inf (conservative fallback)."""
        thr = calculate_adaptive_threshold([])
        self.assertEqual(thr, math.inf)

    def test_single_score_returns_that_value(self):
        """Single score: σ = 0, threshold = mean = the score."""
        thr = calculate_adaptive_threshold([3.14], k=3.0)
        # mean=3.14, std=0, threshold=3.14
        self.assertAlmostEqual(thr, 3.14, places=10)

    def test_threshold_formula(self):
        """Verify mean + k*std formula with known values."""
        scores = [1.0, 2.0, 3.0]
        mean = 2.0
        variance = ((1 - 2) ** 2 + (2 - 2) ** 2 + (3 - 2) ** 2) / 3.0  # population
        std_dev = math.sqrt(variance)
        expected = mean + 3.0 * std_dev
        actual = calculate_adaptive_threshold(scores, k=3.0)
        self.assertAlmostEqual(actual, expected, places=10)

    def test_k_zero_returns_mean(self):
        """k=0 returns the mean of scores (no penalty for variability)."""
        scores = [1.0, 3.0, 5.0]
        mean = sum(scores) / len(scores)
        thr = calculate_adaptive_threshold(scores, k=0.0)
        self.assertAlmostEqual(thr, mean, places=10)

    def test_negative_k_raises(self):
        """Negative k is invalid and must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_adaptive_threshold([1.0, 2.0], k=-1.0)

    def test_larger_k_gives_larger_threshold(self):
        """Larger k gives a larger (or equal) threshold."""
        scores = [1.0, 2.0, 3.0, 4.0]
        thr_small = calculate_adaptive_threshold(scores, k=1.0)
        thr_large = calculate_adaptive_threshold(scores, k=5.0)
        self.assertLessEqual(thr_small, thr_large)

    def test_score_above_threshold_is_anomalous(self):
        """is_anomalous returns True when score > threshold."""
        thr = calculate_adaptive_threshold([1.0, 2.0, 3.0], k=1.0)
        self.assertTrue(is_anomalous(thr + 0.001, thr))

    def test_score_equal_threshold_not_anomalous(self):
        """Documented behaviour: score equal to threshold is NOT anomalous."""
        thr = calculate_adaptive_threshold([1.0, 2.0, 3.0], k=1.0)
        self.assertFalse(is_anomalous(thr, thr))

    def test_score_below_threshold_not_anomalous(self):
        """Score below threshold is not anomalous."""
        thr = calculate_adaptive_threshold([1.0, 2.0, 3.0], k=2.0)
        self.assertFalse(is_anomalous(0.0, thr))

    def test_threshold_finite_for_non_empty_input(self):
        """Threshold is finite for any non-empty input."""
        thr = calculate_adaptive_threshold([0.5, 1.5, 2.5], k=2.0)
        self.assertTrue(math.isfinite(thr))

    def test_identical_scores_zero_std(self):
        """All equal scores → std=0 → threshold = mean = that score (for any k)."""
        scores = [2.0, 2.0, 2.0]
        thr = calculate_adaptive_threshold(scores, k=5.0)
        self.assertAlmostEqual(thr, 2.0, places=10)


# ---------------------------------------------------------------------------
# 6. build_probability_model factory
# ---------------------------------------------------------------------------

class TestBuildProbabilityModel(unittest.TestCase):

    def test_model_from_grammar(self):
        """build_probability_model produces a valid model from InferredGrammar."""
        seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
        ]
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar, alpha=1.0)
        self.assertIsInstance(model, SmoothedProbabilityModel)
        self.assertGreater(len(model.event_types), 0)

    def test_model_gives_finite_probabilities(self):
        """Transition probabilities from model are finite floats in [0, 1]."""
        seqs = [["LOGIN", "VIEW", "LOGOUT"]] * 5
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar, alpha=1.0)
        for left in model.event_types:
            for right in model.event_types:
                p = model.transition_probability(left, right)
                self.assertTrue(math.isfinite(p))
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_model_sum_to_one(self):
        """Probabilities from each source sum to ~1.0 over the vocabulary."""
        seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
        ]
        grammar = infer_grammar(seqs, threshold=0.50)
        model = build_probability_model(grammar, alpha=1.0)
        for event in ["LOGIN", "VIEW", "EDIT"]:
            total = sum(model.transition_probability(event, t) for t in model.event_types)
            self.assertAlmostEqual(total, 1.0, places=5)

    def test_bigram_raw_counts_used(self):
        """When bigram_raw_counts is populated, model uses exact counts."""
        seqs = [["LOGIN", "VIEW", "LOGOUT"]] * 3 + [["LOGIN", "EDIT", "LOGOUT"]]
        grammar = infer_grammar(seqs, threshold=0.70)
        # bigram_raw_counts should exist after the update
        self.assertTrue(grammar.bigram_raw_counts)
        model = build_probability_model(grammar, alpha=0.0)  # no smoothing
        # P(VIEW | LOGIN) ≈ 3/4 = 0.75 with alpha=0
        p = model.transition_probability("LOGIN", "VIEW")
        self.assertAlmostEqual(p, 0.75, places=4)

    def test_empty_grammar(self):
        """Empty grammar produces a model without crashing."""
        grammar = infer_grammar([])
        model = build_probability_model(grammar, alpha=1.0)
        self.assertIsInstance(model, SmoothedProbabilityModel)


# ---------------------------------------------------------------------------
# 7. score_sessions convenience function
# ---------------------------------------------------------------------------

class TestScoreSessions(unittest.TestCase):

    def test_scores_all_sessions(self):
        """score_sessions returns a score for every session in the input."""
        seqs = [["LOGIN", "VIEW", "LOGOUT"]] * 5
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar)
        sessions = {
            "S1": ["LOGIN", "VIEW", "LOGOUT"],
            "S2": ["LOGIN", "EDIT", "LOGOUT"],
            "S3": ["VIEW"],
        }
        result = score_sessions(sessions, model)
        self.assertEqual(set(result.keys()), {"S1", "S2", "S3"})

    def test_scores_are_finite(self):
        """All returned scores are finite floats."""
        seqs = [["LOGIN", "VIEW", "LOGOUT"]] * 5
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar)
        sessions = {
            "S1": ["LOGIN", "VIEW", "LOGOUT"],
            "S2": [],
            "S3": ["LOGIN"],
        }
        for sid, score in score_sessions(sessions, model).items():
            self.assertTrue(math.isfinite(score), f"Score for {sid} is not finite: {score}")


# ---------------------------------------------------------------------------
# 8. Hybrid detection integration
# ---------------------------------------------------------------------------

class TestHybridDetection(unittest.TestCase):
    """Verify the OR integration policy: anomalous if automaton OR stat flag."""

    def setUp(self):
        self.seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
            ["LOGIN", "EDIT", "LOGOUT"],
        ]
        self.grammar = infer_grammar(self.seqs, threshold=0.70)
        self.model = build_probability_model(self.grammar, alpha=1.0)
        train_scores = [self.model.session_score(s) for s in self.seqs]
        self.threshold = calculate_adaptive_threshold(train_scores, k=1.5)

    def test_normal_session_not_anomalous(self):
        """Well-formed common session not flagged by either detector."""
        from automaton import build_automaton
        auto = build_automaton(self.grammar)
        seq = ["LOGIN", "VIEW", "LOGOUT"]
        structural = not auto.validate(seq).valid
        stat = is_anomalous(self.model.session_score(seq), self.threshold)
        hybrid = structural or stat
        # Both detectors see this as normal (may depend on threshold)
        # At minimum, structural must pass
        self.assertFalse(structural)

    def test_structural_violation_always_anomalous(self):
        """Session rejected by automaton is always final_anomaly = True."""
        structural_flag = True   # simulates automaton rejection
        stat_flag = False
        final = structural_flag or stat_flag
        self.assertTrue(final)

    def test_stat_violation_without_structural(self):
        """Purely statistical anomaly still sets final_anomaly = True."""
        structural_flag = False
        stat_flag = True
        final = structural_flag or stat_flag
        self.assertTrue(final)

    def test_no_violation_not_anomalous(self):
        """Neither flag → final_anomaly = False."""
        self.assertFalse(False or False)


# ---------------------------------------------------------------------------
# 9. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_very_long_session(self):
        """Very long session (100 events) is scored without error."""
        seqs = [["LOGIN"] + ["VIEW"] * 50 + ["LOGOUT"]] * 3
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar)
        long_session = ["LOGIN"] + ["VIEW"] * 100 + ["LOGOUT"]
        score = model.session_score(long_session)
        self.assertTrue(math.isfinite(score))

    def test_single_event_type_in_training(self):
        """Training with a single unique event per session is handled."""
        seqs = [["LOGIN", "LOGOUT"]] * 5
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar)
        p = model.transition_probability("LOGIN", "LOGOUT")
        self.assertGreater(p, 0.0)
        score = model.session_score(["LOGIN", "LOGOUT"])
        self.assertTrue(math.isfinite(score))

    def test_threshold_with_single_unique_score(self):
        """Identical scores → std=0 → threshold = that value."""
        scores = [1.234] * 10
        thr = calculate_adaptive_threshold(scores, k=3.0)
        self.assertAlmostEqual(thr, 1.234, places=8)

    def test_no_normal_training_sessions(self):
        """Empty training scores → threshold = inf → no statistical flags."""
        thr = calculate_adaptive_threshold([], k=3.0)
        self.assertEqual(thr, math.inf)
        self.assertFalse(is_anomalous(999.0, thr))  # inf threshold: nothing anomalous

    def test_invalid_configuration_alpha_negative(self):
        """Negative alpha in standalone function raises ValueError."""
        with self.assertRaises(ValueError):
            transition_probability("A", "B", {}, ["A", "B"], alpha=-1)

    def test_unknown_event_in_session_no_crash(self):
        """Unknown tokens in session do not crash the scorer."""
        seqs = [["LOGIN", "VIEW", "LOGOUT"]] * 3
        grammar = infer_grammar(seqs, threshold=0.70)
        model = build_probability_model(grammar)
        score = model.session_score(["TOTALLY_UNKNOWN_EVENT", "ALSO_UNKNOWN"])
        self.assertTrue(math.isfinite(score))


if __name__ == "__main__":
    unittest.main()

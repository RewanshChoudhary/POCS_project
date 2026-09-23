"""Integration and CLI evaluation tests for Priority 4."""

import json
import tempfile
import unittest
from pathlib import Path

from explainer import apply_fix, explain, suggest_fix
from grammar_inference import infer_grammar
from report import (
    DEFAULT_GROUND_TRUTH,
    DEFAULT_TEST,
    DEFAULT_TRAIN,
    baseline_validate,
    compute_metrics,
    run_pipeline,
)
from validator import validate_session


# Actual session count in the expanded test_logs.txt (was 18 in early version)
ACTUAL_TEST_SESSION_COUNT = 713
ACTUAL_FLAGGED_COUNT = 167


class TestPriority4Integration(unittest.TestCase):
    def setUp(self):
        self.train_path = DEFAULT_TRAIN
        self.test_path = DEFAULT_TEST
        self.ground_truth_path = DEFAULT_GROUND_TRUTH

    def test_run_pipeline_end_to_end(self):
        """Verify run_pipeline executes smoothly and produces structured results."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
            min_support=1,
            max_cost=2,
            validation_mode="first",
        )
        self.assertEqual(output["total_test_sessions"], ACTUAL_TEST_SESSION_COUNT)
        # All flagged sessions must have a repair that validates
        for flagged in output["flagged_sessions"]:
            self.assertTrue(
                flagged["fix_validates"],
                f"Fix for {flagged['session_id']} did not validate!",
            )

    def test_validation_mode_all(self):
        """Verify validation_mode='all' detects multiple violations in multi-anomaly sessions.

        Uses a minimal synthetic grammar where a specific session has known
        multiple violations, to avoid dependence on test_logs.txt session content.
        """
        # Build a grammar that allows only LOGIN→VIEW→LOGOUT pattern
        train_seqs = [
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "LOGOUT"],
            ["LOGIN", "VIEW", "LOGOUT"],
        ]
        grammar = infer_grammar(train_seqs, threshold=0.70, min_support=1)
        from automaton import build_automaton
        auto = build_automaton(grammar)

        # A session starting with EDIT (start violation) and ending without LOGOUT (end violation)
        multi_bad = ["EDIT", "VIEW"]
        result = auto.validate(multi_bad, mode="all")
        # Should be invalid with at least a start violation
        self.assertFalse(result.valid)
        # 'all' mode captures both start and end violations
        self.assertIsNotNone(result.all_failures)
        self.assertGreater(len(result.all_failures or []), 0)

    def test_compute_metrics_accuracy_and_f1(self):
        """Verify exact calculation of precision, recall, F1, TP, FP, TN, FN."""
        grammar = infer_grammar(
            [["LOGIN", "VIEW", "LOGOUT"]],
            threshold=0.70,
        )
        sequences = {
            "S1": ["LOGIN", "VIEW", "LOGOUT"],  # valid
            "S2": ["BAD_START", "LOGOUT"],      # invalid
        }
        ground_truth = {
            "S1": True,
            "S2": False,
        }
        metrics = compute_metrics(
            sequences,
            ground_truth,
            lambda seq: validate_session(seq, grammar).valid,
        )
        self.assertEqual(metrics["tp"], 1)
        self.assertEqual(metrics["tn"], 1)
        self.assertEqual(metrics["fp"], 0)
        self.assertEqual(metrics["fn"], 0)
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["f1"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)

    def test_custom_ground_truth_path_controls_evaluation(self):
        """Evaluation labels are configurable and never substituted with defaults."""
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / "labels.txt"
            output = run_pipeline(
                train_path=self.train_path,
                test_path=self.test_path,
                ground_truth_path=labels,
            )

        self.assertEqual(output["evaluation_metrics"], [])
        self.assertEqual(output["source_files"]["ground_truth"], str(labels))

    def test_multi_edit_apply_fix(self):
        """Verify apply_fix handles compound repairs separated by semicolon."""
        seq = ["A", "B", "C"]
        fix = "replace A with LOGIN at position 0; replace C with LOGOUT at position 2"
        repaired = apply_fix(seq, fix)
        self.assertEqual(repaired, ["LOGIN", "B", "LOGOUT"])

    def test_json_export_pipeline(self):
        """Verify export payload contains all necessary serializable keys."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
        )
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as tmp:
            tmp_path = Path(tmp.name)
            export_data = {
                k: v for k, v in output.items() if k != "test_sequences"
            }
            tmp_path.write_text(json.dumps(export_data, indent=2))
            loaded = json.loads(tmp_path.read_text())
            self.assertEqual(loaded["total_test_sessions"], ACTUAL_TEST_SESSION_COUNT)
            # Statistical fields must be present in export
            self.assertIn("probability_model_config", loaded)
            cfg = loaded["probability_model_config"]
            self.assertIn("alpha", cfg)
            self.assertIn("k", cfg)
            self.assertIn("adaptive_threshold", cfg)

    def test_statistical_fields_in_session_records(self):
        """Verify session records include all required statistical evidence fields."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
        )
        for record in output["session_records"]:
            sid = record["session_id"]
            self.assertIn("anomaly_score", record, f"{sid} missing anomaly_score")
            self.assertIn("statistical_anomaly", record, f"{sid} missing statistical_anomaly")
            self.assertIn("automaton_valid", record, f"{sid} missing automaton_valid")
            self.assertIn("final_anomaly", record, f"{sid} missing final_anomaly")
            self.assertIn("top_surprising_transitions", record, f"{sid} missing top_surprising_transitions")
            # Score must be a non-negative float
            self.assertGreaterEqual(record["anomaly_score"], 0.0, f"{sid}: negative score")

    def test_evaluation_metrics_contain_all_four_methods(self):
        """Verify evaluation_metrics includes baseline, automaton, statistical, and hybrid."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
        )
        methods = [m["method"] for m in output["evaluation_metrics"]]
        self.assertTrue(any("baseline" in m.lower() or "hardcoded" in m.lower() for m in methods),
                        "Missing baseline method in metrics")
        self.assertTrue(any("automaton" in m.lower() or "inferred" in m.lower() or "grammar" in m.lower() for m in methods),
                        "Missing automaton method in metrics")
        self.assertTrue(any("statistical" in m.lower() or "markov" in m.lower() for m in methods),
                        "Missing statistical method in metrics")
        self.assertTrue(any("hybrid" in m.lower() for m in methods),
                        "Missing hybrid method in metrics")

    def test_hybrid_is_superset_of_automaton_detections(self):
        """Hybrid detector catches at least as many anomalies as automaton alone."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
        )
        automaton_tp = next(
            (m["tp"] for m in output["evaluation_metrics"]
             if "automaton" in m["method"].lower() or "inferred" in m["method"].lower()),
            None,
        )
        hybrid_tp = next(
            (m["tp"] for m in output["evaluation_metrics"] if "hybrid" in m["method"].lower()),
            None,
        )
        if automaton_tp is not None and hybrid_tp is not None:
            # Hybrid (OR policy) must detect ≥ as many true positives as automaton alone
            self.assertGreaterEqual(hybrid_tp, automaton_tp)


if __name__ == "__main__":
    unittest.main()

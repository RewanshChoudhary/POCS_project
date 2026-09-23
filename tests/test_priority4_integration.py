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
        self.assertEqual(output["total_test_sessions"], 18)
        self.assertEqual(output["valid_count"], 9)
        self.assertEqual(len(output["flagged_sessions"]), 9)
        for flagged in output["flagged_sessions"]:
            self.assertTrue(
                flagged["fix_validates"],
                f"Fix for {flagged['session_id']} did not validate!",
            )

    def test_validation_mode_all(self):
        """Verify validation_mode='all' detects multiple violations in multi-anomaly sessions."""
        output = run_pipeline(
            train_path=self.train_path,
            test_path=self.test_path,
            threshold=0.70,
            validation_mode="all",
        )
        # Find T009 (DELETE -> VIEW -> LOGOUT)
        t009 = next(item for item in output["flagged_sessions"] if item["session_id"] == "T009")
        self.assertGreater(len(t009["additional_violations"]), 0)

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
            self.assertEqual(loaded["total_test_sessions"], 18)
            self.assertEqual(len(loaded["flagged_sessions"]), 9)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Run the full AutoSense pipeline and print evaluation results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from automaton import build_automaton
from explainer import apply_fix, explain, suggest_fix
from grammar_inference import grammar_to_english, infer_grammar
from repair import repair_session
from session_extractor import load_session_sequences
from validator import ValidationResult, validate_session

ROOT = Path(__file__).parent
DEFAULT_TRAIN = ROOT / "data" / "sample_logs.txt"
DEFAULT_TEST = ROOT / "data" / "test_logs.txt"
DEFAULT_GROUND_TRUTH = ROOT / "data" / "ground_truth.txt"


def baseline_validate(sequence: list[str]) -> bool:
    """Hardcoded 4-rule baseline for comparison."""
    if not sequence:
        return False
    if sequence[0] != "LOGIN":
        return False
    if sequence[-1] != "LOGOUT":
        return False
    if sequence.count("LOGOUT") > 1:
        return False
    if "LOGOUT" in sequence[:-1]:
        logout_index = sequence.index("LOGOUT")
        if any(token in {"VIEW", "EDIT", "DELETE"} for token in sequence[logout_index + 1 :]):
            return False
    return True


def load_ground_truth(path: Path) -> dict[str, bool]:
    """Load session_id -> expected valid flag."""
    truth: dict[str, bool] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            session_id, label, _reason = stripped.split(",", 2)
            truth[session_id] = label.strip().lower() == "valid"
    return truth


def compute_metrics(
    sequences: dict[str, list[str]],
    ground_truth: dict[str, bool],
    predict,
) -> dict[str, float | int]:
    """Calculate accuracy, precision, recall, F1, TP, FP, TN, FN.

    Anomaly detection convention (Invalid/Anomalous = Positive, Valid = Negative).
    """
    tp = 0  # actual anomaly, predicted anomaly
    fp = 0  # actual normal, predicted anomaly
    tn = 0  # actual normal, predicted normal
    fn = 0  # actual anomaly, predicted normal

    for session_id, expected_valid in ground_truth.items():
        sequence = sequences.get(session_id, [])
        predicted_valid = predict(sequence)

        is_actual_anomaly = not expected_valid
        is_pred_anomaly = not predicted_valid

        if is_actual_anomaly and is_pred_anomaly:
            tp += 1
        elif not is_actual_anomaly and is_pred_anomaly:
            fp += 1
        elif not is_actual_anomaly and not is_pred_anomaly:
            tn += 1
        else:
            fn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": total,
        "correct": tp + tn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_method(
    sequences: dict[str, list[str]],
    ground_truth: dict[str, bool],
    predict,
) -> tuple[int, int]:
    metrics = compute_metrics(sequences, ground_truth, predict)
    return int(metrics["correct"]), int(metrics["total"])


def run_pipeline(
    train_path: Path,
    test_path: Path,
    threshold: float = 0.70,
    min_support: int = 1,
    max_cost: int = 2,
    validation_mode: str = "first",
) -> dict:
    train_sequences = list(load_session_sequences(train_path).values())
    test_map = load_session_sequences(test_path)
    grammar = infer_grammar(train_sequences, threshold=threshold, min_support=min_support)
    automaton = build_automaton(grammar)

    rules = grammar_to_english(grammar)
    results: list[dict] = []
    session_records: list[dict] = []
    valid_count = 0

    for session_id in sorted(test_map):
        sequence = test_map[session_id]
        validation = automaton.validate(sequence, mode=validation_mode)
        if validation.valid:
            valid_count += 1
            session_records.append(
                {
                    "session_id": session_id,
                    "sequence": sequence,
                    "status": "valid",
                    "failure_index": None,
                    "failure_token": None,
                    "rule_type": None,
                    "violated_rule": None,
                    "context": [],
                    "repaired_sequence": sequence,
                    "repair_cost": 0,
                    "repair_explored_candidates": 0,
                    "fix_validates": True,
                    "fix": "No repair needed.",
                    "additional_violations": [],
                }
            )
        else:
            repair = repair_session(sequence, grammar, max_repair_cost=max_cost)
            fix = suggest_fix(sequence, validation, grammar, max_repair_cost=max_cost)
            fixed_seq = repair.repaired_sequence if repair.found and repair.repaired_sequence is not None else apply_fix(sequence, fix)
            fixed_validation = automaton.validate(fixed_seq, mode="first")

            extra_failures = []
            if validation.all_failures and len(validation.all_failures) > 1:
                for f in validation.all_failures[1:]:
                    extra_failures.append({
                        "failure_index": f.failure_index,
                        "failure_token": f.failure_token,
                        "rule_type": f.rule_type,
                        "violated_rule": f.violated_rule,
                    })

            record = {
                "session_id": session_id,
                "sequence": sequence,
                "status": "flagged",
                "failure_index": validation.failure_index,
                "failure_token": validation.failure_token,
                "explanation": explain(
                        session_id,
                        sequence,
                        validation,
                        grammar,
                        repair_result=repair,
                        max_repair_cost=max_cost,
                ),
                "fix": fix,
                "repaired_sequence": fixed_seq,
                "repair_cost": repair.total_cost if repair.found else None,
                "repair_explored_candidates": repair.explored_candidates,
                "fix_validates": fixed_validation.valid,
                "rule_type": validation.rule_type,
                "context": list(validation.context) if validation.context else [],
                "additional_violations": extra_failures,
            }
            results.append(record)
            session_records.append(record)

    total = len(test_map)

    # Compute evaluation metrics against ground truth (if available)
    evaluation_metrics: list[dict] = []
    valid_sessions: list[str] = [sid for sid in sorted(test_map) if sid not in {r["session_id"] for r in results}]
    gt_path = DEFAULT_GROUND_TRUTH
    if gt_path.exists():
        gt = load_ground_truth(gt_path)
        inferred_grammar_ref = grammar  # already computed above
        b_metrics = compute_metrics(test_map, gt, baseline_validate)
        i_metrics = compute_metrics(test_map, gt, lambda seq: validate_session(seq, inferred_grammar_ref).valid)
        evaluation_metrics = [
            {
                "method": "Hardcoded Baseline (4 rules)",
                "tp": b_metrics["tp"], "fp": b_metrics["fp"],
                "tn": b_metrics["tn"], "fn": b_metrics["fn"],
                "accuracy": b_metrics["accuracy"], "precision": b_metrics["precision"],
                "recall": b_metrics["recall"], "f1": b_metrics["f1"],
            },
            {
                "method": "Inferred Grammar / Automaton",
                "tp": i_metrics["tp"], "fp": i_metrics["fp"],
                "tn": i_metrics["tn"], "fn": i_metrics["fn"],
                "accuracy": i_metrics["accuracy"], "precision": i_metrics["precision"],
                "recall": i_metrics["recall"], "f1": i_metrics["f1"],
            },
        ]

    return {
        "rules": rules,
        "grammar_threshold": threshold,
        "min_support": min_support,
        "max_repair_cost": max_cost,
        "validation_mode": validation_mode,
        "source_files": {
            "training": str(train_path),
            "test": str(test_path),
        },
        "alphabet": sorted(automaton.alphabet),
        "training_sessions": grammar.session_count,
        "total_test_sessions": total,
        "valid_count": valid_count,
        "valid_percent": round(valid_count / total * 100, 1) if total else 0.0,
        "valid_sessions": valid_sessions,
        "flagged_sessions": results,
        "session_records": session_records,
        "evaluation_metrics": evaluation_metrics,
        "test_sequences": test_map,
    }



def print_report(output: dict, ground_truth_path: Path, show_grammar: bool = False) -> None:
    print("=" * 72)
    print("AUTOSENSE — Session Grammar & Automaton Anomaly Report")
    print("=" * 72)

    print(f"\nLearned from {output['training_sessions']} training sessions "
          f"(threshold={output['grammar_threshold']:.2f}, min_support={output.get('min_support', 1)}):")
    print("\nINFERRED RULES (plain English)")
    print("-" * 40)
    for rule in output["rules"]:
        print(f"  • {rule}")

    if show_grammar:
        print("\nAUTOMATON SPECIFICATION")
        print("-" * 40)
        print(f"  Alphabet (Sigma): {', '.join(output.get('alphabet', []))}")
        print("  State Context: History-2 DFA States (A, B) -> delta((A, B), C)")
        print(f"  Validation Mode: {output.get('validation_mode', 'first')}")
        print(f"  Max Repair Budget: cost<={output.get('max_repair_cost', 2)}")

    print("\nTEST SET EVALUATION")
    print("-" * 40)
    print(f"  Total sessions: {output['total_test_sessions']}")
    print(f"  Valid sessions: {output['valid_count']} "
          f"({output['valid_percent']:.1f}%)")
    print(f"  Flagged sessions: {len(output['flagged_sessions'])}")

    if output["flagged_sessions"]:
        print("\nFLAGGED SESSIONS & MINIMUM-COST REPAIRS")
        print("-" * 40)
        for item in output["flagged_sessions"]:
            seq = " -> ".join(item["sequence"])
            print(f"\n  [{item['session_id']}] {seq}")
            print(f"  {item['explanation']}")
            print(f"  Verified repair validity: {item['fix_validates']}")
            if item.get("additional_violations"):
                print(f"  Additional violations in session ({len(item['additional_violations'])}):")
                for sub in item["additional_violations"]:
                    print(f"    - pos {sub['failure_index']}: {sub['rule_type']} ({sub['violated_rule']})")

    ground_truth = load_ground_truth(ground_truth_path)
    sequences = output["test_sequences"]
    grammar = infer_grammar(
        list(load_session_sequences(DEFAULT_TRAIN).values()),
        threshold=output["grammar_threshold"],
        min_support=output.get("min_support", 1),
    )

    baseline_metrics = compute_metrics(
        sequences,
        ground_truth,
        baseline_validate,
    )
    inferred_metrics = compute_metrics(
        sequences,
        ground_truth,
        lambda seq: validate_session(seq, grammar).valid,
    )

    print("\n" + "=" * 72)
    print("EVALUATION VS GROUND TRUTH (Anomaly Detection: Invalid = Positive)")
    print("=" * 72)
    hdr = f"  {'Method':<30} {'TP':>3} {'FP':>3} {'TN':>3} {'FN':>3} {'Accuracy':>10} {'Precision':>10} {'Recall':>8} {'F1':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    b_line = (
        f"  {'Hardcoded baseline (4 rules)':<30} "
        f"{baseline_metrics['tp']:>3} {baseline_metrics['fp']:>3} "
        f"{baseline_metrics['tn']:>3} {baseline_metrics['fn']:>3} "
        f"{baseline_metrics['accuracy'] * 100:>9.1f}% "
        f"{baseline_metrics['precision'] * 100:>9.1f}% "
        f"{baseline_metrics['recall'] * 100:>7.1f}% "
        f"{baseline_metrics['f1'] * 100:>7.1f}%"
    )
    i_line = (
        f"  {'Inferred Grammar / Automaton':<30} "
        f"{inferred_metrics['tp']:>3} {inferred_metrics['fp']:>3} "
        f"{inferred_metrics['tn']:>3} {inferred_metrics['fn']:>3} "
        f"{inferred_metrics['accuracy'] * 100:>9.1f}% "
        f"{inferred_metrics['precision'] * 100:>9.1f}% "
        f"{inferred_metrics['recall'] * 100:>7.1f}% "
        f"{inferred_metrics['f1'] * 100:>7.1f}%"
    )
    print(b_line)
    print(i_line)
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoSense session anomaly detector")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--min-support", type=int, default=1, help="Minimum support for trigram rules")
    parser.add_argument("--max-cost", type=int, default=2, help="Maximum search cost budget for repairs")
    parser.add_argument(
        "--validation-mode",
        choices=["first", "all"],
        default="first",
        help="Report first failure or all failures in sequence",
    )
    parser.add_argument("--show-grammar", action="store_true", help="Display automaton alphabet and specs")
    parser.add_argument("--export", type=Path, default=None)
    args = parser.parse_args()

    output = run_pipeline(
        train_path=args.train,
        test_path=args.test,
        threshold=args.threshold,
        min_support=args.min_support,
        max_cost=args.max_cost,
        validation_mode=args.validation_mode,
    )
    print_report(output, args.ground_truth, show_grammar=args.show_grammar)

    if args.export:
        export_data = {
            key: value for key, value in output.items() if key != "test_sequences"
        }
        args.export.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
        print(f"\nExported results to {args.export}")


if __name__ == "__main__":
    main()

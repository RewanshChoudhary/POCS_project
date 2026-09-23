#!/usr/bin/env python3
"""Run the full AutoSense pipeline and print evaluation results."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from automaton import build_automaton
from explainer import apply_fix, explain, suggest_fix
from grammar_inference import grammar_to_english, infer_grammar
from probability_model import (
    build_probability_model,
    calculate_adaptive_threshold,
    is_anomalous,
    score_sessions,
)
from repair import repair_session
from session_extractor import load_session_sequences
from validator import validate_session

ROOT = Path(__file__).parent
DEFAULT_TRAIN = ROOT / "data" / "sample_logs.txt"
DEFAULT_TEST = ROOT / "data" / "test_logs.txt"
DEFAULT_GROUND_TRUTH = ROOT / "data" / "sample2_ground_truth.csv"


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
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0

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
        "false_positive_rate": false_positive_rate,
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
    alpha: float = 1.0,
    k: float = 3.0,
    ground_truth_path: Path | None = None,
) -> dict:
    """Run the full AutoSense detection pipeline.

    Hybrid detection policy
    -----------------------
        structural_anomaly = automaton_rejected
        statistical_anomaly = nll_score > adaptive_threshold
        final_anomaly       = structural_anomaly OR statistical_anomaly

    Parameters
    ----------
    train_path:      Log file for grammar inference and probability model training.
    test_path:       Log file for evaluation sessions.
    threshold:       Frequency threshold for grammar rule acceptance (0–1).
    min_support:     Minimum trigram context support for trigram rules to apply.
    max_cost:        Maximum UCS repair budget.
    validation_mode: 'first' or 'all' — how many violations to report.
    alpha:           Laplace smoothing parameter for transition probabilities.
    k:               Sensitivity multiplier for adaptive threshold (mean + k·σ).
    ground_truth_path: Optional labels used only for evaluation; never for training
                       or threshold calibration.
    """
    train_map = load_session_sequences(train_path)
    train_sequences = list(train_map.values())
    test_map = load_session_sequences(test_path)
    grammar = infer_grammar(train_sequences, threshold=threshold, min_support=min_support)
    automaton = build_automaton(grammar)

    # --- Statistical model: train on training data only ---
    prob_model = build_probability_model(grammar, alpha=alpha)
    train_scores_map = score_sessions(train_map, prob_model)
    train_scores_list = list(train_scores_map.values())
    adaptive_threshold = calculate_adaptive_threshold(train_scores_list, k=k)

    rules = grammar_to_english(grammar)
    results: list[dict] = []
    session_records: list[dict] = []
    valid_count = 0

    for session_id in sorted(test_map):
        sequence = test_map[session_id]
        validation = automaton.validate(sequence, mode=validation_mode)

        # Statistical scoring for this test session
        nll_score = prob_model.session_score(sequence)
        stat_flag = is_anomalous(nll_score, adaptive_threshold)
        top_surprises = prob_model.top_surprising_transitions(sequence, n=3)

        # Hybrid decision: automaton OR statistical
        structural_anomaly = not validation.valid
        final_anomaly = structural_anomaly or stat_flag

        if validation.valid:
            valid_count += 1
            session_records.append(
                {
                    "session_id": session_id,
                    "sequence": sequence,
                    "status": "valid" if not final_anomaly else "stat_flagged",
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
                    # Statistical fields
                    "anomaly_score": round(nll_score, 4),
                    "adaptive_threshold": round(adaptive_threshold, 4) if adaptive_threshold != float("inf") else None,
                    "statistical_anomaly": stat_flag,
                    "automaton_valid": True,
                    "final_anomaly": final_anomaly,
                    "top_surprising_transitions": top_surprises,
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
                # Statistical fields
                "anomaly_score": round(nll_score, 4),
                "adaptive_threshold": round(adaptive_threshold, 4) if adaptive_threshold != float("inf") else None,
                "statistical_anomaly": stat_flag,
                "automaton_valid": False,
                "final_anomaly": True,
                "top_surprising_transitions": top_surprises,
            }
            results.append(record)
            session_records.append(record)

    total = len(test_map)

    # Compute evaluation metrics against ground truth (if available)
    evaluation_metrics: list[dict] = []
    test_score_summary: dict[str, float | int | None] = {
        "normal_count": None,
        "anomalous_count": None,
        "mean_normal_nll": None,
        "mean_anomalous_nll": None,
    }
    valid_sessions: list[str] = [sid for sid in sorted(test_map) if sid not in {r["session_id"] for r in results}]
    gt_path = ground_truth_path or DEFAULT_GROUND_TRUTH
    if gt_path.exists():
        gt = load_ground_truth(gt_path)
        inferred_grammar_ref = grammar  # already computed above
        test_scores = score_sessions(test_map, prob_model)
        normal_scores = [test_scores[sid] for sid, valid in gt.items() if valid and sid in test_scores]
        anomalous_scores = [test_scores[sid] for sid, valid in gt.items() if not valid and sid in test_scores]
        test_score_summary = {
            "normal_count": len(normal_scores),
            "anomalous_count": len(anomalous_scores),
            "mean_normal_nll": round(sum(normal_scores) / len(normal_scores), 4) if normal_scores else None,
            "mean_anomalous_nll": round(sum(anomalous_scores) / len(anomalous_scores), 4) if anomalous_scores else None,
        }

        b_metrics = compute_metrics(test_map, gt, baseline_validate)
        i_metrics = compute_metrics(test_map, gt, lambda seq: validate_session(seq, inferred_grammar_ref).valid)

        # Statistical model: flag if NLL score > adaptive_threshold.  Score
        # directly from the sequence so identical sequences remain independent
        # evaluation examples rather than being matched to an arbitrary ID.
        def stat_predict(seq: list[str]) -> bool:
            return not is_anomalous(prob_model.session_score(seq), adaptive_threshold)
        s_metrics = compute_metrics(test_map, gt, stat_predict)

        # Hybrid: flag if automaton OR statistical
        def hybrid_predict(seq: list[str]) -> bool:
            struct_valid = validate_session(seq, inferred_grammar_ref).valid
            stat_valid = not is_anomalous(prob_model.session_score(seq), adaptive_threshold)
            return struct_valid and stat_valid

        h_metrics = compute_metrics(test_map, gt, hybrid_predict)

        evaluation_metrics = [
            {
                "method": "Hardcoded Baseline (4 rules)",
                "tp": b_metrics["tp"], "fp": b_metrics["fp"],
                "tn": b_metrics["tn"], "fn": b_metrics["fn"],
                "accuracy": b_metrics["accuracy"], "precision": b_metrics["precision"],
                "recall": b_metrics["recall"], "f1": b_metrics["f1"],
                "false_positive_rate": b_metrics["false_positive_rate"],
            },
            {
                "method": "Inferred Grammar / Automaton",
                "tp": i_metrics["tp"], "fp": i_metrics["fp"],
                "tn": i_metrics["tn"], "fn": i_metrics["fn"],
                "accuracy": i_metrics["accuracy"], "precision": i_metrics["precision"],
                "recall": i_metrics["recall"], "f1": i_metrics["f1"],
                "false_positive_rate": i_metrics["false_positive_rate"],
            },
            {
                "method": f"Statistical (1st-order Markov, α={alpha}, k={k})",
                "tp": s_metrics["tp"], "fp": s_metrics["fp"],
                "tn": s_metrics["tn"], "fn": s_metrics["fn"],
                "accuracy": s_metrics["accuracy"], "precision": s_metrics["precision"],
                "recall": s_metrics["recall"], "f1": s_metrics["f1"],
                "false_positive_rate": s_metrics["false_positive_rate"],
            },
            {
                "method": "Hybrid (Automaton OR Statistical)",
                "tp": h_metrics["tp"], "fp": h_metrics["fp"],
                "tn": h_metrics["tn"], "fn": h_metrics["fn"],
                "accuracy": h_metrics["accuracy"], "precision": h_metrics["precision"],
                "recall": h_metrics["recall"], "f1": h_metrics["f1"],
                "false_positive_rate": h_metrics["false_positive_rate"],
            },
        ]

    # Training score statistics for reporting
    if train_scores_list:
        train_mean = sum(train_scores_list) / len(train_scores_list)
        train_variance = sum((s - train_mean) ** 2 for s in train_scores_list) / len(train_scores_list)
        train_std = math.sqrt(train_variance)
    else:
        train_mean = train_std = 0.0

    return {
        "rules": rules,
        "grammar_threshold": threshold,
        "min_support": min_support,
        "max_repair_cost": max_cost,
        "validation_mode": validation_mode,
        "source_files": {
            "training": str(train_path),
            "test": str(test_path),
            "ground_truth": str(gt_path),
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
        "test_score_summary": test_score_summary,
        "test_sequences": test_map,
        # Statistical model configuration
        "probability_model_config": {
            "alpha": alpha,
            "k": k,
            "adaptive_threshold": round(adaptive_threshold, 4) if adaptive_threshold != float("inf") else None,
            "train_score_mean": round(train_mean, 4),
            "train_score_std": round(train_std, 4),
            "training_sessions_scored": len(train_scores_list),
        },
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

    # Statistical model configuration summary
    pm_cfg = output.get("probability_model_config", {})
    if pm_cfg:
        print("\nSTATISTICAL MODEL CONFIGURATION")
        print("-" * 40)
        print(f"  Smoothing (α):          {pm_cfg.get('alpha', 1.0)}")
        print(f"  Threshold sensitivity:  k = {pm_cfg.get('k', 3.0)}")
        thr = pm_cfg.get("adaptive_threshold")
        print(f"  Adaptive threshold (T): {thr if thr is not None else '∞ (no training scores)'}")
        print(f"  Training scores:        mean={pm_cfg.get('train_score_mean', 0):.4f}, "
              f"σ={pm_cfg.get('train_score_std', 0):.4f} "
              f"(n={pm_cfg.get('training_sessions_scored', 0)})")
        print("  Threshold formula:      T = mean + k × σ  (heuristic; assumes unimodal distribution)")

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
            # Statistical evidence
            score = item.get("anomaly_score")
            thr_val = item.get("adaptive_threshold")
            stat_flag = item.get("statistical_anomaly", False)
            if score is not None:
                thr_str = f"{thr_val:.4f}" if thr_val is not None else "∞"
                print(f"  Statistical: NLL score={score:.4f}  threshold={thr_str}  "
                      f"stat_anomaly={'YES' if stat_flag else 'no'}")
            if item.get("top_surprising_transitions"):
                print("  Most surprising transitions:")
                for tr in item["top_surprising_transitions"][:3]:
                    print(f"    pos {tr['position']}: {tr['previous_event']} → {tr['current_event']}  "
                          f"P={tr['transition_probability']:.4f}  surprise={tr['surprise']:.2f}  ({tr['reason']})")
            if item.get("additional_violations"):
                print(f"  Additional violations in session ({len(item['additional_violations'])}):")
                for sub in item["additional_violations"]:
                    print(f"    - pos {sub['failure_index']}: {sub['rule_type']} ({sub['violated_rule']})")

    if output["evaluation_metrics"]:
        print("\n" + "=" * 72)
        print("EVALUATION VS GROUND TRUTH (Anomaly Detection: Invalid = Positive)")
        print("=" * 72)
        col_w = 40
        hdr = f"  {'Method':<{col_w}} {'TP':>3} {'FP':>3} {'TN':>3} {'FN':>3} {'Accuracy':>10} {'Precision':>10} {'Recall':>8} {'F1':>8}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))

        def metric_line(name: str, m: dict) -> str:
            return (
                f"  {name:<{col_w}} "
                f"{m['tp']:>3} {m['fp']:>3} "
                f"{m['tn']:>3} {m['fn']:>3} "
                f"{m['accuracy'] * 100:>9.1f}% "
                f"{m['precision'] * 100:>9.1f}% "
                f"{m['recall'] * 100:>7.1f}% "
                f"{m['f1'] * 100:>7.1f}%"
            )

        for metrics in output["evaluation_metrics"]:
            print(metric_line(metrics["method"], metrics))
        print("=" * 72)
        score_summary = output.get("test_score_summary", {})
        if score_summary.get("mean_normal_nll") is not None:
            print("  Mean NLL by ground-truth label: "
                  f"normal={score_summary['mean_normal_nll']:.4f} "
                  f"anomalous={score_summary['mean_anomalous_nll']:.4f}")
    print("\nNOTE: Statistical model is a thresholding heuristic (mean + k·σ),")
    print("      not a calibrated risk score. Results depend on training data size.")
    print("      Hybrid policy: anomalous if structural OR statistical flag fires.")


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
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Laplace smoothing parameter α for transition probabilities (default: 1.0)",
    )
    parser.add_argument(
        "--k",
        type=float,
        default=3.0,
        help="Adaptive threshold sensitivity: T = mean + k × σ (default: 3.0)",
    )
    args = parser.parse_args()

    output = run_pipeline(
        train_path=args.train,
        test_path=args.test,
        threshold=args.threshold,
        min_support=args.min_support,
        max_cost=args.max_cost,
        validation_mode=args.validation_mode,
        alpha=args.alpha,
        k=args.k,
        ground_truth_path=args.ground_truth,
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

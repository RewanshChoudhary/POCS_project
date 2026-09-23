"""Turn validation failures into readable explanations and minimal fixes."""

from __future__ import annotations

import re

from grammar_inference import InferredGrammar, allowed_followers, allowed_starts
from validator import ValidationResult

from repair import RepairOperation, RepairResult, repair_session

INSERT_BEFORE = re.compile(r"^insert (\S+) before (\S+)$")
INSERT_AT = re.compile(r"^insert (\S+) at position (\d+)$")
APPEND = re.compile(r"^append (\S+)$")
REMOVE_AT = re.compile(r"^remove (\S+) at position (\d+)$")
REPLACE = re.compile(r"^replace (\S+) with (\S+)$")
REPLACE_AT = re.compile(r"^replace (\S+) with (\S+) at position (\d+)$")


def suggest_fix(
    sequence: list[str],
    result: ValidationResult,
    grammar: InferredGrammar,
    max_repair_cost: int = 2,
) -> str:
    """Propose a minimal corrective fix using search-based repair or structural heuristics."""
    if result.valid:
        return "No fix needed."

    # Try optimal bounded search-based repair first
    repair = repair_session(sequence, grammar, max_repair_cost=max_repair_cost)
    if repair.found and repair.operations:
        return "; ".join(str(op) for op in repair.operations)

    # Heuristic fallback if search budget exhausted
    if result.rule_type == "empty":
        starts = allowed_starts(grammar)
        start = starts[0] if starts else _top_token(grammar.start_rules)
        return f"insert {start} at position 0"

    if result.rule_type == "start" and result.failure_index == 0:
        starts = allowed_starts(grammar) or result.expected or []
        start = starts[0] if starts else _top_token(grammar.start_rules)
        return f"insert {start} at position 0"

    if result.rule_type in ("transition", "trigram_transition") and result.failure_index is not None:
        index = result.failure_index
        left = sequence[index - 1]
        followers = result.expected or allowed_followers(grammar, left) or []
        if followers:
            return f"insert {followers[0]} before {sequence[index]}"
        replacement = _top_token(grammar.bigram_rules.get(left, {}))
        return f"replace {sequence[index]} with {replacement}"

    if result.rule_type == "terminal" and result.failure_index is not None:
        return f"remove {result.failure_token} at position {result.failure_index}"

    if result.rule_type == "end":
        expected = result.expected or []
        end = expected[0] if expected else _top_token(grammar.end_rules)
        if end not in sequence:
            return f"append {end}"
        return f"remove {result.failure_token} at position {result.failure_index}"

    return "review session manually"


def apply_fix(sequence: list[str], fix: str) -> list[str]:
    """Apply a fix string or composite multi-edit repair to a sequence."""
    updated = sequence.copy()

    # Handle multiple operations separated by semicolon
    if ";" in fix:
        for part in fix.split(";"):
            updated = apply_fix(updated, part.strip())
        return updated

    match = INSERT_BEFORE.match(fix)
    if match:
        token, before = match.groups()
        if before in updated:
            index = updated.index(before)
            updated.insert(index, token)
        return updated

    match = INSERT_AT.match(fix)
    if match:
        token, position = match.groups()
        pos = int(position)
        updated.insert(min(pos, len(updated)), token)
        return updated

    match = APPEND.match(fix)
    if match:
        updated.append(match.group(1))
        return updated

    match = REMOVE_AT.match(fix)
    if match:
        token, position = match.groups()
        pos = int(position)
        if 0 <= pos < len(updated) and updated[pos] == token:
            updated.pop(pos)
        return updated

    match = REPLACE_AT.match(fix)
    if match:
        old, new, position = match.groups()
        pos = int(position)
        if 0 <= pos < len(updated) and updated[pos] == old:
            updated[pos] = new
        return updated

    match = REPLACE.match(fix)
    if match:
        old, new = match.groups()
        if old in updated:
            index = updated.index(old)
            updated[index] = new
        return updated

    return updated


def explain(
    session_id: str,
    sequence: list[str],
    result: ValidationResult,
    grammar: InferredGrammar,
    repair_result: RepairResult | None = None,
    max_repair_cost: int = 2,
) -> str:
    """Format a detailed human-readable explanation with context and minimum-cost repair."""
    if result.valid:
        return f"Session {session_id} VALID: {' -> '.join(sequence)}"

    if repair_result is None:
        repair_result = repair_session(sequence, grammar, max_repair_cost=max_repair_cost)

    expected_text = ", ".join(result.expected) if result.expected else "none"
    token = result.failure_token if result.failure_token is not None else "EMPTY"
    index = result.failure_index if result.failure_index is not None else 0
    ctx_text = f" [context: {' -> '.join(result.context)}]" if result.context else ""

    if repair_result.found and repair_result.operations:
        ops_text = "; ".join(str(op) for op in repair_result.operations)
        repair_msg = (
            f"Minimal fix (cost {repair_result.total_cost}, guaranteed minimum within search budget): "
            f"{ops_text} (yields: {' -> '.join(repair_result.repaired_sequence or [])})"
        )
    elif repair_result.found and not repair_result.operations:
        repair_msg = "No fix needed (already valid)."
    else:
        fallback_fix = suggest_fix(sequence, result, grammar, max_repair_cost=max_repair_cost)
        repair_msg = f"Minimal fix: {fallback_fix} ({repair_result.reason})."

    return (
        f"Session {session_id} INVALID at position {index} (token={token}){ctx_text}: "
        f'violated rule "{result.violated_rule}" (expected one of: {expected_text}). '
        f"{repair_msg}"
    )


def _top_token(freq_map: dict[str, float], preferred: list[str] | None = None) -> str:
    if preferred:
        return preferred[0]
    if not freq_map:
        return "LOGIN"
    return max(freq_map, key=freq_map.get)


if __name__ == "__main__":
    from pathlib import Path

    from grammar_inference import infer_grammar
    from session_extractor import load_session_sequences
    from validator import validate_session

    root = Path(__file__).parent
    grammar = infer_grammar(list(load_session_sequences(root / "data" / "sample_logs.txt").values()))
    sequences = load_session_sequences(root / "data" / "test_logs.txt")

    for session_id in ("T003", "T005", "T013"):
        sequence = sequences[session_id]
        result = validate_session(sequence, grammar)
        print(explain(session_id, sequence, result, grammar))


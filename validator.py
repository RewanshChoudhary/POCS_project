"""Validate session sequences against an inferred grammar."""

from __future__ import annotations

from dataclasses import dataclass

from grammar_inference import (
    InferredGrammar,
    allowed_ends,
    allowed_followers,
    allowed_starts,
    allowed_trigram_followers,
)


@dataclass
class ValidationResult:
    valid: bool
    failure_index: int | None = None
    failure_token: str | None = None
    violated_rule: str | None = None
    expected: list[str] | None = None
    rule_type: str | None = None
    context: tuple[str, ...] | None = None
    all_failures: list[ValidationResult] | None = None


def validate_session(
    sequence: list[str],
    grammar: InferredGrammar,
    mode: str = "first",
) -> ValidationResult:
    """Check a session against inferred start, context-aware trigram, bigram, and end rules.

    mode: 'first' returns immediate first failure; 'all' captures all violations across the sequence.
    Delegates to the deterministic finite automaton representation derived from grammar.
    """
    from automaton import Automaton

    return Automaton.from_grammar(grammar).validate(sequence, mode=mode)


if __name__ == "__main__":
    from pathlib import Path

    from session_extractor import load_session_sequences
    from grammar_inference import infer_grammar

    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    test = Path(__file__).parent / "data" / "test_logs.txt"
    grammar = infer_grammar(list(load_session_sequences(sample).values()))
    sequences = load_session_sequences(test)

    invalid = sequences.get("T003", ["VIEW", "EDIT", "LOGOUT"])
    result = validate_session(invalid, grammar)
    print(f"T003 valid={result.valid} index={result.failure_index} token={result.failure_token}")
    print(f"  rule: {result.violated_rule}")

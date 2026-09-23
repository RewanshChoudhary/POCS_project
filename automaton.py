"""Finite automaton representation generated from an inferred session grammar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from grammar_inference import (
    InferredGrammar,
    allowed_ends,
    allowed_followers,
    allowed_starts,
    allowed_trigram_followers,
)
from validator import ValidationResult

START_STATE: tuple[str, ...] = ("__START__",)


@dataclass
class Automaton:
    """Deterministic Finite Automaton representing an inferred session grammar.

    Formal Definition (Q, Sigma, delta, q0, F):
    - States (Q): Tuples representing historical context:
        * START_STATE: ("__START__",)
        * 1-event context: (A,)
        * 2-event context: (A, B)
    - Alphabet (Sigma): Set of valid event tokens learned from grammar.
    - Initial State (q0): START_STATE.
    - Accepting States (F): Any state whose most recent token is in allowed_ends.
    - Transition function (delta):
        * delta(START_STATE, A) = (A,) if A in allowed_starts
        * delta((A,), B) = (A, B) if B allowed after A
        * delta((A, B), C) = (B, C) if C allowed after context (A, B)
        * delta(state, C) = None if state ends in a terminal event
    - Determinism:
        Every (state, event) pair yields at most one deterministic next state.
    """

    grammar: InferredGrammar
    alphabet: set[str] = field(default_factory=set)
    initial_state: tuple[str, ...] = START_STATE
    _ends: set[str] = field(default_factory=set, init=False)
    _starts: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self._ends = set(allowed_ends(self.grammar))
        self._starts = set(allowed_starts(self.grammar))
        if not self.alphabet:
            self.alphabet = (
                set(self.grammar.start_rules)
                | set(self.grammar.end_rules)
                | set(self.grammar.bigram_rules)
                | {c for followers in self.grammar.bigram_rules.values() for c in followers}
            )

    @classmethod
    def from_grammar(cls, grammar: InferredGrammar) -> Automaton:
        """Construct an Automaton from an InferredGrammar."""
        return cls(grammar=grammar)

    def is_accepting(self, state: tuple[str, ...]) -> bool:
        """Check if a state is an accepting (final) state.

        Only non-initial states whose latest token is an allowed end token are accepting.
        """
        if not state or state == START_STATE:
            return False
        return state[-1] in self._ends

    def is_terminal(self, state: tuple[str, ...]) -> bool:
        """Check if state ends in a terminal event (which forbids further events)."""
        return self.is_accepting(state)

    def allowed_events(self, state: tuple[str, ...]) -> list[str]:
        """Compute the list of valid next events allowed from a given state."""
        if state == START_STATE:
            return sorted(self._starts)

        latest_token = state[-1]
        # Terminal states forbid any subsequent events
        if latest_token in self._ends:
            return []

        # If 2-event context is available (A, B)
        if len(state) >= 2:
            context = (state[-2], state[-1])
            support = self.grammar.trigram_support.get(context, 0)
            if support >= self.grammar.min_support:
                tri_followers = allowed_trigram_followers(self.grammar, context)
                if tri_followers:
                    return tri_followers

        # Bigram fallback
        followers = allowed_followers(self.grammar, latest_token)
        if followers:
            return followers

        # Unconstrained state: all non-terminal vocabulary plus terminal tokens
        return sorted(self.alphabet)

    def next_state(self, state: tuple[str, ...], event: str) -> tuple[str, ...] | None:
        """Transition function delta(state, event) -> next_state | None.

        Returns the new state if the event is permitted, or None if the transition is invalid.
        """
        if state == START_STATE:
            if self._starts and event not in self._starts:
                return None
            return (event,)

        left = state[-1]
        # Terminal check: no transitions out of terminal events
        if left in self._ends:
            return None

        # Contextual trigram check
        if len(state) >= 2:
            context = (state[-2], left)
            support = self.grammar.trigram_support.get(context, 0)
            if support >= self.grammar.min_support:
                tri_followers = allowed_trigram_followers(self.grammar, context)
                if tri_followers:
                    if event not in tri_followers:
                        return None
                    return (left, event)

        # Bigram fallback check
        followers = allowed_followers(self.grammar, left)
        if followers and event not in followers:
            return None

        return (left, event)

    def accepts(self, events: Sequence[str]) -> bool:
        """Return True if the sequence is accepted by the automaton into a final state."""
        if not events:
            return False

        current = self.initial_state
        for event in events:
            next_s = self.next_state(current, event)
            if next_s is None:
                return False
            current = next_s

        return self.is_accepting(current)

    def validate(self, events: Sequence[str], mode: str = "first") -> ValidationResult:
        """Validate sequence step-by-step and return structured failure details on rejection.

        mode: 'first' returns immediately on first failure; 'all' captures all violations.
        """
        if not events:
            return ValidationResult(
                valid=False,
                failure_index=0,
                failure_token=None,
                violated_rule="Session is empty.",
                expected=sorted(self._starts) or list(self.grammar.start_rules),
                rule_type="empty",
                context=(),
            )

        failures: list[ValidationResult] = []

        # 1. Start event
        if self._starts and events[0] not in self._starts:
            freq = self.grammar.start_rules.get(events[0], 0.0)
            res = ValidationResult(
                valid=False,
                failure_index=0,
                failure_token=events[0],
                violated_rule=(
                    f"{events[0]} starts only {freq * 100:.1f}% of training sessions "
                    f"(threshold {self.grammar.threshold * 100:.0f}%)."
                ),
                expected=sorted(self._starts),
                rule_type="start",
                context=(),
            )
            if mode == "first":
                return res
            failures.append(res)

        current = (events[0],)

        # 2. Sequence transitions
        for index in range(len(events) - 1):
            left = events[index]
            right = events[index + 1]

            # Terminal check
            if left in self._ends:
                freq = self.grammar.end_rules.get(left, 0.0)
                res = ValidationResult(
                    valid=False,
                    failure_index=index + 1,
                    failure_token=right,
                    violated_rule=(
                        f"{left} is a terminal event (ends {freq * 100:.1f}% of training "
                        f"sessions) but is followed by {right}."
                    ),
                    expected=[],
                    rule_type="terminal",
                    context=(left,),
                )
                if mode == "first":
                    return res
                failures.append(res)
                current = (left, right)
                continue

            # Context-aware trigram check
            trigram_checked = False
            if len(current) >= 2 or index >= 1:
                context = (events[index - 1], left)
                support = self.grammar.trigram_support.get(context, 0)
                if support >= self.grammar.min_support:
                    tri_followers = allowed_trigram_followers(self.grammar, context)
                    if tri_followers:
                        trigram_checked = True
                        if right not in tri_followers:
                            freq = self.grammar.trigram_rules.get(context, {}).get(right, 0.0)
                            res = ValidationResult(
                                valid=False,
                                failure_index=index + 1,
                                failure_token=right,
                                violated_rule=(
                                    f"After context {context[0]} -> {context[1]}, {right} appears next in only "
                                    f"{freq * 100:.1f}% of cases with support {support} "
                                    f"(threshold {self.grammar.threshold * 100:.0f}%, min_support {self.grammar.min_support})."
                                ),
                                expected=tri_followers,
                                rule_type="trigram_transition",
                                context=context,
                            )
                            if mode == "first":
                                return res
                            failures.append(res)

            # Bigram fallback check
            if not trigram_checked:
                followers = allowed_followers(self.grammar, left)
                if followers and right not in followers:
                    freq = self.grammar.bigram_rules.get(left, {}).get(right, 0.0)
                    res = ValidationResult(
                        valid=False,
                        failure_index=index + 1,
                        failure_token=right,
                        violated_rule=(
                            f"After {left}, {right} appears next in only {freq * 100:.1f}% "
                            f"of training sessions (threshold {self.grammar.threshold * 100:.0f}%)."
                        ),
                        expected=followers,
                        rule_type="transition",
                        context=(left,),
                    )
                    if mode == "first":
                        return res
                    failures.append(res)

            current = (left, right)

        # 3. End event
        last = events[-1]
        if self._ends and last not in self._ends:
            freq = self.grammar.end_rules.get(last, 0.0)
            res = ValidationResult(
                valid=False,
                failure_index=len(events) - 1,
                failure_token=last,
                violated_rule=(
                    f"{last} ends only {freq * 100:.1f}% of training sessions "
                    f"(threshold {self.grammar.threshold * 100:.0f}%)."
                ),
                expected=sorted(self._ends),
                rule_type="end",
                context=(last,),
            )
            if mode == "first":
                return res
            failures.append(res)

        if failures:
            primary = failures[0]
            return ValidationResult(
                valid=False,
                failure_index=primary.failure_index,
                failure_token=primary.failure_token,
                violated_rule=primary.violated_rule,
                expected=primary.expected,
                rule_type=primary.rule_type,
                context=primary.context,
                all_failures=failures,
            )

        return ValidationResult(valid=True)


def build_automaton(grammar: InferredGrammar) -> Automaton:
    """Build a deterministic finite automaton from an inferred grammar."""
    return Automaton.from_grammar(grammar)


if __name__ == "__main__":
    from pathlib import Path
    from session_extractor import load_session_sequences

    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    grammar = InferredGrammar(threshold=0.70)
    train_seqs = list(load_session_sequences(sample).values())
    grammar = InferredGrammar()
    from grammar_inference import infer_grammar
    grammar = infer_grammar(train_seqs, threshold=0.70)
    automaton = build_automaton(grammar)
    print(f"Automaton built with alphabet ({len(automaton.alphabet)} tokens): {sorted(automaton.alphabet)}")
    test_seq = ["LOGIN", "VIEW", "LOGOUT"]
    print(f"Accepts {test_seq}: {automaton.accepts(test_seq)}")

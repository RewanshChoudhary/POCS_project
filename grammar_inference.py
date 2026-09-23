"""Mine session grammar rules from training sequences via frequency counting."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from session_extractor import load_session_sequences


@dataclass
class InferredGrammar:
    start_rules: dict[str, float] = field(default_factory=dict)
    end_rules: dict[str, float] = field(default_factory=dict)
    bigram_rules: dict[str, dict[str, float]] = field(default_factory=dict)
    trigram_rules: dict[tuple[str, str], dict[str, float]] = field(default_factory=dict)
    trigram_support: dict[tuple[str, str], int] = field(default_factory=dict)
    trigram_counts: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    # Raw integer bigram counts {left: {right: count}} used by the probability
    # model to compute exact Laplace-smoothed transition probabilities.
    bigram_raw_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    threshold: float = 0.70
    min_support: int = 1
    session_count: int = 0

    @property
    def flat_trigram_rules(self) -> dict[tuple[str, str, str], float]:
        """Return (A, B, C) -> P(C | A, B) mapping for backwards compatibility."""
        return {
            (ctx[0], ctx[1], c): prob
            for ctx, followers in self.trigram_rules.items()
            for c, prob in followers.items()
        }

    def get_trigram_prob(self, a: str, b: str, c: str) -> float:
        """Query conditional probability P(C | A, B)."""
        return self.trigram_rules.get((a, b), {}).get(c, 0.0)


def infer_grammar(
    sequences: list[list[str]],
    threshold: float = 0.70,
    min_support: int = 1,
) -> InferredGrammar:
    """Derive grammar rules from observed session sequences.

    Counting behavior:
    1. Start rules: P(token is first event across non-empty sessions).
    2. End rules: P(token is last event across non-empty sessions).
    3. Terminal tokens: tokens with end frequency >= threshold are recognized as terminal.
       In training sequences, transitions following an observed terminal token are excluded
       to avoid silently counting invalid post-terminal transitions.
    4. Bigram rules: P(B | A) = count(A, B) / count(A with any valid successor).
    5. Trigram rules: P(C | A, B) = count((A, B), C) / count((A, B) with any valid successor).
       Preserves trigram support counts and transition counts for statistical inspection.
    """
    if not sequences:
        return InferredGrammar(threshold=threshold, min_support=min_support, session_count=0)

    valid_sequences = [seq for seq in sequences if seq]
    total = len(sequences)
    if not valid_sequences or total == 0:
        return InferredGrammar(threshold=threshold, min_support=min_support, session_count=total)

    start_counts: Counter[str] = Counter()
    end_counts: Counter[str] = Counter()

    for sequence in valid_sequences:
        start_counts[sequence[0]] += 1
        end_counts[sequence[-1]] += 1

    start_rules = {token: count / total for token, count in start_counts.items()}
    end_rules = {token: count / total for token, count in end_counts.items()}
    terminal_tokens = {token for token, freq in end_rules.items() if freq >= threshold}

    bigram_counts: dict[str, Counter[str]] = defaultdict(Counter)
    bigram_denoms: Counter[str] = Counter()
    trigram_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    trigram_support: Counter[tuple[str, str]] = Counter()

    for sequence in valid_sequences:
        # Avoid counting post-terminal transitions if terminal event appears earlier
        max_len = len(sequence)
        for idx, token in enumerate(sequence):
            if token in terminal_tokens:
                max_len = idx + 1
                break
        effective_seq = sequence[:max_len]

        # Bigram counts: P(B | A)
        for index in range(len(effective_seq) - 1):
            left, right = effective_seq[index], effective_seq[index + 1]
            bigram_counts[left][right] += 1
            bigram_denoms[left] += 1

        # Trigram counts: P(C | A, B) for sequences with at least 3 tokens
        for index in range(len(effective_seq) - 2):
            a = effective_seq[index]
            b = effective_seq[index + 1]
            c = effective_seq[index + 2]
            context = (a, b)
            trigram_counts[context][c] += 1
            trigram_support[context] += 1

    bigram_rules: dict[str, dict[str, float]] = {}
    for left, followers in bigram_counts.items():
        denom = bigram_denoms[left]
        bigram_rules[left] = {
            right: count / denom for right, count in followers.items()
        }

    trigram_rules: dict[tuple[str, str], dict[str, float]] = {}
    for context, followers in trigram_counts.items():
        denom = trigram_support[context]
        trigram_rules[context] = {
            c: count / denom for c, count in followers.items()
        }

    return InferredGrammar(
        start_rules=start_rules,
        end_rules=end_rules,
        bigram_rules=bigram_rules,
        trigram_rules=trigram_rules,
        trigram_support=dict(trigram_support),
        trigram_counts={ctx: dict(counts) for ctx, counts in trigram_counts.items()},
        bigram_raw_counts={left: dict(counts) for left, counts in bigram_counts.items()},
        threshold=threshold,
        min_support=min_support,
        session_count=total,
    )


def allowed_starts(grammar: InferredGrammar) -> list[str]:
    return sorted(
        token for token, freq in grammar.start_rules.items() if freq >= grammar.threshold
    )


def allowed_ends(grammar: InferredGrammar) -> list[str]:
    return sorted(
        token for token, freq in grammar.end_rules.items() if freq >= grammar.threshold
    )


def allowed_followers(grammar: InferredGrammar, token: str) -> list[str]:
    followers = grammar.bigram_rules.get(token, {})
    return sorted(
        follower for follower, freq in followers.items() if freq >= grammar.threshold
    )


def allowed_trigram_followers(grammar: InferredGrammar, context: tuple[str, str]) -> list[str]:
    """Return candidates C following context (A, B) that meet threshold and min_support."""
    if grammar.trigram_support.get(context, 0) < grammar.min_support:
        return []
    followers = grammar.trigram_rules.get(context, {})
    return sorted(
        follower for follower, freq in followers.items() if freq >= grammar.threshold
    )


def grammar_to_english(grammar: InferredGrammar) -> list[str]:
    """Convert inferred rules to plain-English sentences."""
    lines: list[str] = []
    pct = lambda value: round(value * 100, 1)

    for token in sorted(grammar.start_rules, key=grammar.start_rules.get, reverse=True):
        freq = grammar.start_rules[token]
        if freq >= grammar.threshold:
            lines.append(
                f"In {pct(freq)}% of sessions, {token} is the first event."
            )

    for left in sorted(grammar.bigram_rules):
        for right, freq in sorted(
            grammar.bigram_rules[left].items(), key=lambda item: item[1], reverse=True
        ):
            if freq >= grammar.threshold:
                lines.append(
                    f"After {left}, {right} appears next in {pct(freq)}% of cases."
                )

    for context in sorted(grammar.trigram_rules):
        support = grammar.trigram_support.get(context, 0)
        if support >= grammar.min_support:
            for right, freq in sorted(
                grammar.trigram_rules[context].items(), key=lambda item: item[1], reverse=True
            ):
                if freq >= grammar.threshold:
                    lines.append(
                        f"After {context[0]} -> {context[1]}, {right} appears next in {pct(freq)}% of cases (support={support})."
                    )

    for token in sorted(grammar.end_rules, key=grammar.end_rules.get, reverse=True):
        freq = grammar.end_rules[token]
        if freq >= grammar.threshold:
            lines.append(
                f"In {pct(freq)}% of sessions, {token} is the last event."
            )

    return lines


if __name__ == "__main__":
    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    sequences = list(load_session_sequences(sample).values())
    grammar = infer_grammar(sequences, threshold=0.70, min_support=1)
    print(f"Inferred from {grammar.session_count} training sessions (threshold=0.70, min_support=1):\n")
    for rule in grammar_to_english(grammar):
        print(f"  - {rule}")

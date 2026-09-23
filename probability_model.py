"""Smoothed probabilistic session model for statistical anomaly scoring.

Mathematical foundations
------------------------
This module implements three layered statistical techniques on top of the
existing frequency-based grammar inference:

1. **Laplace-smoothed transition probabilities** (additive smoothing):

       P(next | current) = (count(current, next) + α)
                           / (total_from_current  + α × |Σ|)

   Where α (alpha) is the smoothing parameter (default 1.0) and |Σ| is the
   vocabulary size.  Unseen transitions receive a small but finite probability.

2. **Negative log-likelihood (NLL) session score**:

       S(X) = -(1 / (n − 1)) × Σ_{t=2}^{n} log P(e_t | e_{t−1})

   Scores use natural logarithms.  Lower is more normal; higher is more
   surprising.  Single-event and empty sessions are handled safely.

3. **Adaptive anomaly threshold** (mean + k × population σ heuristic):

       T = mean(scores) + k × std_dev(scores)

   This is a thresholding *heuristic*, not a calibrated probability.  It works
   best when training-session score distribution is approximately bell-shaped.
   The parameter k (default 3.0) controls sensitivity; document any tuning.

These three components are kept in a single module to avoid spreading
probability logic across multiple files and to remain within the project's
six-core-module constraint.

Integration policy (hybrid detector)
-------------------------------------
    structural_anomaly = automaton_rejected
    statistical_anomaly = score > adaptive_threshold
    final_anomaly       = structural_anomaly OR statistical_anomaly

Neither detector is preferred; both provide complementary evidence.  The
combined decision is clearly labeled and does not imply malicious intent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from grammar_inference import InferredGrammar



def transition_probability(
    current_event: str,
    next_event: str,
    transition_counts: dict[str, dict[str, int]],
    event_types: list[str],
    alpha: float = 1.0,
) -> float:
    """Compute Laplace-smoothed conditional probability P(next | current).

    Formula
    -------
        P(next | current) = (count(current, next) + α)
                            / (Σ_c count(current, c) + α × |Σ|)

    Parameters
    ----------
    current_event:
        The preceding event token (conditioning context).
    next_event:
        The event whose probability is being estimated.
    transition_counts:
        Nested dict mapping current_event → {next_event: raw_count}.
        Typically sourced from InferredGrammar.bigram_counts-style counts.
    event_types:
        Complete vocabulary list Σ.  Must include every token that could
        appear as next_event.  An empty list is handled safely (returns 0).
    alpha:
        Smoothing parameter (α ≥ 0).  α = 0 gives unsmoothed MLE.
        α = 1 is Laplace (add-one) smoothing.

    Returns
    -------
    float in [0, 1].  Returns 0.0 when event_types is empty.

    Raises
    ------
    ValueError
        If alpha is negative.
    """
    if alpha < 0:
        raise ValueError(f"alpha must be non-negative, got {alpha}")

    vocab_size = len(event_types)
    if vocab_size == 0:
        return 0.0

    followers = transition_counts.get(current_event, {})
    raw_count = followers.get(next_event, 0)
    total_from_current = sum(followers.values())

    numerator = raw_count + alpha
    denominator = total_from_current + alpha * vocab_size

    if denominator == 0.0:
        # Degenerate: no observations and alpha=0 → undefined; return 0.
        return 0.0

    return numerator / denominator


# ---------------------------------------------------------------------------
# Per-transition surprise
# ---------------------------------------------------------------------------

def transition_surprise(
    current_event: str,
    next_event: str,
    prob_model: "SmoothedProbabilityModel",
) -> float:
    """Return − log P(next | current) using the smoothed model.

    Surprise is the information-theoretic contribution of a single transition.
    Higher values indicate lower probability (more surprising) transitions.

    Parameters
    ----------
    current_event, next_event:
        Token pair to evaluate.
    prob_model:
        An initialised SmoothedProbabilityModel instance.

    Returns
    -------
    float ≥ 0.  Protected against log(0) via the model's epsilon.
    """
    p = prob_model.transition_probability(current_event, next_event)
    p_safe = max(p, prob_model.epsilon)
    return -math.log(p_safe)


# ---------------------------------------------------------------------------
# Smoothed probability model class
# ---------------------------------------------------------------------------

@dataclass
class SmoothedProbabilityModel:
    """First-order Markov model with Laplace-smoothed transition probabilities.

    Built from the raw bigram counts extracted during grammar inference.
    Does not replace the existing automaton—provides complementary probabilistic
    evidence.

    Parameters
    ----------
    transition_counts:
        {current: {next: count}} — typically sourced from grammar's bigram
        counts (NOT the normalized frequencies; raw integers required).
    event_types:
        Vocabulary Σ.  All tokens that may appear as next_event.
    alpha:
        Laplace smoothing parameter α.  Default 1.0.
    epsilon:
        Floor probability for log(0) protection.  Default 1e-12.
    """

    transition_counts: dict[str, dict[str, int]]
    event_types: list[str]
    alpha: float = 1.0
    epsilon: float = 1e-12

    # Cache of computed probabilities to avoid recomputation
    _cache: dict[tuple[str, str], float] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.alpha < 0:
            raise ValueError(f"alpha must be non-negative, got {self.alpha}")
        if self.epsilon <= 0:
            raise ValueError(f"epsilon must be positive, got {self.epsilon}")

    def transition_probability(self, current_event: str, next_event: str) -> float:
        """Return P(next_event | current_event) with Laplace smoothing."""
        key = (current_event, next_event)
        if key not in self._cache:
            self._cache[key] = transition_probability(
                current_event,
                next_event,
                self.transition_counts,
                self.event_types,
                self.alpha,
            )
        return self._cache[key]

    def session_score(self, events: Sequence[str]) -> float:
        """Calculate the mean NLL anomaly score for an event sequence.

        Formula
        -------
            S(X) = -(1 / (n−1)) × Σ_{t=2}^{n} log P(e_t | e_{t−1})

        Parameters
        ----------
        events:
            Ordered list of event tokens.

        Returns
        -------
        float ≥ 0.  Returns 0.0 for sessions with fewer than 2 events.
        """
        return calculate_session_anomaly_score(events, self, self.epsilon)

    def top_surprising_transitions(
        self, events: Sequence[str], n: int = 3
    ) -> list[dict]:
        """Return the n most surprising (highest surprise) transitions.

        Each entry contains position, previous_event, current_event,
        transition_probability, and surprise score.  Useful for the
        explanation layer.
        """
        if len(events) < 2:
            return []

        surprises: list[dict] = []
        for i in range(1, len(events)):
            prev = events[i - 1]
            curr = events[i]
            p = self.transition_probability(prev, curr)
            s = -math.log(max(p, self.epsilon))
            surprises.append(
                {
                    "position": i,
                    "previous_event": prev,
                    "current_event": curr,
                    "transition_probability": round(p, 6),
                    "surprise": round(s, 4),
                    "reason": _surprise_reason(p),
                }
            )

        surprises.sort(key=lambda x: x["surprise"], reverse=True)
        return surprises[:n]


def _surprise_reason(p: float) -> str:
    """Label a transition probability with a human-readable reason."""
    if p < 0.01:
        return "Very low-probability transition"
    if p < 0.10:
        return "Low-probability transition"
    if p < 0.30:
        return "Below-average probability transition"
    return "Expected transition"


# ---------------------------------------------------------------------------
# Session anomaly scoring
# ---------------------------------------------------------------------------

def calculate_session_anomaly_score(
    events: Sequence[str],
    prob_model: SmoothedProbabilityModel,
    epsilon: float = 1e-12,
) -> float:
    """Calculate mean negative log-likelihood (NLL) score for a session.

    Formula
    -------
        S(X) = -(1 / (n−1)) × Σ_{t=2}^{n} log P(e_t | e_{t−1})

    Interpretation
    --------------
    Lower score → sequence is more probable under the trained model.
    Higher score → sequence is statistically surprising.

    This is NOT a probability of malicious activity.  It is a statistical
    measure of how unusual the sequence is relative to training data.

    Parameters
    ----------
    events:
        Ordered token sequence.  Fewer than 2 events returns 0.0.
    prob_model:
        A SmoothedProbabilityModel instance.
    epsilon:
        Floor for log(0) protection.  Should be very small (default 1e-12).

    Returns
    -------
    float ≥ 0.
    """
    if not events or len(events) < 2:
        return 0.0

    total_surprise = 0.0
    n_transitions = len(events) - 1

    for i in range(1, len(events)):
        p = prob_model.transition_probability(events[i - 1], events[i])
        p_safe = max(p, epsilon)
        total_surprise += -math.log(p_safe)

    return total_surprise / n_transitions


# ---------------------------------------------------------------------------
# Adaptive threshold
# ---------------------------------------------------------------------------

def calculate_adaptive_threshold(
    normal_scores: list[float],
    k: float = 3.0,
) -> float:
    """Compute anomaly threshold as mean + k × population standard deviation.

    Formula
    -------
        mean   = Σ scores / m
        σ      = sqrt( Σ (score − mean)² / m )
        T      = mean + k × σ

    Statistical note
    ----------------
    This is a thresholding *heuristic*, not a statistically rigorous anomaly
    detector.  The assumption is that normal-session scores are approximately
    unimodal.  On very small datasets or highly skewed distributions this
    heuristic may be unreliable.  Always report actual evaluation results.

    Parameters
    ----------
    normal_scores:
        NLL scores computed ONLY from training/calibration sessions—NOT from
        test sessions.  Must not contain any test-set scores to avoid leakage.
    k:
        Sensitivity multiplier.  Larger k → fewer false positives,
        potentially more false negatives.  Default 3.0.

    Returns
    -------
    float.  Returns +inf if normal_scores is empty (no false positives
    possible when no normal baseline exists).  Returns the single score
    value when normal_scores has exactly one entry (σ=0 → threshold = mean).

    Raises
    ------
    ValueError
        If k is negative.
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")

    if not normal_scores:
        # No calibration data: cannot determine threshold; return +inf so no
        # statistical flags fire (conservative fallback).
        return math.inf

    m = len(normal_scores)
    mean = sum(normal_scores) / m

    # Population standard deviation (not sample, as we're describing training data)
    variance = sum((s - mean) ** 2 for s in normal_scores) / m
    std_dev = math.sqrt(variance)

    return mean + k * std_dev


def is_anomalous(score: float, threshold: float) -> bool:
    """Return True if score strictly exceeds the threshold.

    A score exactly equal to the threshold is NOT flagged (documented choice:
    the boundary is normal, consistent with the strict inequality convention).
    """
    return score > threshold


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def build_probability_model(
    grammar: InferredGrammar,
    alpha: float = 1.0,
    epsilon: float = 1e-12,
) -> SmoothedProbabilityModel:
    """Construct a SmoothedProbabilityModel from an InferredGrammar.

    Reuses the raw bigram transition counts stored in grammar.bigram_rules
    (which are normalised frequencies).  We reconstruct raw counts using the
    stored trigram_support denominator for bigrams, or fall back to inferring
    counts from the normalised values.

    Design choice: we store counts in grammar_inference via bigram_counts
    (which is a private defaultdict inside infer_grammar).  Since we cannot
    access those directly without a refactor, we use an approximation:
    reconstruct integer counts from the stored frequency values × denominator.
    The vocabulary is derived from the full grammar alphabet.

    Parameters
    ----------
    grammar:
        Fully initialised InferredGrammar (output of infer_grammar()).
    alpha:
        Laplace smoothing parameter.
    epsilon:
        Floor for log(0) protection.

    Returns
    -------
    SmoothedProbabilityModel ready for scoring.
    """
    # Derive vocabulary from all tokens seen anywhere in the grammar
    vocab_set: set[str] = (
        set(grammar.start_rules)
        | set(grammar.end_rules)
        | set(grammar.bigram_rules)
        | {c for followers in grammar.bigram_rules.values() for c in followers}
    )
    event_types = sorted(vocab_set)

    # Prefer exact integer counts stored in grammar.bigram_raw_counts.
    # Fall back to reconstruction from normalised bigram_rules if not present
    # (backwards compatibility with grammars built before this field existed).
    if grammar.bigram_raw_counts:
        transition_counts: dict[str, dict[str, int]] = {
            left: dict(counts)
            for left, counts in grammar.bigram_raw_counts.items()
        }
    else:
        # Heuristic reconstruction: estimate raw counts from normalised
        # frequencies by finding the smallest integer denominator.
        transition_counts = {}
        for left, followers in grammar.bigram_rules.items():
            if not followers:
                continue
            min_freq = min(followers.values())
            if min_freq <= 0:
                continue
            raw: dict[str, int] = {}
            for right, freq in followers.items():
                raw[right] = max(1, round(freq / min_freq))
            transition_counts[left] = raw

    return SmoothedProbabilityModel(
        transition_counts=transition_counts,
        event_types=event_types,
        alpha=alpha,
        epsilon=epsilon,
    )


# ---------------------------------------------------------------------------
# Convenience: score a mapping of sessions
# ---------------------------------------------------------------------------

def score_sessions(
    sequences: dict[str, list[str]],
    prob_model: SmoothedProbabilityModel,
) -> dict[str, float]:
    """Score every session in sequences, returning {session_id: nll_score}.

    Parameters
    ----------
    sequences:
        Mapping from session_id to event token list.
    prob_model:
        Initialised SmoothedProbabilityModel.

    Returns
    -------
    dict mapping session_id → NLL score.
    """
    return {
        session_id: prob_model.session_score(seq)
        for session_id, seq in sequences.items()
    }


if __name__ == "__main__":
    from pathlib import Path

    from grammar_inference import infer_grammar
    from session_extractor import load_session_sequences

    root = Path(__file__).parent
    train_seqs = load_session_sequences(root / "data" / "sample_logs.txt")
    grammar = infer_grammar(list(train_seqs.values()), threshold=0.70, min_support=1)

    model = build_probability_model(grammar, alpha=1.0)
    print(f"Vocabulary ({len(model.event_types)} tokens): {model.event_types}")
    print(f"\nP(VIEW | LOGIN)   = {model.transition_probability('LOGIN', 'VIEW'):.4f}")
    print(f"P(LOGOUT | VIEW)  = {model.transition_probability('VIEW', 'LOGOUT'):.4f}")
    print(f"P(LOGIN | LOGOUT) = {model.transition_probability('LOGOUT', 'LOGIN'):.4f} (post-terminal, should be low)")

    # Score some sessions
    normal = ["LOGIN", "VIEW", "LOGOUT"]
    anomalous = ["VIEW", "EDIT", "LOGOUT"]
    print(f"\nNLL score (normal)    {normal}: {calculate_session_anomaly_score(normal, model):.4f}")
    print(f"NLL score (anomalous) {anomalous}: {calculate_session_anomaly_score(anomalous, model):.4f}")

    # Adaptive threshold from training data
    train_scores = [model.session_score(seq) for seq in train_seqs.values()]
    threshold = calculate_adaptive_threshold(train_scores, k=3.0)
    print(f"\nAdaptive threshold (k=3.0): {threshold:.4f}")
    for sid, score in [("normal", model.session_score(normal)), ("anomalous", model.session_score(anomalous))]:
        flag = "ANOMALOUS" if is_anomalous(score, threshold) else "normal"
        print(f"  {sid}: score={score:.4f}  → {flag}")

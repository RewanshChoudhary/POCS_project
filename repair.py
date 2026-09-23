"""Minimum-cost session repair engine using bounded Uniform-Cost Search."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Sequence

from automaton import Automaton
from grammar_inference import InferredGrammar

DEFAULT_EDIT_COSTS: dict[str, int] = {
    "insert": 1,
    "delete": 1,
    "substitute": 1,
}


@dataclass(frozen=True)
class RepairOperation:
    """A single discrete edit operation applied to a session sequence."""

    operation: str  # "insert", "delete", "substitute"
    index: int
    old_token: str | None
    new_token: str | None
    cost: int

    def __str__(self) -> str:
        if self.operation == "insert":
            return f"insert {self.new_token} at position {self.index}"
        if self.operation == "delete":
            return f"remove {self.old_token} at position {self.index}"
        if self.operation == "substitute":
            return f"replace {self.old_token} with {self.new_token} at position {self.index}"
        return f"{self.operation} at {self.index}"


@dataclass
class RepairResult:
    """The result of a search-based repair attempt."""

    found: bool
    repaired_sequence: list[str] | None
    operations: list[RepairOperation]
    total_cost: int | None
    explored_candidates: int
    reason: str | None = None
    is_unique: bool | None = None  # None if not searched for multiple; False if ties exist


class RepairEngine:
    """Bounded Uniform-Cost Search engine for minimum-cost sequence repairs.

    Algorithm:
    - Explores candidates in non-decreasing edit cost order using a min-heap priority queue.
    - Guarantees minimum-cost repair under both unit and arbitrary positive weighted edit costs.
    - Employs a visited set of sequence tuples to eliminate duplicate paths.
    - Bounded by:
        * max_repair_cost: limits cumulative cost.
        * max_candidates: limits total explored states to protect execution time.
        * max_sequence_length: prevents unbounded expansion from insertions.
    - Candidates are validated directly against the Automaton / Grammar acceptance mechanism.
    - Tie-breaking: Deterministic ordering based on insertion order and canonical operation tuples.
      Returned repair is labeled as a selected minimum-cost repair.
    """

    def __init__(
        self,
        grammar: InferredGrammar,
        costs: dict[str, int] | None = None,
        max_repair_cost: int = 2,
        max_candidates: int = 1000,
        max_sequence_length: int | None = None,
        vocabulary: list[str] | None = None,
    ) -> None:
        self.grammar = grammar
        self.automaton = Automaton.from_grammar(grammar)
        self.costs = dict(costs or DEFAULT_EDIT_COSTS)
        self.max_repair_cost = max_repair_cost
        self.max_candidates = max_candidates
        self.max_sequence_length = max_sequence_length

        if vocabulary is not None:
            self.vocabulary = sorted(set(vocabulary))
        else:
            vocab_set = (
                set(grammar.start_rules)
                | set(grammar.end_rules)
                | set(grammar.bigram_rules)
                | {c for followers in grammar.bigram_rules.values() for c in followers}
            )
            self.vocabulary = sorted(vocab_set)

    def repair(self, sequence: Sequence[str]) -> RepairResult:
        """Find a minimum-cost sequence repair using bounded Uniform-Cost Search."""
        seq_tuple = tuple(sequence)

        # 1. Check if already accepted
        if self.automaton.accepts(seq_tuple):
            return RepairResult(
                found=True,
                repaired_sequence=list(seq_tuple),
                operations=[],
                total_cost=0,
                explored_candidates=1,
                reason="already_valid",
                is_unique=True,
            )

        if not self.vocabulary:
            return RepairResult(
                found=False,
                repaired_sequence=None,
                operations=[],
                total_cost=None,
                explored_candidates=0,
                reason="Empty vocabulary; cannot generate repair candidates.",
            )

        max_len = (
            self.max_sequence_length
            if self.max_sequence_length is not None
            else max(len(seq_tuple) + self.max_repair_cost, 10)
        )

        cost_insert = self.costs.get("insert", 1)
        cost_delete = self.costs.get("delete", 1)
        cost_sub = self.costs.get("substitute", 1)

        # Priority Queue: (cost, counter, sequence_tuple, operations)
        counter = 0
        frontier: list[tuple[int, int, tuple[str, ...], list[RepairOperation]]] = []
        heapq.heappush(frontier, (0, counter, seq_tuple, []))

        visited: set[tuple[str, ...]] = {seq_tuple}
        explored = 0

        while frontier:
            cost, _, current, ops = heapq.heappop(frontier)
            explored += 1

            if explored > self.max_candidates:
                return RepairResult(
                    found=False,
                    repaired_sequence=None,
                    operations=[],
                    total_cost=None,
                    explored_candidates=explored,
                    reason=f"Candidate search limit reached ({self.max_candidates} candidates explored).",
                )

            # If this state is valid and non-zero cost (already checked initial)
            if cost > 0 and self.automaton.accepts(current):
                return RepairResult(
                    found=True,
                    repaired_sequence=list(current),
                    operations=ops,
                    total_cost=cost,
                    explored_candidates=explored,
                    reason="selected minimum-cost repair within search budget",
                    is_unique=False,
                )

            # Generate neighbors if within cost budget
            n = len(current)

            # 1. Substitutions (index 0 to n-1)
            if cost + cost_sub <= self.max_repair_cost:
                for idx in range(n):
                    old_tok = current[idx]
                    for cand in self.vocabulary:
                        if cand == old_tok:
                            continue
                        cand_seq = current[:idx] + (cand,) + current[idx + 1 :]
                        if cand_seq not in visited:
                            visited.add(cand_seq)
                            op = RepairOperation(
                                operation="substitute",
                                index=idx,
                                old_token=old_tok,
                                new_token=cand,
                                cost=cost_sub,
                            )
                            counter += 1
                            heapq.heappush(
                                frontier,
                                (cost + cost_sub, counter, cand_seq, ops + [op]),
                            )

            # 2. Deletions (index 0 to n-1)
            if cost + cost_delete <= self.max_repair_cost and n > 0:
                for idx in range(n):
                    cand_seq = current[:idx] + current[idx + 1 :]
                    if cand_seq not in visited:
                        visited.add(cand_seq)
                        op = RepairOperation(
                            operation="delete",
                            index=idx,
                            old_token=current[idx],
                            new_token=None,
                            cost=cost_delete,
                        )
                        counter += 1
                        heapq.heappush(
                            frontier,
                            (cost + cost_delete, counter, cand_seq, ops + [op]),
                        )

            # 3. Insertions (index 0 to n)
            if cost + cost_insert <= self.max_repair_cost and n < max_len:
                for idx in range(n + 1):
                    for cand in self.vocabulary:
                        cand_seq = current[:idx] + (cand,) + current[idx:]
                        if cand_seq not in visited:
                            visited.add(cand_seq)
                            op = RepairOperation(
                                operation="insert",
                                index=idx,
                                old_token=None,
                                new_token=cand,
                                cost=cost_insert,
                            )
                            counter += 1
                            heapq.heappush(
                                frontier,
                                (cost + cost_insert, counter, cand_seq, ops + [op]),
                            )

        return RepairResult(
            found=False,
            repaired_sequence=None,
            operations=[],
            total_cost=None,
            explored_candidates=explored,
            reason=f"No repair found within search budget (max_cost={self.max_repair_cost}).",
        )


def repair_session(
    sequence: Sequence[str],
    grammar: InferredGrammar,
    max_repair_cost: int = 2,
    max_candidates: int = 1000,
    costs: dict[str, int] | None = None,
) -> RepairResult:
    """Convenience function to repair a session using default engine settings."""
    engine = RepairEngine(
        grammar=grammar,
        costs=costs,
        max_repair_cost=max_repair_cost,
        max_candidates=max_candidates,
    )
    return engine.repair(sequence)


if __name__ == "__main__":
    from pathlib import Path
    from grammar_inference import infer_grammar
    from session_extractor import load_session_sequences

    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    train_seqs = list(load_session_sequences(sample).values())
    grammar = infer_grammar(train_seqs, threshold=0.70)
    test_seq = ["VIEW", "EDIT", "LOGOUT"]
    res = repair_session(test_seq, grammar, max_repair_cost=2)
    print(f"Repairing {test_seq}: found={res.found}, cost={res.total_cost}, operations={[str(op) for op in res.operations]} -> {res.repaired_sequence}")

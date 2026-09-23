"""Group tokens into ordered session event sequences."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tokenizer import tokenize_file


def extract_sessions(tokens: list[dict]) -> dict[str, list[dict]]:
    """Group tokens by session ID, ordered by timestamp then file order."""
    grouped: dict[str, list[tuple[str, int, dict]]] = defaultdict(list)
    for index, token in enumerate(tokens):
        grouped[token["session"]].append((token["timestamp"], index, token))

    sessions: dict[str, list[dict]] = {}
    for session_id, entries in grouped.items():
        entries.sort(key=lambda item: (item[0], item[1]))
        sessions[session_id] = [entry[2] for entry in entries]
    return sessions


def sessions_to_sequences(sessions: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Convert session token lists to event-type sequences."""
    return {
        session_id: [token["event"] for token in token_list]
        for session_id, token_list in sessions.items()
    }


def load_session_sequences(path: str | Path) -> dict[str, list[str]]:
    """Load a log file and return session event sequences."""
    tokens = tokenize_file(path)
    sessions = extract_sessions(tokens)
    return sessions_to_sequences(sessions)


if __name__ == "__main__":
    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    sequences = load_session_sequences(sample)
    for session_id in sorted(sequences)[:3]:
        print(f"{session_id}: {' -> '.join(sequences[session_id])}")

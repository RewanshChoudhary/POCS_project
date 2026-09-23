"""Convert raw log lines into structured event tokens."""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\S+)\s+session=(?P<session>\S+)\s+event=(?P<event>\S+)(?:\s+(?P<extra>.+))?$"
)
FIELD_PATTERN = re.compile(r"(\w+)=(\S+)")


def tokenize_line(line: str) -> dict | None:
    """Parse one log line into a token dict, or None if malformed."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    match = LINE_PATTERN.match(stripped)
    if not match:
        print(f"Warning: skipping malformed line: {stripped}", file=sys.stderr)
        return None

    fields: dict[str, str] = {
        "timestamp": match.group("timestamp"),
        "session": match.group("session"),
        "event": match.group("event"),
    }
    extra = match.group("extra")
    if extra:
        for key, value in FIELD_PATTERN.findall(extra):
            fields[key] = value
    return fields


def tokenize_file(path: str | Path) -> list[dict]:
    """Parse all lines in a log file, preserving file order."""
    tokens: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            token = tokenize_line(line)
            if token is not None:
                tokens.append(token)
    return tokens


if __name__ == "__main__":
    sample = Path(__file__).parent / "data" / "sample_logs.txt"
    for token in tokenize_file(sample)[:5]:
        print(f"({token['event']}, {token['session']})")

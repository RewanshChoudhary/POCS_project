#!/usr/bin/env python3
"""
Generate large synthetic log files for AutoSense.
  data/sample_logs.txt  — 150 valid training sessions  (S001–S150)
  data/test_logs.txt    — 61 test sessions, including one very long session (T001–T061)
  data/ground_truth.txt — answer key for the 61 test sessions
"""

from __future__ import annotations
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

ACTIONS = ["VIEW", "EDIT", "DELETE"]
USERS = [
    "alice", "bob", "carol", "dave", "eve", "frank", "grace", "henry",
    "iris", "jack", "kate", "leo", "mia", "nick", "olivia", "paul",
    "quinn", "rose", "sam", "tina", "uma", "victor", "wendy", "xavier",
    "yara", "zack", "amy", "ben", "cara", "dan", "ella", "fay", "gus",
    "hana", "ivan", "julia", "kevin", "laura", "mike", "nora", "oscar",
    "petra", "rob", "sara", "tim", "ursula", "vera", "will", "xena",
    "yen", "zeus", "ada", "bram", "cleo", "dean", "esme", "finn",
    "greta", "hugo", "ida", "joel",
]
PAGES = [
    "home", "dashboard", "profile", "reports", "settings", "feed", "map",
    "calendar", "admin", "logs", "stats", "doc", "archive", "items",
    "search", "preview", "config", "form", "task", "note", "route",
    "summary", "users", "filter", "post", "event", "bio", "sheet",
    "draft", "cache", "spam", "temp", "old", "log",
]

BASE_TIME = datetime(2024, 1, 15, 8, 0, 0)


def ts(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def pick_user(i: int) -> str:
    return USERS[i % len(USERS)]


def pick_page() -> str:
    return random.choice(PAGES)


# ─── Training sessions (all valid) ────────────────────────────────────────────
def gen_training_session(idx: int, start: datetime) -> tuple[list[str], datetime]:
    sid = f"S{idx:03d}"
    user = pick_user(idx)
    t = start
    lines: list[str] = []

    lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}")
    t += timedelta(seconds=random.randint(2, 5))

    # Choose a body pattern
    pattern = random.choices(
        ["single", "two", "three", "vev", "ede", "vve", "ved", "dee", "evd", "vvv", "eve", "edd"],
        weights=      [15,     20,     15,     8,    6,    6,    6,    5,    5,    4,    5,    5],
    )[0]

    if pattern == "single":
        action = random.choice(ACTIONS)
        lines.append(f"{ts(t)} session={sid} event={action} page={pick_page()}")
        t += timedelta(seconds=random.randint(3, 8))
    elif pattern == "two":
        a1, a2 = random.choice(ACTIONS), random.choice(ACTIONS)
        for a in [a1, a2]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "three":
        for _ in range(3):
            lines.append(f"{ts(t)} session={sid} event={random.choice(ACTIONS)} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 6))
    elif pattern == "vev":
        for a in ["VIEW", "EDIT", "VIEW"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "ede":
        for a in ["EDIT", "DELETE", "EDIT"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "vve":
        for a in ["VIEW", "VIEW", "EDIT"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "ved":
        for a in ["VIEW", "EDIT", "DELETE"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "dee":
        for a in ["DELETE", "EDIT", "EDIT"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "evd":
        for a in ["EDIT", "VIEW", "DELETE"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "vvv":
        for _ in range(3):
            lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "eve":
        for a in ["EDIT", "VIEW", "EDIT"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))
    elif pattern == "edd":
        for a in ["EDIT", "DELETE", "DELETE"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}")
            t += timedelta(seconds=random.randint(3, 7))

    lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}")
    t += timedelta(seconds=random.randint(5, 15))
    return lines, t


# ─── Test sessions ─────────────────────────────────────────────────────────────
# Anomaly catalogue:
#   start   — starts without LOGIN (VIEW/EDIT/DELETE/LOGOUT first)
#   end     — missing LOGOUT (truncated)
#   terminal — double LOGOUT or action after LOGOUT
#   transition — rare mid-sequence transition
#   valid   — totally normal

def make_test_session(idx: int, kind: str, start: datetime) -> tuple[list[str], datetime, str, str]:
    """Returns (lines, next_start, truth_label, reason)."""
    sid = f"T{idx:03d}"
    user = pick_user(idx + 100)
    t = start
    lines: list[str] = []

    if kind == "valid_simple":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->VIEW->LOGOUT session"

    elif kind == "valid_edit":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->EDIT->LOGOUT session"

    elif kind == "valid_delete":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->DELETE->LOGOUT session"

    elif kind == "valid_long":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        for a in ["VIEW", "EDIT", "DELETE"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->VIEW->EDIT->DELETE->LOGOUT session"

    elif kind == "valid_ve":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->VIEW->EDIT->LOGOUT session"

    elif kind == "valid_vve":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        for a in ["VIEW", "VIEW", "EDIT"]:
            lines.append(f"{ts(t)} session={sid} event={a} page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->VIEW->VIEW->EDIT->LOGOUT session"

    elif kind == "valid_ed":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "normal LOGIN->EDIT->DELETE->LOGOUT session"

    elif kind == "valid_very_long":
        # Deliberately long normal session for scale and UI testing.
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        for event_index in range(120):
            lines.append(
                f"{ts(t)} session={sid} event=VIEW page=activity-{event_index:03d}"
            )
            t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "valid", "very long 122-event LOGIN->VIEW*->LOGOUT session"

    elif kind == "no_login_view":
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGIN (starts with VIEW)"

    elif kind == "no_login_edit":
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGIN (starts with EDIT)"

    elif kind == "no_login_delete":
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGIN (starts with DELETE)"

    elif kind == "no_login_logout":
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "single LOGOUT without LOGIN"

    elif kind == "no_logout":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGOUT (truncated session)"

    elif kind == "no_logout_edit":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGOUT (truncated after EDIT)"

    elif kind == "no_logout_bare":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        t += timedelta(seconds=7)
        label, reason = "invalid", "missing LOGOUT (only LOGIN in session)"

    elif kind == "double_logout":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "double LOGOUT"

    elif kind == "after_logout_view":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=7)
        label, reason = "invalid", "action after LOGOUT (VIEW appended)"

    elif kind == "after_logout_edit":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=7)
        label, reason = "invalid", "action after LOGOUT (EDIT appended)"

    elif kind == "after_logout_delete":
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=7)
        label, reason = "invalid", "action after LOGOUT (DELETE appended)"

    elif kind == "rare_del_view":
        # LOGIN->DELETE->VIEW->LOGOUT — DELETE->VIEW is rare in training
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "DELETE->VIEW trigram violation (rare transition in training data)"

    elif kind == "rare_ve_del":
        # LOGIN->VIEW->EDIT->DELETE->LOGOUT — VIEW->EDIT->DELETE rare
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "VIEW->EDIT->DELETE trigram violation (rare in training data)"

    elif kind == "rare_ve_view":
        # LOGIN->VIEW->EDIT->VIEW->LOGOUT — VIEW->EDIT->VIEW rare
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=VIEW page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "VIEW->EDIT->VIEW trigram violation (rare back-transition)"

    elif kind == "rare_del_edit":
        # LOGIN->DELETE->EDIT->LOGOUT — LOGIN->DELETE->EDIT rare
        lines.append(f"{ts(t)} session={sid} event=LOGIN user={user}"); t += timedelta(seconds=3)
        lines.append(f"{ts(t)} session={sid} event=DELETE page={pick_page()}"); t += timedelta(seconds=4)
        lines.append(f"{ts(t)} session={sid} event=EDIT page={pick_page()}"); t += timedelta(seconds=5)
        lines.append(f"{ts(t)} session={sid} event=LOGOUT user={user}"); t += timedelta(seconds=7)
        label, reason = "invalid", "DELETE->EDIT trigram violation (rare transition after LOGIN->DELETE)"

    else:
        raise ValueError(f"Unknown kind: {kind}")

    t += timedelta(seconds=random.randint(3, 8))
    return lines, t, label, reason


# ─── Test session schedule (60 regular sessions + one long session) ────────────
TEST_KINDS = [
    # ~30 valid (50%)
    "valid_simple", "valid_simple", "valid_simple", "valid_simple", "valid_simple",
    "valid_edit",   "valid_edit",   "valid_edit",   "valid_edit",
    "valid_delete", "valid_delete", "valid_delete",
    "valid_long",   "valid_long",
    "valid_ve",     "valid_ve",     "valid_ve",
    "valid_vve",    "valid_vve",
    "valid_ed",     "valid_ed",
    "valid_simple", "valid_edit",   "valid_delete",
    "valid_long",   "valid_ve",     "valid_vve",
    "valid_ed",     "valid_simple", "valid_edit",
    # ~30 invalid (50%)
    "no_login_view",    "no_login_view",    "no_login_view",
    "no_login_edit",    "no_login_edit",
    "no_login_delete",  "no_login_delete",
    "no_login_logout",  "no_login_logout",
    "no_logout",        "no_logout",        "no_logout",
    "no_logout_edit",   "no_logout_edit",
    "no_logout_bare",
    "double_logout",    "double_logout",    "double_logout",
    "after_logout_view","after_logout_view",
    "after_logout_edit","after_logout_edit",
    "after_logout_delete",
    "rare_del_view",    "rare_del_view",
    "rare_ve_del",      "rare_ve_del",
    "rare_ve_view",     "rare_ve_view",
    "rare_del_edit",
]

random.shuffle(TEST_KINDS)


def main():
    out = Path(__file__).parent

    # ── Training ────────────────────────────────────────────────────────────────
    train_lines: list[str] = []
    t = BASE_TIME
    for i in range(1, 151):
        session_lines, t = gen_training_session(i, t)
        train_lines.extend(session_lines)
        t += timedelta(seconds=random.randint(5, 20))

    (out / "sample_logs.txt").write_text("\n".join(train_lines) + "\n", encoding="utf-8")
    print(f"[gen] sample_logs.txt  — {len(train_lines)} events across 150 training sessions")

    # ── Test ────────────────────────────────────────────────────────────────────
    test_lines: list[str] = []
    gt_lines = ["# session_id,valid|invalid,reason"]
    t = datetime(2024, 2, 1, 8, 0, 0)

    for i, kind in enumerate(TEST_KINDS, start=1):
        session_lines, t, label, reason = make_test_session(i, kind, t)
        test_lines.extend(session_lines)
        gt_lines.append(f"T{i:03d},{label},{reason}")

    # Appending after the shuffled set keeps T001–T060 deterministic and makes the
    # stress-case easy to find in the generated files.
    session_lines, t, label, reason = make_test_session(61, "valid_very_long", t)
    test_lines.extend(session_lines)
    gt_lines.append(f"T061,{label},{reason}")

    (out / "test_logs.txt").write_text("\n".join(test_lines) + "\n", encoding="utf-8")
    (out / "ground_truth.txt").write_text("\n".join(gt_lines) + "\n", encoding="utf-8")
    print(f"[gen] test_logs.txt    — {len(test_lines)} events across 61 test sessions")
    print(f"[gen] ground_truth.txt — {len(gt_lines)-1} entries")


if __name__ == "__main__":
    main()

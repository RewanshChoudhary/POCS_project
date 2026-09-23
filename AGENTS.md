# AGENTS.md — AutoSense Context for AI Coding Agents

This file gives coding agents enough context to work on AutoSense without re-reading the full spec.

## Purpose

**AutoSense** is a Theory of Computation course project: a Python CLI that detects anomalous user sessions in log files by **inferring session grammar from training data** and **explaining rejections** with pinpoint failure locations and minimal single-token fixes.

## Hard Constraints (never violate)

1. **Single process, single language:** Python only. No microservices, no web framework.
2. **No database:** Input/output are flat files (`.txt`, `.json`).
3. **No external ML/NLP libraries:** Grammar inference uses plain frequency/sequence counting only.
4. **No auth, deployment, Docker, CI/CD.**
5. **CLI only** — entry point is `python report.py`.
6. **Exactly six core Python modules** — do not add a 7th module without asking the user.
7. **No premature generalization** — build for the sample log format only.

## Novelty Rules (do not simplify)

- **Grammar inference must be data-driven.** Rules are computed from `data/sample_logs.txt` every run. Changing training data must change output rules. Never hardcode LOGIN/LOGOUT rules in `grammar_inference.py`.
- **Explainer must be specific.** On rejection, report: (a) exact token position, (b) violated inferred rule, (c) minimal corrective edit. Never return generic "invalid session" messages.

## File Structure

```
autosense/
├── data/
│   ├── sample_logs.txt       # training (~35 sessions)
│   ├── test_logs.txt         # evaluation (~18 sessions)
│   └── ground_truth.txt      # answer key for Phase 3 eval
├── tokenizer.py              # raw line → token dict
├── session_extractor.py      # tokens → session sequences
├── grammar_inference.py      # sessions → inferred rules
├── automaton.py              # grammar → DFA state representation & validation
├── validator.py              # session + rules → valid/invalid + failure point
├── repair.py                 # bounded Uniform-Cost Search minimum-cost repair engine
├── explainer.py              # failure → explanation + minimal fix
├── report.py                 # full pipeline CLI
├── README.md                 # human documentation
└── AGENTS.md                 # this file
```

## Log Format

```
2024-01-15T10:00:01 session=S001 event=LOGIN user=alice
2024-01-15T10:00:05 session=S001 event=VIEW page=home
2024-01-15T10:00:12 session=S001 event=LOGOUT user=alice
```

**Token vocabulary:** `LOGIN`, `VIEW`, `EDIT`, `DELETE`, `LOGOUT`

**Valid pattern (ground truth for data):** `LOGIN → (VIEW|EDIT|DELETE)* → LOGOUT`

## Module Responsibilities

| Module | Key functions |
|---|---|
| `tokenizer.py` | `tokenize_line()`, `tokenize_file()` |
| `session_extractor.py` | `extract_sessions()`, `sessions_to_sequences()`, `load_session_sequences()` |
| `grammar_inference.py` | `infer_grammar()`, `grammar_to_english()`, `allowed_starts/ends/followers()`, `allowed_trigram_followers()` |
| `automaton.py` | `Automaton`, `build_automaton()`, `next_state()`, `accepts()`, `validate()` |
| `validator.py` | `validate_session()` → `ValidationResult` with `failure_index`, `violated_rule`, `rule_type`, `context`, `all_failures` |
| `repair.py` | `RepairEngine`, `repair_session()`, `RepairOperation`, `RepairResult` (Uniform-Cost Search) |
| `explainer.py` | `explain()`, `suggest_fix()`, `apply_fix()` |
| `report.py` | `run_pipeline()`, `baseline_validate()`, `compute_metrics()`, `main()` |

## Validation Order (first failure wins)

1. **Start rule** — first token must meet start frequency threshold.
2. **Terminal rule** — tokens in `allowed_ends` (e.g. LOGOUT at 100%) must not be followed by anything.
3. **Context-aware Trigram transition rule** — for position >= 2, if context (A, B) has support >= min_support and rules >= threshold, next token must meet trigram rule.
4. **Bigram/transition fallback** — if trigram is inconclusive (insufficient context support or diffuse followers), adjacent pair must meet follower frequency threshold.
5. **End rule** — last token must meet end frequency threshold.

## Explainer Fix Strategies

Repairs are solved using a bounded Uniform-Cost Search (min-heap) exploring insertions, deletions, and substitutions to guarantee the minimum-cost edit sequence within the search budget. Structural heuristics are available as fallback.

| `rule_type` | Fix |
|---|---|
| `empty` / `start` | `insert LOGIN at position 0` / substitute start |
| `transition` / `trigram_transition` | minimum-cost replacement, insertion, or deletion |
| `terminal` | `remove <token> at position N` |
| `end` (truncated, no LOGOUT in session) | `append LOGOUT` |
| `end` (extra token after LOGOUT) | `remove <token> at position N` |

## How to Run

```bash
cd ~/Projects/autosense
python report.py                          # default threshold 0.70, min-support 1, max-cost 2
python report.py --threshold 0.75
python report.py --min-support 2
python report.py --max-cost 3
python report.py --validation-mode all    # report all violations across sequence
python report.py --show-grammar           # print automaton alphabet and specs
python report.py --export results.json
```

Unit and integration test suite:

```bash
python -m unittest discover -v
```

## Evaluation

- Ground truth: `data/ground_truth.txt` (format: `session_id,valid|invalid,reason`)
- Baseline (inline in `report.py`): 4 hand-coded rules (start LOGIN, end LOGOUT, no double LOGOUT, no action after LOGOUT)
- Report prints accuracy table comparing baseline vs inferred grammar

Current results (threshold=0.70): baseline 94.4%, inferred **100.0%** on 18 test sessions.

## What NOT to Do

- Add `baseline.py`, `utils/`, config YAML, or plugin systems
- Use scikit-learn, spaCy, transformers, or any pretrained model
- Hardcode grammar rules that should be inferred
- Return bare `False` from validator without failure metadata
- Edit the plan file at `~/.cursor/plans/autosense_cli_build_*.plan.md`

## When Changing Code

Update this file if you change: validation order, fix strategies, CLI flags, file structure, or evaluation workflow.

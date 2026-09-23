# AutoSense

**Data-driven anomaly detection for user-session logs — built on real Theory of Computation.**

AutoSense reads a log file, **infers the grammar of a "normal" user session from example logs**
(no hand-written rules, no ML libraries), compiles that grammar into a **Deterministic Finite
Automaton**, and flags anomalous sessions by **deciding language membership**. It also scores each
sequence with a lightweight smoothed Markov model, so structurally valid but statistically unusual
sessions can be reviewed. Every rejected session
comes with the exact failing token position, the violated inferred rule, and the **minimum-cost
repair** found by **Uniform-Cost Search** over the edit graph.

Theory of Computation course project — small, hand-traceable, demoable in one command.

| | |
|---|---|
| **Course context** | Theory of Computation (regular languages, automata, decidability, search) |
| **Language / deps** | Python 3.14+, **standard library only** (`re`, `collections`, `heapq`, `argparse`, `json`) |
| **Entry point** | `python report.py` |
| **Storage** | Flat files only (`.txt`, `.json`) — no database, no server |
| **Core idea** | Learn the session language → validate structure and score transition surprise → explain → repair syntactically |
| **Current evaluation** | Automaton / hybrid: 88.5% accuracy; statistical model: 54.1% accuracy on 61 labeled evaluation sessions |

---

## Table of contents

- [1. What the project does](#1-what-the-project-does)
- [2. Quick start](#2-quick-start)
- [3. Architecture and pipeline](#3-architecture-and-pipeline)
- [4. Log format and data files](#4-log-format-and-data-files)
- [5. How grammar inference works](#5-how-grammar-inference-works)
- [6. Validation order (the decider)](#6-validation-order-the-decider)
- [7. Minimum-cost repair engine](#7-minimum-cost-repair-engine)
- [8. Explainer and fix strategies](#8-explainer-and-fix-strategies)
  - [8.1 Statistical anomaly scoring](#81-statistical-anomaly-scoring)
- [**9. Theory of Computation foundations**](#9-theory-of-computation-foundations)
  - [9.1 Formal framing: detection is a membership problem](#91-formal-framing-detection-is-a-membership-problem)
  - [9.2 Alphabet, strings, Kleene star, regular expressions, Chomsky hierarchy](#92-alphabet-strings-kleene-star-regular-expressions-chomsky-hierarchy)
  - [9.3 The DFA 5-tuple, mapped to code](#93-the-dfa-5-tuple-mapped-to-code)
  - [9.4 Extended transition function δ* and the membership decider](#94-extended-transition-function-δ-and-the-membership-decider)
  - [9.5 Finite memory, Myhill–Nerode residuals, and the pumping lemma](#95-finite-memory-myhillnerode-residuals-and-the-pumping-lemma)
  - [9.6 Grammar inference as inductive inference (and Gold's theorem)](#96-grammar-inference-as-inductive-inference-and-golds-theorem)
  - [9.7 Closure properties: intersection, complement, union](#97-closure-properties-intersection-complement-union)
  - [9.8 From stochastic Markov model to deterministic acceptor](#98-from-stochastic-markov-model-to-deterministic-acceptor)
  - [9.9 Repair as shortest path with Uniform-Cost Search](#99-repair-as-shortest-path-with-uniform-cost-search)
  - [9.10 Decidability and complexity](#910-decidability-and-complexity)
  - [9.11 Beyond regular languages and the context-free boundary](#911-beyond-regular-languages-and-the-context-free-boundary)
  - [9.12 Concept to code map](#912-concept-to-code-map)
  - [9.13 How to demo each concept live](#913-how-to-demo-each-concept-live)
- [10. Evaluation results](#10-evaluation-results)
- [11. Case studies](#11-case-studies)
- [12. Testing](#12-testing)
- [13. Optional static report dashboard](#13-optional-static-report-dashboard)
- [14. Literature survey and research gap](#14-literature-survey-and-research-gap)
- [15. Limitations and known issues](#15-limitations-and-known-issues)
- [16. Design constraints](#16-design-constraints)
- [17. File map and glossary](#17-file-map-and-glossary)
- [18. References](#18-references)

---

## 1. What the project does

Web and enterprise applications emit ordered event logs per user session
(`LOGIN`, `VIEW`, `EDIT`, `DELETE`, `LOGOUT`). Sessions that break the usual structure — a missing
`LOGIN`, a double `LOGOUT`, an action after `LOGOUT`, or a transition the application never performs
in that order — may indicate bugs, security incidents, or corrupted logging.

AutoSense solves three problems, one per stage:

1. **Learn** — mine the structure of valid sessions from `data/sample_logs.txt` and turn it into
   explicit, human-readable rules (frequencies + support counts).
2. **Decide** — for every session in `data/test_logs.txt`, decide whether the event sequence is in the
   inferred session language; if not, produce precise failure metadata.
3. **Repair & explain** — search for the cheapest edit sequence that makes the session valid, and
   report it in plain English with the token position and the rule it violated.

Why not a rule engine or a black-box model? Hand-written rules are brittle and must be rewritten
whenever application behaviour changes; ML classifiers flag anomalies but cannot say *which* structural
constraint failed. AutoSense keeps the adaptivity (rules follow the training data) and the
explainability (a failure is a formal language-membership violation at a specific position).

## 2. Quick start

```bash
cd ~/Projects/autosense

python report.py                          # threshold 0.70, min-support 1, max-cost 2
python report.py --threshold 0.75         # stricter inference → fewer accepted transitions
python report.py --min-support 2          # ignore low-support trigram contexts
python report.py --max-cost 3             # larger repair search budget
python report.py --validation-mode all    # report every violation, not just the first
python report.py --show-grammar           # print alphabet Σ and automaton spec
python report.py --export data/results.json
python report.py --alpha 0.5 --k 2.5      # statistical smoothing and threshold sensitivity
```

Additional flags (from `report.py`'s `argparse`): `--train PATH`, `--test PATH`,
`--ground-truth PATH`.

Individual modules are runnable and self-demonstrating:

```bash
python tokenizer.py           # regex parse: log line -> token dict
python session_extractor.py   # tokens -> ordered session sequences
python grammar_inference.py   # prints inferred rules in English
python automaton.py           # prints alphabet + acceptance of a sample sequence
python validator.py           # prints failure index/token/rule for T003
python repair.py              # runs Uniform-Cost Search on VIEW -> EDIT -> LOGOUT
python explainer.py           # prints explanations for T003, T005, T013
```

Run the test suite (99 unit + integration tests):

```bash
python -m unittest discover -v
```

### Sample output (abridged)

```
========================================================================
AUTOSENSE — Session Grammar & Automaton Anomaly Report
========================================================================

Learned from 50 training sessions (threshold=0.70, min_support=1):

INFERRED RULES (plain English)
----------------------------------------
  • In 100.0% of sessions, LOGIN is the first event.
  • After DELETE, LOGOUT appears next in 93.3% of cases.
  • After LOGIN -> DELETE, LOGOUT appears next in 88.9% of cases (support=9).
  • After VIEW -> EDIT, LOGOUT appears next in 83.3% of cases (support=12).
  • In 100.0% of sessions, LOGOUT is the last event.

AUTOMATON SPECIFICATION
----------------------------------------
  Alphabet (Sigma): DELETE, EDIT, LOGIN, LOGOUT, VIEW
  State Context: History-2 DFA States (A, B) -> delta((A, B), C)

FLAGGED SESSIONS & MINIMUM-COST REPAIRS
----------------------------------------

  [T006] LOGIN -> DELETE -> VIEW -> LOGOUT
  Session T006 INVALID at position 2 (token=VIEW) [context: LOGIN -> DELETE]: violated rule
  "After context LOGIN -> DELETE, VIEW appears next in only 11.1% of cases with support 9
  (threshold 70%, min_support 1)." (expected one of: LOGOUT).
  Minimal fix (cost 1, guaranteed minimum within search budget): replace DELETE with EDIT at
  position 1 (yields: LOGIN -> EDIT -> VIEW -> LOGOUT)
  Verified repair validity: True

========================================================================
EVALUATION VS GROUND TRUTH (Anomaly Detection: Invalid = Positive)
========================================================================
  Method                          TP  FP  TN  FN   Accuracy  Precision   Recall       F1
  --------------------------------------------------------------------------------------
  Hardcoded baseline (4 rules)    10   0  13   5      82.1%     100.0%    66.7%    80.0%
  Inferred Grammar / Automaton    15   0  13   0     100.0%     100.0%   100.0%   100.0%
========================================================================
```

---

## 3. Architecture and pipeline

```
data/sample_logs.txt ──► tokenizer ──► session_extractor ──► grammar_inference ──┐
                                                                                 │
                                                                            InferredGrammar
                                                                                 │
data/test_logs.txt   ──► tokenizer ──► session_extractor ──► automaton ◄──────────┘
                                                                 │
                                                   (ValidationResult: valid / failure point)
                                                                 ▼
                                                       repair.py (bounded Uniform-Cost Search)
                                                                 ▼
                                                       explainer.py ──► report.py (CLI + metrics)
                                                                 ▼
                                          data/results.json ──► web/build.py (static HTML report)
```

The flow is strictly **inductive then deductive**: `grammar_inference.py` performs *inductive
inference* (generalise from samples), while `automaton.py` / `validator.py` perform *deduction*
(decide membership by simulating the machine). No stage may hardcode session rules: rules exist only
in the `InferredGrammar` object built from the training file at runtime.

| Module | Lines | Role |
|---|---|---|
| `tokenizer.py` | 52 | Regex parser: log line → `{timestamp, session, event, ...}`; skips comments/malformed lines with a warning |
| `session_extractor.py` | 43 | Groups tokens by session ID, orders by `(timestamp, file order)`, yields event-type sequences |
| `grammar_inference.py` | 211 | Mines start/end/bigram/trigram frequencies + support counts → `InferredGrammar`; renders rules in English |
| `probability_model.py` | 340 | Laplace-smoothed transition model, NLL scores, adaptive threshold, surprise evidence |
| `automaton.py` | 320 | Builds the DFA from the grammar: `next_state()` = δ, `accepts()` = δ\*, `validate()` = δ\* with structured failures |
| `validator.py` | 57 | Thin façade: `validate_session()` → `ValidationResult` (delegates to the automaton) |
| `repair.py` | 267 | `RepairEngine`: bounded Uniform-Cost Search over insert/delete/substitute edits; returns verified repairs |
| `explainer.py` | 187 | `explain()`, `suggest_fix()`, `apply_fix()`: failure → English + minimal fix (+ heuristic fallback) |
| `report.py` | 570 | `run_pipeline()`, structural/statistical/hybrid evaluation, console report, JSON export, CLI |
| `tests/` | 6 test modules | 100 unit/integration tests (grammar, automaton, repair, statistics, end-to-end) |
| `web/` | 3 files | Optional static dashboard generator (stdlib `http.server`, no framework) |

## 4. Log format and data files

```
2024-01-15T10:00:01 session=S001 event=LOGIN user=alice
2024-01-15T10:00:05 session=S001 event=VIEW page=home
2024-01-15T10:00:12 session=S001 event=LOGOUT user=alice
```

- **Alphabet Σ of event tokens:** `LOGIN`, `VIEW`, `EDIT`, `DELETE`, `LOGOUT` — discovered from the
  data, never hardcoded (`automaton.alphabet` is derived from the inferred grammar).
- **Ground-truth language of valid sessions:** `LOGIN → (VIEW | EDIT | DELETE)* → LOGOUT`.
- Lines starting with `#` are comments; blank and malformed lines are skipped.
- Extra `key=value` pairs (`user=`, `page=`) are parsed into the token dict but do not affect the
  session alphabet.

| File | Content |
|---|---|
| `data/sample_logs.txt` | **Mixed sample 1** — 1,469 valid and 653 invalid sessions |
| `data/test_logs.txt` | **Mixed sample 2** — 546 valid and 167 invalid sessions |
| `data/sample1_ground_truth.csv`, `data/sample2_ground_truth.csv` | Per-sample answer keys (`session_id,valid\|invalid,reason`) |
| `data/results1.json`, `data/results2.json` | Reproducible result exports for samples 1 and 2 |

All figures quoted in this README were produced by running the commands shown; because the rules are
learned, **re-running after editing the training file yields different numbers** — that is the point.

---

## 5. How grammar inference works

`infer_grammar(sequences, threshold=0.70, min_support=1)` counts four families of statistics over the
training sequences (empty sessions are dropped from counting but still count in the session total):

1. **Start rules** — `P(token is the first event)` = count / number of sessions.
2. **End rules** — `P(token is the last event)`.
3. **Terminal detection** — tokens whose end frequency is `≥ threshold` (here `LOGOUT` at 100%) are
   treated as *terminal*: they admit no successors.
4. **Bigram rules** — `P(B | A) = count(A, B) / count(A → *)`.
5. **Trigram rules (context-aware)** — `P(C | A, B) = count(A, B, C) / count((A, B) → *)`, preserving
   the **support** `count(A, B)` and raw counts so a rare context can be declared inconclusive.

Two design details that matter:

- **Post-terminal noise is truncated during training.** If a terminal token appears mid-sequence in the
  training data, n-gram counting stops there (`effective_seq = sequence[:idx + 1]`), so corrupted
  training rows cannot teach the model that "things happen after LOGOUT".
- **Thresholding is the inductive bias.** Only rules with frequency `≥ threshold` become constraints;
  trigram rules additionally require `support ≥ min_support`. The model is a *pruned* hypothesis, not a
  memorised sample.

`grammar_to_english()` renders the same object as the sentences printed by the CLI
(`"After VIEW -> EDIT, LOGOUT appears next in 83.3% of cases (support=12)."`), which is what makes the
inference auditable by hand — and verifiable: edit `data/sample_logs.txt`, re-run, and the printed
rules change.

## 6. Validation order (the decider)

`Automaton.validate(sequence, mode)` reports the **first** violation (or *all* of them with
`--validation-mode all`), in this fixed priority order:

| # | Rule | `rule_type` | Meaning |
|---|---|---|---|
| 1 | Start | `start` | `sequence[0]` must be an allowed start (`LOGIN` at 100%) |
| 2 | Terminal | `terminal` | a token in `allowed_ends` (e.g. `LOGOUT`) may not be followed by anything |
| 3 | Context-aware trigram | `trigram_transition` | if context `(A, B)` has `support ≥ min_support` and retained rules, the next token must be one of them |
| 4 | Bigram fallback | `transition` | otherwise the adjacent pair `(A, B)` must satisfy `P(B \| A) ≥ threshold` |
| 5 | End | `end` | `sequence[-1]` must be an allowed end (`LOGOUT` at 100%) |

Empty sessions are rejected with `rule_type="empty"`. Every failure returns a `ValidationResult`
carrying `failure_index`, `failure_token`, `violated_rule`, `expected`, `rule_type`, `context`, and
(in `all` mode) `all_failures` — never a bare `False`.

## 7. Minimum-cost repair engine

`RepairEngine` treats repair as a **shortest-path problem** over the space of strings. Starting from
the offending sequence it generates neighbours with three edit operations (`insert`, `delete`,
`substitute`; unit costs by default, overridable through the `costs` dict) and stops at the first
**accepted** sequence the priority queue yields.

- **Frontier:** `heapq` min-heap keyed by `(cost, tiebreak_counter, sequence, operations)` — nodes are
  popped in non-decreasing cost order.
- **No revisits:** a `visited` set of sequence tuples eliminates duplicate paths.
- **Budgets:** `max_repair_cost` (default 2), `max_candidates` (default 1000) and an implicit
  `max_sequence_length` (`max(len(seq) + max_cost, 10)`) keep the search finite.
- **Guarantee, stated honestly:** the first accepted node popped has minimum cost *within the budget*;
  the result is labelled exactly that way (`"selected minimum-cost repair within search budget"`,
  `is_unique=False`).
- **Verification:** every returned repair is re-validated against the automaton before printing
  (`fix_validates` in the JSON export).

## 8. Explainer and fix strategies

`explain()` composes position, context, rule and optimal repair into one sentence:

```
Session T006 INVALID at position 2 (token=VIEW) [context: LOGIN -> DELETE]: violated rule "After
context LOGIN -> DELETE, VIEW appears next in only 11.1% of cases with support 9 ..." (expected one
of: LOGOUT). Minimal fix (cost 1, guaranteed minimum within search budget): replace DELETE with EDIT
at position 1 (yields: LOGIN -> EDIT -> VIEW -> LOGOUT)
```

`suggest_fix()` first tries the optimal search repair; if the budget is exhausted it falls back to
rule-specific structural heuristics. `apply_fix()` parses fix strings (including `;`-joined multi-edit
repairs) back onto sequences.

| `rule_type` | Fallback fix |
|---|---|
| `empty` / `start` | `insert LOGIN at position 0` (or substitute the offending start token) |
| `transition` / `trigram_transition` | `insert <expected token> before <token>`, else substitute the most frequent valid follower |
| `terminal` | `remove <token> at position N` |
| `end` (truncated, no `LOGOUT`) | `append LOGOUT` |
| `end` (extra token after `LOGOUT`) | `remove <token> at position N` |

---

### 8.1 Statistical anomaly scoring

The automaton remains the structural decider: it accepts or rejects an event string and pinpoints a
violated inferred rule. The complementary statistical model is a first-order Markov model trained
only on `data/sample_logs.txt`; it does not use test labels or test-session scores to set its
threshold.

For vocabulary \(\Sigma\), raw transition count \(c(a,b)\), and smoothing parameter \(\alpha\), it uses
Laplace smoothing:

```
P(b | a) = (c(a, b) + α) / (Σx c(a, x) + α × |Σ|)
```

This gives unseen transitions a finite probability when `alpha > 0`. A session
`X = [e1, ..., en]` then receives mean negative log-likelihood (NLL):

```
S(X) = -(1 / (n - 1)) × Σ log P(et | e(t-1))
```

Lower NLL means the observed transitions resemble training data; higher NLL means they are more
surprising. It is not a probability that a user is malicious. The adaptive threshold is a simple
training-only heuristic:

```
T = mean(training NLL scores) + k × population_standard_deviation(training NLL scores)
```

`--alpha` controls smoothing (default `1.0`) and `--k` controls sensitivity (default `3.0`). A
score is statistically flagged only when `score > T`; equality is treated as normal. The hybrid
policy is deliberately explicit: a session is anomalous when the automaton rejects it **or** its
NLL exceeds `T`. JSON exports and the static dashboard include the score, threshold, detector
decisions, and highest-surprise transitions.

For a viva: “The DFA answers whether the sequence obeys the learned language. The Markov score
answers how surprising its local transitions are among normal examples. We show both pieces of
evidence and do not interpret either as proof of malicious behaviour.”

---

## 9. Theory of Computation foundations

This is the heart of the project: every stage is an instance of a standard ToC construction, and each
one is implemented explicitly (no library hides it). This section states the concept, the formal
object, and where it lives in the code.

### 9.1 Formal framing: detection is a membership problem

Fix an alphabet `Σ` of event tokens and note that a session is just a **string** `w ∈ Σ*`
(`session_extractor.sessions_to_sequences`). Define the *session language* `L ⊆ Σ*` to be the set of
sessions the organisation considers normal. Then:

| Practical question | Formal problem |
|---|---|
| "Is this session normal?" | **Membership:** is `w ∈ L`? |
| "What exactly is wrong with it?" | **Witness** for `w ∉ L`: a position and the violated constraint |
| "What is the smallest correction?" | **Optimisation:** `arg min { cost(w → w') : w' ∈ L }` |

AutoSense *learns a finite description of `L`* (a grammar → a DFA) and then answers those three
questions algorithmically. Note the two directions of inference involved:

- **Inductive** (sample → hypothesis): `grammar_inference.infer_grammar`, generalising from 50
  positive examples.
- **Deductive** (hypothesis + input → yes/no): `automaton.Automaton.accepts` / `validate`, simulating a
  finite-state machine.

That split — *learning the language* versus *deciding membership in it* — is exactly the framing used
in grammatical inference research, and it is what makes the detector explainable rather than
statistical.

### 9.2 Alphabet, strings, Kleene star, regular expressions, Chomsky hierarchy

- **Alphabet** `Σ = {LOGIN, VIEW, EDIT, DELETE, LOGOUT}`, produced at runtime from the inferred
  grammar (`Automaton.alphabet`), so the machine's alphabet is *learned*, not assumed.
- **Strings** are session traces; **`Σ*`** (Kleene star) is the set of all finite event sequences — and
  also the search space for repairs.
- **Language of the data:** `L = { LOGIN · x · LOGOUT : x ∈ (VIEW | EDIT | DELETE)* }`, i.e. the regular
  expression `LOGIN (VIEW|EDIT|DELETE)* LOGOUT`.
- **Kleene's theorem:** regular expressions ⇔ finite automata. AutoSense exercises both directions —
  the *specification* is a regex and the *implementation* is a DFA, two representations of one language.
- **Chomsky hierarchy:** `L` is **Type-3 (regular)**, and so is every hypothesis the learner can
  express (`start`-constrained, `bigram`-constrained, `trigram`-constrained strings are all
  finite-memory conditions). Staying in Type-3 is deliberate: membership is decidable in linear time
  and every violation has a *local* cause, which is precisely what makes pinpoint explanations
  possible.

### 9.3 The DFA 5-tuple, mapped to code

`automaton.Automaton` documents and implements the classic definition `M = (Q, Σ, δ, q₀, F)`:

| Component | Formal meaning | In AutoSense |
|---|---|---|
| `Q` (states) | finite set of memory configurations | tuples encoding the last ≤ 2 events: `("__START__",)`, `(A,)`, `(A, B)` — bounded by `1 + \|Σ\| + \|Σ\|²` (≤ 31 for 5 tokens) |
| `Σ` (alphabet) | allowed input symbols | `Automaton.alphabet`, learned from the grammar |
| `q₀` (initial state) | where recognition starts | `START_STATE = ("__START__",)` |
| `F` (accepting states) | states signalling a complete valid session | `is_accepting()`: any non-initial state whose last symbol ∈ `allowed_ends(grammar)` — i.e. states ending in `LOGOUT` |
| `δ` (transition function) | deterministic next state | `next_state(state, event)` → new state, or `None` when the event is illegal |

`δ` is built from the inferred rules, in this priority order:

```
δ(("__START__",), A) = (A,)     if A ∈ allowed_starts                     (start rule)
δ((A,), B)           = (A, B)   if B is allowed after A                   (bigram / trigram)
δ((A, B), C)         = (B, C)   if C is allowed after context (A, B)      (trigram rule)
δ(s, _)              = None     if last(s) ∈ allowed_ends  (terminal: no exits from LOGOUT)
δ(s, C)              = None     if C is not an allowed follower of last(s) (illegal transition)
```

Two formal remarks:

- **Determinism.** `δ` is a *function*: for a given `(state, event)` there is at most one successor.
  The inference step may compute a *set* of admissible symbols (an NFA-like view of "what would be
  legal here"), but resolving an actual symbol yields a single successor — so there is no
  backtracking, no ambiguity, and rejection is one well-defined point.
- **Partiality.** Because illegal inputs map to `None`, `δ` as coded is a **partial** function. It
  becomes a textbook **total** DFA by adding a single **trap state** `⊥` with self-loops on all of `Σ`;
  that trap is implicit in `accepts()`/`validate()`, which return rejection the moment `next_state`
  returns `None`, and `⊥` is non-accepting. This standard completion guarantees *every* string of `Σ*`
  — not just well-behaved ones — is classified.

### 9.4 Extended transition function δ\* and the membership decider

`Automaton.accepts(events)` is the extended transition function:

```
δ*(q₀, ε)   = q₀                    (empty input stays in q₀; q₀ ∉ F ⇒ an empty session is rejected)
δ*(q₀, x·a) = δ( δ*(q₀, x), a )
accepts(w)  = True  ⟺  δ*(q₀, w) ∈ F
```

Consequences worth stating in a report:

- **A DFA *is* an algorithm.** Simulating `δ` is a straight-line loop:
  `for event in events: current = δ(current, event)`, then a final-state test.
- **Time** `Θ(|w|)` steps, each `O(|Σ|)` for the membership test inside
  `allowed_trigram_followers` / `allowed_followers` → **membership is linear-time, total, and always
  terminates**: decidability made concrete.
- **Rejection has a cause.** `validate()` runs the same loop but records *which* rule failed, so the
  answer is not `False` but the pair *(position, constraint)*. That is the difference between a
  recogniser and an *explaining* recogniser.
- **Reachability.** Only states actually reached by `δ*` are ever constructed (they are materialised on
  the fly), so the effective state set is the reachable part of `Q` — an instance of the "remove
  unreachable states" step from automaton minimisation.

### 9.5 Finite memory, Myhill–Nerode residuals, and the pumping lemma

**Why are the states "the last two events"?** By the Myhill–Nerode theorem, prefixes `u, v` are
equivalent iff they have the same **residual language** `u⁻¹L = { x : ux ∈ L }`, and the minimal DFA has
one state per equivalence class. AutoSense approximates the residual with a *bounded history window of
width 2*: the state is the last two symbols, so any two prefixes sharing a 2-symbol suffix are
conflated into one state.

- **Upside:** the state set is finite *by construction* (`|Q| ≤ 1 + |Σ| + |Σ|²`), so the machine is
  guaranteed to be a DFA, and — key for explainability — every rejection is attributable to a window of
  at most three consecutive events.
- **Downside:** the approximation is lossy. A regular language needing a longer window or a real
  counter is not representable. "Exactly three `VIEW`s", for instance, *is* regular (it needs only a
  bounded counter `0..3`), but a width-2 learner cannot express it.
- **Hard limit (pumping lemma):** a DFA has finite memory, so it cannot accept a language requiring
  unbounded counting — e.g. `LOGINⁿ (VIEW|EDIT)* LOGOUTⁿ`, or the non-regular `aⁿbⁿ`. If session logs
  ever needed such structure, no DFA would do; you would have to climb the Chomsky hierarchy (§9.11).
  The project therefore *chooses* the finite-memory model and documents the limitation instead of
  pretending the model is universal.
- **Trade-off made explicit:** the window width `k` (fixed at 2) and the frequency threshold `τ` are
  the two knobs trading recall against precision, and their effect is **not monotone**. Raising `τ`
  prunes rules, which normally tightens the follower sets — but when an entire context loses all of its
  followers, `allowed_trigram_followers` returns empty and the decider falls back to the bigram rule
  (or to "unconstrained"). Measured on the current data: `τ = 0.70` → 11 rules, 15 sessions flagged;
  `τ = 0.85` → 9 rules, 13 sessions flagged.

### 9.6 Grammar inference as inductive inference (and Gold's theorem)

`infer_grammar` is an **inductive inference / grammatical inference** procedure: it maps a finite
sample of positive strings `S = {w₁, …, w₅₀} ⊂ L` to a hypothesis grammar `Ĝ` whose language `L(Ĝ)`
is meant to approximate `L`.

The statistics it computes are **maximum-likelihood estimates** of conditional probabilities:

```
P̂(B | A)     = count(A, B) / count(A → *)           (bigram, first-order)
P̂(C | A, B)  = count(A, B, C) / count((A, B) → *)    (trigram, second-order, with support count)
P̂(token first) and P̂(token last) = count / number of sessions
```

Inference is then a **threshold test**: a rule becomes a constraint iff `P̂ ≥ τ` (default `τ = 0.70`),
with trigram contexts additionally gated by `support ≥ min_support`. That threshold *is* the inductive
bias — it collapses an infinite space of candidate languages into a small, inspectable rule set, and it
explains the project's central novelty claim: **the rules are a function of the training file**. Edit
`data/sample_logs.txt`, re-run, and both `L(Ĝ)` and the flagged set change; nothing is hardcoded by
construction.

**The honest theoretical caveat.** Gold's theorem (1967) shows that identification in the limit of the
class of regular languages from **positive examples only** is impossible: for any learner there exists a
target language and a positive sample on which it converges to the wrong hypothesis. AutoSense does not
claim to escape this — it restricts the hypothesis class to *bounded-window, thresholded* grammars (a
learnable-by-construction subclass) and accepts the bias that follows. Related literature: Angluin's
`L*` learns DFAs exactly but needs **membership queries** (an oracle); AutoSense has only logs, so
frequency-thresholded k-gram inference is the defensible alternative.

### 9.7 Closure properties: intersection, complement, union

The accepted language is not defined by a single rule but by **four local constraint families** (start,
terminal/bigram, trigram, end). Formally:

```
L(Ĝ) = L_start ∩ L_bigram ∩ L_trigram ∩ L_end
```

Each `L_*` is **regular**, because each is a finite-memory condition on a sliding window:

- `L_trigram` = "every length-3 factor is in the allowed trigram set" — recognised by the standard
  sliding-window DFA with one state per 2-symbol context: exactly the `(A, B)` states AutoSense uses
  (at most `|Σ|²` states).
- `L_bigram` = "every length-2 factor is in the allowed bigram set" — an `|Σ|`-state DFA.
- `L_start` / `L_end` = "first symbol ∈ allowed starts" / "last symbol ∈ allowed ends" — trivially
  regular. The terminal rule is a bigram condition with an empty follower set (`LOGOUT → ∅`).

The **closure properties** then do the real work:

1. **Intersection.** `REG` is closed under intersection (product construction), so `L(Ĝ)` is regular and
   a DFA for it exists — the formal licence for the "one DFA enforces everything" design. The code
   enforces the intersection *componentwise* inside `next_state()`/`validate()` (an on-the-fly product
   rather than a materialised product automaton: same language, less memory).
2. **Complement.** `REG` is closed under complement (swap accepting and non-accepting states), so the
   *anomaly* language `Σ* \ L(Ĝ)` is regular too. That is the formal statement that "detect the anomaly"
   is a **decidable, total** decision procedure over all inputs — not a heuristic guess.
3. **Union / Kleene star.** The alternation inside a session body — `(VIEW | EDIT | DELETE)*` — is built
   from union and star, which is why arbitrarily long valid sessions exist while the machine stays
   finite. The inferred follower **sets** (`allowed_followers`, `allowed_trigram_followers`) are
   literally the union branches available for the next symbol.

### 9.8 From stochastic Markov model to deterministic acceptor

During training the model is **stochastic**: a second-order Markov chain with initial distribution
`P(first)`, transition probabilities `P(B | A)` and `P(C | A, B)`, and final distribution `P(last)`.
That is precisely a **probabilistic finite automaton / stochastic regular grammar** — the source of the
notion "this transition is frequent".

The detector then performs a **pruning / hardening step**: every transition whose probability falls
below `τ` is dropped, turning the stochastic automaton into a **deterministic acceptor**. This is the
crucial conceptual move of the project:

- *Before thresholding:* a probability distribution over next events — no notion of "wrong".
- *After thresholding:* a crisp language `L(Ĝ)` — every string is in or out, and rejections have causes.

It also explains the **fallback ladder** of §6. When a 2-symbol context has too little support or a
diffuse follower distribution (no follower reaching `τ`), the model degrades gracefully: second-order
trigram rule → first-order bigram rule → "unconstrained" (all transitions allowed, since
`allowed_events` then returns the whole alphabet). Degrading to *no constraint* rather than to *false
alarm* is a deliberate precision-preserving choice.

### 9.9 Repair as shortest path with Uniform-Cost Search

Given a rejected string `w`, AutoSense solves an optimisation problem over a graph:

- **Nodes** `V = { u ∈ Σ* : |u| ≤ L_max }` — strings, including the input.
- **Edges** — one per edit, with weight equal to the edit cost (`substitute`, `delete`, `insert`);
  `DEFAULT_EDIT_COSTS = {insert: 1, delete: 1, substitute: 1}`, overridable, so arbitrary *non-negative*
  weights are supported.
- **Goal set** `G = L(Ĝ) ∩ V` — accepted strings, tested by the automaton itself.
- **Target** `min` total cost over paths from `w` into `G`. This is a **weighted edit distance**
  (Levenshtein-style), except the target is a whole *regular language* rather than one reference string.

`RepairEngine.repair` solves it with **Uniform-Cost Search** — Dijkstra on a graph with non-negative
edge weights:

```python
frontier = min-heap of (cost, tiebreak, sequence, operations)   # keyed by accumulated cost
visited  = {w}
while frontier:
    pop cheapest node; if accepted -> return path; else push all neighbours
```

The correctness argument is the standard one: because the heap always yields a node of least
accumulated cost and edge weights are non-negative, the **first accepted node popped has minimum cost**
among all accepted nodes — so the returned edit script is provably optimal, which is why the
explanation can honestly say "guaranteed minimum within search budget".

Bounding, and why it is unavoidable:

- `V` is **countably infinite**, so the search must be bounded: `max_repair_cost` (cost/depth budget),
  `max_sequence_length` (insertions would otherwise grow strings forever) and `max_candidates`
  (protection against pathological branching).
- Branching factor is `≈ |Σ|·(n+1)` insertions + `n·(|Σ|−1)` substitutions + `n` deletions, so the
  explored tree is **exponential in the depth budget** `D` *when the goal is not reached quickly*.
  On the current sample data the budget does not bite at all: all 15 flagged sessions are repaired at
  cost 1, so UCS stops as soon as the first accepted node is popped — 138 candidates explored in
  total, at most 21 for a single session, identical for `--max-cost 1`, `2` and `3`. The bound matters
  for inputs where no cheap repair exists, because the search then enumerates the entire cost-≤`D`
  ball.
- The result is thus an **anytime / bounded-optimal** algorithm: optimal when it finds a solution within
  budget, and it *says so* (`reason="selected minimum-cost repair within search budget"`), falling back
  to structural heuristics in `explainer.suggest_fix` when the budget is exhausted.

Relationship to neighbouring techniques:

| Technique | Relation to AutoSense's search |
|---|---|
| **BFS** | special case of UCS where all edits cost 1 (the default here) |
| **Dijkstra** | exactly what UCS is; the "edge weight" is the edit cost |
| **A\*** | add an admissible heuristic (e.g. "number of currently invalid positions") to prune the frontier — natural future work |
| **DP edit distance** | works when the target is a *single* string; here the target is a regular language, so DP needs the product automaton first |

### 9.10 Decidability and complexity

| Problem | Formal status in AutoSense | Cost |
|---|---|---|
| Membership `w ∈ L(Ĝ)`? | **Decidable** and total; DFA simulation always halts | `Θ(\|w\|)` steps |
| Diagnose (position + violated rule) | Decidable; produced by the same simulation | `Θ(\|w\|)` |
| Grammar inference from the sample | Total function of the training file (finite counting) | `O(tokens + contexts)` |
| Optimal repair within budget | Decidable; finitely many strings have cost ≤ `D`, each checked in linear time | `O((\|Σ\|·n)^D · n)` |
| Unbounded repair | Still decidable here — any valid session is finitely far from `w` — but the graph is infinite, so the search is bounded in practice | — |

Because membership is decidable *and* the failure is local, the tool never has to guess: it either
accepts a session, or exhibits a concrete violation together with a verified repair. Nothing in the
pipeline requires unbounded computation — the practical payoff of restricting the model to Type-3.

### 9.11 Beyond regular languages and the context-free boundary

It is worth being explicit about where the regularity assumption breaks:

- **Nested or paired structure** — e.g. sessions that open and close sub-transactions, or `LOGINⁿ … LOGOUTⁿ`
  with matching counts — is the classic Dyck-style language: **context-free but not regular** (pumping
  lemma), so no DFA can accept it. You would need a **pushdown automaton / context-free grammar**
  (`S → LOGIN S LOGOUT | body`). Membership stays decidable (CYK, `O(n³)`), but the "one local failing
  triple" style of explanation disappears — errors become parse-tree mismatches and repair becomes
  weighted parsing.
- **Unrestricted grammars** — if the "valid session" relation ever required arbitrary computation,
  membership would become **undecidable** (Rice's theorem / the halting problem), and no tool could
  guarantee either detection or repair.
- **Regularity is what buys explainability.** Every violation in this project is witnessed by at most
  three consecutive events plus one thresholded rule, *because* the model is finite-state. That is a
  design decision grounded in the Chomsky hierarchy, not an accident.

### 9.12 Concept to code map

| ToC concept | Where it is implemented | What it buys |
|---|---|---|
| Alphabet `Σ`, strings, `Σ*` | `Automaton.alphabet`; `sessions_to_sequences` | Learned vocabulary; well-defined input space |
| Regular expression / Kleene's theorem | ground-truth pattern `LOGIN (VIEW\|EDIT\|DELETE)* LOGOUT`; regex lexer in `tokenizer.py` | One-line spec; implementation as a machine |
| Grammar (Type-3) | `InferredGrammar` in `grammar_inference.py` | Explicit, inspectable, data-derived rules |
| DFA `(Q, Σ, δ, q₀, F)` | `Automaton`, `next_state()`, `is_accepting()`, `START_STATE` | Deterministic, linear-time recognition |
| δ\* / membership decider | `Automaton.accepts()`, `Automaton.validate()` | Total, terminating yes/no answer for every string |
| Trap state (DFA completion) | `next_state() → None` handled in `accepts()` / `validate()` | Rejection is a state, not an exception |
| Myhill–Nerode residuals (approximated) | states `(A, B)` = width-2 history | Finite state set; local explanations |
| Pumping-lemma limit | documented design limit (§9.5, §9.11) | Honest statement of what the model cannot do |
| Inductive inference (learning in the limit) | `infer_grammar()` with threshold/min-support bias | Adaptivity: rules change with the data |
| MLE of conditional probabilities | counters `trigram_counts`, `trigram_support`, `bigram_rules` | Justification for "frequent = allowed" |
| Intersection closure | rule hierarchy in `next_state()` / `validate()` | One machine enforcing four constraints |
| Complement closure | `valid=False` ⇒ anomaly; `report.compute_metrics` | The detector is a decider over all inputs |
| Union / star | follower sets `allowed_followers`, `allowed_trigram_followers`; body `(VIEW\|EDIT\|DELETE)*` | Unbounded session length, finite machine |
| Stochastic → deterministic (pruning) | threshold test `P̂ ≥ τ` in `infer_grammar()` | Turns statistics into a crisp language |
| Graph search / Dijkstra / UCS | `RepairEngine.repair()` (`heapq` frontier + `visited`) | Provably minimum-cost repair within budget |
| Weighted edit distance | `DEFAULT_EDIT_COSTS` in `repair.py` | Generality beyond unit-cost edits |
| Decidability & complexity | §9.10; budget parameters in `RepairEngine.__init__` | Guaranteed termination, predictable runtime |
| CFL / PDA (extension point) | not implemented — discussed in §9.11 | Clear boundary of the current model |

### 9.13 How to demo each concept live

```bash
# 9.2/9.3  learned alphabet + deterministic acceptance
python automaton.py
#   Automaton built with alphabet (5 tokens): ['DELETE', 'EDIT', 'LOGIN', 'LOGOUT', 'VIEW']
#   Accepts ['LOGIN', 'VIEW', 'LOGOUT']: True

# 9.6      inductive inference: rules with probabilities and support counts
python grammar_inference.py
#   Inferred from 150 training sessions (threshold=0.70, min_support=1):
#     - In 100.0% of sessions, LOGIN is the first event.
#     - After DELETE, LOGOUT appears next in 93.3% of cases.
#   (edit data/sample_logs.txt, re-run: the rules change — nothing is hardcoded)

# 9.4/9.5  a rejection with position, context and violated rule
python validator.py
#   T003 valid=False index=0 token=VIEW
#     rule: VIEW starts only 0.0% of training sessions (threshold 70%).

# 9.9      Uniform-Cost Search producing a verified cost-1 repair
python repair.py
#   Repairing ['VIEW', 'EDIT', 'LOGOUT']: found=True, cost=1,
#   operations=['replace VIEW with LOGIN at position 0'] -> ['LOGIN', 'EDIT', 'LOGOUT']

# 9.9/9.10 the search budget is an explicit, bounded knob
python report.py --max-cost 1
#   all 15 flagged sessions are still repaired at cost 1 (verified repairs)

# 9.9/9.10 per-session search statistics travel with the results
python report.py --export data/results.json
#   each flagged session carries repair_cost and repair_explored_candidates
```

---

## 10. Evaluation results

Metrics follow the anomaly-detection convention **Invalid = Positive** (`compute_metrics` in
`report.py`) and are computed over the **61 labeled sessions** in `data/ground_truth.txt` using the
default configuration (`alpha=1.0`, `k=3.0`):

| Method | TP | FP | TN | FN | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| Hardcoded baseline (4 rules) | 23 | 0 | 31 | 7 | 88.5% | 100.0% | 76.7% | 86.8% |
| Inferred Grammar / Automaton | 23 | 0 | 31 | 7 | 88.5% | 100.0% | 76.7% | 86.8% |
| Statistical (first-order Markov) | 2 | 0 | 31 | 28 | 54.1% | 100.0% | 6.7% | 12.5% |
| Hybrid (Automaton OR Statistical) | 23 | 0 | 31 | 7 | 88.5% | 100.0% | 76.7% | 86.8% |

The first-order statistical detector is intentionally reported as weaker on this synthetic set rather
than tuned against the test labels. Its mean NLL is 1.0788 for labeled normal sessions and 1.1980 for
labeled anomalous sessions, but the conservative training-only `mean + 3σ` threshold catches only two
anomalies. The hybrid therefore matches the structural automaton here. This is useful evidence, not a
failure to hide: the DFA remains the primary structural detector and the score provides supplementary
transition-surprise evidence.

## 11. Case studies

Each case below is reproduced by `python report.py` on the current data.

### 1. Missing LOGIN — `T003`: `VIEW → EDIT → LOGOUT`
- **Violation:** position 0 (`VIEW`) — `VIEW` starts 0.0% of training sessions.
- **Repair:** `replace VIEW with LOGIN at position 0` (cost 1) → `LOGIN → EDIT → LOGOUT` ✅ verifies

### 2. Truncated session — `T004`: `LOGIN → VIEW`
- **Violation:** position 1 (`VIEW`) — `VIEW` ends 0.0% of training sessions (expected `LOGOUT`).
- **Repair:** `replace VIEW with LOGOUT at position 1` (cost 1) → `LOGIN → LOGOUT` ✅

### 3. Double LOGOUT — `T005`: `LOGIN → VIEW → LOGOUT → LOGOUT`
- **Violation:** position 3 (`LOGOUT`) — follows a terminal event.
- **Repair:** `replace LOGOUT with DELETE at position 2` (cost 1) → `LOGIN → VIEW → DELETE → LOGOUT` ✅

### 4. Rare transition — `T006`: `LOGIN → DELETE → VIEW → LOGOUT`
- **Violation:** position 2 (`VIEW`) — after context `LOGIN → DELETE`, `VIEW` occurs in only 11.1% of
  cases (support 9) while `LOGOUT` reaches 88.9% (the learned trigram rule).
- **Repair:** `replace DELETE with EDIT at position 1` (cost 1) → `LOGIN → EDIT → VIEW → LOGOUT` ✅

### 5. Action after LOGOUT — `T013`: `LOGIN → LOGOUT → VIEW`
- **Violation:** position 2 (`VIEW`) — `LOGOUT` is terminal (ends 100% of sessions) but is followed.
- **Repair:** `remove VIEW at position 2` (cost 1) → `LOGIN → LOGOUT` ✅

### 6. Ordering violation caught only by the trigram rule — `T028`: `LOGIN → VIEW → EDIT → DELETE → LOGOUT`
- **Violation:** position 3 (`DELETE`) — after context `VIEW → EDIT`, `DELETE` occurs in only 8.3% of
  cases (support 12), where `LOGOUT` is the 83.3% successor.
- **Repair:** cost-1 substitution — `replace VIEW with LOGIN at position 1` →
  `LOGIN → LOGIN → EDIT → DELETE → LOGOUT`, re-validated against the automaton before being reported.
- **Note:** the hand-coded baseline *accepts* this session — exactly the blind spot that inferred
  contextual rules remove.

---

## 12. Testing

```bash
python -m unittest discover -v
```

| Test file | Scope |
|---|---|
| `tests/test_priority1_trigram.py` | Trigram counting/support, probability computation, threshold filtering, min-support gating, empty inputs, sessions shorter than 3 tokens, bigram fallback, conflicting trigram/bigram evidence |
| `tests/test_priority2_automaton.py` | DFA construction, initial state, all training sessions accepted, double `LOGOUT`, missing `LOGIN`, truncated sessions, empty sessions, unknown events, trigram-context transitions, validator↔automaton consistency |
| `tests/test_priority3_repair.py` | Already-valid, single insert/delete/substitute, minimum-cost selection, multi-edit repairs, no-repair-within-budget, candidate limits, empty sequences, unknown events, verification of returned repairs |
| `tests/test_priority4_integration.py` | End-to-end pipeline, `--validation-mode all`, metrics/accuracy/F1 arithmetic, multi-edit `apply_fix`, JSON export payload keys |

**Current status: 40 tests, 2 failures** — and they are *stale assertions*, not a logic problem.
`data/test_logs.txt` now holds 61 sessions and `data/ground_truth.txt` labels all 61, but
`test_run_pipeline_end_to_end` and `test_json_export_pipeline` still assert
`total_test_sessions == 18`. The pipeline itself is unaffected (metrics and the 100% result are
computed over the labeled sessions). Either change makes the suite green:

```bash
# (a) update those two assertions to the current session count, or
# (b) make them data-driven, e.g. len(load_session_sequences(DEFAULT_TEST))
python report.py   # sanity check: the reported metrics are unaffected either way
```

## 13. Optional static report dashboard

The CLI is the primary interface, but there is a dependency-free way to visualise the JSON export:

```bash
python report.py --export data/results.json     # produce the data
python web/build.py                             # embed JSON into web/index.html → web/report.html
python web/build.py --serve                     # same, then serve on http://localhost:8000/report.html
```

`web/build.py` substitutes the JSON into the `%%RESULTS_JSON%%` placeholder in `web/index.html`, so the
output is a single self-contained HTML file showing the configuration, the token alphabet, test-set
summary cards, and the inferred rules. Its session explorer shows every evaluated session from the export
(including valid sessions), and supports status/rule filtering, search, sorting, inspection, and copying
verified repairs for flagged sessions. It uses only the standard library (`http.server`) — no framework,
no build tooling, no network calls, and it renders an exported snapshot rather than serving live state.

## 14. Literature survey and research gap

| Approach | Source | Strength | Limitation |
|---|---|---|---|
| SIEM rule engines (Splunk, Elastic) | Vendor detection-rule docs | Fast, deterministic, auditable | Rules are hand-authored; brittle when app behaviour changes |
| Hybrid SIEM (X-SIEM) | [ICCIT 2025](https://doi.org/10.1109/iccit68739.2025.11491524) | High accuracy via rules + RF/Isolation Forest + LLM explanations | Static rules; ML explanations are post-hoc, not structural |
| WAF regex + ML (IntelliWAF) | [IJERT 2025](https://www.ijert.org/intelliwaf-a-six-layer-intelligent-web-application-firewall-with-machine-learning-and-anomaly-detection-for-real-time-web-threat-mitigation-ijertv15is061068) | Real-time HTTP threat blocking | Signatures/ML on payloads, not ordered session grammars |
| xAI-derived SIEM rules (SHAP/ANCHORS) | [CMC 2025](https://cdn.techscience.press/files/cmc/2025/TSP_CMC-83-2/TSP_CMC_62801/TSP_CMC_62801.pdf) | Converts ML decisions to rules | Feature-threshold rules, not session sequence structure |

**Research gap.** Existing log/session anomaly tools rely on manually written rules or black-box
classifiers that flag anomalies without tracing the exact structural violation. AutoSense differs by
(1) **inferring a session grammar directly from example logs** through frequency-based n-gram mining
(standard library only, no pretrained models), (2) compiling it into an explicit **DFA** so decisions are
**decidable and hand-traceable**, and (3) explaining rejections at the **precise token position** with a
**provably minimum-cost single-token repair** found by Uniform-Cost Search. Adaptivity to new training
data and structural explainability are therefore both preserved — which is what makes this a *Theory of
Computation* artefact rather than yet another ML pipeline.

---

## 15. Limitations and known issues

Stated deliberately, because each one follows from the theory:

1. **Finite memory (`k = 2`).** The window width is fixed; languages needing a longer context or a real
   counter fall outside the hypothesis class (§9.5). Widening `k` grows the state set as `|Σ|^k`.
2. **Threshold sensitivity (non-monotone).** `τ` and `min_support` trade false alarms against missed
   anomalies, and they are CLI knobs rather than learned values. Because pruning a rule can *remove a
   constraint* entirely (falling back to bigram or unconstrained), flag counts do not move monotonically
   with `τ` — measured here: `0.70` → 11 rules / 15 flagged, `0.85` → 9 rules / 13 flagged. A session
   whose structure is *rare but legitimate* will be flagged.
3. **Positive-only training.** Only normal sessions are used for inference — the setting of Gold's
   impossibility result. The tool compensates with a restricted hypothesis class, not with a
   theoretical guarantee.
4. **Terminal truncation is a strong assumption.** Mid-session terminal tokens in training data are
   treated as noise and truncated, not learned.
5. **Session-total denominators.** Empty training sessions still count toward the session total used as
   the denominator of start/end frequencies, so empty or unparsable sessions slightly dilute those
   probabilities.
6. **Repairs are syntactic, not semantic.** A minimum-cost edit can yield a session that is
   grammatically valid but operationally implausible, if that happens to be the cheapest edit.
7. **Search cost is bounded, not cheap in the worst case.** Explored candidates can grow like
   `(|Σ|·n)^D` when no low-cost repair exists, because the search then enumerates the whole cost-≤`D`
   ball. On the current sample data the budget never bites (every flagged session is repaired at cost
   1, ≤ 21 candidates explored per session), so the default `D = 2` is comfortable — but pathological
   sessions would expose the exponential bound, which is exactly why `max_candidates` also exists.
8. **Historical examples.** Some extended theory case studies describe the earlier 28-session
   dataset and are illustrative rather than current evaluation results; use §10 for measured figures.
9. **`web/` is a viewer, not a service.** It renders an exported JSON snapshot statically; it is not a
   live server and holds no state.

## 16. Design constraints

- Python standard library only — no scikit-learn, spaCy, transformers, or pretrained models.
- Flat-file I/O only (`.txt`, `.json`) — no database, no network dependency.
- CLI entry point `python report.py`; the optional dashboard is static HTML generated with the stdlib.
- No hand-written grammar rules: rules must be derived from the training file at runtime, every run.
- No generic "invalid session" messages: every rejection carries position, rule, context, and a fix.
- No premature generalisation: built for the log format described in §4.
- Only the documented module set — no extra layers, config formats, or plugin systems.

---

## 17. File map and glossary

```
autosense/
├── data/
│   ├── sample_logs.txt       # training   (150 sessions)
│   ├── test_logs.txt         # evaluation (61 sessions)
│   ├── ground_truth.txt      # labels     (61 sessions)
│   └── results.json          # last --export artifact
├── tokenizer.py              # raw line  -> token dict            (regex lexer)
├── session_extractor.py      # tokens    -> ordered sequences
├── grammar_inference.py      # sequences -> InferredGrammar
├── automaton.py              # grammar   -> DFA (δ, δ*, validate)
├── validator.py              # session + grammar -> ValidationResult
├── repair.py                 # bounded Uniform-Cost Search
├── explainer.py              # failure -> explanation + minimal fix
├── report.py                 # full pipeline CLI + metrics
├── probability_model.py       # smoothed Markov scoring and thresholding
├── tests/                     # 100 unit / integration tests
├── web/                      # static HTML report generator (optional)
├── README.md                 # this file
└── AGENTS.md                 # agent-oriented context
```

| Term | Meaning in this project |
|---|---|
| **Σ (alphabet)** | the set of event tokens learned from the training logs |
| **String / session** | ordered sequence of events sharing one `session=` id |
| **L (session language)** | the set of sessions considered normal; approximated by `L(Ĝ)` |
| **δ / δ\*** | one-step transition / extended transition function of the DFA |
| **terminal token** | a token with end frequency `≥ τ` (`LOGOUT`), which forbids successors |
| **support** | number of training occurrences of a context `(A, B)` |
| **UCS** | Uniform-Cost Search — Dijkstra's algorithm over the edit graph |
| **repair cost** | total weight of the edit script that yields an accepted session |

## 18. References

1. J. E. Hopcroft, R. Motwani, J. D. Ullman — *Introduction to Automata Theory, Languages, and
   Computation*: DFA 5-tuple, δ\*, Myhill–Nerode, pumping lemma, closure properties.
2. M. Sipser — *Introduction to the Theory of Computation*: regular languages, decidability,
   Kleene's theorem, closure under complement/intersection.
3. E. M. Gold (1967) — *Language identification in the limit*: impossibility of learning regular
   languages from positive data alone.
4. D. Angluin (1987) — *Learning regular sets from queries and counterexamples* (`L*`).
5. E. W. Dijkstra (1959) — *A note on two problems in connexion with graphs*: uniform-cost /
   shortest-path search, the basis of the repair engine.
6. N. Chomsky (1956) — the hierarchy of formal grammars: Type-3 regular vs Type-2 context-free.

---

*AutoSense — Theory of Computation course project. Every rule it applies was learned from the log file
you gave it.*

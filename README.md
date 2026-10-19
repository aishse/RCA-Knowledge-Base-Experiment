# RCA Knowledge Base for Hardware Debugging Agents

Does giving a debugging agent memory of past root-cause analyses (RCA) make it better,
cheaper, or faster at fixing new hardware bugs? This repo runs Codex headless on Verilog
debugging tasks from ChipBench, first with no memory (baseline) and then with an RCA
knowledge base (KB) built on one set of tasks and evaluated, frozen, on a disjoint set.

> **Status:** complete. Baseline 17 / 24, case-library KB 15 / 24 (A 7 → 8, B 10 → 7).
> **The KB did not help on the held-out set.** See [KB Results](#kb-results).

## Overview

The take-home asks how to store, organize and retrieve knowledge from previous RCA runs.
I narrowed it to a small, controlled experiment:

- **Tasks:** ChipBench's zero-shot Verilog debugging set (89 tasks, 4 bug categories),
  graded deterministically by simulating the agent's fix against the golden design.
- **Agent:** Codex CLI in headless mode (`codex exec`) with default settings.
- **Sets:** A = 12 tasks to build the KB, B = 12 disjoint tasks to evaluate it.
- **Metrics:** correctness (pass/fail, mismatch count), tokens, wall-clock time, and
  qualitative analysis of the trajectories.

With 12 tasks per set the numbers are indicative, not statistically significant, so the
report leans on qualitative comparison of trajectories alongside the metrics.

## Results

| Condition | Set | Passed | Mean time | Mean input tokens | Mean output tokens |
|---|---|---|---|---|---|
| Baseline (no KB) | A | 7 / 12 | 39 s | 143k | 3.2k |
| Baseline (no KB) | B | 10 / 12 | 45 s | 148k | 3.6k |
| KB (case library) | A (mutable) | 8 / 12 | 39 s | 154k | 3.2k |
| KB (case library) | B (frozen) | **7 / 12** | 42 s | 139k | 3.3k |

One run per task. Input tokens include cached tokens (most of them).

## Quickstart

### Requirements

- macOS (tested) with Python 3.11 and `pip install -r requirements.txt` (`openai`, `python-dotenv`).
- An OpenAI API key in a `.env` file in the repo root (`OPENAI_API_KEY=...`, git-ignored). It is used for
  Codex and for KB embeddings.
- **Icarus Verilog 12**, the version ChipBench pins in its Dockerfile (see
  [Simulator](#2-simulator-icarus-verilog-12) for why not 13). Build from source:

  ```bash
  brew install autoconf bison flex gperf
  export PATH="$(brew --prefix bison)/bin:$(brew --prefix flex)/bin:$PATH"   # macOS ships Bison 2.3; v12 needs 3.x
  git clone -b v12-branch https://github.com/steveicarus/iverilog.git ~/iverilog-src
  cd ~/iverilog-src && sh autoconf.sh && ./configure --prefix=$HOME/.local/iverilog12
  # v12's driver/main.c is missing #include <mach-o/dyld.h> on macOS; add it under
  # #ifdef __APPLE__ after #include <assert.h>, then:
  make -j8 && make install
  export PATH="$HOME/.local/iverilog12/bin:$PATH"
  iverilog -V 2>&1 | head -1    # Icarus Verilog version 12
  ```

  Make sure no other `iverilog` (e.g. Homebrew's v13) comes first on your `PATH`.
  Codex uses the same `iverilog` when it simulates.

- **Codex CLI**, logged in with an API key:

  ```bash
  npm install -g @openai/codex
  codex --version
  printenv OPENAI_API_KEY | codex login --with-api-key
  codex login status
  ```

### Running

Run every script from the repo root.

```bash
# 1. Get the benchmark (pinned commit)
git clone https://github.com/zhongkaiyu/ChipBench.git 

# 2. Import the 89 zero-shot debugging tasks into tasks/
python3 scripts/import_problems.py "ChipBench/Verilog Debugging"

# 3. Check every task is gradeable -> validation_results.json
python3 scripts/validate.py

# 4. Seeded A/B split -> split.json
python3 scripts/split.py

# 5. Baseline (no KB) on A and B -> results/baseline/
caffeinate -i python3 scripts/run_experiment.py --mode baseline

# 6. KB: A with a growing KB, freeze, then B with the frozen KB -> results/kb/
caffeinate -i python3 scripts/run_experiment.py --mode kb
```

`tasks/`, `validation_results.json` and `split.json` are committed, so steps 1–4 are
only needed to reproduce them. `run_experiment.py` skips tasks that already have a
`result.json`, so an interrupted run can be resumed.

## How It Works

```
ChipBench prompt.txt ──import──► tasks/<category>/<problem>/
                                   spec.txt    buggy.sv      (agent sees these)
                                   ref.sv      test.sv       (hidden, grading only)
                                        │
                     validate.py ───────┤  golden passes? buggy fails?
                     split.py ──────────┤  seeded, task-disjoint A / B
                                        ▼
run_experiment.py ── for each task ──► run_codex.py
    1. fresh temp workspace outside the repo: spec.txt + TopModule.sv (= buggy.sv)
    2. codex exec --json --sandbox workspace-write --skip-git-repo-check <prompt>
    3. grader.py: simulate Codex's TopModule.sv against RefModule in Icarus
    4. save trajectory, final RTL, prompt, tokens, time, grade -> result.json
```

### Project Structure

```
.
├── scripts/
│   ├── import_problems.py   # ChipBench prompt -> spec.txt + buggy.sv (+ ref/test)
│   ├── grader.py            # compile + simulate candidate vs golden, count mismatches
│   ├── validate.py          # golden-passes / buggy-fails check for every task
│   ├── split.py             # seeded A/B split
│   ├── run_codex.py         # run Codex on one task in an isolated workspace
│   ├── kb.py                # KB records, embeddings, retrieval, prompt formatting
│   └── run_experiment.py    # run a condition (baseline or kb) over A and B
├── tasks/<category>/<problem>/   # spec.txt, buggy.sv, ref.sv, test.sv
├── results/<condition>/<category>/<problem>/
│   ├── trajectory.jsonl     # full Codex event stream (--json)
│   ├── stderr.log
│   ├── prompt.txt           # exact prompt used
│   ├── TopModule.sv         # Codex's final RTL
│   ├── result.json          # pass/fail, mismatches, seconds, tokens, commands, leak flag
│   └── retrieved.json       # (kb runs) which KB cases were retrieved, with scores
├── results/kb/kb_A.jsonl     # the KB as it grew during phase A (one case per line)
├── results/kb/kb_frozen.jsonl  # the frozen copy used for phase B
├── validation_results.json
├── split.json
└── README.md
```

## Design Decisions

### 1. Benchmark: ChipBench zero-shot debugging

- **ChipBench over HWE-Bench.** HWE-Bench tasks are real repo bugs (OpenTitan, Ibex,
  CVA6, …) but need per-task Docker images and Verilator builds, and the paper reports
  millions of tokens per task. That is too heavy to run several conditions in a day.
  ChipBench tasks are small, self-contained, and graded in about a second.
- **Zero-shot over one-shot.** The one-shot prompts are the same bugs with a VCD waveform
  appended, and the waveform includes the *golden* outputs (e.g. `gray_out_ref`) next to the
  buggy ones. The baseline could read the answer off the waveform, leaving little room for
  a KB to help. Codex can also simulate on its own, which is closer to real RCA.

### 2. Simulator: Icarus Verilog 12

ChipBench's Dockerfile builds Icarus from `v12-branch`. Homebrew installs v13, which
rejects a forward reference in every ChipBench testbench (`$dumpvars(..., tb_mismatch, ...)`
appears before `tb_mismatch` is declared). I built v12 from source to match the benchmark
exactly instead of modifying the testbenches.

### 3. Extracting the buggy code

Each ChipBench `*_prompt.txt` is a spec followed by fenced code. The **last** code block is
always the buggy `TopModule`. Seven prompts (FIFOs, full subtractor) contain an extra block
before it with a provided helper module, so "first block" would be wrong. The marker sentence
("Based on the problem description above…") has two wordings across the 89 prompts, so the
import splits on the last fence (`rsplit("```", 2)`) rather than on that sentence.

### 4. Validating the task set

`validate.py` checks every task is gradeable with Icarus 12:

- **Golden check:** the reference design, used as the candidate, must pass its own testbench (0 mismatches).
- **Buggy check:** the original buggy design must fail (otherwise the bug is invisible to the grader
  and an agent could "solve" it by changing nothing).

**First pass: 78 / 89 usable.** The 11 failures fell into two groups.

**a) Validation artifact: helper modules (8 tasks, fixed)**

| Task | Helper module | Error |
|---|---|---|
| arithmetic/Prob019_full_subtractor | `decoder_38` | Unknown module type |
| arithmetic/Prob021_asynchronous_FIFO | `dual_port_RAM` | Unknown module type |
| arithmetic/Prob022_synchronous_FIFO | `dual_port_RAM` | Unknown module type |
| assignment/Prob021_asynchronous_FIFO | `dual_port_RAM` | Unknown module type |
| assignment/Prob022_synchronous_FIFO | `dual_port_RAM` | Unknown module type |
| timing/Prob018_comparison_of_three_inputs | `slave_mod` | Unknown module type |
| timing/Prob021_asynchronous_FIFO | `dual_port_RAM` | Module declared twice |
| timing/Prob022_synchronous_FIFO | `dual_port_RAM` | Module declared twice |

These designs have a helper module that lives in the *candidate's* file (`buggy.sv`), not
inside `RefModule`. The first golden check used `ref.sv` with `RefModule` renamed to
`TopModule`, which either left the helper undefined or, where `ref.sv` also defines the
helper, defined it twice.

*Fix:* the golden candidate is now built from `buggy.sv` with only the buggy `TopModule`
swapped for the correct one, so it matches what a perfect fix would look like. This resolved
all 8 failures. The issue was confined to `validate.py`: real candidates are edited copies of
`buggy.sv`, so they always include the helper modules.

**b) Benchmark issue: least common multiple (3 tasks, excluded)**

`arithmetic/`, `assignment/` and `timing/Prob013_least_common_multiple`: the golden design
compiles but **mismatches against an identical copy of itself** (389 of 399 samples). A design
compared with itself should never mismatch, so the testbench or reference is not usable under
Icarus 12 on macOS. `timing/Prob013`'s buggy design also fails to compile
(`mcd_out is not a valid l-value`). All three were excluded.

**Final: 86 / 89 usable.** One buggy design (`timing/Prob022_synchronous_FIFO`) hangs the
simulator in a zero-delay loop. It still counts as "buggy fails" via the grader's timeout, so
the task is usable, but it's a reminder that grading needs a timeout.

### 5. Task split

- **Task-disjoint:** no task appears in both A and B. ChipBench reuses 33 designs across its
  tasks with different injected bugs, so a design can appear in both sets with *different*
  bugs. I kept this deliberately: it allows comparing B tasks whose design was seen in A
  against B tasks whose design was not (3 of 12 B tasks share a design with A:
  `assignment/Prob012`, `timing/Prob012`, `timing/Prob002`).
- **Method:** shuffle all 86 usable tasks with a fixed seed (`SEED = 0`), take the first 12 as
  A and the next 12 as B. The category mix was checked rather than forced:

  | Set | arithmetic | assignment | timing | state machine |
  |---|---|---|---|---|
  | A | 3 | 5 | 3 | 1 |
  | B | 2 | 4 | 5 | 1 |

- **Size:** 12 / 12 instead of 20 / 20 to leave time for the KB comparison and for reading
  trajectories closely (quality over quantity).

### 6. Agent harness

- **Isolation:** each run gets a fresh temp directory outside the repo containing only
  `spec.txt` and `TopModule.sv`, so `ref.sv` and `test.sv` are never next to the agent.
- **Default settings:** `codex exec --json --sandbox workspace-write --skip-git-repo-check`.
  `workspace-write` is the minimum needed to edit the file (the default is read-only).
  Codex CLI version 0.163.0, model `gpt-5.4`
- **Prompt:** the same base prompt in every condition (`build_prompt()` only *appends* KB
  context), so the KB is the only difference between conditions. It names the two files,
  says Icarus is available, asks for an in-place fix that keeps the module interface, and
  asks for a closing `SYMPTOM / ROOT CAUSE / FIX` summary (raw material for KB records).
  The exact prompt is saved with every run.
- **Leak check:** Codex's sandbox restricts writes but not reads, so it could in principle
  read the golden files elsewhere on disk. Every command in every trajectory is scanned for
  `RefModule`, `ref.sv`, `chipagents_takehome` and `ChipBench`, and flagged in `result.json`.
  (Agents do wander: in the smoke test Codex ran `find .. -name AGENTS.md` on its parent directory.)

## Baseline Analysis

Codex (default settings, no KB) passed **17 / 24** tasks: **7 / 12 on A** and **10 / 12 on B**.
All 24 trajectories passed the leak check. Total cost: 3.49M input tokens (mostly cached),
82k output tokens, 17 minutes of agent time.

| | Passing runs (17) | Failing runs (7) |
|---|---|---|
| Median time | 31 s | 39 s |
| Median input tokens | 125k | 170k |
| Median shell commands | 5 | 6 |
| Median lines changed in `TopModule.sv` | **2** | **16** |

By bug category: state machine 2/2, arithmetic 4/5, assignment 7/9, **timing 4/8**.

### Failure modes

Reading all 7 failing trajectories against the true fix (`buggy.sv` vs the golden design):

| Task | Set | True bug | What Codex did | Mode |
|---|---|---|---|---|
| assignment/Prob001 sequence detect | A | wrong constant (`0111_0011` → `0111_0001`) | fixed the constant **and** compared the post-shift window | over-repair |
| assignment/Prob002 extraneous items | A | wrong constant (`001` → `011`) | fixed the constant **and** shifted both comparison windows | over-repair |
| arithmetic/Prob002 extraneous items | A | reversed shift direction | fixed the shift **and** compared the post-shift window | over-repair |
| timing/Prob010 8→16 width converter | A | first byte held in `always @(*)` instead of a register | correct diagnosis, then rewrote the module with an extra pipeline stage | over-repair |
| timing/Prob027 settable counter | A | `number` in `always @(*)` instead of a register | made `number` clocked **and** changed `zero`'s timing | over-repair |
| timing/Prob002 extraneous items | B | match half computed combinationally instead of registered | rewrote detection on the post-shift window | over-repair |
| timing/Prob012 overlapping FSM | B | `flag` in `always @(*)` instead of a register | changed `<=` to `=` in next-state logic (a style issue), missed the real bug | mis-localization |

**1. The dominant failure is over-repair, not failure to find the bug.** In 6 of 7 failures
Codex located the real root cause, usually fixing it correctly, then changed something
else that was not broken. Failing fixes changed a median of 16 lines versus 2 for passing ones.

**2. Self-verification does not catch it.** Codex writes and runs its own testbench in most
runs, but that testbench encodes its own reading of the spec, so it confirms the wrong timing.
On timing/Prob010 its summary reports the fix as verified; it fails with 72 mismatches.

**3. Two recurring bug patterns.** "State held in `always @(*)` that should be clocked" is the
true bug in timing/Prob010, timing/Prob027, timing/Prob002 and timing/Prob012, and Codex
missed or over-repaired all four. The "extraneous items" sequence detector failed in all three
of its variants (16 mismatches each), the same post-shift-window mistake every time.

### Implications for the KB

- **The repair discipline is the target.** A lesson like *"there is one injected bug; change only
  the root cause and preserve every other signal's cycle timing"* directly addresses 6 of 7 failures.
- **Learn from failures.** 5 of the 7 failures are in set A, so a KB built only from passing runs
  would miss the main lesson. After grading an A task, the true fix is known (as in a real
  post-mortem), so records can store what actually went wrong. Only set A's answers are used.
  
### Other observations

- **Prompt framing matters.** With an early, vaguer prompt, Codex rewrote the whole Gray-code
  counter; with the final RCA prompt it made the exact one-line fix in the smoke test. One run each,
  so suggestive only.


## RCA Knowledge Base

### Design space

The baseline showed that Codex usually *finds* the bug but over-repairs it (6 of 7 failures),
and that both set-B failures share a design with a set-A task. I considered:

| Idea | Data structure | Interface | Targets |
|---|---|---|---|
| Lessons playbook | short list of general rules | always in the prompt | over-repair |
| **Case library (chosen)** | one post-mortem record per past task | **top-k retrieved into the prompt (RAG, push)** | seen designs, specific bug patterns |
| Bug-pattern checklist | taxonomy of bug types seen in A | in the prompt | recurring patterns (e.g. state in `always @(*)`) |
| `AGENTS.md` | rules file | Codex's native instruction file (trajectories show it looks for one) | over-repair |
| Search tool / MCP | same case records | agent calls `kb_search` when it wants (pull) | scale |
| Diff guardrail | statistics of past fixes | check run after editing | self-verification blind spot |
| Testbench artifacts | reusable testbench templates | files in the workspace | tokens / time |

**Why a case library with push retrieval:** case records with a confirmed root cause and fix are
how production RCA knowledge bases are usually built (post-mortems of resolved bugs). Pushing the
top 3 cases into the prompt guarantees the agent sees them, so the experiment measures the
*content* of the KB rather than whether the agent chooses to use a tool. Retrieving only the top 3
keeps the prompt size bounded as the KB grows, and a bad record only affects tasks similar enough
to retrieve it. A pull interface (CLI or MCP tool) over the same records is the production-style
next step; I left it out because it changes two things at once (content and interface) and the
agent might never call it.

### What a record stores

After each set-A task is graded, `make_record` (`scripts/kb.py`) builds one case from the saved run:

| Field | Source |
|---|---|
| `task`, `spec`, `buggy_code` | the task files |
| `agent_summary` | Codex's final `SYMPTOM / ROOT CAUSE / FIX` message |
| `passed`, `mismatches` | the grader |
| `lines_changed` | diff of `buggy.sv` vs Codex's final `TopModule.sv` |
| `true_fix`, `true_fix_lines` | diff of `buggy.sv` vs the golden design (built with `build_golden`) |
| `failure_mode`, `touched_root_cause`, `extra_edits`, `unnecessary_edits` | computed from the two diffs (below); `unnecessary_edits` lists the lines of the buggy design the agent changed that the confirmed fix did not need |
| `lesson` | one sentence, chosen by failure mode |
| `embedding` | OpenAI embedding of `spec + buggy_code` |

Records are written for **passing and failing** runs: 5 of the 7 baseline failures are in set A,
so a KB built only from successes would miss the main lesson. Using the golden design for set-A
tasks mirrors a real post-mortem, where the confirmed fix is known once the bug is resolved. No
set-B answers are ever used.

### Failure-mode classification

Lessons state what happened rather than an assumed cause, so a wrong hypothesis can't spread
through the KB. The lines removed by the true fix are the faulty lines; comparing them with the
lines Codex removed gives:

| Mode | Rule | Lesson (abridged) |
|---|---|---|
| `passed` | grader passed | "Fixed with an N-line change…", plus "a smaller fix targeting only the root cause would also have worked" if Codex changed lines the fix didn't need |
| `missed_root_cause` | Codex touched none of the faulty lines | "Missed the root cause: the agent did not modify the faulty lines." |
| `over_repair` | touched the faulty lines **and** other lines | "Also changed N lines the fix did not need; the edits are [*the exact lines*]. Those extra edits likely caused the mismatches. Change only the root cause." |
| `wrong_fix` | touched only the faulty lines, still failed | "The change was incorrect. Compare with the confirmed fix." |

On the 7 baseline failures this rule gives 6 `over_repair` and 1 `missed_root_cause`
(`timing/Prob012`), matching a manual reading of every trajectory. A first version that compared
total line counts (agent > 2× true fix) mislabeled 3 over-repairs as `wrong_fix`, because the
reference's formatting inflates the true-fix line count.

### Retrieval

- **Embeddings:** OpenAI `text-embedding-3-small` on `spec + "\n\n" + buggy_code`, which is only what
  the agent can see. Never the bug category or any grading file. Vectors are stored inline in each
  record, so the frozen KB never needs re-embedding.
- **Similarity:** cosine similarity between the new task's embedding and every record.
- **Top k = 3**, no threshold and no deduplication.
- I chose embeddings over keyword (TF-IDF) scoring because specs describe designs in prose. At 12
  records any reasonable method finds the obvious matches.

### Augmentation

`format_cases` turns the retrieved records into a section appended to the unchanged base prompt
(`build_prompt(kb_context)`):

```
## Past debugging cases (from a knowledge base of previously debugged designs)
These cases may or may not be relevant to this task. Use them as hints, not as answers.

### Case 1: <task> (outcome: PASS|FAIL)
Agent's diagnosis (verified): <Codex's summary, ≤1200 chars>     <- passing cases only
Confirmed fix (diff of buggy -> correct): <true fix, ≤1200 chars>
Lesson: <one sentence>
```

**Only verified information is shown.** A passing case's diagnosis was confirmed by the grader, so
it is shown and labeled *verified*. A failing case's diagnosis is wrong by definition, so it is
**never** shown: the agent sees only the confirmed fix and a lesson that names the exact lines the
earlier attempt changed unnecessarily. Showing an unverified diagnosis risks teaching the mistake.
For example, the failed extraneous-items attempts in set A reasoned that the detector should compare
the just-shifted window, which is wrong; a similar B task could copy that edit. The spec, buggy code
and embedding of past cases are not included either. The exact prompt for every
run is saved in `prompt.txt`, and the retrieved cases with scores in `retrieved.json`.

### Protocol

```
Phase A (mutable): for each A task, in split.json order:
    retrieve top 3 from kb_A.jsonl -> run Codex -> grade -> append a record
Freeze:            copy kb_A.jsonl -> kb_frozen.jsonl
Phase B (frozen):  for each B task: retrieve top 3 from kb_frozen.jsonl -> run Codex -> grade
```

The first A task sees an empty KB (same as the baseline), and each later A task can retrieve
every earlier one. The run is resumable: finished tasks are skipped, and a finished A task that
is missing from the KB is recorded on the next run.

### Offline retrieval check

Before any KB run, I embedded the 12 set-A *baseline* results and retrieved the top 3 for each
set-B task (no Codex):

```text
arithmetic/Prob014_sequence_generator
   0.868  state_machine/Prob012_state_machine_overlapping_sequence_detection  (passed)
   0.855  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.854  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
arithmetic/Prob031_johnson_counter
   0.858  timing/Prob027_settable_counter  (over_repair)
   0.801  timing/Prob023_gray_code_counter  (passed)
   0.798  state_machine/Prob012_state_machine_overlapping_sequence_detection  (passed)
assignment/Prob012_state_machine_overlapping_sequence_detection
   1.000  state_machine/Prob012_state_machine_overlapping_sequence_detection  (passed)
   0.879  assignment/Prob004_continuous_input_sequence_detect2  (passed)
   0.859  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
timing/Prob003_non-overlapping_sequence_detect
   0.940  assignment/Prob004_continuous_input_sequence_detect2  (passed)
   0.900  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.900  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
state_machine/Prob003_non-overlapping_sequence_detect
   0.945  assignment/Prob004_continuous_input_sequence_detect2  (passed)
   0.897  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.897  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
timing/Prob016_odd-number_division_with_a_duty_cycle_of_half
   0.837  timing/Prob027_settable_counter  (over_repair)
   0.820  timing/Prob010_integer_multiple_data_bit_width_conversion_8to16  (over_repair)
   0.812  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
timing/Prob002_extraneous_items_sequence_detect
   0.997  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.997  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.902  assignment/Prob001_continuous_input_sequence_detect  (over_repair)
timing/Prob026_simple_stopwatch
   0.878  timing/Prob027_settable_counter  (over_repair)
   0.820  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.820  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
assignment/Prob007_data_accumulation_output
   0.892  timing/Prob010_integer_multiple_data_bit_width_conversion_8to16  (over_repair)
   0.815  arithmetic/Prob002_extraneous_items_sequence_detect  (over_repair)
   0.814  assignment/Prob002_extraneous_items_sequence_detect  (over_repair)
assignment/Prob024_multiplication_and_bitwise_operations
   0.835  arithmetic/Prob011_4-bit_carry_look-ahead_adder_circuit  (passed)
   0.795  timing/Prob027_settable_counter  (over_repair)
   0.792  timing/Prob010_integer_multiple_data_bit_width_conversion_8to16  (over_repair)
assignment/Prob031_johnson_counter
   0.858  timing/Prob027_settable_counter  (over_repair)
   0.801  timing/Prob023_gray_code_counter  (passed)
   0.797  state_machine/Prob012_state_machine_overlapping_sequence_detection  (passed)
timing/Prob012_state_machine_overlapping_sequence_detection
   0.997  state_machine/Prob012_state_machine_overlapping_sequence_detection  (passed)
   0.876  assignment/Prob004_continuous_input_sequence_detect2  (passed)
   0.858  assignment/Prob002_extraneous_items_sequence_detect  (over_repair) 
```

- **Seen designs find their counterpart almost perfectly:** `timing/Prob002` → both A
  extraneous-items cases (0.997), `timing/Prob012` and `assignment/Prob012` →
  `state_machine/Prob012` (0.997 / 1.000). The spec is identical and the code differs only at the
  injected bug.
- **Unseen designs get sensible neighbors:** sequence detectors → sequence detectors, counters →
  counters, data accumulation → the width converter, multiplication → the adder.
- **Scores are compressed (≈0.79–1.0)** because every spec is "a clocked Verilog module that does X",
  so there is no natural similarity threshold.
- **Redundancy:** set A contains two variants of the same design (extraneous items), and they fill 2
  of the 3 slots for 8 of the 12 B tasks. I kept plain top 3 for simplicity and because the two
  cases carry different bugs (see What I'd Do Next).
- **Failure cases appear almost everywhere:** half of the A records are over-repair failures, so
  nearly every B task sees an over-repair lesson. This is a property of *this* set A; a set A
  with fewer failures would surface that lesson less often.

## KB Results

With the case library, Codex passed **15 / 24**: **8 / 12 on A** (baseline 7) and **7 / 12 on B**
(baseline 10). All 24 trajectories passed the leak check.

| | Baseline A | KB A | Baseline B | KB B |
|---|---|---|---|---|
| Passed | 7 / 12 | 8 / 12 | 10 / 12 | **7 / 12** |
| Mean time | 39 s | 39 s | 45 s | 42 s |
| Mean input tokens (cached) | 143k | 154k (142k) | 148k | 139k (128k) |
| Mean output tokens | 3.2k | 3.2k | 3.6k | 3.3k |
| Median lines changed | 10 | **5** | 4 | **8.5** |

Cost is essentially unchanged: the three retrieved cases add a few thousand prompt tokens, which
are small next to the ~140k tokens Codex spends reading files and simulating, and mostly cached.

### Task-level changes

| Task | Set | Baseline | KB | KB failure mode |
|---|---|---|---|---|
| timing/Prob010 width converter | A | 72 mismatches | **pass** | – |
| timing/Prob003 non-overlapping detector | B | pass | 1 mismatch | `wrong_fix` |
| timing/Prob016 odd clock divider | B | pass (7 lines) | 513 mismatches (23 lines) | `over_repair` |
| assignment/Prob007 data accumulation | B | pass (2 lines) | 258 mismatches (39 lines) | `over_repair` |
| timing/Prob002 extraneous items *(seen design)* | B | 16 mismatches | 16 mismatches | `over_repair` |
| timing/Prob012 overlapping FSM *(seen design)* | B | 30 mismatches | 30 mismatches | `missed_root_cause` |

Every other task kept its baseline outcome. Failure modes: baseline 6 `over_repair` / 1
`missed_root_cause`; KB 6 `over_repair` / 2 `wrong_fix` / 1 `missed_root_cause`.

### What worked

- **Set A got slightly better and edits got smaller.** One A task flipped to pass and none regressed,
  and the median edit in A halved (10 → 5 lines). `assignment/Prob001` still failed, but with a 2-line
  edit instead of 16: it no longer over-repaired, though the remaining change was still wrong.
- **Retrieval itself worked.** Seen designs retrieved their set-A counterpart at 0.997–1.000 similarity,
  and unseen designs got sensible neighbors (see [Offline retrieval check](#offline-retrieval-check)).
- **No extra cost.** Time and tokens are within run-to-run noise of the baseline.

### What failed

- **Set B got worse (10 → 7), and every regression is on an *unseen* design.** Seen designs stayed at
  1 / 3; unseen designs dropped from 9 / 9 to 6 / 9. The cases that were supposed to help most (same
  design, different bug) changed nothing, and the cases that were only loosely related hurt.
- **Two regressions are large over-repairs, the exact failure the KB was meant to prevent.**
  Edits in B grew (median 4 → 8.5 lines). Both large regressions retrieved `timing/Prob010` from set A:
  a **passing** case whose "verified" diagnosis describes rewriting the module into one synchronous
  block (47 lines changed against an 11-line true fix). The KB labels it *verified* because the grader
  passed it, but it is an over-repair that happened to be correct. A plausible reading is that showing
  a successful rewrite as a worked example encouraged rewrites on loosely related designs
  (`assignment/Prob007`: 2-line baseline fix → 39-line rewrite). This is a hypothesis from one run per
  task, not a measured effect.
- **The seen-design cases didn't transfer** because the set-A variants of those designs carry
  *different* injected bugs. The KB told Codex what was wrong last time, which is not what is wrong now
  (see `timing/Prob002` below), and `timing/Prob012` missed the root cause in both conditions.
- **Some of the difference is variance.** `timing/Prob003` and `state_machine/Prob003` retrieved the
  same three cases; one passed and one failed by a single mismatch (a combinational output lost its
  `rst_n` gating). With one run per task, a ±2 swing on 12 tasks is within what repeated runs could show.

### How set A affects set B

The KB is only as good as set A's mix of outcomes. Half of the A records are over-repair failures and
one of the "successes" is itself an over-repair, so most B tasks received at least one case built
around a large rewrite. The retrieved cases are also dominated by two variants of the same design
(extraneous items), which fill 2 of 3 slots for 8 of 12 B tasks. A different set A (or a different
order of A, since each A task only sees earlier ones) would give B different neighbors. In this split,
set A was too small and too skewed for its cases to transfer.

### Conclusion

A push-RAG case library, built from 12 post-mortems, did **not** improve Codex on a disjoint set
(B 10 → 7, unchanged cost). It slightly helped the tasks it was built from (A 7 → 8, smaller edits),
which suggests the records carry useful information but that **retrieved cases are not a reliable
way to change *how* the agent repairs** (scope of edits, spec interpretation). Specific cases teach
"what was wrong in that design", while the dominant failure is a general behavior. Two cautions on
reading these numbers: one run per task, and set B's baseline results informed the KB's design (which
information is shown), so B is not perfectly held out. A clean re-test would freeze the design and
evaluate on a third set drawn from the 62 unused validated tasks, with several runs per task.

### The KB cannot override the agent's interpretation of the spec

`timing/Prob002` (extraneous-items detector, a seen design) shows a limit of the KB:

- **Without the KB (baseline)** Codex decided the detector should compare the *just-shifted* 9-bit
  window and rewrote the detection logic around it (16 mismatches).
- **With the KB** it retrieved both set-A variants of the same design (similarity 0.997). Both were
  failures, and their lessons named the exact line `else if (a_tem[2:0] == 3'b110)` as an edit that
  was not needed. No unverified diagnosis was shown. Codex still rewrote the detector around the
  just-shifted window (`{a_tem[7:0], a}`), removed that same line, and failed with the same 16 mismatches.
- **The actual bug** (the `match_f` half computed in `always @(*)` instead of a register) appears in
  neither retrieved case, because the set-A variants of this design had different injected bugs.

So this failure comes from how Codex *interprets* an ambiguous spec ("the output match is updated
sequentially"), not from missing information. The baseline makes the same mistake without any KB,
and an explicit warning from a related post-mortem did not change it. A case library helps when the
missing piece is knowledge, like a bug pattern or a confirmed fix; it helps much less when the agent
is confident in a wrong reading of the spec. That connects to the baseline finding that every failure
is a one-cycle timing disagreement caused by loosely specified latency (see
[Baseline Analysis](#baseline-analysis)).

## Limitations & Known Issues

- 12 tasks per set and one run per task: results are indicative, not statistically significant.
- ChipBench bugs are small, single-module, hand-injected bugs, far simpler than real RTL RCA.
- The leak check only inspects shell commands Codex runs.
- **The harness assumes the injected bug is in `TopModule`,** not in helper modules in `buggy.sv`. This
  holds for ChipBench (helpers match the spec-provided copies apart from whitespace and comments), but
  not necessarily for other benchmarks. Because `RefModule` uses the candidate's helper modules in 6
  tasks, an agent editing a helper could also change the reference's behavior.
- **Retrieval is one-shot per task.** The KB is retrieved once from the initial spec and code, not
  re-queried as the agent learns more during debugging.
- **The KB depends on the order of set A** (one fixed seeded order), and on its mix of passes and failures.
- **Unnecessary edits are matched line by line,** so for large rewrites the list includes structural
  lines such as `begin`, which makes those lessons noisier.

## What I'd Do Next

- **Pull interface:** expose the same case store as a `kb_search` tool (CLI or MCP) and measure whether
  and when the agent chooses to query it.
- **Always-on lessons layer:** combine retrieved cases with a short set of general rules distilled from
  set A, so the over-repair lesson reaches tasks with no close match.
- **Score cases by quality, not just pass/fail:** a passing but oversized fix (`timing/Prob010`, 47
  lines vs an 11-line true fix) should be shown as the confirmed minimal fix, or not as a worked example.
- **Robustness:** verify that non-`TopModule` modules in the agent's file are unchanged from `buggy.sv`.
- **Vector storage at scale:** embeddings are stored inline in each JSONL record, which is
  simple and makes freezing the KB a single file copy. At production scale I'd move them to
  a vector database (e.g. FAISS or pgvector) for fast nearest-neighbor search and metadata
  filtering, and keep the human-readable cases separate from the vectors.
- **Diversity-aware retrieval:** some retrieved cases are redundant (same design, different bug). Limit
  results to one case per design, or use MMR (maximal marginal relevance).
- **Repeated runs:** several runs per task per condition, to separate the KB's effect from run-to-run variance.
- **Simulation ablation:** Codex usually writes its own testbench, which encodes its own reading of the
  spec and so tends to confirm wrong fixes (`timing/Prob002`, `timing/Prob003`). Compare three
  conditions: no simulation, self-written testbench (current), and a provided stimulus-only testbench,
  to see whether self-verification helps or reinforces misinterpretations.
  
## AI Usage

I used an AI assistant (Claude) as a planning and review partner: to discuss design options, explain unfamiliar tools (Icarus Verilog, Codex CLI), review my code, and draft this README's structure. I wrote the scripts myself with its guidance, and every design decision was mine for this project.

## Sources

- ChipBench: Z. Yu, C. Zhou et al., *ChipBench: A Next-Step Benchmark for Evaluating LLM Performance
  in AI-Aided Chip Design*, [arXiv:2601.21448](https://arxiv.org/abs/2601.21448);
  code [github.com/zhongkaiyu/ChipBench](https://github.com/zhongkaiyu/ChipBench) (MIT), commit `b4ba3a0`.
- HWE-Bench: *HWE-Bench: Benchmarking LLM Agents on Real-World Hardware Bug Repair Tasks*,
  [arXiv:2604.14709](https://arxiv.org/pdf/2604.14709).
- Icarus Verilog: [github.com/steveicarus/iverilog](https://github.com/steveicarus/iverilog), `v12-branch`.
- Codex CLI: [OpenAI Codex non-interactive mode docs](https://learn.chatgpt.com/docs/non-interactive-mode).

## Time Spent

~9–10 hours: ~2 h setup (Codex, building Icarus 12 from source), ~2 h import/grader/validation, ~1.5 h Codex runner and baseline, ~2.5 h KB design and implementation, ~1.5 h analysis and write-up.

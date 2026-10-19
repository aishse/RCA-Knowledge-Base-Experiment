# RCA Knowledge Base for Hardware Debugging Agents

> **Status:** complete. Baseline 15 / 24, case-library KB 15 / 24. **The KB did not measurably
> change correctness**; two identical baseline runs differed on 4 of 12 set-B tasks. See [KB Results](#kb-results).

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
| Baseline (no KB) | A | 7 / 12 | 38 s | 137k | 3.0k |
| Baseline (no KB) | B | 8 / 12 | 40 s | 147k | 3.1k |
| KB (mutable) | A | 8 / 12 | 39 s | 154k | 3.2k |
| KB (frozen) | B | 7 / 12 | 42 s | 139k | 3.3k |

One run per task. Input tokens include cached tokens (most of them). An earlier baseline run also
showed set A passing 7/12 cases and set B passing 10/12 cases. 

## Quickstart

### Requirements

- macOS (tested) with Python 3.11 and `pip install -r requirements.txt` (`openai`, `python-dotenv`).
- An OpenAI API key in a `.env` file in the repo root (`OPENAI_API_KEY=...`, git-ignored). It is used for
  Codex and for KB embeddings.
- **Icarus Verilog 12**, the version ChipBench pins in its Dockerfile (see
  [Simulator](#2-simulator-icarus-verilog-12) for why not 13). Build from source:

  ```bash
  brew install autoconf bison flex gperf

  export PATH="$(brew --prefix bison)/bin:$(brew --prefix flex)/bin:$PATH" 

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
git -C ChipBench checkout b4ba3a0

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
`result.json`, so an interrupted run can be resumed. Results are committed, so to rerun a
condition from scratch, move `results/<condition>/` aside first.

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
├── results/smoke/           # one-task smoke test of the runner
├── validation_results.json   # usable / unusable tasks with grader logs
├── split.json                # seed + A and B task lists
├── requirements.txt
├── .env                      # OPENAI_API_KEY (you create it; git-ignored)
└── README.md
```

## Design Decisions

### 1. Benchmark: ChipBench zero-shot debugging

- **ChipBench over HWE-Bench.** The HWE-Bench tasks need per-task Docker images and Verilator builds, which is too heavy. ChipBench tasks are small, self-contained, and graded in about a second.
- **Zero-shot over one-shot.** The one-shot prompts are the same bugs with a VCD waveform
  appended, and the waveform includes the *golden* outputs (e.g. `gray_out_ref`) next to the
  buggy ones. The baseline could read the answer off the waveform, making a KB less useful for Codex. Codex is also able to simulate on its own using Icarus.  

### 2. Simulator: Icarus Verilog 12

ChipBench's Dockerfile builds Icarus from `v12-branch`. Homebrew installs v13, which rejects a forward reference in every ChipBench testbench
(`tb_mismatch` is used in `$dumpvars` before it is declared). I built v12 from source to match the
benchmark exactly instead of modifying the testbenches.

### 3. Extracting the buggy code

Each ChipBench `*_prompt.txt` is a spec followed by fenced code. The **last** code block in the prompt is
always the buggy `TopModule`. Seven prompts (FIFOs, full subtractor) contain an extra block
before it with a provided helper module, so "first block" would be wrong. Initially, using the marker sentence
("Based on the problem description above…") made sense as the split point. However, it has different wordings across the 89 prompts, so the
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
swapped for the correct one from `ref.sv`, so it matches what a perfect fix would look like. This resolved
all 8 failures.

**b) Benchmark issue: least common multiple (3 tasks, excluded)**

`arithmetic/`, `assignment/` and `timing/Prob013_least_common_multiple`: the golden design
compiles but **mismatches against an identical copy of itself** (389 of 399 samples). The reference
drives `lcm_out` to high-impedance (`'hz`) whenever its GCD register is 0, which is most of the
run. The testbench's check, `ref === (ref ^ dut ^ ref)`, turns `z` into `x` through the XOR, and
`z === x` is false, so even a perfect design fails. No candidate can pass these tasks.
`timing/Prob013`'s buggy design also fails to compile (`mcd_out is not a valid l-value`).
All three were excluded.

**Final: 86 / 89 usable.** 

### 5. Task split

- **Method:** shuffle all 86 usable tasks with a fixed seed (`SEED = 0`), take the first 12 as
  A and the next 12 as B. The category mix was checked rather than forced:

  | Set | arithmetic | assignment | timing | state machine |
  |---|---|---|---|---|
  | A | 3 | 5 | 3 | 1 |
  | B | 2 | 4 | 5 | 1 |

- **Design-disjoint vs task-disjoint**: I noticed that some designs were reused across the different bug types. I considered a split that was both task and design disjoint, but then set B wouldn't have any relevant lessons based on design to reference from. The lessons would be too disjoint from set B to be useful. Keeping it task-disjoint means 3 of 12
  B tasks share a design with A (`assignment/Prob012`, `timing/Prob012`, `timing/Prob002`), which
  allows comparing seen vs unseen designs.
  
- **Size:** 12 / 12 to leave time for the KB comparison and for reading
  trajectories closely. 

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

Codex (default settings, no KB) passed **15 / 24** tasks: **7 / 12 on A** and **8 / 12 on B**.
All 24 trajectories passed the leak check. Total cost: 3.41M input tokens (mostly cached),
74k output tokens, 16 minutes of agent time.

| | Passing runs (15) | Failing runs (9) |
|---|---|---|
| Median time | 32 s | 41 s |
| Median input tokens | 135k | 125k |
| Median shell commands | 6 | 5 |
| Median lines changed in `TopModule.sv` | **2** | **35** |

By bug category: state machine 2/2, arithmetic 4/5, assignment 6/9, **timing 3/8**.


### Failure modes

Comparing each failing fix with the true fix (`buggy.sv` vs the golden design):

| Task | Set | True bug | Lines changed | Mismatches | Mode |
|---|---|---|---|---|---|
| assignment/Prob001 sequence detect | A | wrong constant | 16 | 4 | over-repair |
| assignment/Prob002 extraneous items | A | wrong constant | 37 | 16 | over-repair |
| arithmetic/Prob002 extraneous items | A | reversed shift direction | 37 | 16 | over-repair |
| timing/Prob010 8→16 width converter | A | first byte held in `always @(*)` instead of a register | 50 | 72 | over-repair |
| timing/Prob027 settable counter | A | `number` in `always @(*)` instead of a register | 29 | 260 | over-repair |
| timing/Prob002 extraneous items | B | match half computed combinationally instead of registered | 35 | 16 | over-repair |
| timing/Prob016 odd clock divider | B | output block uses undeclared `clk`/`rst_n` | 49 | 430 | over-repair |
| assignment/Prob007 data accumulation | B | counter wraps at 2 instead of 3 | 4 | 122 | over-repair |
| timing/Prob003 non-overlapping detector | B | outputs registered instead of combinational | 29 | 1 | wrong fix |


**1. The dominant failure is over-repair, not failure to find the bug.** In 8 of 9 failures Codex
changed the faulty lines and also changed lines that weren't broken. On assignment/Prob007 it fixed
the counter wrap correctly, then also changed how `ready_b` gates the first sample, a 4-line edit
that caused 122 mismatches. Failing fixes changed a median of 35 lines vs 2 for passing ones.

**2. Self-verification does not catch it.** All 9 failing runs simulated their fix with Icarus, and 8
of 9 final summaries say the fix was verified or simulated. Codex's testbench encodes its own reading
of the spec, so it confirms the wrong timing.

### Run-to-run variance

An earlier identical baseline run scored 17 / 24. Set A had the same 5 failures, but **4 of the 12
set-B tasks changed outcome**: timing/Prob003, timing/Prob016 and assignment/Prob007 passed in
run 1 and failed in run 2, and timing/Prob012 did the reverse. Differences of 2–3 tasks per set
are within noise at this sample size.


## RCA Knowledge Base

### Design space

In the first baseline run, Codex usually *found* the bug but over-repaired it (6 of 7 failures),
and both set-B failures shared a design with a set-A task. The second run confirms the over-repair pattern. I considered:

| Idea | Data structure | Interface | Targets |
|---|---|---|---|
| Lessons playbook | short list of general rules | always in the prompt | over-repair |
| **Case library (chosen)** | one post-mortem record per past task | **top-k retrieved into the prompt (RAG, push)** | seen designs, specific bug patterns |
| `AGENTS.md` | rules file | Codex's native instruction file (trajectories show it looks for one) | over-repair |


**Why a case library with push retrieval:** records with a confirmed root cause and fix are how
production RCA knowledge bases are usually built (post-mortems of resolved bugs). Pushing the top 3
into the prompt guarantees the agent sees them, so the experiment measures the KB's *content* rather
than whether the agent chooses to use a tool, and top-k keeps the prompt size fixed as the KB grows.
Embeddings find similar designs even when specs describe them in different words.

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

Records are written for **passing and failing** runs: 5 of the baseline failures (in both runs) are in set A,
so a KB built only from successes would miss the main lesson. No
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

On the first baseline run's 7 failures this rule gives 6 `over_repair` and 1 `missed_root_cause`
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


## KB Results

With the case library, Codex passed **15 / 24**: **8 / 12 on A** and **7 / 12 on B**, the same total
as the baseline. All 24 trajectories passed the leak check.

| | Baseline A | KB A | Baseline B | KB B |
|---|---|---|---|---|
| Passed | 7 / 12 | 8 / 12 | 8 / 12 | 7 / 12 |
| Mean time | 38 s | 39 s | 40 s | 42 s |
| Mean input tokens | 137k | 154k | 147k | 139k |
| Mean output tokens | 3.0k | 3.2k | 3.1k | 3.3k |
| Median lines changed | 22.5 | **5** | 5 | 8.5 |

### Task-level changes vs the baseline

| Task | Set | Baseline run 1 | Baseline run 2 | KB |
|---|---|---|---|---|
| timing/Prob010 width converter | A | 72 | 72 | **pass** |
| timing/Prob012 overlapping FSM *(seen design)* | B | 30 | pass | 30 |
| timing/Prob003 non-overlapping detector | B | pass | 1 | 1 |
| timing/Prob016 odd clock divider | B | pass | 430 | 513 |
| assignment/Prob007 data accumulation | B | pass | 122 | 258 |
| timing/Prob002 extraneous items *(seen design)* | B | 16 | 16 | 16 |

(Numbers are mismatch counts.) Every other task passed or failed in all three runs.

### What the comparison shows

- **No measurable effect on correctness.** The KB is +1 on A and −1 on B against the baseline, while
  two identical baseline runs differed by 2 on B. The three B tasks that failed with the KB
  (Prob003, Prob016, Prob007) also failed in baseline run 2, so they are tasks Codex is unreliable
  on, not tasks the KB broke.
- **Smaller edits on set A.** Median lines changed in A was 5 with the KB vs 10 and 22.5 in the two
  baseline runs. This is the behavior the KB targeted (over-repair), and it is the most consistent
  signal in the data. It didn't turn into more passes: assignment/Prob001 went from a 16-line to a
  2-line edit and still failed.
- **No improvement on seen designs.** Seen designs retrieved their set-A counterpart (similarity
  0.997–1.000), but those cases carry a *different* injected bug, so they describe what was wrong
  last time rather than now. timing/Prob002 failed identically in all three runs (see below).
- **No extra cost.** Time and tokens are within run-to-run noise.


### How set A affects set B

The KB is only as good as set A's mix of cases. Half of the A records are over-repair failures,
two are variants of the same design (filling 2 of 3 retrieval slots for 8 of 12 B tasks), and one
"success" is itself an over-repair. Each A task only sees earlier A tasks, so the order of A matters
too. In this split, set A was too small and too skewed for its cases to transfer to new designs. 


### Codex behavior

I ran the baseline twice to check how consistent Codex is. With identical inputs, 4 of 12 set-B tasks
changed outcome. In both runs Codex usually located the root cause but didn't consistently stop at it,
and the tasks that flipped are ones where the spec leaves timing ambiguous. So a single run is a noisy
measurement of an agent, and a KB's effect has to be measured over repeated runs.

### Conclusion

A push-RAG case library built from 12 post-mortems **did not measurably change Codex's correctness**
on a disjoint set, at no extra cost. It did shrink edits on the tasks it was built from. The
retrieved cases seem to influence *how much* the agent edits more than *whether* it gets the fix
right. The dominant remaining failure is the agent's interpretation of loosely specified timing,
which its own testbench then confirms. The biggest lesson about method: with one run per task,
run-to-run variance (4 of 12 B tasks flipped between identical baseline runs) is as large as any
KB effect, so evaluating a KB needs several runs per task.


### The KB cannot override the agent's interpretation of the spec

`timing/Prob002` (extraneous-items detector, a seen design) shows a limit of the KB:

- **Without the KB (baseline run 1)** Codex decided the detector should compare the *just-shifted* 9-bit
  window and rewrote the detection logic around it (16 mismatches). Baseline run 2 failed with the same 16 mismatches.
- **With the KB** it retrieved both set-A variants of the same design (similarity 0.997). Both were
  failures, and their lessons named the exact line `else if (a_tem[2:0] == 3'b110)` as an edit that
  was not needed. No unverified diagnosis was shown. Codex still rewrote the detector around the
  just-shifted window (`{a_tem[7:0], a}`), removed that same line, and failed with the same 16 mismatches.
- **The actual bug** (the `match_f` half computed in `always @(*)` instead of a register) appears in
  neither retrieved case, because the set-A variants of this design had different injected bugs.

So this failure comes from how Codex *interprets* an ambiguous spec ("the output match is updated
sequentially"), not from missing information. Both baseline runs fail the same way without any KB,
and an explicit warning from a related post-mortem did not change it. A case library helps when the
missing piece is knowledge, like a bug pattern or a confirmed fix; it helps much less when the agent
is confident in a wrong reading of the spec. That connects to the baseline finding that Codex's own testbench confirms its reading of the spec
(see [Baseline Analysis](#baseline-analysis)).

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

- **Build a pull interface:** expose the same case store as a `kb_search` tool (CLI or MCP) and measure whether
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

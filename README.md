# RCA Knowledge Base for Hardware Debugging Agents

Does giving a debugging agent memory of past root-cause analyses (RCA) make it better,
cheaper, or faster at fixing new hardware bugs? This repo runs Codex headless on Verilog
debugging tasks from ChipBench, first with no memory (baseline) and then with an RCA
knowledge base (KB) built on one set of tasks and evaluated, frozen, on a disjoint set.

> **Status:** baseline in progress. KB design, results and discussion are TODO.

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

TODO: baseline vs KB table (correctness, tokens, time) for set A and set B.

## Quickstart

### Requirements

- macOS (tested) with Python 3.11. The scripts use only the standard library.
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
│   └── run_experiment.py    # run a whole condition over A and B
├── tasks/<category>/<problem>/   # spec.txt, buggy.sv, ref.sv, test.sv
├── results/<condition>/<category>/<problem>/
│   ├── trajectory.jsonl     # full Codex event stream (--json)
│   ├── stderr.log
│   ├── prompt.txt           # exact prompt used
│   ├── TopModule.sv         # Codex's final RTL
│   └── result.json          # pass/fail, mismatches, seconds, tokens, commands, leak flag
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
  TODO: Codex version and model (trajectories report `gpt-5.4`).
- **Prompt:** the same base prompt in every condition (`build_prompt()` only *appends* KB
  context), so the KB is the only difference between conditions. It names the two files,
  says Icarus is available, asks for an in-place fix that keeps the module interface, and
  asks for a closing `SYMPTOM / ROOT CAUSE / FIX` summary (raw material for KB records).
  The exact prompt is saved with every run.
- **Leak check:** Codex's sandbox restricts writes but not reads, so it could in principle
  read the golden files elsewhere on disk. Every command in every trajectory is scanned for
  `RefModule`, `ref.sv`, `chipagents_takehome` and `ChipBench`, and flagged in `result.json`.
  (Agents do wander: in the smoke test Codex ran `find .. -name AGENTS.md` on its parent directory.)

## Early Observations

- **Correct root cause, wrong repair.** On `timing/Prob010` (8→16-bit width converter) Codex
  correctly identified the bug (`data_r` stored in a combinational block, so the first byte was
  overwritten) but then rewrote the module and added an extra pipeline stage, delaying the output
  one cycle (72 mismatches). Its own testbench agreed with its fix, because it encoded Codex's
  own reading of the spec: self-verification confirmed the interpretation, not the real behavior.
- **Prompt framing matters.** With an early, vaguer prompt Codex rewrote the whole Gray-code
  counter. With the final RCA-focused prompt it made the exact one-line fix
  (`bin_out[0] = gray_wire[0]^bin_out[1]`). One run each, so suggestive only.
- **Run-to-run variance.** The same Gray-code task took 47 s / 149k input tokens in the smoke
  test and 81 s / 201k in the baseline. Small baseline-vs-KB differences may be noise.

## RCA Knowledge Base

TODO: what is stored, how it is organized, how the agent retrieves it, how it is updated on A
and frozen for B.

## Limitations & Known Issues

- 12 tasks per set and one run per task: results are indicative, not statistically significant.
- ChipBench bugs are small, single-module, hand-injected bugs, far simpler than real RTL RCA.
- The leak check only inspects shell commands Codex runs.
- TODO

## What I'd Do Next

TODO

## AI Usage

AI tools were allowed. TODO: one or two lines on how you used them.

## Sources

- ChipBench: Z. Yu, C. Zhou et al., *ChipBench: A Next-Step Benchmark for Evaluating LLM Performance
  in AI-Aided Chip Design*, [arXiv:2601.21448](https://arxiv.org/abs/2601.21448);
  code [github.com/zhongkaiyu/ChipBench](https://github.com/zhongkaiyu/ChipBench) (MIT), commit `b4ba3a0`.
- HWE-Bench: *HWE-Bench: Benchmarking LLM Agents on Real-World Hardware Bug Repair Tasks*,
  [arXiv:2604.14709](https://arxiv.org/pdf/2604.14709).
- Icarus Verilog: [github.com/steveicarus/iverilog](https://github.com/steveicarus/iverilog), `v12-branch`.
- Codex CLI: [OpenAI Codex non-interactive mode docs](https://learn.chatgpt.com/docs/non-interactive-mode).

## Time Spent

TODO

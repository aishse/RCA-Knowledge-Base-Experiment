# chipagents_takehome

## Rough notes (clean up when you write documentation): 
### Which benchmark should we use?
ChipBench debug (Recommended)
### How many tasks? Each Codex run probably takes 1–3 minutes, and each task runs at least twice: once for the baseline and once with the KB.
~40 tasks, A=20 / B=20 (Recommended)
### What should Codex see in its workspace? (It never sees the correct RefModule.)
Spec + buggy RTL + iverilog (Recommended)

First thing-> Need to import the problemset

Codex can only see prompt, ref, and test
per the docs: 

   -  *_prompt.txt: prompt given to the LLM (natural language + code context) for generating or fixing Verilog.
   -  *_ref.sv: reference Verilog implementation (bug‑free).
   -  *_test.sv: testbench for automatic simulation and checking.

Choosing the zero shot problems, because the one-shot has waveforms next to the buggy output, which means the baseline will be able to solve
everything without the need of a knowledge base, most likely. 

Need to ensure there is a proper split between set A and B of bug types
How to ensure the correct module is extracted from the prompt: 
- my assumption is that the very last code block provided is the buggy code. the rest is part of the prompt, and used by the llm to make their decisions on the next iteration of the code. 


using icarus-verilog to compile and run --> llm reasoning can be prone to hallucinations and for a golden 

## Vaildating the taskset 

I created `validate.py` to check which of the test problems are usable with Icarus Verilog 12 (the version from the Dockerfile).

### Checks

- **Golden check:** the reference design, used as the candidate, must pass its own testbench (0 mismatches).
- **Buggy check:** the original buggy design must fail (otherwise the bug is invisible to the grader
  and an agent could "solve" it by changing nothing).

### First pass: 78 / 89 usable

The 11 failures fell into two groups.

**1. Validation artifact: helper modules (8 tasks)**

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

These designs had a helper module that lives in the *candidate's* file
(`buggy.sv`), not inside `RefModule`. The first golden check used `ref.sv` with
`RefModule` renamed to `TopModule`, which either left the helper undefined or, where
`ref.sv` also defines the helper, defined it twice.

*Fix*: The golden candidate is now built from buggy.sv with only the buggy TopModule swapped for the correct one, so it matches what a perfect fix would look like. This resolved all 8 failures.

**2. Benchmark issue: least common multiple (3 tasks, excluded)**

`arithmetic/`, `assignment/` and `timing/Prob013_least_common_multiple`: the golden
design compiles but **mismatches against an identical copy of itself** (389 of 399
samples). A design compared with itself should never mismatch, so the testbench or
reference was not usable under Icarus 12 on MacOS. `timing/Prob013`'s buggy design also fails to
compile (`mcd_out is not a valid l-value`). All three were excluded.

### Final: 86 / 89 usable 

One buggy design (`timing/Prob022_synchronous_FIFO`) hangs the simulator in a
zero-delay loop. It still counts as "buggy fails" via the grader's timeout, so the
task is usable, but it's a reminder that grading needs a timeout.


## Task Splitting
Since A and B are **disjoint**, the straightforward method for splitting is to save all usable problems into a list, shuffle them randomly, and split the top $2n$ sets
into sets of n each. I also added a summary output that shows the split across all categories.



### Installation guide: 
```bash
brew install icarus-verilog
iverilog -V | head -1

# 2. Codex CLI
npm install -g @openai/codex
codex --version

export OPENAI_API_KEY=sk-...
printenv OPENAI_API_KEY | codex login --with-api-key
codex login status
```

<!-- One sentence: what it does and who/what it's for. -->
A short description of what this project does.

## Overview

<!-- 3–5 sentences. What problem did you pick, and how did you interpret
the open-ended prompt? Say plainly that you narrowed the scope and why. -->

## Demo

<!-- Show it working: example input/output, a short terminal transcript,
or a screenshot/GIF. Reviewers often look here first. -->

```
$ python main.py --example
...
```

## Quickstart

```bash
git clone <repo-url>
cd chipagents_takehome
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# any env vars, e.g.:
export OPENAI_API_KEY=...   # or whichever provider you use
python main.py
```

<!-- Test these steps from a fresh clone before submitting. -->

## How It Works

<!-- The architecture in plain words. A small diagram or a numbered
flow helps a lot, e.g.:
1. Input is parsed into ...
2. The agent decides ... using tools X and Y
3. Results are checked by ...
Keep it high-level and point to the relevant files. -->

### Project Structure

```
.
├── src/
│   ├── ...
├── tests/
├── NOTES.md
└── README.md
```

## Design Decisions

<!-- The most important section for your interview. 3–6 decisions, each
with what you chose, what you considered instead, and why. -->

- **Decision 1:** Chose X over Y because ...
- **Decision 2:** ...
- **Decision 3:** ...

## Testing & Evaluation

<!-- How do you know it works? Unit tests, example cases, a small eval
set, manual checks. Be honest about coverage. -->

```bash
pytest
```

## Limitations & Known Issues

<!-- What doesn't work, edge cases you know about, shortcuts you took on
purpose. Naming these yourself reads as good judgment. -->

- ...

## What I'd Do Next

<!-- Your safety valve. Anything you scoped out goes here, ideally with
a sentence on how you'd approach it. -->

- ...

## Time Spent

<!-- Optional, but it helps reviewers calibrate. Roughly how long, and
where it went. -->

~X hours: Y on core implementation, Z on testing, W on write-up.

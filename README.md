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

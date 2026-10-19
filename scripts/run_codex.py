PROMPT = """ You are a Verilog debugger. Your job is to analyze the provided Verilog code and perform a root cause analysis of any errors or issues present. 

Files in this directory:
- spec.txt: the intended behavior of the module `TopModule`
- TopModule.sv: an implementation of TopModule that contains a bug

Your task: find the root cause of the bug and fix TopModule.sv in place.
- Keep the module name and port list unchanged, and keep any other modules in the file.
- Icarus Verilog is installed (`iverilog -g2012`, `vvp`) if you want to write your own testbench and simulate.
- Work only inside this directory.

When you are done, end with a short summary in this format:
SYMPTOM: what behavior was wrong
ROOT CAUSE: the faulty line(s) and why they are wrong
FIX: what you changed
"""


import json
import time
import tempfile
import subprocess
import shutil
from pathlib import Path

from grader import grade

def run_task(task_dir, out_dir, timeout=900):
    """
    Runs the specified task

    Args:
        task_dir (str): directory with task information
        out_dir (str): directory to output result of task
        timeout (int, optional): timeout for the task in seconds. Defaults to 900.

    Raises:
        Exception: If there is an error during the execution of the task, such as a timeout or if the modified TopModule.sv is not found.
        
    """
    task_dir = Path(task_dir)
    tmp_dir = Path(tempfile.mkdtemp())

    try: 
        shutil.copy(task_dir / "spec.txt", tmp_dir / "spec.txt")
        shutil.copy(task_dir / "buggy.sv", tmp_dir / "TopModule.sv")

        prompt = build_prompt()

        try:
            # run Codex with the prompt and the buggy TopModule.sv in a temporary directory
            print(
                f"  ▶ Codex starting on {task_dir.parent.name}/{task_dir.name}...",
                flush=True,
            )

            time_start = time.monotonic()
            result = subprocess.run(
                ["codex", "exec", "--json", "--sandbox", "workspace-write",
                "--skip-git-repo-check", prompt],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL
            )
            time_end = time.monotonic()
            time_taken = time_end - time_start
            print(f"  ■ Codex finished in {time_taken:.0f}s, grading...", flush=True)

        except subprocess.TimeoutExpired:
            raise Exception("Timeout occurred while running Codex")

        # Save stdout and stderr
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "trajectory.jsonl", "w") as f:
            f.write(result.stdout)
        with open(out_dir / "stderr.log", "w") as f:
            f.write(result.stderr)

        # Read the modified TopModule.sv and save a copy to out_dir
        modified_file = Path(tmp_dir) / "TopModule.sv"
        if modified_file.exists():
            shutil.copy(modified_file, out_dir / "TopModule.sv")

            # grade the modified TopModule.sv
            passed, info = grade(task_dir, modified_file.read_text(), timeout=20)
            print(
                f"  {'✅ PASS' if passed else '❌ FAIL'} ({info.get('mismatches')} mismatches)",
                flush=True,
            )
        else:
            raise Exception("Modified TopModule.sv not found in the temporary directory.")

        # save the prompt to a file in out_dir
        (out_dir / "prompt.txt").write_text(prompt)

        total_input_tokens = 0
        total_output_tokens = 0

        # count tokens and commands ran
        commands = []

        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if data.get("type") == "turn.completed":
                    usage = data.get("usage", {})
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                if data.get("type") == "item.completed" and data.get("item", {}).get("type") == "command_execution":
                    commands.append(data["item"].get("command", ""))

            except json.JSONDecodeError:
                continue

        # checking if Codex ran commands that contain any references to the reference module or test files
        leak = any(
            m in cmd
            for cmd in commands
            for m in ["RefModule", "ref.sv", "chipagents_takehome", "ChipBench"]
        )

        # Write final results to a JSON file
        with open(out_dir / "result.json", "w") as f:
            json.dump(
                {
                    "task": str(task_dir),
                    "passed": passed,
                    "mismatches": info.get("mismatches", 0),
                    "seconds": time_taken,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "commands": len(commands),
                    "leak_suspected": leak,
                },
                f,
            )
    finally: 
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_prompt(kb_context=""):
    """
    Builds the prompt for Codex, optionally including a knowledge base context.

    Args:
        kb_context (str, optional): Extra text from the KB to append to the base prompt. Defaults to "".

    Returns:
        str: The built prompt.
    """

    if kb_context:
        return PROMPT + "\n\n" + kb_context
    return PROMPT

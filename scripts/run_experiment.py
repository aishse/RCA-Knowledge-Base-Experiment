import json 
import shutil
import sys
from pathlib import Path
from run_codex import run_task
import argparse 
from kb import load_kb, append_record, make_record, retrieve, record_text, format_cases

KB_DIR = Path("results/kb")
KB_A = KB_DIR / "kb_A.jsonl"
KB_FROZEN = KB_DIR / "kb_frozen.jsonl"

def main():
    parser = argparse.ArgumentParser(description="Run Codex RCA in baseline or KB mode")
    parser.add_argument("--mode", choices=["baseline", "kb"], default="baseline", help="Experiment mode")
    args = parser.parse_args()
    experiment_mode = args.mode

    # Load the split.json file
    with open("split.json", "r") as f:
        split_data = json.load(f)
    if experiment_mode == "kb":
        for task in split_data["A"]:
            try:
                run_kb_mode(task, KB_A)
            except Exception as e:
                print(f"Error running task {task}: {e}", file=sys.stderr)
                continue

        shutil.copy(KB_A, KB_FROZEN)
        print(f"Froze KB with {len(load_kb(KB_FROZEN))} records")
            
        # Phase B: KB is read-only
        for task in split_data["B"]:
            try:
                run_kb_mode(task, KB_FROZEN, frozen=True)
            except Exception as e:
                print(f"Error running task {task}: {e}", file=sys.stderr)
                continue

        results_dir = Path("results") / "kb"
        results = [
            json.loads(p.read_text()) for p in sorted(results_dir.glob("*/*/result.json"))
        ]

        for r in results:
            print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['task']}")

        passed = sum(r["passed"] for r in results)
        print(f"\n{passed} / {len(results)} passed")
            
    if experiment_mode == "baseline":
        run_baseline(split_data["A"])
        run_baseline(split_data["B"])
        results_dir = Path("results") / "baseline"
        results = [
            json.loads(p.read_text()) for p in sorted(results_dir.glob("*/*/result.json"))
        ]

        for r in results:
            print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['task']}")

        passed = sum(r["passed"] for r in results)
        print(f"\n{passed} / {len(results)} passed")

def run_kb_mode(task, kb_path, frozen=False):
    """
    Retrieve from kb_path, run task with Codex agent, and append to kb_path if learn is True.
    
    Args:
        task (str): The task to run.
        kb_path (str): Path to the knowledge base JSONL file.
        frozen (bool, optional): If True, do not append to the knowledge base. Defaults to False.
    """
    task_dir = Path("tasks") / task
    out_dir = KB_DIR / task
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if (out_dir / "result.json").exists():
        print(f"Skipping {task} (already done)")
        if not frozen and task not in {r["task"] for r in load_kb(kb_path)}:
            append_record(kb_path, make_record(task_dir, out_dir))
        return

    records = load_kb(kb_path)
    query = record_text((task_dir / "spec.txt").read_text(), (task_dir / "buggy.sv").read_text())
    hits = retrieve(records, query, k=3)

    # Augment + generate
    run_task(task_dir, out_dir, kb_context=format_cases(hits))

    # Log what was retrieved
    (out_dir / "retrieved.json").write_text(json.dumps(
        [{"task": r["task"], "score": round(s, 4), "failure_mode": r["failure_mode"]} for s, r in hits],
        indent=2))

    # if kb is not frozen, add this run as a new case, unless it's already there
    if not frozen and task not in {r["task"] for r in load_kb(kb_path)}:
        append_record(kb_path, make_record(task_dir, out_dir))


def run_baseline(dataset: list):
    """
    Runs the baseline experiment on the tasks specified in split_data.

    Args:
        dataset (list): A list of tasks to run.
    """
    for task in dataset:
        out_dir = Path("results") / "baseline" / task
        if (out_dir / "result.json").exists():
            print(f"Skipping {task} as results already exist.")
            continue
        try:
            run_task(Path("tasks") / task, out_dir)
        except Exception as e:
            print(f"Error running task {task}: {e}", file=sys.stderr)
            continue
if __name__ == "__main__":
    main()

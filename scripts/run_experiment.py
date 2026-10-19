import json 
import sys
from pathlib import Path
from run_codex import run_task
import argparse 


def main():
    parser = argparse.ArgumentParser(description="Run Codex RCA in baseline or KB mode")
    parser.add_argument("--mode", choices=["baseline", "kb"], default="baseline", help="Experiment mode")
    args = parser.parse_args()
    experiment_mode = args.mode
    
    # Load the split.json file
    with open("split.json", "r") as f:
        split_data = json.load(f)
    
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

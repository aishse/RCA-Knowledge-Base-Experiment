"""
Validates taskset for gradeability. Ensures that each task performed is structured correctly and can be graded by the grader.py script. 
This script should be run after importing the ChipBench problems into the local task catalog using import_problems.py.
"""
from pathlib import Path 
from grader import grade
import json 
import re

def validate_taskset(taskset_path):
    # iterate through each task directory in the taskset
    usable_set = []
    useable_set = []
    unuseable_set = []

    # for every task in the directory run teh grader and check if the buggy and golden code can be graded successfully
    for task_dir in sorted(Path("tasks").glob("*/*")):
        if task_dir.is_dir(): 
            category = task_dir.parent.name  
            name = task_dir.name 
            print(f"Validating task: {category}/{name}")

            ref = Path(task_dir / "ref.sv").read_text()
            buggy = Path(task_dir / "buggy.sv").read_text()
            golden = build_golden(buggy, ref)

            # buggy should fail and golden should pass
            buggy_passed,buggy_info =  grade(task_dir, buggy)
            golden_passed, golden_info = grade(task_dir, golden)

            usable = not buggy_passed and golden_passed

            # if the task is not usable, add it to the unusable set with the reason why
            if not usable:
                unuseable_set.append({
                    "task": f"{category}/{name}", 
                    "buggy_passed": buggy_passed, 
                    "golden_passed": golden_passed, 
                    "buggy_info": buggy_info, 
                    "golden_info": golden_info})
            else:
                useable_set.append(
                    {
                        "task": f"{category}/{name}",
                        "buggy_passed": buggy_passed,
                        "golden_passed": golden_passed,
                        "buggy_info": buggy_info,
                        "golden_info": golden_info,
                    }
                )

    print(f"Usable tasks: {len(useable_set)}")
    print(f"Unusable tasks: {len(unuseable_set)}")
    with open("validation_results.json", "w") as f:
        json.dump({"usable": useable_set, "unusable": unuseable_set}, f, indent=4)


def find_module(text, name):
    """Find the block from 'module <name>' to its 'endmodule'."""
    match = re.search(rf"module\s+{name}\b.*?endmodule", text, re.DOTALL)
    if match is None:
        raise ValueError(f"module {name} not found")
    return match


def build_golden(buggy, ref):
    """buggy.sv with only its TopModule replaced by the correct RefModule.
    Keeps any helper modules (e.g. dual_port_RAM) that buggy.sv defines."""
    top = find_module(buggy, "TopModule")
    ref_block = find_module(ref, "RefModule").group(0)
    ref_block = ref_block.replace("RefModule", "TopModule", 1)
    return buggy[: top.start()] + ref_block + buggy[top.end() :]


validate_taskset("tasks")

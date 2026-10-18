"""
Import the ChipBench problems into the local task catalog.

"""

from pathlib import Path 
import shutil 
import argparse 

CATEGORIES = ["arithmetic", "assignment", "timing", "state_machine"]

def main():

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Import ChipBench problems into the local task catalog.")
    parser.add_argument("chipbench_path", type=str, help="Path to the ChipBench Verilog Debugging directory.")
    parser.add_argument("--local_catalog_path", type=str, help="Path to the local task catalog directory.", default="tasks")
    args = parser.parse_args()

    # Validate the provided paths
    chipbench_path = Path(args.chipbench_path)
    local_catalog_path = Path(args.local_catalog_path)

    if not chipbench_path.exists() or not chipbench_path.is_dir():
        raise Exception(f"Error: The specified ChipBench path '{chipbench_path}' does not exist or is not a directory.")
        

    if not local_catalog_path.exists():
        print(f"Creating local task catalog directory at '{local_catalog_path}'.")
        local_catalog_path.mkdir(parents=True)

    # iterate over each category and copy the problems to the local catalog
    for category in CATEGORIES:
        folder = chipbench_path / f"dataset_debug_zero_shot_{category}"

        if not folder.exists() or not folder.is_dir():
            raise Exception(f"Error: The category folder '{folder}' does not exist. Please ensure that the ChipBench dataset is correctly structured.")

        # read the problems from the problems.txt file
        with open(folder / "problems.txt", "r") as f:
            problems = [line.strip() for line in f.readlines() if line.strip()]

        for name in problems:
            # Create a directory for the problem in the local catalog
            problem_dir = local_catalog_path / category / name
            problem_dir.mkdir(parents=True, exist_ok=True)

            with open(f"{folder}/{name}_prompt.txt", "r") as prompt_file:
                text = prompt_file.read()

            # get the code block and spec from prompt.txt by performing a reverse split on the last two occurrences of "```"
            spec, buggy_code, _ = text.rsplit("```", 2)
            
            # write the spec and buggy code to the problem directory
            with open(problem_dir / "spec.txt", "w") as spec_file:
                spec_file.write(spec.strip() + "\n")
            
            with open(problem_dir / "buggy.sv", "w") as buggy_file:
                buggy_file.write(buggy_code.strip() + "\n")

            shutil.copy(folder / f"{name}_ref.sv", problem_dir / "ref.sv")
            shutil.copy(folder / f"{name}_test.sv", problem_dir / "test.sv")
    print("Import completed successfully.")
    
    
if __name__ == "__main__":
    main()
       
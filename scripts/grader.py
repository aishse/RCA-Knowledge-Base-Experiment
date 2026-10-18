"""
Runs icarus-verilog to compile and run the testbench for a given problem, and checks if the output matches the expected output.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def grade(task_dir, candidate_code, timeout=20):

    # verifies if iverilog is installed and available in the PATH
    if shutil.which("iverilog") is None:
        raise Exception("iverilog not found on PATH. Did you open a new terminal after installing v12?")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        task_dir = Path(task_dir)

        # copy reference and test files to the temporary directory
        shutil.copy(task_dir / "ref.sv", temp_path / "ref.sv")
        shutil.copy(task_dir / "test.sv", temp_path / "test.sv")

        # write the candidate code to a temporary file
        candidate_file = temp_path / "TopModule.sv"
        with open(candidate_file, "w") as f:
            f.write(candidate_code)

        # compile the testbench using icarus-verilog
        try:
            compile_result = subprocess.run(["iverilog", "-g2012", "-o", "sim.vvp", "test.sv", "ref.sv","TopModule.sv"], cwd=temp_path, capture_output=True, text=True, timeout=timeout)
            if compile_result.returncode != 0:
                return _fail(f"Compilation failed:\n{compile_result.stderr}")

        except subprocess.TimeoutExpired:
            return _fail("Compilation timed out.")
        except Exception as e:
            return _fail(f"Compilation failed with error: {str(e)}")

        # run the simulation
        try:
            result = subprocess.run(["vvp",  "-n", "sim.vvp"], cwd=temp_path, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                return _fail(f"Simulation failed:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            return _fail("Simulation timed out.")
        except Exception as e:
            return  _fail(f"Simulation failed with error: {str(e)}")

        # extract mismatch information from the simulation output
        match = re.search(r"Mismatches: (\d+) in (\d+) samples", result.stdout)
        if match is None:
            return _fail("Could not find mismatch information in simulation output.")

        # build result dictionary

        mismatches = int(match.group(1))
        samples = int(match.group(2))
        passed = mismatches == 0 and samples > 0 and "TIMEOUT" not in result.stdout
        return passed, {
            "mismatches": mismatches,
            "samples": samples,
            "log":  result.stdout
        }


def _fail(log):
    return False, {"mismatches": None, "samples": None, "log": log}


if __name__ == "__main__":
    print("Running tests for grader.py...\n")
    print("Comparing golden to golden (should pass):")
    
    ref = Path("tasks/assignment/Prob023_gray_code_counter/ref.sv").read_text()
    golden = ref.replace("module RefModule", "module TopModule", 1)
    passed, result = grade("tasks/assignment/Prob023_gray_code_counter", golden)
    assert passed and result["mismatches"] == 0, "golden design should pass"

    print("\nComparing golden to buggy (should fail):\n")
    ref = Path("tasks/assignment/Prob023_gray_code_counter/ref.sv").read_text()
    buggy = Path("tasks/assignment/Prob023_gray_code_counter/buggy.sv").read_text()
    passed, result = grade("tasks/assignment/Prob023_gray_code_counter", buggy)
    
    assert not passed and result["mismatches"] > 0, "buggy design should fail"\
    
    print("\nAll tests passed for grader.py.")

import json
import difflib
from pathlib import Path
from grader import build_golden
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
EMBED_MODEL = "text-embedding-3-small"
_client = OpenAI()

def embed(text):
    """
    Generates an embedding for the given text using OpenAI's embedding model.

    Args:
        text (str): The input text to generate an embedding for.
    """
    response = _client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return response.data[0].embedding


def record_text(spec, buggy_code):
    """
    Combines the spec and buggy code into a single string for embedding.

    Args:
        spec (str): The specification text.
        buggy_code (str): The buggy code text.

    Returns:
        str: The combined text.
    """
    return spec + "\n\n" + buggy_code

def cosine(a, b):
    """
    Computes the cosine similarity between two vectors. Used to compare embeddings. 

    Args:
        a (list): First vector.
        b (list): Second vector.

    Returns:
        float: Cosine similarity between the two vectors.
    """
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0


def format_cases(hits, max_chars=1200):
    """
    Turn [(score, record), ...] into the prompt section Codex reads.
    
    Args:
        hits (list): A list of tuples containing similarity scores and records.
        max_chars (int, optional): Maximum number of characters to include from each record. Defaults
        to 1200.
    Returns:
        str: Formatted string of past debugging cases for the prompt.
    """
    if not hits:
        return ""
    parts = [
        "## Past debugging cases (from a knowledge base of previously debugged designs)",
        "These cases may or may not be relevant to this task. Use them as hints, not as answers.",
    ]
    for i, (score, r) in enumerate(hits, 1):
        case = f"\n### Case {i}: {r['task']} (outcome: {'PASS' if r['passed'] else 'FAIL'})\n"

        # Only show the agent's reasoning when the grader confirmed it was right
        if r["passed"]:
            case += f"Agent's diagnosis (verified):\n{r['agent_summary'][:max_chars]}\n\n"

        case += f"Confirmed fix (diff of buggy -> correct):\n{r['true_fix'][:max_chars]}\n\n"
        case += f"Lesson: {r['lesson']}"
        parts.append(case)
    return "\n".join(parts)


def retrieve(records, query_text, k=3):
    """
    Retrieves similar records to query text based on cosine similarity. 

    Args:
        records (list): A list of records, each with an "embedding" key.
        query_text (str): The text to query.
        k (int, optional): The number of similar records to return. Defaults to 3.

    Returns:
        list[tuple[float, dict]]: A list of tuples, each containing a similarity score and a record.
    """
    
    query_embedding = embed(query_text)
    scored_records = [
        (cosine(query_embedding, record["embedding"]), record)
        for record in records
    ]
    scored_records.sort(key=lambda x: x[0], reverse=True)
    
    return scored_records[:k]


def changed_lines(before, after):
    """Return the +/- lines of a diff between two texts."""
    diff = difflib.unified_diff(
        before.splitlines(), after.splitlines(), lineterm="", n=0
    )
    res = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            res.append(line)
    return res


def make_record(task_dir, out_dir):
    """
    Makes a record of the task execution, including the spec, buggy code, agent summary, and grading results.

    Args:
        task_dir (str): Path to the task directory containing spec.txt, buggy.sv, and ref.sv
        out_dir (str): Path to the output directory containing the result.json and trajectory.jsonl files

    Returns:
        dict: A dictionary containing the task record.
    """
    task_dir, out_dir = Path(task_dir), Path(out_dir)

    spec = (task_dir / "spec.txt").read_text()
    buggy = (task_dir / "buggy.sv").read_text()
    ref = (task_dir / "ref.sv").read_text()
    result = json.loads((out_dir / "result.json").read_text())

    # Codex's final file (fall back to buggy if it's missing)
    final_path = out_dir / "TopModule.sv"
    final = final_path.read_text() if final_path.exists() else buggy

    # get the agent summary from the trajectory.jsonl file
    agent_summary = ""
    for line in (out_dir / "trajectory.jsonl").read_text().splitlines(): 
        try:
            data = json.loads(line)
            if data.get("type") == "item.completed" and data.get("item", {}).get("type") == "agent_message":
                agent_summary = data["item"].get("text", "")
        except json.JSONDecodeError:
            continue
    if not agent_summary:
        agent_summary = "(agent produced no summary)"

    # Compute the diff between the buggy and final code, and the buggy and golden code
    agent_diff = changed_lines(buggy, final)
    true_diff  = changed_lines(buggy, build_golden(buggy, ref))

    # checking if it touched the root cause by checking if any of the lines removed by the agent are also in the true fix
    true_removed  = {l[1:].strip() for l in true_diff  if l.startswith("-") and l[1:].strip()}
    agent_removed = {l[1:].strip() for l in agent_diff if l.startswith("-") and l[1:].strip()}

    touched_root_cause = bool(true_removed & agent_removed) 

    # checking if the agent made any extra edits that were not in the true fix
    unnecessary_edits = sorted(agent_removed - true_removed)

    if result["passed"]:
        failure_mode = "passed"
    elif not touched_root_cause:
        failure_mode = "missed_root_cause"
    elif len(unnecessary_edits) > 0:
        failure_mode = "over_repair"
    else:
        failure_mode = "wrong_fix"

    # lessons for each failure mode that can be used to provide feedback to model's attempt
    lessons = {
        "passed": f"Fixed with a {len(agent_diff)}-line change that matched the reference behavior."
        + (
            " A smaller fix targeting only the root cause would also have worked."
            if len(unnecessary_edits) > 0
            else ""
        ),
        "missed_root_cause": f"Missed the root cause: the agent did not modify the faulty lines.",
        "over_repair": (
            f"Modified the faulty lines but also changed { len(unnecessary_edits)  } lines the fix did not need; The edits are {unnecessary_edits}. It's likely that "
            f"those extra edits caused the {result['mismatches']} mismatches. Change only the root cause."
        ),
        "wrong_fix": "Modified the faulty lines, but the change was incorrect. Compare with the confirmed fix.",
    }

    # return a record dictionary with all the relevant information
    return {
        "task": f"{task_dir.parent.name}/{task_dir.name}",
        "spec": spec,
        "buggy_code": buggy,
        "agent_summary": agent_summary,
        "passed": result["passed"],
        "mismatches": result["mismatches"],
        "lines_changed": len(agent_diff),
        "true_fix": "\n".join(true_diff),
        "true_fix_lines": len(true_diff),
        "failure_mode": failure_mode,
        "touched_root_cause": touched_root_cause,
        "extra_edits": len(unnecessary_edits),
        "unnecessary_edits": unnecessary_edits,
        "lesson": lessons[failure_mode],
        "embedding": embed(record_text(spec, buggy)),
    }

def append_record(kb_path, record):
    """
    Appends a record to the knowledge base JSON file.

    Args:
        kb_path (str): Path to the knowledge base JSON file.
        record (dict): The record to append.
    """
    kb_path = Path(kb_path)
    kb_path.parent.mkdir(parents=True, exist_ok=True)

    with open(kb_path, "a") as f:
        f.write(json.dumps(record) + "\n")

def load_kb(kb_path):
    """
    Loads the knowledge base from a JSON file.

    Args:
        kb_path (str): Path to the knowledge base JSON file.
    """

    kb_path = Path(kb_path)
    if not kb_path.exists():
        return []
    
    return [json.loads(line) for line in kb_path.read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    split = json.load(open("split.json"))
    records = [
        make_record(Path("tasks") / t, Path("results/baseline") / t) for t in split["A"]
    ]

    for t in split["B"]:
        d = Path("tasks") / t
        query = record_text((d / "spec.txt").read_text(), (d / "buggy.sv").read_text())
        hits = retrieve(records, query, k=3)
        print(t)
        for score, r in hits:
            print(f"   {score:.3f}  {r['task']}  ({r['failure_mode']})")

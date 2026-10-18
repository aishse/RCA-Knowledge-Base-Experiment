import json 
import random 
from collections import Counter

PER_SET = 12
SEED = 0


def main():
    
    # get usable tasks
    usable = [t["task"] for t in json.load(open("validation_results.json"))["usable"]]
    usable.sort()                      

    rng = random.Random(SEED)
    
    # shuffle the usable tasks so that we can get a random split
    rng.shuffle(usable)

    set_a = usable[:PER_SET]
    set_b = usable[PER_SET : 2 * PER_SET]  # next 12, so no overlap with A

    with open("split.json", "w") as f:
        json.dump({"seed": SEED, "A": set_a, "B": set_b}, f, indent=2)
    
    for name, s in [("A", set_a), ("B", set_b)]:
      print(name, Counter(t.split("/")[0] for t in s))

if __name__ == "__main__":
    main()
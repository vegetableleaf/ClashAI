# How many ext-frame live logs (10-16/17) are NOT in the gate holdout? (they are the only live logs with opponent spells)
import json, sys
from pathlib import Path
hold = {l.strip().removesuffix(".jsonl") for l in open(Path(__file__).parent.parent / "gate" / "gate_holdout.txt") if l.strip()}
ext = json.load(open(Path(__file__).parent.parent / "data" / "ext_1016_17.json"))
def names(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(k, str) and k.startswith("live_play_"): yield Path(k).name.removesuffix(".jsonl")
            yield from names(v)
    elif isinstance(o, list):
        for v in o: yield from names(v)
    elif isinstance(o, str) and "live_play_" in o:
        yield Path(o).name
n = set(names(ext))
print("ext logs named:", len(n), "in holdout:", len(n & hold), "free:", len(n - hold))
print("type", type(ext).__name__, list(ext)[:8] if isinstance(ext, dict) else len(ext))

"""RD1 vs slot re-drive: same accepted plays per shard? (build_mix_memory.plays) usage: RD SLOT SHARDS_FILE"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mix_memory import plays
rd, sl, sf = map(Path, sys.argv[1:4])
bad, n = [], 0
for sid in sf.read_text().split():
    a, b = plays(rd / "rows" / f"{sid}.parquet"), plays(sl / "rows" / f"{sid}.parquet")
    n += len(a)
    if a != b:
        bad.append((sid, len(a), len(b), len(a ^ b)))
print(json.dumps({"shards": len(sf.read_text().split()), "plays": n, "mismatched_shards": len(bad), "first": bad[:10]}))

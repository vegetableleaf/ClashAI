"""mk_mvm_jobs.py TAGS.txt HF_DATA_DIR N OUT.jsonl -- OPP-PUSH style S0b: rebuild hf_ref.py's `--jobs N` file (pairs.py --mvm rows:
the first N test-split (split 2) tier-A HF replays in parquet order) without the re-drive dir, which lived on the stopped pod 32657.
TAGS.txt = the tier-A tags = every tag in data/hf_ref_bec5811a.json.gz (hf_ref.py writes one record pair per tier-A replay).
Run with the eval tree's humanlike dir on PYTHONPATH (imports hf_ref.job_row / split_of, so the rows are hf_ref.py's own)."""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from hf_ref import job_row, split_of

tags, data, n, out = set(Path(sys.argv[1]).read_text().split()), Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
rows = []
for rp in sorted((data / "replays").glob("part-*.parquet")):
    for r in pq.read_table(rp, columns=["replay_tag", "payload_json"]).to_pylist():
        if r["replay_tag"] in tags and split_of(r["replay_tag"]) == 2 and len(rows) < n:
            rows.append(job_row(r))
    if len(rows) >= n:
        break
out.write_text("".join(json.dumps(x) + "\n" for x in rows))
print("wrote", out, len(rows), "job rows")

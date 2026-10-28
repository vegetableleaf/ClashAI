"""verify_out.py OUT [--drop] -- every shard's shards/<sid>.json parses, its grades/<sid>.jsonl parses with that many
replays, and each listed parquet opens with that many rows (and its sha256 when recorded). --drop deletes a bad shard's
files so run.sh re-drives it. (A host reboot at 02:22 10-28 left zero-length files: write + rename without fsync.)"""
import hashlib, json, sys
from pathlib import Path
import pyarrow.parquet as pq

out, drop = Path(sys.argv[1]), "--drop" in sys.argv
bad = {}
for p in sorted((out / "shards").glob("*.json")):
    sid = p.stem
    try:
        d = json.loads(p.read_text())
        gl = (out / "grades" / f"{sid}.jsonl").read_text().splitlines()
        assert len([json.loads(l) for l in gl]) == d["replays"], "grades count"
        files = d.get("files") or ([dict(path=f"rows/{sid}.parquet", rows=d["rows"], sha256=d.get("parquet_sha256"))]
                                   if d["rows"] else [])
        for f in files:
            fp = out / f["path"]
            assert pq.ParquetFile(fp).metadata.num_rows == f["rows"], "rows " + f["path"]
            if f.get("sha256"):
                assert hashlib.sha256(fp.read_bytes()).hexdigest() == f["sha256"], "sha " + f["path"]
    except Exception as e:
        bad[sid] = f"{type(e).__name__}: {str(e)[:120]}"
print(json.dumps(dict(shards=len(list((out / "shards").glob("*.json"))), bad=bad), indent=1))
if drop:
    for sid in bad:
        for f in [out / "shards" / f"{sid}.json", out / "grades" / f"{sid}.jsonl", *(out / "rows").glob(f"{sid}*.parquet")]:
            f.unlink(missing_ok=True)

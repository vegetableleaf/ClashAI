"""Peak RSS of mine.hf_shard on N shards in one process (memory budget check for the shared pod).
    python -B rss_probe.py ROWS_DIR HF_ROOT OUT_DIR N"""
import resource
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mine  # noqa: E402

rows, hf, out, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
Path(out).mkdir(parents=True, exist_ok=True)
for f in sorted(Path(rows).glob('*.parquet'))[:n]:
    print(mine.hf_shard((str(f), hf, out)), 'maxrss_MB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)

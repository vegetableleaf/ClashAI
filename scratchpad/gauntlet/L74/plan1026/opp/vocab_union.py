"""Union card vocab of a re-drive's row shards (parquet schema metadata only) -> JSON list, '<pad>' first, keys sorted
(the dataset_gen convention). usage: python vocab_union.py ROWS_DIR OUT.json"""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

keys = set()
files = sorted(Path(sys.argv[1]).glob("*.parquet"))
for f in files:
    keys.update(k for k in json.loads(pq.read_schema(f).metadata[b"meta"])["card_vocab"] if k != "<pad>")
vocab = ["<pad>"] + sorted(keys)
Path(sys.argv[2]).write_text(json.dumps(vocab))
print(len(files), "files", len(vocab), "ids")

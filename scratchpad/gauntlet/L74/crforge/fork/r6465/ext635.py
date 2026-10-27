"""6.5(b) measurement: extract.py batch on the client-160635001 matches with the 16.635.3 tables (module global swapped,
extract.py itself unedited). argv: tables_dir out.jsonl since(EDT stamp)."""
import json, sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\extract')
import extract
extract.TABLES = Path(sys.argv[1])
st = extract.batch(sys.argv[2], sys.argv[3])
print(json.dumps(st, default=str))

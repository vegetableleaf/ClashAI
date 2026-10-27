"""Base results with some matches replaced. python3 merge.py BASE.jsonl NEW.jsonl > OUT"""
import json, sys
new = {json.loads(l)['match']: l for l in open(sys.argv[2])}
for l in open(sys.argv[1]):
    m = json.loads(l)['match']
    sys.stdout.write(new.pop(m, l))
for l in new.values():
    sys.stdout.write(l)

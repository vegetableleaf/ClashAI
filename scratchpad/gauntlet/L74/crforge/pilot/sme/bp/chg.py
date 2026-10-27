"""Matches whose input record differs between two inputs files (comma list). python -I chg.py A B"""
import json, sys
A = {json.loads(l)['match']: l for l in open(sys.argv[1])}
print(','.join(m for l in open(sys.argv[2]) for m in [json.loads(l)['match']] if A.get(m) != l))

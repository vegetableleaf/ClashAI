"""inputs_j7x.jsonl = the RNG-free log-only records of inputs_expanded + the 138 API-backed RNG-free records (811)."""
import json, sys
D = sys.argv[1]
n = 0
with open(D + '/inputs_j7x.jsonl', 'w', newline='\n') as w:
    for f in ('inputs_rngfree.jsonl', 'inputs_expanded.jsonl'):
        for line in open(D + '/' + f):
            r = json.loads(line)
            if r.get('rng_free'):
                w.write(line if line.endswith('\n') else line + '\n'); n += 1
print(n)

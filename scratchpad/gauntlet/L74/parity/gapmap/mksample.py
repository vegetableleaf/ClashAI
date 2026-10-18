"""Sample of the unlabeled failing fights (joined.tsv class '?') for first-divergence dossiers -> sample.txt + args_sample.txt.
All own (X-Bow, Log ...) + up to 5 per opp card with >= 5 mass, + 30 random others (seed 7)."""
import random
from collections import defaultdict
J = [l.rstrip('\n').split('\t') for l in open('joined.tsv', encoding='utf-8')]
U = [j for j in J if j[6] == '?']
by = defaultdict(list)
for j in U:
    by[j[2]].append(j)
pick = []
for c, xs in by.items():
    if c.startswith('own '):
        pick += xs
    elif sum(1 - float(x[3]) for x in xs) >= 5:
        pick += xs[:5]
rest = [j for j in U if j not in pick]
random.Random(7).shuffle(rest)
pick += rest[:30]
args = defaultdict(set)
with open('sample.txt', 'w') as f:
    for j in pick:
        f.write(f"{j[0]}@{j[1]}\t{j[2]}\t{j[3]}\t{j[4]}\n")
        args[j[0]].add(j[1])
with open('args_sample.txt', 'w', newline='\n') as f:
    for m, ts in sorted(args.items()):
        f.write(f"{m}:{','.join(sorted(ts, key=int))}\n")
print(len(pick), 'fights in', len(args), 'matches; unlabeled', len(U))

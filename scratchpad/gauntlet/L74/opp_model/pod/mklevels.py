"""O0 (pod-local): write the 13k level table with our tower set to T into the O0 checkout copy.  python mklevels.py SRC DST T"""
import json, sys
src, dst, t = sys.argv[1], sys.argv[2], int(sys.argv[3])
j = json.load(open(src, encoding='utf-8'))
j['own']['tower'] = t
j['o0_note'] = f'O0 pod-local copy of stage2/levels/levels13k.json (sha 3547c8d3) with own.tower = {t}; never synced back'
json.dump(j, open(dst, 'w', encoding='utf-8'), indent=1)
print('own', j['own']['tower'], 'profiles', len(j['opp_profiles']))

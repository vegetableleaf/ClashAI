import json, glob, sys
for f in sorted(glob.glob(sys.argv[1] + '/laws/*.json')):
    d = json.load(open(f))
    e = d.get('end') or {}
    if e.get('cls') == 'tiebreak':
        print(d['match'], {k: v for k, v in e.items() if k not in ('cls',)})

"""Outcome + lethal fires of named matches across runs.  python match_lines.py <tag list e.g. lad:17,lad:185> <run>:<arm> ...
Each run dir holds v3_<arm>_<evo|lad>/matches.jsonl and fires_<arm>_<s>/fires_*.jsonl."""
import glob, json, os, sys

tags = [t.split(':') for t in sys.argv[1].split(',')]
for spec in sys.argv[2:]:
    O, arm = spec.rsplit(':', 1)
    for s, n in tags:
        tag = f's0:gen:{n}'
        rec = next((json.loads(l) for l in open(f'{O}/v3_{arm}_{s}/matches.jsonl') if json.loads(l)['tag'] == tag), None)
        fires = sorted((json.loads(l) for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl') for l in open(f)
                        if json.loads(l)['tag'] == tag), key=lambda x: x['t_sec'])
        print(f'{os.path.basename(O)} {arm} {s}:{n}: {rec["outcome"]} {rec["crowns_for"]}-{rec["crowns_against"]} '
              f'end {rec["end_tick"]} | fires {[(x["why"], round(x["t_sec"], 2), x["target"]["lane"], x["target"]["hp"]) for x in fires]}')

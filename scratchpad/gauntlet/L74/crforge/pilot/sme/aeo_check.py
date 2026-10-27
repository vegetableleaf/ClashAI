"""Area-effect start/end timing, sim vs live: for every sim area effect of a name (first line a, last line z at one
point), does the recorded frame at a+k / z+k (k = -2..+5) show an area effect of that card at that point?
    python3 aeo_check.py RUNDIR SIM_NAME CARD_ID [PLAY_CARD] [--repr]   e.g. Lightning 28000007 Lightning"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run, name, cid = sys.argv[1], sys.argv[2], int(sys.argv[3])
play = sys.argv[4] if len(sys.argv) > 4 else name
fdir = '/workspace/pilot/sme_live/frames'
st, en = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
n = 0
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p):
        continue
    plan = json.load(open(p))
    if not any(c.get('card') == play for c in plan['cmds']):
        continue
    frames = load_frames(os.path.join(fdir, m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'aeo'))[0]
    if o is None:
        continue
    life = {}
    for x in o:
        for e in x['E']:
            if e[1] == 'A' and e[2] == name:
                k = e[0]
                a = life.setdefault(k, [x['t'], x['t'], e[3], e[4], e[5]])
                a[1] = x['t']
    for k, (a, z, side, px, py) in life.items():
        n += 1
        for d in range(-2, 6):
            for ref, tab in ((a, st), (z, en)):
                fr = frames.get(ref + d)
                if fr is None:
                    continue
                has = any(q[0] == side and q[1] == px and q[2] == py and q[3] == cid for q in fr['A'])
                tab[d][0] += has
                tab[d][1] += 1
print(name, 'sim area effects', n)
print('recorded shows it at first sim line + k:', {k: tuple(v) for k, v in sorted(st.items())})
print('recorded shows it at last sim line + k: ', {k: tuple(v) for k, v in sorted(en.items())})

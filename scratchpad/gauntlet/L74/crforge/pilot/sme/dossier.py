"""Body-position dossier (ticket A2c item 3): for a match whose first true divergence is a body position, follow the
most-displaced body from its creation in the sim to 40 ticks past the onset, against its recorded twin.
    python3 dossier.py RUNDIR MATCH [MATCH ...]   (SME_REPR as for the run)
Per body: sim row + its play (run, point, source, extractor window), creation line, first recorded frame with a non-zero
offset, the offset series, and what stood within 1200 units of it when the offset first appeared."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch, card_name  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
for m in sys.argv[2:]:
    r = json.load(open(os.path.join(run, m, 'result.json')))
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    e0 = r['episodes'][0]
    t0 = e0['start']
    body = [x for x in e0['detail'] if x[0] == 'U_rec_only' and isinstance(x[3], list)]
    if not body:
        print(m, 'no paired body at the onset'); continue
    x = max(body, key=lambda x: abs(x[3][0]) + abs(x[3][1]))
    side, rx, ry, rhp = x[1]
    sx, sy = rx + x[3][0], ry + x[3][1]
    o = run_batch([(runnable(plan), t0 + 45, 0)], os.path.join(run, m, 'dossier'))[0]
    by = {s['t']: s for s in o}
    ent = next((e for e in by[t0]['E'] if e[3] == side and e[4] == sx and e[5] == sy and e[1] == 'C'), None)
    if ent is None:
        print(m, 'sim twin not found'); continue
    eid, row, src = ent[0], ent[2], ent[8]
    born = min(s['t'] for s in o if any(e[0] == eid for e in s['E']))
    cmd = plan['cmds'][int(src[3:])] if src.startswith('cmd') else None
    rcard = next((e[3] for e in frames[t0]['E'] if e[0] == side and e[1] == rx and e[2] == ry), None)
    series, first_off, near = [], None, None
    for t in sorted(t for t in frames if born <= t <= t0 + 40):
        se = next((e for e in by.get(t, {'E': []})['E'] if e[0] == eid), None)
        if se is None:
            continue
        cands = [e for e in frames[t]['E'] if e[0] == side and e[3] == rcard]
        if not cands:
            series.append((t, None)); continue
        c = min(cands, key=lambda e: abs(e[1] - se[4]) + abs(e[2] - se[5]))
        d = (c[1] - se[4], c[2] - se[5])
        if abs(d[0]) + abs(d[1]) > 1500:
            series.append((t, None)); continue
        series.append((t, d))
        if first_off is None and d != (0, 0):
            first_off = t
            near = sorted(((abs(e[4] - se[4]) + abs(e[5] - se[5]), e[1] + ':' + e[2], e[3]) for e in by[t]['E']
                           if e[0] != eid and abs(e[4] - se[4]) + abs(e[5] - se[5]) < 1200), key=lambda z: z[0])[:6]
    mx = max((abs(d[0]) + abs(d[1]) for _, d in series if d), default=0)
    print('=' * 100)
    print(m, '| onset', t0, '| body', row, 'side', side, '(reader card %s)' % card_name(rcard) if rcard else '')
    if cmd:
        s_ = cmd.get('_src', {})
        print('  play', src, cmd.get('card'), 'run', cmd['run'], 'point', (cmd.get('x'), cmd.get('y')), 'source', s_.get('source'),
              'window', (s_.get('lo'), s_.get('hi')), 'extractor tick', s_.get('tick'))
    else:
        print('  made by another body (no play of its own):', src or '-')
    print('  sim creation line', born, '| first recorded frame with an offset', first_off,
          '(%s ticks after creation)' % (first_off - born if first_off else '-'), '| max |dx|+|dy|', mx)
    print('  offsets (tick: dx,dy):', ' '.join('%d:%s' % (t, '%d,%d' % d if d else '-') for t, d in series if t >= (first_off or born) - 6)[:900])
    print('  within 1200 at the first offset (dist, sim row, side):', near)

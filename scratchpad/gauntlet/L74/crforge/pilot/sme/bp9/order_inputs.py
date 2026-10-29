"""order_inputs.py IN.jsonl OUT.jsonl [FRAMES_DIR] -- A2c-9R: same-tick plays of the two sides in the game's creation order.

The game runs plays sharing a run tick in a fixed order per tick, and the reader lists bodies in the game's entity order, so the
first recorded frame at or after the tick that shows the new bodies of both plays gives that order: the play whose new bodies sit
earlier in the frame's row list was created first. crforge runs same-tick commands in queue order (Standard1v1Battle: "within a
tick, the run order") and plan_from keeps the inputs' order for plays with equal tick, so moving the earlier-created play first in
rec['plays'] is the whole change. A play with no new body in reach (a spell) gives no order; the pair keeps its order.
New body: a row of the play's side within 1,500 (Manhattan) of its point whose (side, card id) is not within 20 of a row of the
frame before the tick. Prints every pair: tick, the two plays, the reader's first rows, and whether the order changed."""
import json, os, sys
src, dst = sys.argv[1], sys.argv[2]
FR = sys.argv[3] if len(sys.argv) > 3 else '/workspace/pilot/sme_live/frames2'


def first_new(ts, p, run):
    """(first frame tick, the play's new body rows in it, the frame before the tick) or None."""
    before = [f for t, f in ts if t < run]
    old = before[-1]['E'] if before else []
    for t, f in ts:
        if t < run or t > run + 10: continue
        rows = [k for k, e in enumerate(f['E']) if e[0] == p['side'] and e[3] != -1 and abs(e[1] - p['x']) + abs(e[2] - p['y']) <= 1500
                and not any(o[0] == e[0] and o[3] == e[3] and abs(o[1] - e[1]) <= 20 and abs(o[2] - e[2]) <= 20 for o in old)]
        if rows: return t, rows, (before[-1]['t'] if before else None)
    return None


def first_rows(frames, ts, p, run):
    r = first_new(ts, p, run)
    return (r[0], min(r[1])) if r else None


# ENG-FIX5 (SME_SAMETICK_GEN=1 with SME_SAMETICK_ORDER, off by default): the reader lists our EVOLVED bodies (Knight_EV1,
# Tesla_EV1, ... reader codes 13xxxxxx) after every other body, so their rows say nothing about creation order (FRESH6
# 031310@3931: MK row 10, Knight_EV1 row 12, but phase2 generations Knight 5000172 < MK 5000173; the SIM with the Knight
# first is exact at 3954 / 3957). phase2 'generation' is the game's entity id (the address of an ents row maps it), so a
# play's reading is the lowest generation of its new bodies. It counts only when every new row has one and it is above
# every generation of the frame before the tick (a spell's spurious "new body" is older: FRESH4 235316 Tornado). A tick
# whose read plays all count is sorted by generation; otherwise by the row reading, as before.
def gen_frames(path):
    """{tick: [generation or None per ents row]} of a raw live log, first frame of each tick (as live_frames.convert)."""
    out = {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]: continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in out: continue
        g = {u.get('address'): u.get('generation') for u in (d.get('phase2') or {}).get('units') or []}
        out[t] = [g.get(e[7]) if len(e) > 7 else None for e in d['ents']]
    return out


def gen_reading(ts, p, run, gens):
    r = first_new(ts, p, run)
    if r is None or r[0] not in gens: return None
    g = [gens[r[0]][k] if k < len(gens[r[0]]) else None for k in r[1]]
    old = [x for x in gens.get(r[2], []) if x is not None] if r[2] is not None else []
    if any(x is None for x in g) or (old and min(g) <= max(old)): return None
    return min(g)


def reorder(rec, log, fr=None, gens=None):
    """fr: the match's frames as [(t, frame)] (extract.py passes live_frames.convert's); None reads FR/<match>.jsonl.
    gens: gen_frames(raw log) for the ENG-FIX5 generation reading (None = the row reading only, as before)."""
    plays = rec['plays']
    out = list(plays)
    by = {}
    for i, p in enumerate(plays):
        if p['kind'] == 'play': by.setdefault(p['tick'], []).append(i)
    for tick, ix in sorted(by.items()):
        if len({plays[i]['side'] for i in ix}) < 2: continue
        if fr is None:
            fr = []
            for l in open(os.path.join(FR, rec['match'] + '.jsonl')):
                f = json.loads(l); fr.append((f['t'], f))
        seen = {i: first_rows(None, fr, plays[i], tick) for i in ix}
        known = [i for i in ix if seen[i] is not None]
        # only plays with a reading are ordered; they keep the slots they had, sorted by (first frame, first row)
        new = sorted(known, key=lambda i: seen[i])
        if gens is not None and len(known) >= 2:
            g = {i: gen_reading(fr, plays[i], tick, gens) for i in known}
            if all(g[i] is not None for i in known): new = sorted(known, key=lambda i: g[i])
        slots = sorted(known)
        changed = new != slots
        for s, i in zip(slots, new): out[s] = plays[i]
        log.append('%s %d %s %s' % (rec['match'][10:], tick, 'REORDERED' if changed else 'kept',
                                    [(plays[i]['side'], plays[i]['card'], plays[i]['source'], seen[i]) for i in ix]))
    return dict(rec, plays=out)


if __name__ == '__main__':
    log = []
    with open(dst, 'w') as w:
        for l in open(src):
            rec = json.loads(l)
            new = reorder(rec, log)
            w.write(l if new['plays'] == rec['plays'] else json.dumps(new) + '\n')  # unchanged records byte for byte
    print('\n'.join(log))
    print('pairs', len(log), 'reordered', sum('REORDERED' in x for x in log))

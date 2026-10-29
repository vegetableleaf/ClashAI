"""ENG-FIX5: our plays' run - tap lag (tap = the latest own_tap of the same card at or before the run), histogram, and the
plays with a short lag (<= SHORT) with the reader's elixir at the tap and over the pending window (did it read 10.0?).
python -I lag_census.py LIVE_DIR SHORT INPUTS.jsonl [...]"""
import collections, json, os, sys
LD, SHORT = sys.argv[1], int(sys.argv[2])
hist = collections.Counter()
short = []
for f in sys.argv[3:]:
    for l in open(f):
        r = json.loads(l)
        my = r['my_side']
        taps = r['own_taps']
        el = None
        for p in r['plays']:
            if p['side'] != my or p['kind'] != 'play':
                continue
            ts = [t['tick'] for t in taps if t['name'] == p['card'] and t['tick'] <= p['tick']]
            if not ts:
                continue
            lag = p['tick'] - max(ts)
            hist[min(lag, 60)] += 1
            if lag <= SHORT:
                if el is None:
                    el = {}
                    for line in open(os.path.join(LD, r['match'] + '.jsonl'), 'rb'):
                        if b'"frame"' in line[:40]:
                            d = json.loads(line)
                            if d['tick'] is not None and d['tick'] >= 0 and d['tick'] not in el:
                                el[d['tick']] = d['elixir']
                tap = max(ts)
                win = [el[t] for t in sorted(el) if tap <= t <= p['tick'] + 1]
                short.append((r['match'][10:], r.get('game_build'), p['card'], tap, p['tick'], lag, el.get(tap), max(win) if win else None))
print('lag histogram (run - tap):', sorted(hist.items()))
print('short-lag plays (<= %d): %d' % (SHORT, len(short)))
for s in short:
    print('  %s build %s %s tap %d run %d lag %d el_at_tap %s max_el_in_window %s' % s)

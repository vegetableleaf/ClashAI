"""CLXIII's own elixir at its reach X-Bow (SIM: board sample s[4] at the X-Bow tick; live: match_memory event el) and the
opponent's TRUE elixir (SIM s[1]); lock by CLXIII elixir bin.  python el_b.py live | NAME=ROWS ..."""
import bisect, json, sys
import siege_b as SB
import card as CD
def bins(v, lk):
    B = ((0, 3), (3, 5), (5, 7), (7, 11))
    return ' '.join(f"{a}-{b}: {sum(a <= x < b for x in v)/len(v):.2f}/{(lambda s: sum(s)/len(s) if s else float('nan'))([l for x, l in zip(v, lk) if a <= x < b]):.2f}" for a, b in B)
for arg in sys.argv[1:]:
    if arg == 'live':
        import live_dump as LD
        from pipeline import match_memory as M
        own, lk = [], []
        for r in CD.live_records('calibration'):
            if not r.get('xb'):
                continue
            m = LD.read(CD.LOGS / r['id'])
            ev = M.build(m['side'], m['samples'], m['plays']).events(m['last'] + 1)
            for e in ev:
                if e['type'] == 'play' and e['mine'] and e['card'] == 'x-bow' and e.get('reach') and e.get('xb') and e.get('el') is not None:
                    own.append(e['el']); lk.append(int(e['xb']['locked']))
        print(f"live n {len(own)} CLXIII elixir mean {sum(own)/len(own):.2f} | share/lock by bin {bins(own, lk)}")
        continue
    name, root = arg.split('=', 1)
    import xbow_count as XC
    own, opp, lk = [], [], []
    for r, (_, h) in zip(CD.sim_records(root), XC.rows(root)):
        st = [s[0] for s in h['samples']]
        for t, l in r['xb']:
            i = bisect.bisect_right(st, t) - 1
            if i >= 0:
                own.append(h['samples'][i][4]); opp.append(h['samples'][i][1] or 0); lk.append(l)
    print(f"{name} n {len(own)} CLXIII elixir mean {sum(own)/len(own):.2f} opp true elixir {sum(opp)/len(opp):.2f} | share/lock by CLXIII bin {bins(own, lk)}")

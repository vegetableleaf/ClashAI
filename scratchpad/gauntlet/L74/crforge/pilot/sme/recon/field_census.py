"""RECON field census (laptop): how often do the EXTRACTED inputs of every frozen fresh set break each hard rule?
A rule that real, exactly-replayed matches break is too strict (or measures an extraction gap).

    python -I field_census.py > ../results/live/recon/field_census.txt
"""
import collections, json, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import sme_live  # noqa: E402

SME = os.path.dirname(HERE)
SETS = ['fresh4', 'fresh5', 'fresh6', 'fresh7', 'fresh8']


def main():
    tab = recon.Tab()
    n = collections.Counter()
    lows, own_res, zone_bad, travel = [], [], [], collections.Counter()
    for fs in SETS:
        fdir = os.path.join(SME, 'engfix', fs, 'frames')
        for line in open(os.path.join(SME, 'engfix', fs, 'inputs_all.jsonl')):
            rec = json.loads(line)
            fp = os.path.join(fdir, rec['match'] + '.jsonl')
            if not os.path.exists(fp):
                continue
            frames = sme_live.load_frames(fp)
            me, opp = rec['my_side'], 1 - rec['my_side']
            plan = recon.base_plan(rec, frames)
            e0 = recon.start_elixir(frames, plan, me, tab)
            n['records'] += 1
            n['cycle_ok_opp'] += plan['_cycle_base'][opp]
            n['cycle_ok_own'] += plan['_cycle_base'][me]
            low = recon.bank_min(plan, opp, tab, e0)
            if low is None:
                n['elixir_skipped'] += 1
            else:
                lows.append((low, fs, rec['match'][-6:], ','.join(f.split(':')[1] for f in rec['flags'])))
            # own bank model vs the reader's own elixir, at frames >= 60 ticks from any own command (cost timing aside)
            trace = recon.bank_trace(plan, me, tab, e0)
            runs = sorted(c['run'] for c in plan['cmds'] if c['side'] == me and c['kind'] in ('play', 'ability'))
            for t in sorted(frames)[::25] if trace else ():
                if not any(abs(t - r) < 60 for r in runs):
                    own_res.append((abs(recon.bank_at(trace, t) - frames[t]['el'] / 10000), fs, rec['match'][-6:], t))
            for c in plan['cmds']:
                if c['kind'] != 'play':
                    continue
                n['plays'] += 1
                if not recon.zone_ok(tab, c['card'], c['side'], c['x'], c['y'], recon.towers_down(frames, c['side'], c['run'])):
                    zone_bad.append((fs, rec['match'][-6:], c['side'], c['card'], c['x'], c['y'], c['run']))
                tr = recon.travel_runs(c, frames, tab)
                if tab.projectile(c['card']):
                    s = c['_src']
                    key = 'none' if tr is None else 'in_window' if s['lo'] <= min(tr) <= s['hi'] else 'outside'
                    travel[(c['card'], key)] += 1
    print('records', n['records'], '| opponent cycle ok', n['cycle_ok_opp'], '| own cycle ok', n['cycle_ok_own'],
          '| elixir rule skipped (elixir-making deck)', n['elixir_skipped'])
    ls = sorted(lows)
    print('opponent bank minimum over the match: n %d, min %.2f, p5 %.2f, median %.2f' % (
        len(ls), ls[0][0], ls[len(ls) // 20][0], statistics.median(x[0] for x in ls)))
    print('  below -SLACK (%.1f): %s' % (recon.SLACK, [x for x in ls if x[0] < -recon.SLACK]))
    r = sorted(x[0] for x in own_res)
    print('own bank model |model - reader| (elixir), %d frames: median %.3f, p95 %.3f, max %.3f' % (
        len(r), statistics.median(r), r[int(.95 * len(r))], r[-1]))
    print('  worst 8:', sorted(own_res, reverse=True)[:8])
    print('zone breaks among %d extracted plays: %d' % (n['plays'], len(zone_bad)))
    for z in zone_bad[:30]:
        print('  ', z)
    print('travel rule on extracted projectile-spell plays (card, verdict vs the extractor window): count')
    for k, v in sorted(travel.items()):
        print('  ', k, v)



if __name__ == '__main__':
    main()

"""Threat metrics (ape_punish.score section 1: lane enemy value on our half >= 5 elixir for > 3 s) on SIM board rows, with
ape_punish's SIM body value vs the one (live) rule of push_cal.card_val. The drift-test gate (exploit/tools/drift_check.py,
via ape/ape_score.py, same sim_value) uses the first.
  python threat_check.py DIR [DIR ...]    (pod; DIR/*/D3/matches.jsonl with 'hab')"""
import glob
import json
import sys
from collections import defaultdict

import push_cal as PC

AP = PC.AP


def rows(h, rule):
    side = h['L']
    smp = h['samples']
    king_y = next(t[3] for t in smp[0][5] if t[0] == side and t[1] == 'k')
    low = king_y < 16000

    def own(x, y):
        x, y = (x / 1000, y / 1000) if max(abs(x), abs(y)) > 100 else (x, y)
        return (x, 1 - y / 32) if low else (18 - x, y / 32)

    top = defaultdict(int)
    for s in smp:
        for _, name, _, mx, _, _ in s[6]:
            top[AP.L.vocab.engine_key(name) or ''] = max(top[AP.L.vocab.engine_key(name) or ''], mx)
    S = []
    for t, _a, _b, _c, el, tw, en, _xb in smp:
        vh, vl, on = [0.0, 0.0], [0.0, 0.0], {}
        for uid, name, hp, mx, x, y in en:
            if rule == 'old':
                v = AP.sim_value(name, hp, mx)
            else:
                v = None if mx < PC.MIN_MX else PC.card_val(AP.L.vocab.engine_key(name) or '', hp, mx, top)[0]
            if v is None:
                continue
            ox, oy = own(x, y)
            lane = int(ox >= 9)
            vl[lane] += v
            if oy > .5:
                vh[lane] += v
                on[uid] = v
        S.append(dict(t=t, vh=vh, vl=vl, cov=None, el=el, mc=AP.SIM_MC, on=on,
                      tw=sum(max(0, t_[4]) for t_ in tw if t_[0] == side)))
    P = []
    for q in h['own']:
        if q[3]:
            ox, oy = own(q[8], q[9])
            P.append(dict(t=q[0], name=AP.SIM_NAME.get(AP.slug(q[2]).replace('_evo', ''), q[2]), x=ox, y=oy, el=q[5]))
    return AP.score(S, P)


def main():
    tot = {r: defaultdict(float) for r in ('old', 'card')}
    n = 0
    for d in sys.argv[1:]:
        for f in sorted(glob.glob(f'{d}/*/D3/matches.jsonl')):
            for line in open(f):
                j = json.loads(line)
                if not j.get('hab') or not j['hab']['samples']:
                    continue
                n += 1
                for r in tot:
                    for k, v in rows(j['hab'], r).items():
                        tot[r][k] += v
    for r, t in tot.items():
        print(f"{r:4s} matches {n}: threats / match {t['thr'] / n:.2f}, ignored share {t['thr_ign'] / t['thr']:.3f}, "
              f"idle share {t['thr_idle'] / t['thr']:.3f}, wrong share {t['thr_wrong'] / t['thr']:.3f}, "
              f"s unanswered / threat {t['thr_secs'] / t['thr']:.2f}, HP lost 15 s idle {t['thr_idle_lost'] / max(1, t['thr_idle']):.0f}"
              f" / answered {t['thr_ans_lost'] / max(1, t['thr_ans']):.0f}")


if __name__ == '__main__':
    main()

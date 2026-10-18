"""Opponent-pool drift (successor task, 10-17 night): live 13k opponents vs the RL training pool and the D3 eval pool.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/successor/drift/drift.py      -> drift.json + drift.txt (here)

Live side: every ladder match in overnight.out with a log (ladder.py: result, trophies before/after), the model from the
log's start event, the opponent's PLAYED cards from fights.py play detection (census_cards.one; the 10-17 11:59 census
census_all.json is reused for the logs it holds), opponent tower level / tower troop from the first frame's crown-tower max_hp
(troops/tower_table.json, exact +-1), opponent card levels = the reader's per-body level field (frame ents_state[2]).
Pools (weights exactly as the code draws them):
  train  = icebow/data/rltest/decks_rl.json (sha b43dd085, shipped in every RL data_rl.tgz since 10-13), P ~ sides
           (rl_royale.deck_weights alpha 1, floor 0; league_decks drops the icebow deck), opponent deck of EVERY matchup
  exploit= L74/exploit/decks_struggle.json, P ~ sides (same alpha / floor), 30% of matchups when factorial factor B is on
  d3     = L74/mix/decks_live_eval.json, P ~ max(n_live, 0.5 x mean) (gap.py squares sides; search_s0.opp_deck_for alpha .5 floor .5)
"""
import collections
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path[:0] = [str(REPO), str(REPO / 'scratchpad/gauntlet/L74/weekend'), str(HERE)]
import archetypes as A                                                    # noqa: E402
from ladder import ladder                                                 # noqa: E402

LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
CENSUS = Path('C:/Users/benpe/pod_backup_weekend/parity1016/census/census_all.json')
TRAIN = HERE / 'in/icebow/data/rltest/decks_rl.json'
EXPLOIT = REPO / 'scratchpad/gauntlet/L74/exploit/decks_struggle.json'
D3 = REPO / 'scratchpad/gauntlet/L74/mix/decks_live_eval.json'
LEVELS = REPO / 'scratchpad/gauntlet/L74/levels/live_levels.json'
TOWERS = json.loads((REPO / 'scratchpad/gauntlet/L74/troops/tower_table.json').read_text())
ICE = sorted(['Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons'])
CUE = 'rlarm_gae_cue_u250_u0130'
U250 = 'rlarm_gae_u0250'
SINCE = 'live_play_20261007'
BUILD_END = 'live_play_20261015_143000'      # decks_live_eval.json was built ~14:40 10-15 from live matches up to then
SLOTS = {(3500, 6500), (14500, 6500), (3500, 25500), (14500, 25500)}
FORM = {'': '', 'evo': '@evo', 'hero': '@hero'}
# live names whose canon differs from the engine's (vocab.py over all census_all opponent plays: Spirit Empress's two bodies)
LIVE_ALIAS = {'mergemaidenmounted': 'mergemaiden', 'mergemaidennormal': 'mergemaiden'}


# ------------------------------------------------------------------------------------------------------------------ pools
def weights(sides, alpha, floor):
    """rl_royale.deck_weights, copied (importing rl_royale pulls torch)."""
    w = [float(s) ** alpha for s in sides]
    m = sum(w) / len(w)
    w = [max(x, floor * m) for x in w]
    t = sum(w)
    return [x / t for x in w]


def pool(path, kind):
    decks = [d for d in json.loads(Path(path).read_text())['decks'] if sorted(n.split('@')[0] for n in d['engine']) != ICE]
    if kind == 'd3':
        p = weights([d['sides'] for d in decks], 1.0, 0.5)        # sqrt(sides**2) = n_live, floor .5 x mean
    else:
        p = weights([d['sides'] for d in decks], 1.0, 0.0)
    return [(d['engine'], q) for d, q in zip(decks, p)]


def pool_stats(rows):
    arch, card, form = collections.Counter(), collections.Counter(), collections.Counter()
    for eng, q in rows:
        arch[A.classify(eng)] += q
        for n in eng:
            b, _, f = n.partition('@')
            card[A.canon(b)] += q
            form[A.canon(b) + ('@evo' if f == 'evolution' else '@hero' if f == 'hero' else '')] += q
    return dict(arch=arch, card=card, form=form, n=len(rows), pmax=max(q for _, q in rows))


def mix(a, b, wb):
    out = {}
    for k in ('arch', 'card', 'form'):
        c = collections.Counter()
        for x, v in a[k].items():
            c[x] += (1 - wb) * v
        for x, v in b[k].items():
            c[x] += wb * v
        out[k] = c
    return out


# ------------------------------------------------------------------------------------------------------------------- live
def first_line(path):
    with open(path, 'rb') as f:
        return json.loads(f.readline())


def towers_and_levels(path):
    """-> (opp king level, opp princess-slot kind 'PrincessTower'/troop/'unknown', Counter of opp card levels (one per body))."""
    king = prin = None
    lv, seen = collections.Counter(), set()
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40]:
                continue
            e = json.loads(raw)
            me = e['my_side']
            if king is None:
                ks = [a[5] for a in e['ents'] if a[3] == -1 and a[0] != me and abs(a[1] - 9000) < 1000]
                ps = {a[5] for a in e['ents'] if a[3] == -1 and a[0] != me
                      and any(abs(a[1] - x) < 600 and abs(a[2] - y) < 600 for x, y in SLOTS)}
                king = next((int(l) for l, r in TOWERS.items() for k in ks if abs(r['king'] - k) <= 1), 'unknown')
                hits = [(n, int(l)) for l, r in TOWERS.items() for n, v in r.items() if n != 'king' for p in ps if abs(v - p) <= 1]
                prin = hits[0] if len(ps) == 1 and len(hits) == 1 else ('unknown', None)
            if 'ents_state' not in e:
                continue
            for a, st in zip(e['ents'], e['ents_state']):
                if a[0] == me or a[3] == -1:
                    continue
                k = (a[3], st[3])
                if k not in seen:
                    seen.add(k)
                    lv[st[2]] += 1
    return king, prin, lv


def live_rows(ms):
    from scratchpad.gauntlet.L74.parity.coverage import census_cards as C
    cen = json.loads(CENSUS.read_text())['per_match']
    cen_last = max(cen)                       # logs up to here that the census skipped (not main account / unreadable) stay out
    rows = []
    for m in ms:
        if not m['log'] or m['log'] < SINCE or m['delta'] is None:
            continue
        p = LOGS / m['log']
        if not p.is_file():
            continue
        stem = p.stem
        plays = cen.get(stem)
        if plays is None:
            if stem <= cen_last:
                continue
            _, reason, plays, _ = C.one(str(p))
            if reason:
                continue                      # not the main account / unreadable
        ck = first_line(p).get('ckpt') or ''
        mark = 'CXXXVIII' if CUE in ck else 'CXXIV' if U250 in ck else 'other'
        opp = collections.Counter()
        for lab, n in plays.items():
            if lab.startswith('opp '):
                name, f = lab[4:], ''
                for s in (' evo', ' hero'):
                    if name.endswith(s):
                        name, f = name[:-len(s)], s[1:]
                c = A.canon(name)
                opp[LIVE_ALIAS.get(c, c) + FORM[f]] += n
        if not opp:
            continue
        rows.append(dict(log=stem, mark=mark, win=int(m['result'] == 'WIN'), before=m.get('before'), delta=m['delta'],
                         opp=dict(opp)))
    return rows


# --------------------------------------------------------------------------------------------------------------- reporting
def wilson(k, n, z=1.96):
    if n == 0:
        return float('nan'), float('nan')
    p = k / n
    c = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    m = (p + z * z / (2 * n)) / (1 + z * z / n)
    return 100 * (m - c), 100 * (m + c)


def base_set(r):
    return {k.split('@')[0] for k in r['opp']}


def live_stats(rows):
    arch, card, form, plays = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for r in rows:
        arch[A.classify(base_set(r))] += 1
        for c in base_set(r):
            card[c] += 1
        for k, n in r['opp'].items():
            form[k] += 1
            plays[k] += n
    n = len(rows)
    return dict(n=n, arch={k: v / n for k, v in arch.items()}, card={k: v / n for k, v in card.items()},
                form={k: v / n for k, v in form.items()}, plays=plays)


def winrate(rows, key):
    g = collections.defaultdict(list)
    for r in rows:
        for k in key(r):
            g[k].append(r['win'])
    return g


def main():
    ms, bad, nseg = ladder()
    rows = live_rows(ms)
    by = lambda f: [r for r in rows if f(r)]                                          # noqa: E731
    win = dict(
        cue=by(lambda r: r['mark'] == 'CXXXVIII'),
        cue_hi=by(lambda r: r['mark'] == 'CXXXVIII' and (r['before'] or 0) >= 12800),
        hi=by(lambda r: (r['before'] or 0) >= 12800),
        last120=rows[-120:],
        build=by(lambda r: r['log'] < BUILD_END),
        u250=by(lambda r: r['mark'] == 'CXXIV'),
    )
    train, expl, d3 = pool_stats(pool(TRAIN, 'train')), pool_stats(pool(EXPLOIT, 'x')), pool_stats(pool(D3, 'd3'))
    trainB = mix(train, expl, 0.3)
    L = {k: live_stats(v) for k, v in win.items()}
    out = dict(windows={k: dict(n=len(v), first=v[0]['log'] if v else None, last=v[-1]['log'] if v else None,
                                win=sum(r['win'] for r in v) / max(1, len(v)),
                                trophies=[min((r['before'] or 0) for r in v), max((r['before'] or 0) for r in v)] if v else None)
                        for k, v in win.items()},
               anchors=dict(segments=nseg, inconsistent=bad))
    T = []
    w = T.append
    w(f"live rows (main account, plays read, since {SINCE}): {len(rows)}; ladder anchors {nseg}, {bad} inconsistent (>2 tr)")
    for k, v in out['windows'].items():
        w(f"  window {k:8s} n {v['n']:4d}  win {100*v['win']:.1f}%  trophies-before {v['trophies']}  {v['first']} .. {v['last']}")
    w(f"pools: train {train['n']} decks (max p {train['pmax']:.4f}); exploit {expl['n']} (max p {expl['pmax']:.4f}); "
      f"d3 {d3['n']} (max p {d3['pmax']:.4f})")

    # 1. archetypes
    archs = list(A.ORDER) + ['other']
    w("\n== ARCHETYPE share (A.classify; live = played cards; pool = full deck)  + live win rate per window")
    w(f"{'arch':17s} {'train':>6s} {'+B':>6s} {'d3':>6s} {'build':>6s} {'last120':>7s} {'cue':>6s} {'cue>=12.8k':>10s}"
      f" | {'cue n':>5s} {'cue win%':>8s} {'95% CI':>13s} | {'u250 n':>6s} {'u250 win%':>9s} {'build n':>7s} {'build win':>9s}")
    for a in archs:
        def wr(rs):
            g = [r['win'] for r in rs if A.classify(base_set(r)) == a]
            return len(g), (100 * sum(g) / len(g) if g else float('nan')), wilson(sum(g), len(g))
        nc, pc, ci = wr(win['cue']); nu, pu, _ = wr(win['u250']); nb, pb, _ = wr(win['build'])
        w(f"{a:17s} {100*train['arch'][a]:6.1f} {100*trainB['arch'][a]:6.1f} {100*d3['arch'][a]:6.1f} "
          f"{100*L['build']['arch'].get(a,0):6.1f} {100*L['last120']['arch'].get(a,0):7.1f} {100*L['cue']['arch'].get(a,0):6.1f} "
          f"{100*L['cue_hi']['arch'].get(a,0):10.1f} | {nc:5d} {pc:8.1f} [{ci[0]:5.1f},{ci[1]:5.1f}] | {nu:6d} {pu:9.1f} {nb:7d} {pb:9.1f}")
    unf = [a for a in A.ORDER if A.unfavorable(a)]
    for nm, st in (('train', train), ('train+B', trainB), ('d3', d3)):
        w(f"  unfavourable six share in {nm}: {100*sum(st['arch'][a] for a in unf):.1f}%")
    for k in ('build', 'last120', 'cue', 'cue_hi'):
        w(f"  unfavourable six share live {k}: {100*sum(L[k]['arch'].get(a, 0) for a in unf):.1f}%")

    # 2. cards: presence share (live = seen played, a lower bound) vs pools, with win rates
    w("\n== CARD presence (% of matches / % of pool draws), top 45 by last120 presence; live win% (cue window, all CXXIV+CXXXVIII since 10-15)")
    rec = by(lambda r: r['log'] >= 'live_play_20261015')
    wr_card = winrate(rec, base_set)
    wr_cue = winrate(win['cue'], base_set)
    base = 100 * sum(r['win'] for r in rec) / len(rec)
    w(f"   (overall win since 10-15: {base:.1f}% over {len(rec)} matches)")
    w(f"{'card':17s} {'train':>6s} {'+B':>6s} {'d3':>6s} {'build':>6s} {'last120':>7s} {'cue':>6s} {'L/T':>6s} {'L/D3':>5s}"
      f" | {'cue n':>5s} {'cue win':>7s} | {'1015+ n':>7s} {'win%':>5s} {'95% CI':>13s} {'cost':>6s}")
    top = sorted(L['last120']['card'], key=lambda c: -L['last120']['card'][c])[:45]
    for c in top:
        lv, tv, dv = L['last120']['card'][c], train['card'].get(c, 0), d3['card'].get(c, 0)
        g, gc = wr_card.get(c, []), wr_cue.get(c, [])
        ci = wilson(sum(g), len(g))
        w(f"{c:17s} {100*tv:6.1f} {100*trainB['card'].get(c,0):6.1f} {100*dv:6.1f} {100*L['build']['card'].get(c,0):6.1f} "
          f"{100*lv:7.1f} {100*L['cue']['card'].get(c,0):6.1f} {lv/tv if tv else float('inf'):6.1f} {lv/dv if dv else float('inf'):5.1f} | "
          f"{len(gc):5d} {100*sum(gc)/len(gc) if gc else float('nan'):7.1f} | {len(g):7d} {100*sum(g)/len(g) if g else float('nan'):5.1f} "
          f"[{ci[0]:5.1f},{ci[1]:5.1f}] {len(g)*(base-100*sum(g)/len(g))/100 if g else 0:+6.1f}")

    # 3. plays from cards the pools lack
    w("\n== live opponent PLAYS from cards a pool lacks (base card; exact form) and from cards the pool holds rarely")
    for k in ('build', 'last120', 'cue', 'cue_hi'):
        P = L[k]['plays']; tot = sum(P.values())
        for nm, st in (('train', train), ('train+B', trainB), ('d3', d3)):
            nob = sum(n for f, n in P.items() if st['card'].get(f.split('@')[0], 0) == 0)
            nof = sum(n for f, n in P.items() if st['form'].get(f, 0) == 0)
            rare = sum(n for f, n in P.items() if st['card'].get(f.split('@')[0], 0) < 0.01)
            w(f"  {k:8s} vs {nm:8s}: {tot:5d} plays; base card absent {100*nob/tot:5.1f}%; exact form absent {100*nof/tot:5.1f}%; "
              f"base card in < 1% of pool draws {100*rare/tot:5.1f}%")
    P = L['last120']['plays']; tot = sum(P.values())
    miss = collections.Counter({f: n for f, n in P.items() if train['form'].get(f, 0) == 0})
    w("  last120 plays whose exact form the TRAIN pool lacks (top 20): " +
      ", ".join(f"{f} {100*n/tot:.1f}%" for f, n in miss.most_common(20)))
    miss = collections.Counter({f: n for f, n in P.items() if d3['form'].get(f, 0) == 0})
    w("  last120 plays whose exact form the D3 pool lacks (top 20): " +
      ", ".join(f"{f} {100*n/tot:.1f}%" for f, n in miss.most_common(20)))
    lowt = collections.Counter({f: n for f, n in P.items() if train['card'].get(f.split('@')[0], 0) < 0.01})
    w("  last120 plays from base cards in < 1% of TRAIN draws (top 20): " +
      ", ".join(f"{f} {100*n/tot:.1f}% (train {100*train['card'].get(f.split('@')[0],0):.2f}%)" for f, n in lowt.most_common(20)))

    # 4. tower / card levels + tower troops for the recent windows
    w("\n== opponent tower level / tower troop / card levels (frames), vs live_levels.json (310 matches 10-15..10-17 09:57) and SIM L11")
    tab = json.loads(LEVELS.read_text())
    tl = collections.Counter(p[1] for p in tab['opp_profiles'])
    w(f"  live_levels.json opp tower: {dict(sorted(tl.items()))} (n {sum(tl.values())})")
    for k in ('cue', 'cue_hi', 'last120'):
        kings, prins, lvs = collections.Counter(), collections.Counter(), collections.Counter()
        for r in win[k]:
            kg, pr, lv = towers_and_levels(LOGS / (r['log'] + '.jsonl'))
            kings[kg] += 1; prins[pr[0]] += 1; lvs.update(lv)
        n = len(win[k]); nl = sum(lvs.values())
        troop = n - prins.get('PrincessTower', 0) - prins.get('unknown', 0)
        ci = wilson(troop, n - prins.get('unknown', 0))
        w(f"  {k:8s} n {n}: opp king level {dict(sorted(kings.items(), key=str))}; princess slot {dict(prins)} -> troop "
          f"{100*troop/max(1, n - prins.get('unknown', 0)):.1f}% [{ci[0]:.1f}, {ci[1]:.1f}]")
        w(f"           opp card levels (one reading per body, n {nl}): " +
          ", ".join(f"{l}: {100*c/nl:.1f}%" for l, c in sorted(lvs.items()) if c / max(1, nl) >= 0.005))
        out[f'levels_{k}'] = dict(king=dict(kings), princess=dict(prins), card=dict(lvs))

    # 5. trophy cost / drift product per archetype (cue window and since 10-15)
    w("\n== DRIFT x COST per archetype: live share (last120) - train share, matchup win (since 10-15, both Marks), "
      "matches lost per 100 vs an average opponent")
    g = winrate(rec, lambda r: [A.classify(base_set(r))])
    for a in archs:
        x = g.get(a, [])
        if not x:
            continue
        pw = 100 * sum(x) / len(x)
        ci = wilson(sum(x), len(x))
        sh = L['last120']['arch'].get(a, 0)
        w(f"  {a:17s} live {100*sh:5.1f}% train {100*train['arch'][a]:5.1f}% (x{(train['arch'][a]/sh if sh else float('inf')):.2f}) "
          f"| n {len(x):4d} win {pw:5.1f}% [{ci[0]:.1f},{ci[1]:.1f}] | lost/100 vs avg {sh*(base-pw):+5.2f}")
    Path(HERE / 'drift.txt').write_text('\n'.join(T) + '\n', encoding='utf-8')
    out.update(live=rows, pools=dict(train={k: dict(v) for k, v in train.items() if k in ('arch', 'card', 'form')},
                                     d3={k: dict(v) for k, v in d3.items() if k in ('arch', 'card', 'form')},
                                     exploit={k: dict(v) for k, v in expl.items() if k in ('arch', 'card', 'form')}))
    Path(HERE / 'drift.json').write_text(json.dumps(out), encoding='utf-8')
    print('\n'.join(T))


if __name__ == '__main__':
    main()

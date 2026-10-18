"""Second pass over the press matches: (1) the pro-contrast context at each press (enemy births = plays, own plays,
own elixir, overtime) for the pro comparison; (2) the elixir counterfactual: decisions after the press with no card
affordable while an enemy troop is on my half, and whether the press's 2 elixir would have made a hand card affordable;
(3) the two-Ice-Wizard presses: which body the rule used and which one carried the ability.
Out: extra_rows.json + printout. Enemy births = new generation ids on the enemy side (spells are not bodies: missed)."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit                                                             # noqa: E402

R = json.loads((HERE / 'press_rows.json').read_text())
INV = {m['log']: m for m in json.loads((HERE / 'inventory.json').read_text())}
ENTS = re.compile(rb'"ents": (\[.*?\]\]), "ents_state": (\[.*?\]\])')
CONF = re.compile(rb'^\{"event": "confirmed", "tick": (\d+), "name": "([A-Za-z]+)"')
WINCON = {"HogRider", "SuperHogRider", "Giant", "GoblinGiant", "Golem", "RoyalGiant", "ElectroGiant", "Balloon",
          "LavaHound", "RamRider", "BattleRam", "Miner", "RoyalHogs", "Wallbreakers", "ElixirGolem", "GiantSkeleton",
          "SkeletonBalloon", "Pekka", "MegaKnight"}


def run():
    by_log = {}
    for r in R:
        if r.get('truth') not in (None, 'no_phase2'):
            by_log.setdefault(r['log'], []).append(r)
    out = []
    for li, (log, rs) in enumerate(by_log.items()):
        m = INV[log]
        side = m['side']
        mine = (lambda y: y > 16000) if side == 1 else (lambda y: y < 16000)
        P = sorted(r['tick'] for r in rs)
        wins = [(p - 220, p + 130) for p in P]
        seen, births, own_conf, fr, decs, full = {}, [], [], {}, [], {}
        with open(audit.LIVE / log, 'rb') as f:
            for raw in f:
                if raw.startswith(b'{"event": "confirmed"'):
                    c = CONF.match(raw)
                    if c and c.group(2) != b'IceWizard':          # the pros' own_n3 excludes the Ice Wizard itself
                        own_conf.append(int(c.group(1)))
                    continue
                if raw.startswith(b'{"event": "decision"'):
                    t = int(audit.TICK.search(raw).group(1))
                    if any(p < t <= p + 130 for p in P):
                        j = json.loads(raw)
                        pub = j.get('public') or {}
                        hand = [h.get('cost') for h in pub.get('own_hand') or [] if h.get('cost')]
                        decs.append((t, j['decision'].get('no_affordable'), pub.get('own_elixir_raw'), min(hand, default=None)))
                    continue
                if not raw.startswith(b'{"event": "frame"'):
                    continue
                t = int(audit.TICK.search(raw).group(1))
                g = ENTS.search(raw)
                if not g:
                    continue
                ents, st = json.loads(g.group(1)), json.loads(g.group(2))
                for e, s in zip(ents, st):
                    gen = s[3]
                    if gen not in seen:
                        seen[gen] = t
                        if e[0] != side and e[6] not in (12, 13) and e[3] >= 0 and t > 100:
                            births.append((t, audit.NAMES.get(int(e[3]), ''), e[1], e[2]))
                if any(a <= t <= z for a, z in wins):
                    fr[t] = [(e[0], e[1], e[2], e[3], e[6], s[3]) for e, s in zip(ents, st)]
                if t in P:
                    full[t] = json.loads(raw)
        ticks = sorted(fr)
        for r in rs:
            p = r['tick']
            row = {'mark': r['mark'], 'log': log, 'tick': p, 'kind': r['kind'], 'truth': r['truth']}
            b6 = [b for b in births if p - 120 <= b[0] <= p]
            b3 = [b for b in b6 if b[0] >= p - 60]
            row['opp_birth_3s'] = bool(b3)
            row['opp_birth_my_half_6s'] = any(mine(b[3]) for b in b6)
            last = [b[0] for b in births if b[0] <= p]
            row['since_last_opp_birth_s'] = (p - max(last)) / 20 if last else None
            lm = [b[0] for b in births if b[0] <= p and mine(b[3])]
            row['since_last_opp_birth_my_half_s'] = (p - max(lm)) / 20 if lm else None
            f0 = fr.get(max((t for t in ticks if t <= p), default=-1))
            # an enemy troop on my half now that was born within the last 6 s (the pros' 'played on my half' proxy)
            recent = {gen for gen, t0 in seen.items() if p - 120 <= t0 <= p}
            row['opp_recent_troop_on_my_half_6s'] = bool(f0 and any(
                e[0] != side and e[4] not in (12, 13) and e[3] >= 0 and mine(e[2]) and e[5] in recent for e in f0))
            b10 = [b for b in births if p - 200 <= b[0] <= p]
            row['opp_wincon_birth_10s'] = any(b[1] in WINCON for b in b10)
            rec10 = {gen for gen, t0 in seen.items() if p - 200 <= t0 <= p}
            row['opp_wincon_on_my_half_10s'] = bool(f0 and any(
                e[0] != side and mine(e[2]) and e[5] in rec10 and audit.NAMES.get(int(e[3]), '') in WINCON for e in f0))
            el = INV[log]['elixir']                      # inventory: own elixir on frames with tick % 10 == 0
            te = r.get('effect_tick') or p + 23
            k = max((int(t) for t in el if int(t) <= te), default=None)
            row['own_elixir_at_effect'] = el[str(k)] if k is not None and str(k) in el else None
            if r.get('effect_tick') and r.get('age_logged') is not None:
                row['ingame_delay_s'] = round(r['age_logged'] + (r['effect_tick'] - p) / 20, 2)
            row['own_played_3s'] = any(p - 60 <= t <= p for t in own_conf)
            row['overtime'] = p >= 3600
            row['own_elixir'] = r.get('elixir_at')
            # elixir counterfactual
            noaff = [d for d in decs if p < d[0] <= p + 120 and d[1]]
            thr = []
            for d in noaff:
                ft = max((t for t in ticks if t <= d[0]), default=None)
                if ft and any(e[0] != side and e[4] not in (12, 13) and e[3] >= 0 and mine(e[2])
                              and audit.NAMES.get(int(e[3]), '') not in audit.BUILDINGS for e in fr[ft]):
                    thr.append(d)
            row['noaff_threat'] = len(thr) > 0
            row['noaff_threat_cf2'] = any(d[2] is not None and d[3] is not None and d[2] < d[3] <= d[2] + 2 for d in thr)
            # two own Ice Wizards: which carried the ability, which the rule used
            if r.get('n_own_iw') == 2 and p in full:
                j = full[p]
                U = {u['generation']: u for u in (j.get('phase2') or {}).get('units', [])}
                iws = sorted(g for g, u in U.items() if u['name'] == 'IceWizardHero' and u['side'] == side)
                withab = [g for g in iws if ((U[g].get('ability') or {}).get('own_action'))]
                row['two_iw'] = {'gens': iws, 'with_ability': withab, 'rule_gen': r.get('iw_gen'),
                                 'ability_state': [U[g]['ability']['own_action']['state_raw'] for g in withab]}
            out.append(row)
        if li % 40 == 0:
            print(li, len(by_log), file=sys.stderr, flush=True)
    (HERE / 'extra_rows.json').write_text(json.dumps(out))
    return out


def report(out):
    for mark in ('CXXXVIII', 'CXXIV'):
        xs = [x for x in out if x['mark'] == mark]
        n = len(xs)
        f = lambda k: f"{sum(1 for x in xs if x.get(k))}/{n} = {100 * sum(1 for x in xs if x.get(k)) / n:.1f}%"  # noqa: E731
        print(f'\n== {mark}: {n} presses with phase-2 truth')
        for k in ('opp_birth_3s', 'opp_birth_my_half_6s', 'opp_recent_troop_on_my_half_6s', 'opp_wincon_birth_10s',
                  'opp_wincon_on_my_half_10s', 'own_played_3s', 'overtime', 'noaff_threat', 'noaff_threat_cf2'):
            print(f'  {k}: {f(k)}')
        print('  own elixir >= 5 at decision:', sum(1 for x in xs if (x['own_elixir'] or 0) >= 5), '/', n,
              '| <= 2:', sum(1 for x in xs if (x['own_elixir'] or 9) <= 2))
        ee = [x['own_elixir_at_effect'] for x in xs if x.get('own_elixir_at_effect') is not None]
        print('  own elixir >= 5 when the press landed in game:', sum(1 for v in ee if v >= 5), '/', len(ee),
              '| median', sorted(ee)[len(ee) // 2])
        d = sorted(x['ingame_delay_s'] for x in xs if x.get('ingame_delay_s') is not None)
        print('  in-game delay landing -> ability active (s): p10/p25/med/p75/p90',
              [d[int(q * (len(d) - 1))] for q in (.1, .25, .5, .75, .9)], 'n', len(d))
        for k in ('since_last_opp_birth_s', 'since_last_opp_birth_my_half_s'):
            v = sorted(x[k] for x in xs if x[k] is not None)
            print(f'  {k}: median {v[len(v) // 2]}  p25 {v[len(v) // 4]}  p75 {v[3 * len(v) // 4]}')
        tw = [x['two_iw'] for x in xs if x.get('two_iw')]
        print('  two-IW presses:', len(tw), '| rule used the body WITHOUT the ability:',
              sum(1 for t in tw if t['rule_gen'] not in t['with_ability']),
              '| that body was the OLDER one:', sum(1 for t in tw if t['rule_gen'] == min(t['gens'])),
              '| ability-holder state at press:', [s for t in tw for s in t['ability_state']])


if __name__ == '__main__':
    report(run())

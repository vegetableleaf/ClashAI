"""Q1: Tornado pull SIM vs live by mass class, pooled from the fork fin15 J2 Tornado table (FIN15 law A/B arm B = the fin15
law; parity/fin15/analysis/torn_ab_B.txt, 638 caplogs13 logs, 1,485 Tornado victims with pulls). The mass rows there are
exact counts (n, agree, share of bodies where the SIM pulls >300 mt LESS / MORE than live), so the class pools are exact;
the building-targeter pool uses the per-card rows (cards with n >= 8 only).   python q1_classes.py torn_ab_B.txt"""
import re
import sys

mass_rows, card_rows = [], []
for line in open(sys.argv[1]):
    m = re.match(r'fly (\d) mass (\d+) n (\d+) agree ([\d.]+) median live-sim pull (\S+) share sim pulls less by >300 ([\d.]+) more by >300 ([\d.]+)', line)
    if m:
        f, ms, n, a, med, less, more = m.groups()
        mass_rows.append(dict(fly=int(f), mass=int(ms), n=int(n), agree=float(a), med=float(med), less=float(less), more=float(more)))
        continue
    m = re.match(r'(\S+(?: evo| hero)?)\s+(\d+)\s+(\d)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s+([\d.na]+) \(n (\d+)\)', line)
    if m:
        c, ms, f, n, a, d0, pl, ps, r, nf = m.groups()
        card_rows.append(dict(card=c, mass=int(ms), fly=int(f), n=int(n), agree=float(a), pl=int(pl), ps=int(ps),
                              ratio=float(r), nfar=int(nf)))


def pool(rows, name):
    n = sum(r['n'] for r in rows)
    ag = sum(r['n'] * r['agree'] for r in rows) / n
    le = sum(r['n'] * r['less'] for r in rows) / n
    mo = sum(r['n'] * r['more'] for r in rows) / n
    p = ag * (1 - ag) / n
    print(f'{name:34s} n {n:4d}  end point within 0.5 t: {ag:.3f} (+-{1.96 * p ** .5:.3f} binomial)  '
          f'SIM pulls >0.3 t LESS {le:.3f} / MORE {mo:.3f}  (median live-SIM pull per mass row: {sorted({r["med"] for r in rows})})')


print('Fork fin15, all Tornado casts (own 96%), victims inside the Tornado reach at the cast:')
pool([r for r in mass_rows if r['fly'] == 0 and r['mass'] <= 3], 'ground light (mass 1-3)')
pool([r for r in mass_rows if r['fly'] == 0 and 4 <= r['mass'] <= 8], 'ground medium (mass 4-8)')
pool([r for r in mass_rows if r['fly'] == 0 and r['mass'] >= 10], 'ground heavy (mass >= 10)')
pool([r for r in mass_rows if r['fly'] == 1], 'air (all masses)')
pool(mass_rows, 'ALL')
BT = {'HogRider', 'RoyalHogs', 'RoyalHogs evo', 'BattleRam', 'RoyalGiant', 'RoyalGiant evo', 'Golem', 'ElixirGolem', 'ElectroGiant',
      'Balloon', 'Balloon hero', 'LavaHound', 'SkeletonBalloon', 'GoblinGiant', 'Giant', 'RamRider'}
bt = [r for r in card_rows if r['card'] in BT]
n = sum(r['n'] for r in bt)
nf = sum(r['nfar'] for r in bt)
print(f"\nbuilding-targeters (per-card rows, n >= 8 each): n {n}, agree {sum(r['n'] * r['agree'] for r in bt) / n:.3f}, "
      f"n-weighted median pull live {sum(r['n'] * r['pl'] for r in bt) / n:.0f} mt vs SIM {sum(r['n'] * r['ps'] for r in bt) / n:.0f} mt, "
      f"median live/SIM ratio (bodies starting >= 3 t out, weighted) {sum(r['nfar'] * r['ratio'] for r in bt) / nf:.3f} (n {nf})")
for r in sorted(bt, key=lambda r: -r['n']):
    print(f"   {r['card']:16s} mass {r['mass']:2d} n {r['n']:3d} agree {r['agree']:.2f}  median pull live {r['pl']} / SIM {r['ps']} mt  ratio {r['ratio']:.3f} (n {r['nfar']})")

"""ENG-SME: list every SME_TOWER_ZAP firing in extracted inputs, for the owner to confirm in the battle-log replay (the
replay shows the opponent's hand and elixir; it needs the live client, so this only lists candidates). One TSV row per
firing: match, battle time, opponent tag (from the FRESH*.tsv lists given), tower, last hp, last listed / gone ticks, the
inserted run tick and window, the game time (20 ticks per second; regulation 3:00 = tick 3600).
    python -I tower_zap_firings.py INPUTS.jsonl ... [--lists FRESH1.tsv,FRESH2.tsv] > results/live/tower_zap_firings.tsv"""
import argparse, json

ap = argparse.ArgumentParser()
ap.add_argument('inputs', nargs='+')
ap.add_argument('--lists', default='')
a = ap.parse_args()
meta = {}
for f in filter(None, a.lists.split(',')):
    for line in open(f):
        if line.strip() and not line.startswith('#'):
            c = line.rstrip('\n').split('\t')
            meta[c[0]] = c[1:3] if len(c) > 2 else ['-', '-']


def clock(t):
    s = t / 20
    return (f'elapsed {int(s // 60)}:{s % 60:04.1f}, ' +
            (f'clock ~{int((180 - s) // 60)}:{(180 - s) % 60:04.1f} left' if s < 180 else f'overtime +{s - 180:.1f}s'))


print('# match\tbattle_time\topp_tag\ttower(side,x,y)\thp\tlast_listed\tgone\tR\twindow\tzap_level\tgame_time\tinputs')
n = 0
for f in a.inputs:
    for line in open(f):
        r = json.loads(line)
        for z in r.get('tower_zap') or ():
            bt, tag = meta.get(r['match'], [r.get('battle_time') or '-', '-'])
            print('\t'.join(map(str, [r['match'], bt, tag, z['tower'], z['hp'], z['tp'], z['t'], z['R'], z['run_ticks'],
                                      z['zap_level'], clock(z['t']), f.replace('\\', '/').split('/')[-1]])))
            n += 1
print(f'# firings {n}')

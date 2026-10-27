"""F635: how often each 16.635 refusal item appears in the opponent decks of our new-client (160635001) Ranked matches.
    python -I new_client_forms.py --tables <tables/16.635.3>
Decks from the battle log (public: card + evolutionLevel; never hands or elixir). A battle-log Ranked entry counts when
a live log from live_play_20261027_065824 on ended it (the gen_jobs.py time match: start 60-600 s before the battle
end), so the count is over our recorded new-client matches. Prints the item table, most frequent first."""
import argparse, collections, datetime as dt, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
BATTLELOG = ROOT / 'scratchpad/gauntlet/L74/crapi/data/own_battlelog.jsonl'
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
FIRST = 'live_play_20261027_065824'
ITEMS = [  # (label, table card, form: 'evo' / 'hero' / None = any form), what is refused or unread on 16.635.3
    ('mega_knight evo: uppercut GameTagsToSet', 'MegaKnight', 'evo'),
    ('firecracker evo: CastIdSpecificBuff', 'Firecracker', 'evo'),
    ('cannon evo: CastIdSpecificBuff', 'Cannon', 'evo'),
    ('battle_ram evo: PushBackDamage table', 'BattleRam', 'evo'),
    ('hunter (any form): V16_PROJECTILE_DAMAGE_BUG gone', 'Hunter', None),
    ('electro_wizard hero: CustomBuffOnDamageTime', 'ElectroWizard', 'hero'),
    ('giant evo: new evolution (giant_evo_* rows)', 'Giant', 'evo'),
    ('mirror evo: new evolution', 'Mirror', 'evo'),
    ('magic_archer hero: triple shot without root (16.402 too)', 'EliteArcher', 'hero'),
    ('valkyrie hero: delivery mark (F635-1 done)', 'Valkyrie', 'hero'),
    ('golden_knight: delivery mark (F635-1 done)', 'GoldenKnight', None),
    ('balloon hero: delivery mark (F635-1 done)', 'Balloon', 'hero'),
    ('giant hero: delivery mark (F635-1 done)', 'Giant', 'hero'),
    ('barbarian_barrel hero: button untested', 'BarbLog', 'hero'),
    ('goblins hero: button untested', 'Goblins', 'hero'),
]


def id_names(tables):
    out = {}
    for f in ('spells_characters', 'spells_buildings', 'spells_other', 'spells_evolved', 'spells_hero_form'):
        j = json.load(open(Path(tables) / f'{f}.json'))
        for name, row in j['rows'].items():
            out[j['id'] * 1000000 + row['index']] = re.sub(r'_(EV1|hero)$', '', name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', required=True)
    a = ap.parse_args()
    names = id_names(a.tables)
    starts = {}
    for p in LIVE.glob('live_play_202610*.jsonl'):
        if p.stem >= FIRST:
            m = re.match(r'live_play_(\d{8}_\d{6})', p.name)
            starts[p.stem] = dt.datetime.strptime(m.group(1), '%Y%m%d_%H%M%S') + dt.timedelta(hours=4)  # EDT -> UTC
    seen, decks = set(), {}
    for line in open(BATTLELOG):
        b = json.loads(line)['battle']
        key = (b['battleTime'], b['opponent'][0]['tag'])
        if b['type'] != 'pathOfLegend' or key in seen:
            continue
        seen.add(key)
        end = dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S')
        live = min((((end - t0).total_seconds(), s) for s, t0 in starts.items()
                    if 60 <= (end - t0).total_seconds() <= 600), default=None)
        if live is None:
            continue
        decks[live[1]] = [(names.get(c['id'], '?' + c['name']),
                           {1: 'evo', 2: 'hero'}.get(c.get('evolutionLevel') or 0)) for c in b['opponent'][0]['cards']]
    print('new-client live logs from %s: %d; with a Ranked battle-log deck: %d' % (FIRST, len(starts), len(decks)))
    count = collections.Counter()
    for d in decks.values():
        for label, card, form in ITEMS:
            if any(n == card and (form is None or f == form) for n, f in d):
                count[label] += 1
    for label, card, form in sorted(ITEMS, key=lambda i: -count[i[0]]):
        print('%3d/%d  %s' % (count[label], len(decks), label))


if __name__ == '__main__':
    main()

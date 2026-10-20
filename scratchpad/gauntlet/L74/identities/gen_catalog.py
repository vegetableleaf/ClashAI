"""Extend the live card catalog from the device tables (W9, 10-20).

The catalog (research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json, kind libg_live_card_catalog_v1) was
generated from the 15.535.29 libg (152 cards). The game is newer: the 10-12 device pull (apktables device build, the
effective tables of the installed 160402012 client + its server update) has 145 cards, 43 evolutions, 18 hero forms.
This script derives every catalog field the device tables carry and

  check   prints every field where an EXISTING catalog row disagrees with the device (the derivation's evidence), and
          which device cards / forms the catalog lacks;
  write   writes the extended catalog: existing rows keep every value; MISSING form fields (evolution / hero ids and
          their metadata) are filled in; MISSING cards are appended. A backup of the file is written first.

Ids: CR global id = table class x 1e6 + row index over NAMED csv rows (a row with an empty Name continues the previous
entry): spells_characters 26, spells_buildings 27, spells_other 28, spells_evolved 13, spells_hero_form 203. Every id
the live reader reported in 4,534 live logs (raw_id_census.json, 167 ids) resolves under this rule.

  python gen_catalog.py check|write [--device DIR]
"""
import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from dump_tables import PREFIX, rows  # noqa: E402

DEVICE = HERE.parent / 'apktables/out/device_builds/20261012T221627332682Z-50188'
CATALOG = ROOT / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json'
BACKUP = CATALOG.with_name('live_card_catalog.pre_w9_20261020.json')
LIBG = CATALOG.with_name('live_card_catalog.pre_miniongiant_20261020.json')   # the untouched 15.535.29 libg catalog
IDENTITY = ('internal_name', 'type', 'elixir', 'rarity')      # fields the device overrides on a libg row
FIELDS = ('card_id', 'internal_name', 'display_name', 'type', 'elixir', 'rarity', 'unlock_arena', 'standard_1v1',
          'not_in_use', 'not_visible', 'summon_character', 'active_ability', 'active_ability_mana_cost',
          'active_ability_max_charges', 'active_ability_cast_time_ms', 'active_ability_trigger_delay_ms',
          'active_ability_cooldown_ms', 'hero_form', 'hero_form_id', 'hero_character', 'hero_active_ability',
          'hero_ability_mana_cost', 'hero_ability_max_charges', 'hero_ability_cast_time_ms',
          'hero_ability_trigger_delay_ms', 'hero_ability_cooldown_ms', 'evolution_form', 'evolution_form_id',
          'evolution_cycles')


def ids(tables):
    """{table: {Name: (global id, csv row dict)}}"""
    return {t: {d['Name']: (p * 1000000 + i, d) for i, d in enumerate(rows(tables / f'{t}.csv'))} for t, p in PREFIX.items()}


def hero_abilities(tables):
    """{hero form name: (hero character, ability name, ability dict)} from characters/hero_form/*.toml."""
    out = {}
    for spell in sorted((tables / 'characters/hero_form').glob('*_spell.toml')):
        s = tomllib.loads(spell.read_text(encoding='utf-8'))
        body = tomllib.loads(spell.with_name(spell.name.replace('_spell.toml', '.toml')).read_text(encoding='utf-8'))
        abil = body.get('ABILITY') or {}
        name = next(iter(abil)) if len(abil) == 1 else None      # every hero body toml declares exactly one
        for form, rec in (s.get('SPELL_HERO') or {}).items():
            char = (rec.get('SummonCharacter') or rec.get('LinkedChampionCharacter')
                    or (rec.get('SummonCharactersList') or [None])[0])
            out[form] = (char, name, abil.get(name) or {})
    return out


def derive(device_dir):
    """{card_id: catalog row} for every device card, from the device tables alone."""
    dev = json.loads((device_dir / 'cards.json').read_text(encoding='utf-8'))
    tables = device_dir / 'tables/csv_logic'
    idx = ids(tables)
    base_tables = ('spells_characters', 'spells_buildings', 'spells_other')
    evo = {e['form_of']: e for e in dev['evolutions']}
    hero = {h['form_of']: h for h in dev['hero_forms']}
    habil = hero_abilities(tables)
    out = {}
    for c in dev['cards']:
        t = next(t for t in base_tables if c['name'] in idx[t])
        cid, csv = idx[t][c['name']]
        ab = c.get('ability') or {}
        r = dict(card_id=cid, internal_name=c['name'], display_name=c['name'], type=c['kind'], elixir=c['elixir'],
                 rarity=c['rarity'], unlock_arena=csv.get('UnlockArena') or None,
                 not_in_use=csv.get('NotInUse', '').upper() == 'TRUE', not_visible=csv.get('NotVisible', '').upper() == 'TRUE',
                 summon_character=c.get('summon_character'),
                 active_ability=ab.get('name'), active_ability_mana_cost=ab.get('mana_cost'),
                 active_ability_max_charges=ab.get('max_charges'), active_ability_cast_time_ms=ab.get('cast_ms'),
                 active_ability_trigger_delay_ms=ab.get('trigger_delay_ms'), active_ability_cooldown_ms=ab.get('cooldown_ms'))
        e, h = evo.get(c['name']), hero.get(c['name'])
        r.update(evolution_form=e and e['name'], evolution_form_id=e and idx['spells_evolved'][e['name']][0],
                 evolution_cycles=e and e.get('evo_cycles'))
        hc, hn, ha = habil.get(h['name'], (None, None, {})) if h else (None, None, {})
        r.update(hero_form=h and h['name'], hero_form_id=h and idx['spells_hero_form'][h['name']][0], hero_character=hc,
                 hero_active_ability=hn, hero_ability_mana_cost=ha.get('ManaCost'), hero_ability_max_charges=ha.get('MaxCharges'),
                 hero_ability_cast_time_ms=ha.get('CastTime'), hero_ability_trigger_delay_ms=ha.get('TriggerDelay'),
                 hero_ability_cooldown_ms=ha.get('Cooldown'))
        out[cid] = r
    return out, dev


def standard(r):
    """standard_1v1 for an appended row: a visible, in-use card (the rule reproduces every existing row, see check)."""
    return not r['not_in_use'] and not r['not_visible']


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('check', 'write'))
    ap.add_argument('--device', type=Path, default=DEVICE)
    a = ap.parse_args(argv)
    doc = json.loads(CATALOG.read_text(encoding='utf-8'))
    have = {c['card_id']: c for c in doc['cards']}
    libg = {c['card_id'] for c in json.loads(LIBG.read_text(encoding='utf-8'))['cards']}
    dev, _ = derive(a.device)
    diffs, fill, add = [], [], []
    for cid, r in dev.items():
        old = have.get(cid)
        if old is not None and cid not in libg:
            # a hand-made stop-gap row (MinionGiant, 10-20 morning): replaced by the device-derived row
            print('stop-gap row replaced:', {k: (old.get(k), r.get(k)) for k in FIELDS if old.get(k) != dict(r, standard_1v1=standard(r)).get(k)})
            have[cid] = old = {k: dict(r, standard_1v1=standard(r))[k] for k in FIELDS}
        if old is None:
            add.append(dict(r, standard_1v1=standard(r)))
            continue
        for k in FIELDS:
            if k in ('display_name', 'standard_1v1'):
                continue
            if old.get(k) is None and r.get(k) is not None:
                fill.append((cid, old['internal_name'], k, r[k]))
            elif r.get(k) != old.get(k):
                diffs.append((cid, old['internal_name'], k, old.get(k), r.get(k)))
    rule = [(c['internal_name'], c['standard_1v1']) for cid, c in have.items() if cid in dev and standard(dev[cid]) != c['standard_1v1']]
    gone = sorted(c['internal_name'] for cid, c in have.items() if cid not in dev)
    print(f'device cards {len(dev)}; catalog rows {len(have)}; in catalog not on device: {gone}')
    print(f'standard_1v1 rule (visible and in use) disagrees with existing rows: {rule}')
    print(f'existing rows whose value differs from the device ({len(diffs)}):')
    for d in diffs:
        print('  ', d)
    print(f'missing fields to fill ({len(fill)}):')
    for f in fill:
        print('  ', f)
    print(f'cards to append ({len(add)}):', [(r['card_id'], r['internal_name'], r['standard_1v1']) for r in add])
    if a.mode == 'write':
        if not BACKUP.exists():
            shutil.copyfile(CATALOG, BACKUP)
        for cid, name, k, v in fill:
            have[cid][k] = v
        fixed = [d for d in diffs if d[2] in IDENTITY]
        for cid, name, k, old, new in fixed:
            have[cid][k] = new
        cards = [have[c['card_id']] for c in doc['cards']] + [{k: r[k] for k in FIELDS} for r in add]
        doc['cards'] = cards
        doc['counts'] = dict(mapped=len(cards), standard_1v1=sum(bool(c['standard_1v1']) for c in cards),
                             evolutions=sum(c.get('evolution_form_id') is not None for c in cards),
                             hero_forms=sum(c.get('hero_form_id') is not None for c in cards),
                             base_active_abilities=sum(c.get('active_ability') is not None for c in cards),
                             hero_active_abilities=sum(c.get('hero_active_ability') is not None for c in cards),
                             active_ability_forms=sum((c.get('active_ability') is not None) + (c.get('hero_active_ability') is not None)
                                                      for c in cards))
        doc['w9_extension'] = dict(date='2026-10-20', source='apktables device build 20261012T221627332682Z-50188 (tables of the '
                                   'installed 160402012 client + the 10-12 server update)', script='scratchpad/gauntlet/L74/identities/gen_catalog.py',
                                   filled=[f'{n}.{k}' for _, n, k, _ in fill], appended=[r['internal_name'] for r in add],
                                   corrected=[f'{n}.{k}: {o} -> {v}' for _, n, k, o, v in fixed],
                                   stopgap_replaced=sorted(have[c]['internal_name'] for c in have if c not in libg and c in dev),
                                   backup=BACKUP.name,
                                   note='libg rows keep every value except the identity fields (type / elixir / rarity / internal_name) '
                                        'the device contradicts; missing fields are filled from the device; evolution_cycles of a '
                                        'filled row is the device evo_cycles (the libg rows use a different count, see IDENTITIES.md); '
                                        'game_version is the original libg build')
        CATALOG.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
        print('wrote', CATALOG, 'backup', BACKUP)


if __name__ == '__main__':
    main(sys.argv[1:])

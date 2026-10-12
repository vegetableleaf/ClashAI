"""Exact, unit-preserving comparisons of normalized card evidence."""
from __future__ import annotations

import csv
import json
import re
import shlex
from collections import Counter
from pathlib import Path

ICEBOW = ['Xbow', 'Tesla', 'Knight', 'IceWizard', 'IceWizard_hero', 'Skeletons', 'Log', 'Tornado', 'Rocket']
CORE = ('hitpoints', 'damage', 'hit_speed_ms', 'range_milli', 'deploy_time_ms', 'speed', 'elixir')
STAT = set(CORE) | {'radius_milli', 'radius_y_milli', 'area_damage_radius_milli',
    'projectile_radius_milli', 'projectile_radius_y_milli', 'projectile_range_milli',
    'life_duration_ms', 'duration_seconds', 'buff_time_ms', 'damage_per_second',
    'hit_frequency_ms', 'crown_tower_damage_percent', 'shield_hitpoints',
    'spawn_character_deploy_time_ms'}
MISSING = {'status': 'missing'}


def cards_by_name(doc: dict) -> dict:
    return {c['name']: c for section in ('cards', 'evolutions', 'hero_forms') for c in doc.get(section, [])}


def projection(card: dict) -> dict:
    """Keep requested stats at every projectile/spell hop; absence is never zero."""
    out = {k: card.get(k, MISSING) for k in CORE}
    def walk(value, path=''):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('raw', 'tables', 'action_graph', 'ability', 'defaults_applied', 'spawner'):
                    continue
                p = f'{path}.{k}' if path else k
                if k == 'level_scaling':
                    for lk in ('rarity', 'level_count', 'relative_level', 'base_level', 'ladder_rarity', 'multiplier_percent_by_level'):
                        out[p + '.' + lk] = v.get(lk, MISSING)
                elif k in STAT:
                    out[p] = v
                elif isinstance(v, dict):
                    walk(v, p)
    walk(card)
    return out


def diff_values(before: dict, after: dict) -> list[dict]:
    return [dict(field=k, before=before.get(k, MISSING), after=after.get(k, MISSING))
            for k in sorted(before.keys() | after.keys()) if before.get(k, MISSING) != after.get(k, MISSING)]


def compare_cards(apk: dict, sim: dict, names: list[str]) -> list[dict]:
    a, b = cards_by_name(apk), cards_by_name(sim)
    result = []
    for n in names:
        if n not in a or n not in b:
            result.append(dict(card=n, status='missing_card', apk_present=n in a, sim_present=n in b, differences=[]))
            continue
        changes = diff_values(projection(b[n]), projection(a[n]))
        result.append(dict(card=n, status='mismatch' if changes else 'equal', differences=changes))
    return result


def slug(name: str) -> str:
    return re.sub('[^a-z0-9]', '', name.lower())


def base_slug(name: str) -> str:
    return re.sub(r'-(?:ev\d+|hero)$', '', name)


def opponent_counts(census: Path, pro2: Path, docs: list[dict], top: int = 60) -> dict:
    """Deck-presence counts, both seats. Keep pool and PRO2 counts separate too."""
    data = json.loads(census.read_text(encoding='utf-8'))
    aliases = {}
    for doc in docs:
        for c in doc.get('cards', []):
            for n in (c['name'], c.get('display_name', c['name'])):
                aliases[slug(n)] = c['name']
    for d in data['decks']:
        for s, e in zip(d['slugs'], d['engine'], strict=True):
            aliases[slug(base_slug(s))] = e.split('@')[0]
    aliases[slug('the-log')] = 'Log'
    counts, forms = Counter(), Counter()
    for d in data['decks']:
        weight = d.get('sides_census', d['sides'])
        if not isinstance(weight, int) or weight < 0:
            raise ValueError('invalid census weight')
        for s in set(d['slugs']):
            counts[base_slug(s)] += weight
            forms[s] += weight
    pc = Counter()
    rows = 0
    with pro2.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            rows += 1
            for field in ('team_deck', 'opponent_deck'):
                deck = row[field].split(',')
                if len(deck) != 8 or any(not s for s in deck):
                    raise ValueError(f'incomplete PRO2 deck row {rows}')
                for s in set(map(base_slug, deck)):
                    pc[s] += 1
    combined = counts + pc
    ranked = sorted(combined, key=lambda s: (-combined[s], s))[:top]
    selected = [dict(rank=i+1, slug=s, card=aliases.get(slug(s), s),
                     census=counts[s], pro2=pc[s], total=combined[s]) for i, s in enumerate(ranked)]
    variants = []
    for s in forms:
        if base_slug(s) not in ranked or s == base_slug(s):
            continue
        base = aliases.get(slug(base_slug(s)), base_slug(s))
        candidates = [c for doc in docs for sec in ('hero_forms', 'evolutions') for c in doc.get(sec, [])
                      if c.get('form_of') == base and ('hero' in s) == (sec == 'hero_forms')]
        name = candidates[0]['name'] if candidates else base + ('_hero' if s.endswith('-hero') else '_EV1')
        variants.append(dict(card=name, slug=s, count=forms[s]))
    return dict(top=selected, variants=sorted(variants, key=lambda x: (-x['count'], x['card'])),
                census_path=str(census), pro2_path=str(pro2), census_decks=len(data['decks']),
                census_selected_sides=sum(d.get('sides_census',d['sides']) for d in data['decks']),
                pro2_rows=rows, basis='Original census top-deck sides plus crawl-ready PRO2 both seats; overlapping sources cannot be ruled out. PRO2 forms unknown. Not a full-population opponent-only census.')


def check_levels(text: str, doc: dict) -> list[dict]:
    tokens = shlex.split(text, comments=True, posix=True)
    levels = {}
    for i, token in enumerate(tokens):
        if token not in ('--card-levels', '--card_levels') and not token.startswith(('--card-levels=', '--card_levels=')):
            continue
        vals = [token.split('=', 1)[1]] if '=' in token else []
        j = i + 1
        while j < len(tokens) and not tokens[j].startswith('--'):
            vals.append(tokens[j]); j += 1
        for val in vals:
            name, lev = val.split('=', 1)
            levels[name] = int(lev)
    cards = cards_by_name(doc)
    out = []
    for name, level in sorted(levels.items()):
        c = cards.get(name)
        r = doc.get('rarities', {}).get(c.get('rarity')) if c else None
        if not r or r.get('level_count') is None or r.get('relative_level') is None:
            out.append(dict(card=name, level=level, status='unknown_cap')); continue
        low, cap = r['relative_level']+1, r['relative_level']+r['level_count']
        out.append(dict(card=name, level=level, minimum=low, cap=cap,
                        status='ok' if low <= level <= cap else 'out_of_range'))
    return out


def build_changes(previous: dict | None, current: dict) -> dict:
    if previous is None:
        return dict(status='first_build', files=[], cards=[])
    old, new = previous['manifest']['files'], current['manifest']['files']
    files = [dict(path=p, before=old.get(p, {}).get('sha256'), after=new.get(p, {}).get('sha256'))
             for p in sorted(old.keys() | new.keys()) if old.get(p, {}).get('sha256') != new.get(p, {}).get('sha256')]
    a, b = previous.get('card_stats', {}), current.get('card_stats', {})
    cards = [dict(card=n, differences=diff_values(a.get(n, {}), b.get(n, {})))
             for n in sorted(a.keys() | b.keys()) if a.get(n) != b.get(n)]
    interpretation_changed = (previous.get('normalization', {}).get('sources') != current.get('normalization', {}).get('sources')
                              or previous.get('projection_version') != current.get('projection_version'))
    return dict(status='compared', previous=previous['manifest']['fingerprint'], files=files, cards=cards,
                interpretation_changed=interpretation_changed)

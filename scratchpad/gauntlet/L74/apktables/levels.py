"""Integer scaling from effective rarities and the stat object's own rarity."""
from fractions import Fraction

from compare import ICEBOW, cards_by_name, projection

OWNER_LEVELS = dict(Knight=16, Xbow=16, Rocket=16, Tornado=16, Tesla=16,
                    IceWizard=14, IceWizard_hero=14)
SCALED_FIELDS = {'damage', 'hitpoints', 'shield_hitpoints', 'damage_per_second'}


def scale_stat(base, rarity, level, rarities):
    """rarities' percentages are absolute from base, never compounded/rounded."""
    if base is None:
        return None
    if isinstance(level, bool) or not isinstance(level, int):
        raise ValueError('level must be an integer')
    ladder = rarities[rarity]
    index = level - (ladder['relative_level'] + 1)
    multipliers = ladder['multiplier_percent_by_level']
    if not 0 <= index < min(ladder['level_count'], len(multipliers)):
        raise ValueError(f'{rarity} level {level} outside multiplier ladder')
    return int(Fraction(str(base)) * multipliers[index] // 100)


def card_at_level(card, level, rarities):
    # Pinned normalization resolves the Rarity of the summoned unit or spell
    # damage carrier into ladder_rarity; card.rarity is the unlock rarity.
    scaling = card.get('level_scaling', {})
    rarity = scaling.get('ladder_rarity', card.get('rarity'))
    row = dict(card=card['name'], level=level, rarity=rarity, card_rarity=card.get('rarity'))
    if rarity not in rarities or 'multiplier_percent_by_level' not in rarities[rarity]:
        return dict(**row, status='unresolved_ladder', damage=None, hitpoints=None, stats={})
    try:
        # Validate even cards without a direct HP/damage value (e.g. Clone).
        scale_stat(0, rarity, level, rarities)
        stats = {}
        for field, value in projection(card).items():
            if field.rsplit('.', 1)[-1] not in SCALED_FIELDS or not isinstance(value, (int, float)):
                continue
            field_rarity = rarity
            for role, unit in card.get('related_units', {}).items():
                if field.startswith('related_units.' + role + '.'):
                    field_rarity = unit.get('rarity') or rarity
            stats[field] = scale_stat(value, field_rarity, level, rarities)
        multiplier = rarities[rarity]['multiplier_percent_by_level'][level-rarities[rarity]['relative_level']-1]
        return dict(**row, status='ok', multiplier_percent=multiplier,
                    damage=stats.get('damage'), hitpoints=stats.get('hitpoints'), stats=stats)
    except (ValueError, KeyError) as ex:
        return dict(**row, status='unresolved_ladder', error=str(ex), damage=None, hitpoints=None, stats={})


def level_report(doc, opponent_names):
    cards = cards_by_name(doc)
    def rows(names, own=False):
        return [dict(card_at_level(cards[n], OWNER_LEVELS.get(n, 15) if own else 15, doc['rarities']),
                     side='owner' if own else 'opponent') if n in cards else
                dict(card=n, side='owner' if own else 'opponent', level=OWNER_LEVELS.get(n, 15) if own else 15,
                     status='missing_card', damage=None, hitpoints=None, stats={}) for n in names]
    return rows(ICEBOW, True) + rows(opponent_names)


def sanity_table(rows):
    lines = ['|Side|Card|Level|Object rarity|Damage/hit|HP|DPS (if no hit damage)|',
             '|---|---|---:|---|---:|---:|---|']
    for r in rows:
        dps = '; '.join(f'{k}: {v}' for k, v in r['stats'].items() if k.endswith('damage_per_second'))
        val = lambda v: '\u2014' if v is None else str(v)
        lines.append(f"|{r['side']}|{r['card']}|{r['level']}|{r.get('rarity', '?')}|{val(r['damage'])}|{val(r['hitpoints'])}|{dps or (r['status'] if r['status'] != 'ok' else '')}|")
    return lines

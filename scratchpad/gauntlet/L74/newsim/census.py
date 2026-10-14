"""Public deck CSV -> deduplicated census; never fills missing cards or forms."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

from pipeline import vocab
from scratchpad.gauntlet.L74.weekend import archetypes as A
from scratchpad.gauntlet.L74.weekend.adaptive.driver import weighted_sixty


def key(name):
    return re.sub('[^a-z0-9]', '', name.lower())


def aliases(names):
    out = {}
    for name in sorted(names):
        out[key(name)] = name
        canonical = vocab.engine_key(name)
        if canonical:
            out[key(canonical)] = name
    return out


def deck(tokens, mapping):
    converted, missing = [], []
    for token in tokens:
        base, _, form = token.strip().partition('@')
        name = mapping.get(key(base))
        if name is None or form not in ('', 'base', 'evolution', 'hero'):
            missing.append(token)
        else:
            converted.append(name + ('@' + form if form not in ('', 'base') else ''))
    if missing or len(converted) != 8 or len({n.split('@')[0] for n in converted}) != 8:
        return None, missing
    return tuple(sorted(converted)), []


def load_humans(path, names):
    mapping = aliases(names)
    decks, unknown, seen = Counter(), Counter(), {}
    counts = Counter(rows=0, battles=0, duplicate_battles=0, accepted_sides=0, dropped_sides=0)
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        rows = csv.DictReader(f)
        required = {'replay_tag', 'team_deck', 'opponent_deck'}
        if not required <= set(rows.fieldnames or ()):
            raise ValueError(f'CSV needs columns {sorted(required)}')
        for row in rows:
            counts['rows'] += 1
            tag = row['replay_tag'].strip()
            pair = tuple(tuple(sorted(x.strip() for x in row[col].split(',')))
                         for col in ('team_deck', 'opponent_deck'))
            if not tag:
                raise ValueError('empty replay_tag')
            if tag in seen:
                if seen[tag] != pair:
                    raise ValueError(f'conflicting duplicate replay_tag: {tag}')
                counts['duplicate_battles'] += 1
                continue
            seen[tag] = pair
            counts['battles'] += 1
            for tokens in pair:
                result, missing = deck(tokens, mapping)
                unknown.update(missing)
                if result is None:
                    counts['dropped_sides'] += 1
                    continue
                counts['accepted_sides'] += 1
                decks[result] += 1
    counts['unique_decks'] = len(decks)
    counts['deduped_deck_sides'] = sum(decks.values()) - len(decks)
    return decks, dict(**counts, unloadable_card_occurrences=dict(unknown),
                       archetypes=archetype_counts(decks), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())


def archetype_counts(decks):
    out = {}
    for cards, sides in decks.items():
        r = out.setdefault(A.classify(cards), dict(decks=0, sides=0))
        r['decks'] += 1
        r['sides'] += sides
    return out


def combine(sources, human, names, allowed_keys=None, validate=None):
    mapping = aliases(names)
    counts, dropped, missing = Counter(human), Counter(), Counter()
    for data in sources:
        for row in data['decks']:
            cards, absent = deck(row['engine'], mapping)
            if cards is None:
                dropped['invalid_source_sides'] += row['sides']
                missing.update({n: row['sides'] for n in absent})
            else:
                counts[cards] += row['sides']
    for cards in list(counts):
        if allowed_keys is not None and any(vocab.base_key(vocab.engine_key(n)).replace('_', '-') not in allowed_keys for n in cards):
            dropped['policy_vocab_sides'] += counts.pop(cards)
        elif validate is not None:
            reason = validate(cards)
            if reason:
                dropped['runtime_rejected_sides'] += counts.pop(cards)
                dropped['runtime_rejected_decks'] += 1
    natural = archetype_counts(counts)
    rows = [dict(rank=i + 1, engine=list(d), sides=n) for i, (d, n) in enumerate(
        sorted(counts.items(), key=lambda x: (-x[1], x[0])))]
    weighted = weighted_sixty(dict(decks=rows))
    weighted['newsim_census'] = dict(natural_archetypes=natural, dropped=dict(dropped),
                                     unloadable_card_occurrences=dict(missing))
    return weighted


def prepare(out, csv_path, checkpoints):
    """Pod-only loadability check; pure loader above is exercised without SIM."""
    import torch
    from pipeline.royale_env import RoyaleSelfPlayEnv, UnsupportedDeck
    from pipeline.e1_eval import ICEBOW_ENGINE_DECK
    from scratchpad.gauntlet.L74.weekend.adaptive import driver as D
    env = RoyaleSelfPlayEnv(forms_mode='deck', hero_abilities=True, ability_policy='v2')
    human, report = load_humans(csv_path, env.ids)
    if report['battles'] != 1064:
        raise ValueError(f"expected owner's 1064 unique battles, got {report['battles']}")
    allowed = set.intersection(*(set(torch.load(p, map_location='cpu', weights_only=True)['card_vocab']) for p in checkpoints))
    checked = {}
    def validate(cards):
        if cards not in checked:
            try:
                env.reset(ICEBOW_ENGINE_DECK, cards, 0)
                checked[cards] = None
            except (UnsupportedDeck, KeyError) as e:
                checked[cards] = str(e)
        return checked[cards]
    sources = [json.loads((D.REPO / p).read_text()) for p in (D.EVO, D.LAD)]
    products = {'rl': sources, 'evo': sources[:1], 'lad': sources[1:]}
    for label, source in products.items():
        result = combine(source, human, env.ids, allowed, validate)
        (out / f'decks_{label}.json').write_text(json.dumps(result, indent=2)+'\n')
        report[label] = result['newsim_census'] | {'unfavourable_share': result['adaptive_unfavourable_share'],
                                                'weighted_unique_decks': len(result['decks'])}
    report['runtime_rejections'] = [{'deck': list(k), 'why': v} for k, v in checked.items() if v]
    (out / 'census_report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report

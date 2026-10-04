"""Decode --record-native entity tails without deck/cycle inference.

Only the explicit record_native marker enables this schema. Legacy column seven
is kind, never an entity id. This prepares exact unit forms; opponent-play and
full-cycle gen_v3.1 features still require the shared public observation path.
"""
from collections import Counter
from .obs_contract import catalog_card_form, entity_form


def tag_native_recording(rec, stats):
    if rec.get('record_native') is not True:
        raise ValueError('Exact native decoding requires record_native=true')
    out = dict(rec)
    counts = Counter()
    for source in ('frames', 'play_frames'):
        out[source] = []
        for frame in rec.get(source) or []:
            entities, forms, ids = [], [], []
            seen = set()
            for entity in frame.get('entities') or []:
                if isinstance(entity, dict):
                    if 'card_id' not in entity or 'entity_id' not in entity:
                        raise ValueError('Native dict missing card_id/entity_id')
                    cid, eid = int(entity['card_id']), int(entity['entity_id'])
                    form = entity_form(entity)
                    row = dict(entity)
                    side, hp, name = int(entity['side']), entity['hp'], entity.get('name', str(cid))
                else:
                    if len(entity) not in (8, 9):
                        raise ValueError('Native compact row must be 6 or 7 public columns plus card_id/entity_id')
                    cid, eid = int(entity[-2]), int(entity[-1])
                    row = list(entity[:-2])
                    side, hp, name = int(row[0]), row[4], row[3]
                    form = catalog_card_form(cid)[1]
                if cid >= 0 and hp > 0 and str(name) != '-1':
                    if eid < 0 or (side, eid) in seen:
                        raise ValueError('Missing or duplicate native entity identity')
                    seen.add((side, eid))
                    if catalog_card_form(cid)[0] is None:
                        # Unknown IDs must be audited, never inferred from hidden deck slots.
                        counts[f'native_unknown_card_id:{cid}'] += 1
                    counts[f'native_form_observations:{form}'] += 1
                entities.append(row)
                forms.append(form)
                ids.append(eid)
            out[source].append(dict(frame, entities=entities, unit_forms=forms, entity_ids=ids,
                                    native_card_ids=[int(e['card_id']) if isinstance(e, dict) else int(e[-2])
                                                     for e in frame.get('entities') or []]))
    for key, value in counts.items():
        stats[key] = stats.get(key, 0)+value
    return out

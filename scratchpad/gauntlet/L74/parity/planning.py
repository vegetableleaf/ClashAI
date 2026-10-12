"""Mechanics-only public replay planning. No engine imports, including in dry runs."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

OLD_HERO_REASON = 'unsupported_old_IceWizard_hero'


def own_logs(path, expected_sha256):
    """Rehydrate only own hand/next from the exact original, never hidden fields."""
    digest = hashlib.sha256()
    out = []
    with Path(path).open('rb') as f:
        for raw in f:
            digest.update(raw)
            if b'"decision"' not in raw[:80]:
                continue
            j = json.loads(raw)
            if j.get('event') != 'decision' or not j.get('public'):
                continue
            p = j['public']
            # These keys explicitly refer to the owner. Never accept generic next/hand.
            nxt = p.get('own_next_card')
            if isinstance(nxt, str):
                nxt = {'name': nxt}
            out.append(dict(tick=j['tick'], side=p['observer_side'],
                            hand=[{k: h[k] for k in ('name', 'form', 'deck_index') if k in h}
                                  for h in p.get('own_hand', [])],
                            next_card=({k: nxt[k] for k in ('name', 'form') if k in nxt}
                                       if isinstance(nxt, dict) else None)))
    if digest.hexdigest() != expected_sha256:
        raise ValueError('original_log_hash_mismatch')
    return out


def hydrate(source, live):
    result = deepcopy(source)
    if 'own_decisions' in result:
        return result
    try:
        result['own_decisions'] = own_logs(Path(live)/(source['match']+'.jsonl'), source['sha256'])
    except (OSError, ValueError) as e:
        result['mechanics_input_error'] = str(e)
    return result


def forced_deal(hand, next_card, deck):
    """A local hand/queue completion, NOT a claim about a match-long cycle.

    Empty hand slots survive; absent next stays epistemically unknown even though
    a deterministic queue completion is needed by the engine.
    """
    names = [c['name'] for c in deck]
    if len(set(names)) != len(names):
        raise ValueError('duplicate_own_deck_card')
    if len(hand) != 4:
        raise ValueError('logged_hand_not_four_slots')
    slots = [h.get('name') or None for h in hand]
    known = [n for n in slots if n is not None]
    if len(known) != len(set(known)) or any(n not in names for n in known):
        raise ValueError('invalid_logged_hand_cards')
    nxt = next_card.get('name') if next_card else None
    if nxt and (nxt not in names or nxt in known):
        raise ValueError('invalid_logged_next_card')
    queue = ([nxt] if nxt else []) + [n for n in names if n not in known and n != nxt]
    return dict(hand=slots, queue=queue, next_card=nxt,
                next_observed=nxt is not None, order=known+queue)


def plan(source, enabled=False):
    if not enabled:
        return dict(mode='strict_deal', blocks=list(source['blocks']), actions=[], decisions=[], skips=[])
    side = source['observer_side']
    blocks = [b for b in source['blocks'] if not b.startswith('public_deck_side_')]
    if source.get('mechanics_input_error'):
        blocks.append('own_log_unavailable:'+source['mechanics_input_error'])
    own_deck = source['decks'][str(side)]
    decisions, skips = [], []
    for i, dec in enumerate(source.get('own_decisions', [])):
        try:
            if dec['side'] != side:
                raise ValueError('observer_side_changed')
            deal = forced_deal(dec['hand'], dec.get('next_card'), own_deck)
            decisions.append(dict(tick=dec['tick'], row=i, **deal))
        except ValueError as e:
            skips.append(dict(kind='decision', row=i, tick=dec['tick'], reason=str(e)))
    if not decisions:
        blocks.append('no_usable_logged_own_hands')
    by_tick = {r['tick']: r for r in decisions}
    actions = []
    for i, play in enumerate(source['plays']):
        if play['side'] != side:
            actions.append(dict(play, row=i, mode='public_injection', slot=0))
            continue
        # Never repair with a future hand, including across an invalid latest row.
        latest = next((r for r in reversed(source.get('own_decisions', [])) if r['tick'] <= play['tick']), None)
        dec = by_tick.get(latest['tick']) if latest else None
        reason = 'no_logged_hand_before_play' if dec is None else 'own_play_absent_from_logged_hand'
        if dec is None or play['name'] not in dec['hand']:
            skips.append(dict(kind='play', row=i, tick=play['tick'], reason=reason)); continue
        actions.append(dict(play, row=i, mode='logged_hand', slot=dec['hand'].index(play['name']),
                            hand_tick=dec['tick'], hand=dec['hand'], queue=dec['queue']))
    # An injection roster is not an inferred enemy deck. No unplayed candidates.
    enemy = {c['name']: c for c in source['decks'][str(1-side)]}
    roster = []
    for name in dict.fromkeys(p['name'] for p in actions if p['side'] != side):
        if name not in enemy:
            blocks.append('observed_play_missing_metadata:'+name)
        else:
            roster.append(enemy[name])
    required_cards = own_deck+roster
    unsupported = (OLD_HERO_REASON if any(c['name']=='IceWizard' and c['form']==2 for c in required_cards) else None)
    return dict(mode='mechanics', blocks=blocks, decisions=decisions, actions=actions, skips=skips,
                own_deck=own_deck, opponent_roster=roster, old_unsupported=unsupported,
                counts=dict(decisions_total=len(source.get('own_decisions', [])), decisions_used=len(decisions),
                            next_card_observed=sum(d['next_observed'] for d in decisions),
                            plays_total=len(source['plays']), plays_used=len(actions),
                            own_plays=sum(a['side']==side for a in actions),
                            opponent_injections=sum(a['side']!=side for a in actions),
                            measurement_rows=len(source['frames'])))


def planning_report(cohort, enabled=False):
    rows = []
    for source in cohort:
        p = plan(source, enabled)
        rows.append(dict(match=source['match'], sha256=source['sha256'], usable=not p['blocks'],
                         blocks=p['blocks'], skips=p['skips'], counts=p.get('counts', {}),
                         old_unsupported=p.get('old_unsupported')))
    usable = [r for r in rows if r['usable']]
    return dict(status='PLANNING_ONLY_NO_SIM', mode='mechanics' if enabled else 'strict_deal',
                selected=len(rows), usable_matches=len(usable),
                expected_all_three_matches=sum(not r['old_unsupported'] for r in usable),
                expected_new_fork_only_matches=sum(bool(r['old_unsupported']) for r in usable),
                counts={k: sum(r['counts'].get(k, 0) for r in usable)
                        for k in sorted({k for r in rows for k in r['counts']})},
                skip_reasons=dict(Counter(b for r in rows for b in r['blocks']) +
                                  Counter(s['reason'] for r in rows for s in r['skips'])),
                expected_unsupported_reasons=dict(Counter(r['old_unsupported'] for r in usable if r['old_unsupported'])),
                matches=rows)

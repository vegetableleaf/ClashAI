"""Explicit, data-only SIM re-drive and fv5 build. Never imported by training.

record_native denotes the *encoding* expected by the unchanged dataset builder.
recording_origin is always 'royalesim' here; these are not native-game captures.
Unobserved deck forms require explicit acceptance of an exploratory base-form
reconstruction. Their uncertainty is retained on EVERY output row.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.pro2.convert import base, deck_type, phase, TYPES

CHAMPIONS = {'archer-queen', 'golden-knight', 'skeleton-king', 'mighty-miner',
             'monk', 'little-prince', 'goblinstein', 'boss-bandit'}


def card_catalog():
    from pipeline import vocab
    cards = json.loads((ROOT/'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json').read_text(encoding='utf-8'))['cards']
    return {vocab.base_key(vocab.engine_key(c['display_name'])).replace('_', '-'): c for c in cards
            if vocab.engine_key(c['display_name'])}


def snapshot(raw, catalog):
    """SIM public bodies -> existing compact schema; identities mapped by catalog.

    The two engines have different ID spaces. Do not pass SIM IDs as native IDs.
    Private player fields remain in label-side play frames only, as in the source
    corpus; the existing PublicObserver constructs opponent model features.
    """
    from pipeline import vocab
    from pipeline.obs_contract import entity_form
    def lookup(name, form=0):
        key = vocab.base_key(vocab.engine_key(name) or '').replace('_', '-')
        card = catalog.get(key)
        field = ('card_id', 'evolution_form_id', 'hero_form_id')[form]
        if card is None or card.get(field) is None:
            raise ValueError('unmapped_sim_public_identity:' + str(name) + ':' + str(form))
        return card[field]
    entities = [[e['side'], e['x'], e['y'], e['name'], e['hp'], e['max_hp'], e.get('kind', -1),
                 lookup(e['name'], entity_form(e)), e['entity_id']] for e in raw['entities']]
    objects = {}
    for src, dest in [('projectiles', 'projectiles'), ('effects', 'area_effects')]:
        objects[dest] = []
        for e in raw.get(src, []):
            # Tower attack projectiles have no card identity and are not card tokens.
            if str(e.get('name')) in ('-1', '-2', '65535'):
                continue
            row = dict(e, card_id=lookup(e['name']))
            objects[dest].append(row)
    return dict(tick=raw['tick'], entities=entities, public_objects=objects,
                elixir=[p['elixir_exact'] for p in raw['players']],
                towers=[[e['side'], e['type'], None, e['x'], e['y'], e['hp'], e['max_hp']]
                        for e in raw['episode']['crown_towers']],
                players=[dict(side=p['side'], hand=[h['name'] for h in p['hand']], next=p['next_deck_index'])
                         for p in raw['players']])


def drive(source, catalog):
    from pipeline.royale_env import RoyalePoolEnv, NOT_ENOUGH_ELIXIR
    decks = {}
    for s in (0, 1):
        decks[s] = []
        for token in source['decks'][str(s)]:
            if base(token) not in catalog:
                raise ValueError('unsupported_source_card:' + token)
            decks[s].append(dict(slug=base(token), name=catalog[base(token)]['display_name'],
                                 form='evolution' if token.endswith('-ev1') else 'hero' if token.endswith('-hero') else 'base'))
    cmds = {s: [dict(p, card=base(p['card'])) for p in source['plays'] if p['side'] == s] for s in (0, 1)}
    entry = dict(tag=source['tag'], our_side=0, ghost_side=1, our_deck=decks[0], ghost_deck=decks[1],
                 our_commands=cmds[0], ghost_commands=cmds[1])
    env = RoyalePoolEnv(warmup_ticks=0, forms_mode='deck', feature_version=5, seed=424242)
    try:
        env.reset(entry)
        if env.form_fallbacks:
            raise ValueError('unsupported_forms:' + str(env.form_fallbacks))
        # Both sides are driven here in source order, including observed ability presses.
        env._ghosts = []; env._gi = 0; env._pending = []
        suffix = {'base': '', 'hero': '@hero', 'evolution': '@evolution'}
        rec = dict(tag=source['tag'], recording_origin='royalesim', pro2_schema='sim-to-native-encoding-v1',
                   record_native=True, record_full=True, record_every=10, drive_abilities=True,
                   final_decks={str(s): [c['name']+suffix[c['form']] for c in decks[s]] for s in (0, 1)},
                   expected=source['expected'], frames=[], play_frames=[], log=[],
                   forms_unobserved=True, source_sha256=source['source_sha256'])
        commands = list(source['plays']); cursor = 0; pending = []
        # No frame-state synthesis: every frame comes from the running simulator.
        while env.tick <= 6200 and not env.terminated:
            raw = env.raw()
            due = []
            while cursor < len(commands) and commands[cursor]['tick'] <= env.tick:
                due.append(commands[cursor]); cursor += 1
            if env.tick % 10 == 0 or due or pending:
                rec['frames'].append(snapshot(raw, catalog))
            retry = []
            for p in pending + due:
                pf = snapshot(env.raw(), catalog)
                side = p['side']; slug = base(p['card'])
                event = dict(play_index=p['play_index'], tick=p['tick'], side=side, card=slug,
                             ability=p['ability'], x=None if p['x'] is None else round(p['x']*1000),
                             y=None if p['y'] is None else round(p['y']*1000),
                             engine_tick=env.tick, delay_ticks=env.tick-p['tick'],
                             hand_before=pf['players'][side]['hand'])
                if p['ability']:
                    # Only attribute a unique known champion/explicit hero button. Never
                    # guess a hidden hero form from deck composition or use a policy.
                    candidates = {env.card_id(c['name']) for c in decks[side]
                                  if c['slug'] in CHAMPIONS or c['form'] == 'hero'}
                    buttons = [(i, b[3]) for i, b in enumerate(env.core.state().players[side].abilities)
                               if b[3] in candidates]
                    if len(buttons) != 1:
                        result = dict(accepted=False, result_code='ability_identity_unavailable')
                    else:
                        button, cid = buttons[0]
                        event['card'] = next(c['slug'] for c in decks[side] if env.card_id(c['name']) == cid)
                        result = env.eng.act(side=side, ability_button=button)
                else:
                    index = next(i for i, c in enumerate(decks[side]) if c['slug'] == slug)
                    result = env.eng.act(side=side, deck_index=index, x=event['x'], y=event['y'])
                if result['result_code'] == NOT_ENOUGH_ELIXIR and env.tick-p['tick'] < 40:
                    retry.append(p); continue
                event.update(result)
                rec['log'].append(event)
                rec['play_frames'].append(dict(pf, play_index=p['play_index']))
            pending = retry
            env._advance_to(env.tick + 1)
        for p in pending + commands[cursor:]:
            rec['log'].append(dict(play_index=p['play_index'], side=p['side'], tick=p['tick'],
                                   card=base(p['card']), ability=p['ability'], accepted=False, result_code='terminal_before_play'))
        crowns = {str(p.team): int(p.crowns) for p in env.core.state().players}
        rec['final'] = dict(tick=env.tick, crowns=crowns)
        rejected = [e for e in rec['log'] if not e.get('accepted')]
        delayed = [e for e in rec['log'] if e.get('delay_ticks', 0)]
        rec['grade'] = dict(plays_total=len(commands), accepted=sum(e.get('accepted', False) for e in rec['log']),
                            rejected_by_reason=dict(Counter(str(e['result_code']) for e in rejected)),
                            crowns_match=crowns == source['expected']['crowns_by_side'],
                            terminal_vs_last_play_ticks=env.tick-max(p['tick'] for p in commands),
                            delayed_plays=len(delayed), first_command_divergence_tick=min(
                                (e['tick'] for e in rejected+delayed), default=None),
                            unit_missing=None, unit_out_of_place=None,
                            body_fidelity_status='unavailable_no_source_body_snapshots')
        # Reuse the existing public-recording fidelity oracle. Its native-only
        # export requirements remain errors/unavailable on this SIM adapter;
        # do not manufacture generation IDs or source timers to make it pass.
        from research.sandbox_tools.validate_public_capture import inspect
        rec['existing_capture_checks'] = inspect(rec)
        rec['grade']['existing_capture_errors'] = rec['existing_capture_checks']['errors']
        return rec
    finally:
        env.close()


def summarize_rows(npz, grades, output):
    import numpy as np
    with np.load(npz, allow_pickle=False) as z:
        tags, rep, ticks = z['tags'], z['rep'], z['tick']
        meta = json.loads(str(z['meta']))
        phase_counts = Counter(phase(int(t)) for t in ticks)
        deck_counts = Counter()
        for d in meta['decks']:
            deck_counts[deck_type(d['cards'])] += d['rows']
        command_bad = np.zeros(len(ticks), dtype=bool)
        crown_bad = np.zeros(len(ticks), dtype=bool)
        capture_bad = np.zeros(len(ticks), dtype=bool)
        for i, tag in enumerate(tags):
            grade = grades[str(tag)]
            cutoff = grade['first_command_divergence_tick']
            if cutoff is not None:
                command_bad |= (rep == i) & (ticks >= cutoff)
            if not grade['crowns_match']:
                crown_bad |= rep == i
            if grade.get('existing_capture_errors'):
                capture_bad |= rep == i
        np.savez_compressed(output/'row_fidelity.npz', command_diverged=command_bad,
                            outcome_diverged=crown_bad, capture_check_errors=capture_bad,
                            body_fidelity_known=np.zeros(len(ticks), bool),
                            forms_known=np.zeros(len(ticks), bool), rep=rep, tick=ticks, tags=tags)
        with npz.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        return dict(rows=len(ticks), row_deck_types={k: deck_counts[k] for k in TYPES},
                    row_phases={k: phase_counts[k] for k in ('1x', '2x', '3x', 'postgame')},
                    rows_after_command_divergence=int(command_bad.sum()), rows_with_outcome_divergence=int(crown_bad.sum()),
                    rows_with_existing_capture_check_errors=int(capture_bad.sum()),
                    rows_with_unavailable_body_fidelity=len(ticks), rows_with_unobserved_forms=len(ticks),
                    rows_unit_missing=None, rows_unit_out_of_place=None,
                    dataset_sha256=digest)


def stamp_dataset(npz, stamp):
    """Keep SIM origin inside the artifact, not only in a neighboring report."""
    import io
    import zipfile
    import numpy as np
    provenance = dict(recording_origin='royalesim', training_enabled=False,
                      native_equivalence_verified=False, deck_forms_observed=False,
                      unit_state_reference_available=False, runtime=stamp,
                      row_fidelity_sidecar='row_fidelity.npz')
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, np.asarray(json.dumps(provenance)), allow_pickle=False)
    with zipfile.ZipFile(npz, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pro2_provenance.npy', buffer.getvalue())
    path = npz.with_suffix('.json')
    meta = json.loads(path.read_text(encoding='utf-8'))
    meta['pro2_provenance'] = provenance
    path.write_text(json.dumps(meta, indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--allow-unknown-forms', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    if not a.allow_unknown_forms:
        ap.error('Pages do not establish deck forms. Exploratory SIM rows require --allow-unknown-forms; faithful native equivalence remains unproven.')
    if a.out.exists() and any(a.out.iterdir()):
        ap.error('output must be empty; use a new directory for a new run')
    a.out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    from pipeline.royale_runtime import activate
    stamp = activate()  # hard-fail before any simulation if the pinned runtime is unavailable
    catalog = card_catalog()
    corpus = a.out/'corpus'; corpus.mkdir()
    grades, failures, skipped = {}, [], []
    sources = [json.loads(line) for line in a.source.read_text(encoding='utf-8').splitlines() if line]
    if a.limit:
        sources = sources[:a.limit]
    for i, source in enumerate(sources):
        if source['blocks']:
            skipped.append(dict(tag=source['tag'], reasons=source['blocks'])); continue
        t0 = time.monotonic()
        try:
            rec = drive(source, catalog)
            grades[source['tag']] = rec['grade']
            (corpus/('replay_'+source['tag']+'.json')).write_text(json.dumps(rec), encoding='utf-8')
        except (ValueError, KeyError, StopIteration) as e:
            failures.append(dict(tag=source['tag'], reason=str(e), error_type=type(e).__name__))
        print(f'{i+1}/{len(sources)} driven={len(grades)} failed={len(failures)} seconds={time.monotonic()-t0:.1f}', flush=True)
    (a.out/'replay_fidelity.json').write_text(json.dumps(grades, indent=2), encoding='utf-8')
    (a.out/'failures.json').write_text(json.dumps(dict(failed=failures, skipped=skipped), indent=2), encoding='utf-8')
    if not grades:
        raise RuntimeError('No SIM recordings; see failures.json')
    # Same row constructor, identity encoding, public observer and fv5 settings.
    from pipeline.dataset_gen import build
    npz = a.out/'rows.npz'
    built = build([corpus], npz, feature_version=5, grid='lattice', workers=1,
                  wait_stride=40, play_window=20, shift_ticks=0, val_pct=10)
    stamp_dataset(npz, stamp)
    report = dict(status='EXPLORATORY_SIM_ROWS_UNVERIFIED_FOR_TRAINING', source_replays=len(sources),
                  driven=len(grades), failed=len(failures), skipped=len(skipped), runtime=stamp,
                  seconds=time.monotonic()-start, build=built, **summarize_rows(npz, grades, a.out))
    (a.out/'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (a.out/'SUMMARY.txt').write_text(json.dumps(report, indent=2)+'\nNo training/config changes. Bodies cannot be checked against pages; forms unobserved.\n', encoding='utf-8')
    (a.out/'DONE').write_text(report['status']+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""L73 hero dedupe: old (git fd3aad4) vs new dedupe_hero_bodies.
1. Named accuracy: every named frame-side group in named_groups.jsonl (explore.py): the kept 203000023 objects must be
   exactly the IceWizardHero objects. Groups with an unnamed (read-error) object are counted separately.
   Census groups are fed in BOTH list orders (as captured and reversed) since the rule must not depend on order.
2. Recorded live frames (same 1,095 as L73/live_wiring partA_probe.frames): frame-sides with >1 kept 203000023,
   split by whether the names (passive_v2 only) say they are >1 real heroes.
Writes measure.json. CPU only, no model."""
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[3]
sys.path.insert(0, str(WT))
from pipeline.reader_identity_aliases import dedupe_hero_bodies as new, HERO_ICE_WIZARD_ID as H  # noqa: E402

MAIN = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet')
FRAMES = [MAIN / 'L70/reader/sidebyside/re_v2xb.jsonl',
          MAIN / 'L72/improvement_loop/reader_character_identity/passive_v2_raw.jsonl']


def old_fn():
    src = subprocess.run(['git', '-C', str(WT), 'show', 'fd3aad4:pipeline/reader_identity_aliases.py'],
                         capture_output=True, text=True, check=True).stdout
    p = HERE / '_old_aliases.py'
    p.write_text(src, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_old_aliases', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    p.unlink()
    return m.dedupe_hero_bodies


def frames(path):                     # identical filter to L73/live_wiring/partA_probe.py:frames
    for line in open(path, encoding='utf-8'):
        try:
            f = json.loads(line)
        except ValueError:
            continue
        if f.get('battle_active') and f.get('coherent') and \
                len([p for p in f['players'] if any(i >= 0 for i in p['hand_deck_indices'])]) == 1:
            yield f


def kept(fn, ents):
    return [e for e in fn({'entities': ents})['entities'] if e.get('card_id') == H]


def main():
    old = old_fn()
    res = {}
    # 1. named accuracy
    acc = Counter()
    fails = []
    for line in open(HERE / 'named_groups.jsonl'):
        g = json.loads(line)
        objs = g['objs']
        unnamed = any(not e.get('native_name') for e in objs)
        truth = sorted(e['address'] for e in objs if e.get('native_name') == 'IceWizardHero')
        src = g['src'].split(':')[0]
        orders = [('as_listed', objs)] + ([('reversed', objs[::-1])] if src != 'passive_v2' else [])
        for oname, o in orders:
            for fname, fn in (('old', old), ('new', new)):
                got = sorted(e['address'] for e in kept(fn, [dict(e) for e in o]))
                for e in o:                           # per-object, all groups (unnamed objects have no truth)
                    n = e.get('native_name') or 'UNNAMED'
                    acc[f'{fname} objects {n} kept={e["address"] in got} ({oname})'] += 1
                key = f'{fname} {"with_unnamed" if unnamed else "all_named"} {src} {oname}'
                acc[key + ' groups'] += 1
                acc[key + ' exact'] += got == truth
                if fname == 'new' and not unnamed and got != truth:
                    fails.append(dict(src=g['src'], order=oname, truth=truth, got=got))
    res['named_accuracy'] = dict(sorted(acc.items()))
    res['new_named_failures'] = fails[:20]
    # 2. recorded live frames
    live = Counter()
    examples = []
    for path in FRAMES:
        for f in frames(path):
            live['frames'] += 1
            for fname, fn in (('raw', lambda fr: fr), ('old', old), ('new', new)):
                ents = fn(f)['entities']
                multi = []
                for side in (0, 1):
                    k = [e for e in ents if e.get('card_id') == H and e['side'] == side]
                    if len(k) > 1:
                        names = [e.get('native_name') for e in k]
                        multi.append(dict(side=side, n=len(k), names=names))
                if multi:
                    live[f'{fname} frames with >1 same-side 203000023'] += 1
                    real = all(m['names'].count('IceWizardHero') == m['n'] for m in multi)
                    if path.name.startswith('passive'):
                        live[f'{fname} of which named: all kept are IceWizardHero={real}'] += 1
                    if fname == 'new' and len(examples) < 3:
                        examples.append(dict(tick=f['game_tick'], objs=[
                            {k: e.get(k) for k in ('native_name', 'category', 'x', 'y', 'hp', 'max_hp',
                                                   'behavior_state_raw')}
                            for e in ents if e.get('card_id') == H]))
                if fname == 'raw':
                    live['raw beh0 203000023 objects'] += sum(e.get('card_id') == H and
                                                              e.get('behavior_state_raw') == 0 for e in ents)
    res['recorded_frames'] = dict(sorted(live.items()))
    res['new_multi_examples'] = examples
    (HERE / 'measure.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

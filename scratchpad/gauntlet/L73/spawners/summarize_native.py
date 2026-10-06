"""Aggregate native_audit_raw.json -> native_summary.json (+ printed tables)."""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
res = [r for r in json.load(open(os.path.join(HERE, 'native_audit_raw.json'))) if 'error' not in r]
FAMKEY = {'Witch': 'witch', 'DarkWitch': 'night_witch', 'FirespiritHut': 'furnace', 'WitchMother': 'mother_witch', 'Tombstone': 'tombstone',
          'GoblinHut': 'goblin_hut', 'BarbarianHut': 'barbarian_hut', 'Graveyard': 'graveyard', 'GoblinDrill': 'goblin_drill',
          'SkeletonBalloon': 'skeleton_barrel', 'GoblinGiant': 'goblin_giant', 'GoblinCage': 'goblin_cage', 'Phoenix': 'phoenix',
          'ElixirGolem': 'elixir_golem', 'Golem': 'golem', 'LavaHound': 'lava_hound'}
out = {'replays': len(res), 'control_replays': sum(r['control'] for r in res)}
# stage 2: census
cen = collections.Counter()
for r in res:
    for row in r['census']:
        cen[tuple(row[:-1])] += row[-1]
out['census'] = [dict(name=k[0], max_hp=k[1], fv4=k[2], fv5=k[3], fv5_reason=k[4], form=k[5], bodies=v) for k, v in sorted(cen.items())]
pres = collections.Counter(); neg = collections.Counter(); orph = collections.Counter(); ff = collections.Counter(); extra = collections.Counter()
reps = collections.Counter()
for r in res:
    for k, v in r['present_frames'].items(): pres[k.split('|')[1]] += v
    for k, v in r['neg_hp_frames'].items(): neg[k.split('|')[1]] += v
    for k, v in r['orphan_frames'].items(): orph[k] += v
    for k, v in r['famframes'].items(): ff[k] += v
    for k, v in r['extra_tokens'].items(): extra[k] += v
    for n in set(k.split('|')[1] for k in r['present_frames']): reps[n] += 1
out['board'] = {n: dict(replays_seen=reps[n], body_frames=pres[n], hp_le0_body_frames=neg[n],
                        frames_with_parent_class_tokens=ff[n], frames_parent_class_but_no_readable_parent=orph[n],
                        non_parent_tokens_labelled_parent=extra[n]) for n in sorted(pres)}
# stage 4: observer vs truth, by opponent family (a side can count toward several families)
fam = collections.defaultdict(lambda: collections.Counter()); ph_key = collections.defaultdict(collections.Counter)
mi_key = collections.defaultdict(collections.Counter); groups = collections.defaultdict(list)
for r in res:
    for s in r['sides']:
        labels = s['opp_fams'] or (['CONTROL'] if r['control'] else ['OTHER_SPAWNER_DECK_NO_FAMILY_ON_THIS_SIDE'])
        for f in labels:
            c = fam[f]; c['sides'] += 1; c['truth'] += s['truth']; c['inferred'] += s['inferred']
            c['phantom'] += len(s['phantom']); c['missed'] += len(s['missed'])
            c['phantom_elixir'] += s['phantom_elixir']; c['missed_elixir'] += s['missed_elixir']
            c['frames'] += s['frames']; c['opp_past_polluted_frames'] += s['opp_past_polluted_frames']
            c['sides_with_phantom'] += bool(s['phantom'])
            groups[f].append(s)
            for t, k in s['phantom']: ph_key[f][k] += 1
            for t, k in s['missed']: mi_key[f][k] += 1
tab = {}
for f, c in sorted(fam.items()):
    g = groups[f]; nfr = sum(s['frames'] for s in g)
    w = lambda key: sum(s[key] * s['frames'] for s in g) / max(1, nfr)
    tab[f] = dict(c, mae=w('mae'), bias=w('bias'), mae_without_phantoms=w('mae_cf'), bias_without_phantoms=w('bias_cf'),
                  own_card_phantoms=ph_key[f].get(FAMKEY.get(f, '?'), 0), phantom_by_card=dict(ph_key[f].most_common(6)),
                  missed_by_card=dict(mi_key[f].most_common(6)),
                  own_card_truth=None)
# true plays of the family card itself, to express phantoms per real play
for r in res:
    pass
out['observer'] = tab
json.dump(out, open(os.path.join(HERE, 'native_summary.json'), 'w'), indent=1)
print('replays', out['replays'], 'control', out['control_replays'])
print('\nBOARD (stage 2)')
for n, v in out['board'].items(): print(f'{n:16s}', v)
print('\nOBSERVER (stage 4)')
for f, v in tab.items():
    print(f"{f:44s} sides={v['sides']:4d} truth={v['truth']:6d} phantom={v['phantom']:5d} (own {v['own_card_phantoms']:4d}) ph_elix={v['phantom_elixir']:7.0f} "
          f"missed={v['missed']:5d} mae={v['mae']:.2f} bias={v['bias']:+.2f} | w/o phantoms mae={v['mae_without_phantoms']:.2f} bias={v['bias_without_phantoms']:+.2f} "
          f"polluted={v['opp_past_polluted_frames']/max(1,v['frames']):.3f}  ph={v['phantom_by_card']} miss={v['missed_by_card']}")
print('\nCENSUS')
for row in out['census']:
    if row['bodies'] >= 20: print(row)

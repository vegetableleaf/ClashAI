"""Stage 2 + 4 on native re-drive recordings (truth known): body identities the dataset builder sees, and the public
opponent observer's inferred plays vs the TRUE command log, with the elixir-estimate error phantom plays cause.
Read-only on pipeline; CPU; the true log/elixir are used only as the measuring stick, never as model input.
Usage: python native_audit.py [per_stratum=80]"""
import os, sys, json, random, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
FAMN = {'Witch': 'witch', 'DarkWitch': 'night_witch', 'FirespiritHut': 'furnace', 'WitchMother': 'mother_witch', 'Tombstone': 'tombstone',
        'GoblinHut': 'goblin_hut', 'BarbarianHut': 'barbarian_hut', 'Graveyard': 'graveyard', 'GoblinDrill': 'goblin_drill',
        'SkeletonBalloon': 'skeleton_barrel', 'GoblinGiant': 'goblin_giant', 'GoblinCage': 'goblin_cage', 'Phoenix': 'phoenix',
        'ElixirGolem': 'elixir_golem', 'Golem': 'golem', 'LavaHound': 'lava_hound'}
WINDOW = 150   # an inferred play matches a true play of the same card issued 5 ticks later .. 150 ticks earlier


def analyse(path):
    from pipeline import vocab
    from pipeline.native_recording import tag_native_recording
    from pipeline.public_observation import recording_observers
    from pipeline.opp_elixir_count import OppElixirCounter, card_cost
    from pipeline.body_identity import resolve
    inv = {v: k for k, v in vocab._ID.items()}
    r = json.load(open(path, encoding='utf-8'))
    rec = tag_native_recording(r, {})
    obs = recording_observers(rec)
    fams = {s: {n.split('@')[0] for n in r['final_decks'][str(s)] if n.split('@')[0] in FAMN} for s in (0, 1)}
    # --- stage 2 body census: distinct bodies per (side, name, max_hp), legacy (fv4) and corrected (fv5) class ---
    bodies = {}; neg = collections.Counter(); present = collections.Counter(); tokfam = []
    for f in rec['frames']:
        per = collections.Counter(); par = collections.Counter()
        for e, eid, form in zip(f['entities'], f['entity_ids'], f['unit_forms']):
            name = str(e[3])
            if name not in FAMN:
                continue
            key = (int(e[0]), name)
            present[key] += 1
            if e[4] <= 0:
                neg[key] += 1
            if e[5] > 0 and (key, eid) not in bodies:
                c4 = inv.get(vocab.engine_unit_id(name, float(e[5])))
                r5 = resolve(name, float(e[5]), form)
                bodies[(key, eid)] = (int(e[5]), c4, inv.get(r5.cls), r5.reason, int(form))
            if e[4] > 0:   # from_engine drops hp<=0 bodies, so only these reach the model
                per[(key, inv.get(vocab.engine_unit_id(name, float(e[5]))))] += 1
                if resolve(name, float(e[5]), form).reason == 'parent':
                    par[key] += 1
        tokfam.append((f['tick'], per, par))
    census = collections.Counter()
    for ((side, name), eid), v in bodies.items():
        census[(name,) + v] += 1
    # frames where the board shows a family-labelled token: how many of those tokens are not a readable parent
    orphan = collections.Counter(); extra = collections.Counter(); famframes = collections.Counter()
    for t, per, par in tokfam:
        for (key, c4), n in per.items():
            if c4 != FAMN[key[1]]:
                continue
            famframes[key[1]] += 1
            if par.get(key, 0) == 0:
                orphan[key[1]] += 1
            extra[key[1]] += n - min(n, par.get(key, 0))
    out = dict(path=path, fams={s: sorted(v) for s, v in fams.items()}, census=[list(k) + [v] for k, v in census.items()],
               neg_hp_frames={f'{s}|{n}': c for (s, n), c in neg.items()},
               present_frames={f'{s}|{n}': c for (s, n), c in present.items()},
               orphan_frames=dict(orphan), famframes=dict(famframes), extra_tokens=dict(extra), sides=[])
    # --- stage 4: public observer plays vs the true command log ---
    for o in obs:
        opp = 1 - o.side
        truth = sorted([(int(e['tick']), str(e['card']).replace('-', '_')) for e in r['log']
                        if int(e['side']) == opp and e.get('accepted') and e.get('card') and not e.get('ability')])
        used = [False] * len(truth); phantom = []
        plays = sorted(o.plays, key=lambda p: p['tick'])
        for p in plays:
            hit = next((i for i, (tt, tk) in enumerate(truth)
                        if not used[i] and tk == p['card'] and tt - 5 <= p['tick'] <= tt + WINDOW), None)
            if hit is None:
                phantom.append((p['tick'], p['card']))
            else:
                used[hit] = True
        missed = [t for t, u in zip(truth, used) if not u]
        ph = set(phantom)
        plays_cf = [p for p in plays if (p['tick'], p['card']) not in ph]
        cf = OppElixirCounter(); j = 0; err = []; cfe = []; pol = 0
        for f in rec['frames']:
            t = int(f['tick'])
            while j < len(plays_cf) and plays_cf[j]['tick'] < t:
                cf.play(plays_cf[j]['tick'], plays_cf[j]['card'], card_cost(plays_cf[j]['card'])); j += 1
            true = float(f['elixir'][opp])
            err.append(o.estimate_at(t) - true); cfe.append(cf.at(t) - true)
            last = [(p['tick'], p['card']) for p in plays if p['tick'] < t][-3:]
            pol += any(x in ph for x in last)
        n = max(1, len(err))
        out['sides'].append(dict(observer=o.side, opp_fams=sorted(fams[opp]), truth=len(truth), inferred=len(plays),
                                 phantom=phantom, missed=missed,
                                 phantom_elixir=sum(card_cost(k) or 0 for _, k in phantom),
                                 missed_elixir=sum(card_cost(k) or 0 for _, k in missed),
                                 frames=len(err), mae=sum(map(abs, err)) / n, bias=sum(err) / n,
                                 mae_cf=sum(map(abs, cfe)) / n, bias_cf=sum(cfe) / n, opp_past_polluted_frames=pol))
    return out


def safe(p):
    try:
        return analyse(p)
    except Exception as ex:
        return dict(path=p, error=f'{type(ex).__name__}: {ex}')


if __name__ == '__main__':
    import glob
    from multiprocessing import Pool
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    pf = json.load(open(os.path.join(HERE, 'prefilter.json')))
    rng = random.Random(20261006)
    strata = collections.defaultdict(list)
    for p, fam in pf.items():
        for f in fam:
            strata[f].append(p)
    pick = set()
    for f, ps in sorted(strata.items()):
        ps = sorted(ps); rng.shuffle(ps); pick.update(ps[:per])
    allp = sorted(glob.glob(ROOT + r'\scratchpad\gauntlet\ext\corpus_*\*_public_v1\j*\replay_*.json'))
    ctrl = [p for p in allp if p not in pf]; rng.shuffle(ctrl); ctrl = set(ctrl[:150])
    jobs = sorted(pick) + sorted(ctrl)
    print('jobs', len(jobs), 'control', len(ctrl), flush=True)
    res = []
    with Pool(3) as pool:
        for i, x in enumerate(pool.imap_unordered(safe, jobs, chunksize=4)):
            x['control'] = x['path'] in ctrl; res.append(x)
            if i % 200 == 0:
                print(i, flush=True)
    json.dump(res, open(os.path.join(HERE, 'native_audit_raw.json'), 'w'))
    print('errors', sum('error' in x for x in res))

"""Stage 1 + 4 on LIVE reader logs (scratchpad/gauntlet/L68/live_reader/live_play_*.jsonl). Read-only.

A. decision events (public audit = the actual model batch): per opponent spawner family, how many model tokens carry the
   PARENT class vs how many readable parent bodies the raw reader frame holds (resolved by catalog max_hp).
B. frame events (every coherent reader frame): replay pipeline.public_observation.PublicObserver offline exactly as
   live_gen.observe does for feature_version>=4; classify every inferred opponent play of a spawner card by whether its
   new-body group held a parent-HP body; measure the elixir error the child-only ("phantom") plays add, against the
   reader's opp_elixir_true_EVAL_ONLY (measuring stick only). Logged frames carry no projectiles/effects, so this replica
   misses body-less spells; the phantom effect is reported as the DIFFERENCE between the replica with and without phantoms.
"""
import os, sys, json, glob, collections
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
from pipeline import vocab
from pipeline.obs_contract import _catalog_names, catalog_card_form
from pipeline.body_identity import resolve
from pipeline.public_observation import PublicObserver
from pipeline.opp_elixir_count import OppElixirCounter, card_cost

FAM = {'witch', 'night_witch', 'furnace', 'mother_witch', 'tombstone', 'goblin_hut', 'barbarian_hut', 'graveyard', 'goblin_drill',
       'skeleton_barrel', 'goblin_giant', 'goblin_cage', 'phoenix', 'elixir_golem', 'golem', 'lava_hound', 'skeleton_king'}
inv = {v: k for k, v in vocab._ID.items()}


def key_of(cid):
    n = _catalog_names().get(int(cid))
    return (vocab.engine_key(n) if n else None), n


def role(cid, mhp):
    k, n = key_of(cid)
    if n is None or mhp is None or mhp <= 0:
        return 'unreadable'
    return resolve(n, float(mhp), catalog_card_form(int(cid))[1]).reason


def run(path):
    start = None; frames = []; decisions = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('{"event": "frame"') and not line.startswith('{"event": "decision"') and not line.startswith('{"event": "start"'):
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ev = d.get('event')
            if ev == 'start':
                start = d
            elif ev == 'frame':
                frames.append(d)
            elif ev == 'decision' and d.get('public'):
                decisions.append(d)
    if not frames:
        return None
    fv = (start or {}).get('feature_version')
    ck = os.path.basename(os.path.dirname(str((start or {}).get('ckpt'))))
    out = dict(log=os.path.basename(path), ckpt=ck, fv=fv, frames=len(frames), decisions=len(decisions))
    # ---- A: what the model batch holds ----
    tok = collections.Counter()
    for d in decisions:
        pub = d['public']; me = pub['observer_side']
        raw = collections.defaultdict(lambda: collections.Counter())
        for b in pub['raw_bodies']:
            if b['side'] == me or b['card_id'] < 0:
                continue
            k, _ = key_of(b['card_id'])
            if k in FAM:
                raw[k][role(b['card_id'], b['max_hp']) if b['hp'] > 0 else 'hp<=0'] += 1
        model = collections.Counter(inv.get(u['cls']) for u in pub['model_bodies'] if u['side'] == 1)
        for k, c in raw.items():
            tok[(k, 'decisions')] += 1
            tok[(k, 'raw_parent')] += c['parent'] + c['legacy']
            tok[(k, 'raw_child')] += c['child']
            tok[(k, 'raw_unknown')] += c['unknown_hp'] + c['ambiguous_hp'] + c['unreadable']
            tok[(k, 'raw_hp<=0')] += c['hp<=0']
            tok[(k, 'model_parent_tokens')] += model.get(k, 0)
            if model.get(k, 0) > c['parent'] + c['legacy']:
                tok[(k, 'decisions_with_extra_parent_tokens')] += 1
            if c['parent'] + c['legacy'] == 0 and model.get(k, 0) > 0:
                tok[(k, 'decisions_parent_tokens_without_parent')] += 1
        if len(pub['model_bodies']) > 64:
            tok[('all', 'decisions_over_64_units')] += 1
    out['model'] = {f'{k}|{m}': v for (k, m), v in tok.items()}
    # ---- B: public observer replica on every logged frame ----
    side = frames[0]['my_side']
    obs = PublicObserver(side)
    first_seen = {}; hp0 = collections.Counter(); trace = []
    for fr in frames:
        ents = []
        for e in fr.get('ents') or []:
            s, x, y, cid, hp, mhp, kind, addr = e[:8]
            ents.append(dict(side=s, x=x, y=y, card_id=cid, hp=hp, max_hp=mhp, kind=kind, address=addr))
            if s != side and cid >= 0:
                k, _ = key_of(cid)
                if k in FAM and (hp <= 0 or mhp <= 0):
                    hp0[(k, role(cid, mhp) if mhp > 0 else 'unreadable')] += 1
                first_seen.setdefault((k, addr), (fr['tick'], cid, mhp))
        obs.update({'game_tick': fr['tick'], 'entities': ents}, source='reader')
        trace.append((fr['tick'], fr.get('opp_elixir_true_EVAL_ONLY'), fr.get('opp_elixir_est')))
    plays = []
    for p in obs.plays:
        k = p['card']
        group = [(cid, mhp) for (kk, a), (t, cid, mhp) in first_seen.items() if kk == k and t == p['tick']]
        roles = collections.Counter(role(c, m) for c, m in group)
        cls = ('real' if roles['parent'] or roles['legacy'] else 'phantom' if roles['child'] and not (roles['unknown_hp'] or roles['ambiguous_hp']) else 'unknown')
        plays.append(dict(tick=p['tick'], card=k, cls=cls if k in FAM else 'nonfamily', roles=dict(roles)))
    out['plays'] = plays
    out['hp_le0_body_frames'] = {f'{k}|{r}': v for (k, r), v in hp0.items()}
    # elixir: replica with vs without phantom plays; logged estimate vs truth
    ph = {(p['tick'], p['card']) for p in plays if p['cls'] == 'phantom'}
    def replica(skip):
        c = OppElixirCounter(); seq = [p for p in obs.plays if (p['tick'], p['card']) not in skip]; j = 0; res = []
        for t, _, _ in trace:
            while j < len(seq) and seq[j]['tick'] < t:
                c.play(seq[j]['tick'], seq[j]['card'], card_cost(seq[j]['card'])); j += 1
            res.append(c.at(t))
        return res
    a, b = replica(set()), replica(ph)
    tr = [(t, true, est) for t, true, est in trace if true is not None]
    out['elixir'] = dict(n=len(tr), phantom_plays=len(ph), phantom_elixir=sum(card_cost(k) or 0 for _, k in ph),
                         replica_minus_cf_mean=sum(x - y for x, y in zip(a, b)) / max(1, len(a)),
                         replica_minus_cf_max=min((x - y for x, y in zip(a, b)), default=0),
                         logged_bias=sum(est - true for _, true, est in tr if est is not None) / max(1, len(tr)),
                         logged_mae=sum(abs(est - true) for _, true, est in tr if est is not None) / max(1, len(tr)),
                         replica_bias=sum(x - t[1] for x, t in zip(a, trace) if t[1] is not None) / max(1, len(tr)),
                         cf_bias=sum(x - t[1] for x, t in zip(b, trace) if t[1] is not None) / max(1, len(tr)))
    out['fams'] = sorted({p['card'] for p in plays if p['card'] in FAM})
    return out


if __name__ == '__main__':
    logs = sorted(glob.glob(ROOT + r'\scratchpad\gauntlet\L68\live_reader\live_play_*.jsonl'))
    res = []
    for p in logs:
        try:
            r = run(p)
        except Exception as ex:
            r = dict(log=os.path.basename(p), error=f'{type(ex).__name__}: {ex}')
        if r:
            res.append(r)
    json.dump(res, open(os.path.join(HERE, 'live_audit_raw.json'), 'w'), indent=0)
    print('logs', len(res), 'errors', sum('error' in r for r in res))

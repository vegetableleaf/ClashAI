"""SIM verification (c): one short scripted match per family through the pinned RoyaleSim runtime + royale_env raw(),
fv4 vs fv5 classes from obs_contract.from_engine, compared to the NATIVE expectation (native_verify.EXPECT, level 11).
Side 1 plays the family card (base, then its evo/hero form) as often as it can; side 0 fireballs/arrows its bodies and
drops defenders on bodies that cross, so death spawns (egg, brawler, hut/tombstone deaths, curses) happen.
CPU only. Run: research/ext/Royale/.venv/Scripts/python.exe sim_verify.py"""
import os, sys, json, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'; os.environ['OMP_NUM_THREADS'] = '2'
ROOT = r'C:\Users\benpe\ClashBot'; sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, ROOT + '/scratchpad/gauntlet/L73/identity_fix')
from pipeline.royale_runtime import activate
stamp = activate()
from pipeline.royale_env import RoyaleSelfPlayEnv, EMPTY_CARD
from pipeline import vocab
from pipeline.obs_contract import from_engine, load_deck
from native_verify import EXPECT

# SIM applies the client-16402 calibration (calibration.json CLIENT16402_VALUES): FireSpirits 84 -> 215, GoblinBrawler
# 438 -> 1121. Same roles as native's 217 / 1080.
EXPECT = {**EXPECT, ('FirespiritHut', 215): ('child', 'fire_spirit'), ('GoblinCage', 1121): ('child_no_class', 'goblin_cage'),
          ('WitchMother', 629): ('child', 'mother_witch_hog')}   # native: the same hog arrives as card_id -1 ('-1', 629)
FAMS = [('Witch', '', (3500, 26500)), ('Witch', '@evolution', (3500, 26500)), ('DarkWitch', '', (3500, 26500)),
        ('FirespiritHut', '', (6500, 22500)), ('FirespiritHut', '@evolution', (6500, 22500)),
        ('Tombstone', '', (6500, 22500)), ('Tombstone', '@hero', (6500, 22500)), ('GoblinHut', '', (6500, 22500)),
        ('BarbarianHut', '', (6500, 22500)), ('Graveyard', '', (3500, 6500)), ('GoblinDrill', '', (3500, 8500)),
        ('GoblinDrill', '@evolution', (3500, 8500)), ('SkeletonBalloon', '', (3500, 26500)),
        ('SkeletonBalloon', '@evolution', (3500, 26500)), ('GoblinGiant', '', (3500, 26500)),
        ('GoblinGiant', '@evolution', (3500, 26500)), ('GoblinCage', '', (6500, 22500)),
        ('GoblinCage', '@evolution', (6500, 22500)), ('Phoenix', '', (3500, 26500)), ('WitchMother', '', (3500, 26500)),
        ('SkeletonKing', '', (3500, 26500))]
FILL = ['Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Arrows']
DECK0 = ['Fireball', 'Arrows', 'Musketeer', 'Skeletons', 'Knight', 'Valkyrie', 'MiniPekka', 'Archer']
inv = vocab.UNIT_VOCAB
deck = load_deck('icebow')
out = dict(runtime=stamp, families={})
for card, sfx, (x, y) in FAMS:
    env = RoyaleSelfPlayEnv(feature_version=5, forms_mode='deck', hero_abilities=True, ability_policy='v2', tail_cap=2600)
    try:
        env.reset(DECK0, [card + sfx] + FILL, seed=3)
    except Exception as ex:
        out['families'][card + sfx] = dict(error=repr(ex)); print(card + sfx, 'ERROR', ex); continue
    loaded = env.loaded_forms.get(1, [0])[0]
    seen = {}; unnamed_sim = collections.Counter(); issued = 0
    for tick in range(env.tick, 2600, 5):
        raw = env.advance_to(tick)
        if env.done:
            break
        if tick % 10 == 0:
            if env.act(1, 0, x, y).get('accepted'):
                issued += 1
            else:
                for k in range(1, 8):    # cycle the rest from the back so the card (and its evo counter) comes round
                    if env.act(1, k, 9000, 30500).get('accepted'):
                        break
            mine = [e for e in raw['entities'] if e['side'] == 1 and e['name'] == card and e['hp'] > 0]
            if mine and tick % 40 == 0:
                tgt = max(mine, key=lambda e: e['max_hp'])
                for k in (0, 1):          # Fireball / Arrows on the heaviest body
                    if env.act(0, k, int(tgt['x']), int(tgt['y'])).get('accepted'):
                        break
                near = [e for e in mine if e['y'] < 17000]
                if near:
                    for k in range(2, 8):
                        if env.act(0, k, int(near[0]['x']), int(max(min(near[0]['y'] - 1500, 15000), 1500))).get('accepted'):
                            break
        for e in env.core.state().entities:     # bodies raw() drops (EMPTY_CARD): cursed hogs live here, if any
            if e.card_id == EMPTY_CARD and e.team == 1 and e.max_hp > 0 and e.max_hp not in (3052, 4824):
                unnamed_sim[int(e.max_hp)] += 1
        bs = {fv: from_engine(raw, 0, deck, unmapped=set(), feature_version=fv) for fv in (4, 5)}
        for fv in (4, 5):
            pool = collections.defaultdict(list)
            for e in raw['entities']:
                if e['side'] == 1 and (e['hp'] > 0 or e['max_hp'] <= 0):
                    pool[(round(e['x'] / 18000, 6), round(1 - e['y'] / 32000, 6))].append(e)
            for u in bs[fv].units:
                lst = pool.get((round(u.x, 6), round(u.y, 6)))
                if not lst:
                    continue
                e = lst.pop()
                if e['name'] != card:
                    continue
                key = (e['name'], int(e['max_hp']), int(e.get('status_flags', 0)))
                seen.setdefault(key, {}).setdefault(fv, collections.Counter())[(inv[u.cls], u.form, u.hp_frac is None)] += 1
    rows = []
    for (name, mhp, flags), by in sorted(seen.items()):
        role, want = EXPECT.get((name, mhp), ('?', '?'))
        rows.append(dict(name=name, max_hp=mhp, status_flags=flags, native_role=role, native_class=want,
                         fv4={f'{c}/f{f}{"/hp?" if h else ""}': n for (c, f, h), n in by.get(4, {}).items()},
                         fv5={f'{c}/f{f}{"/hp?" if h else ""}': n for (c, f, h), n in by.get(5, {}).items()},
                         fv5_matches_native=all(c == want and (f == 0 if role in ('child', 'child_no_class') else True)
                                                for (c, f, h) in by.get(5, {}))))
    out['families'][card + sfx] = dict(loaded_form=loaded, issued=issued, bodies=rows, unnamed_sim_bodies=dict(unnamed_sim))
    print(card + sfx, 'form', loaded, 'issued', issued, 'unnamed', dict(unnamed_sim))
    for r in rows:
        print('   ', r['max_hp'], 'flags', r['status_flags'], r['native_role'], r['native_class'], '| fv4', r['fv4'], '| fv5', r['fv5'],
              'OK' if r['fv5_matches_native'] else 'MISMATCH')
json.dump(out, open(os.path.join(HERE, 'sim_verify.json'), 'w'), indent=1, default=str)

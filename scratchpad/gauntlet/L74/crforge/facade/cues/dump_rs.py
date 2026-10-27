"""F1c-2 probe: RoyaleSim fin16 Battle.save() 'ents' value sets (what sim_unit_state.extract reads), one scripted match."""
import collections
import json
import sys

sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1c/cb"]
from pipeline.royale_runtime import activate  # noqa: E402
activate()
from pipeline import royale_heroiw as heroiw  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

ICE = ["Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]
OPP = ["BattleRam", "ElectroWizard", "AngryBarbarians", "Valkyrie", "Log", "Freeze", "GoblinCage", "Musketeer"]
rs = RustEngine(**heroiw.engine_options())
rs.set_command_delay_ticks(20)
ids = {c.name: c.card_id for c in rs.cards()}
rs.reset(3, MatchSetup(decks=[[ids[n] for n in ICE], [ids[n] for n in OPP]], shuffle=ShuffleMode.NONE,
                       forms=[[1, 2, 1, 0, 0, 0, 0, 0], [1, 0, 1, 0, 0, 0, 0, 0]]))
vals = collections.defaultdict(collections.Counter)
import random
rng = random.Random(1)
keys = None
for t in range(300):
    cmds = [DeployCommand(s, rng.randrange(4), 18 * rng.randrange(1500, 16500), 18 * (rng.randrange(1500, 14500) if s == 0 else rng.randrange(17500, 30500)))
            for s in (0, 1) if rng.random() < 0.15]
    rs.step(cmds, 10)
    sv = json.loads(rs._battle.save())
    if keys is None:
        keys = list(sv); print("save keys", keys); print("ents keys", list(sv["ents"]))
    E = sv["ents"]
    for k in ("jumping", "dash_state", "attack_phase", "hide", "charged", "kind"):
        for i, a in enumerate(E["alive"]):
            if a:
                vals[k][json.dumps(E[k][i])] += 1
    for i, a in enumerate(E["alive"]):
        if a:
            vals["speed"][E["speed"][i] if E["kind"][i] == "Troop" else "nt"] += 1
    for p in sv["projectiles"]:
        vals["proj_keys"][",".join(sorted(p))] += 1
        vals["proj_buff"][json.dumps(p["buff"])[:80]] += 1
    for s in sv["spells"]:
        vals["spell_motion"][json.dumps({k: sorted(v) for k, v in s["motion"].items()})] += 1
    if rs.state().game_over:
        break
for k, c in vals.items():
    print(k, dict(c.most_common(25)))
# state_json entity row value sets (second pass, same script)
rs.reset(3, MatchSetup(decks=[[ids[n] for n in ICE], [ids[n] for n in OPP]], shuffle=ShuffleMode.NONE,
                       forms=[[1, 2, 1, 0, 0, 0, 0, 0], [1, 0, 1, 0, 0, 0, 0, 0]]))
rng = random.Random(1)
F = sys.modules["royalesim"].ENTITY_FIELDS
rv = collections.defaultdict(collections.Counter)
for t in range(300):
    cmds = [DeployCommand(s, rng.randrange(4), 18 * rng.randrange(1500, 16500), 18 * (rng.randrange(1500, 14500) if s == 0 else rng.randrange(17500, 30500)))
            for s in (0, 1) if rng.random() < 0.15]
    rs.step(cmds, 10)
    st = json.loads(rs._battle.state_json())
    sv = json.loads(rs._battle.save())
    E = sv["ents"]
    slots = [i for i, a in enumerate(E["alive"]) if a]
    for i, row in zip(slots, st["entities"]):
        e = dict(zip(F, row))
        for k in ("stun_ticks", "knockback_ticks", "footprint", "attack_phase", "mount_uid", "charge", "ability_ticks", "status_flags", "deploy_ticks"):
            rv[k][json.dumps(e[k])[:40]] += 1
        rv["dest_set"][e["dest_x"] != -1] += 1
        rv["phase_pair"][(e["attack_phase"], E["attack_phase"][i])] += 1
        rv["stun_ms_vs_ticks"][(E["stun_ms"][i], e["stun_ticks"])] += 1
        rv["charge_vs"][(E["charge_progress"][i], e["charge"], E["charged"][i])] += 1
        for b in e["buffs"]:
            rv["buff"][b[0]] += 1
    if st.get("projectiles"):
        rv["proj_row_len"][len(st["projectiles"][0])] += 1
    if rs.state().game_over:
        break
for k, c in rv.items():
    print("ROW", k, dict(c.most_common(30)))

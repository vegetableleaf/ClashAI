"""F1c-1b diagnostic: the hero Barbarian Barrel's barbarian on crforge -- entity names, root card, ability row, the
champion slot's deploy index vs the body's, and whether PlayerCommands.championUnit names it.
usage: ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I abil_barblog.py
"""
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402

env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6, hero_abilities=True, ability_policy="v2")
env.reset(["BarbLog@hero", "Knight", "Log", "Skeletons", "Tesla", "Rocket", "Tornado", "Xbow"],
          ["Knight", "Valkyrie", "Musketeer", "Log", "HogRider", "Fireball", "Skeletons", "Cannon"], seed=1)
bl = env.ids["BarbLog"]
played = False
while env.tick < 2500 and not played:
    st = env.core.state()
    hand = st.players[0].hand
    if bl in hand and st.players[0].elixir_milli >= 2500:
        r = env.act(0, env.deck_ids[0].index(bl), 9000, 9000)
        print("barblog play", env.tick, r)
        played = r["accepted"]
    elif st.players[0].elixir_milli >= 4000:            # cycle: the cheapest other card at the back
        for c in hand:
            if c != bl and env.act(0, env.deck_ids[0].index(c), 9000, 3000)["accepted"]:
                break
    env.advance_to(env.tick + 5)
env.advance_to(env.tick + 60)
ENGINE = os.environ.get("ROYALE_ENGINE", "royalesim")
st = env.core.state()
print("rows", st.players[0].abilities, "opts", env.ability_options(0))
types = env.core.unit_types()
print("bodies", [(e.uid, e.status_flags, types[e.unit_type]) for e in st.entities if e.team == 0 and e.card_id == bl])
if ENGINE == "crforge":
    cf = env.core._cf

    def field(o, name):
        f = o.getClass().getDeclaredField(name)
        f.setAccessible(True)
        return f.get(o)

    std, cmds = field(cf.s, "std"), field(cf.s, "cmds")
    _rc = cf.getClass().getDeclaredMethod("rootCard", cf.getClass().getClassLoader().loadClass("java.lang.String"))
    _rc.setAccessible(True)

    def root(nm):
        return _rc.invoke(cf, nm)

    for e in std.getBattle().getHolder().entities():
        if hasattr(e, "getData") and "Barb" in str(e.getData().name()):
            nm = str(e.name())
            ab = e.getData().ability()
            print("entity", nm, str(e.getData().name()), "root", root(nm), "ability",
                  None if ab is None else str(ab.name()), "deployIndex",
                  e.getDeployIndex() if hasattr(e, "getDeployIndex") else None)
    buttons = list(field(cf.s, "buttons")[0])
    king = std.getWorld().kingTower(0)
    for b in buttons:
        ctl = king.championSlot(int(b))
        print("slot", b, "champion", str(ctl.getChampion().name()), "deployIndex", ctl.getDeployIndex(),
              "deckIndex", ctl.getDeckIndex(), "live", [str(u.name()) for u in ctl.champions()])
    print("championUnit", cmds.championUnit(0, int(buttons[0]) - 1))
    for p in std.getPlays():
        if p.side() == 0:
            print("play", p, [str(u.name()) for u in p.units()])

# the press and what follows on the barbarian (both engines): buffs, status flags, hp, position, per 5 ticks
opts = env.ability_options(0)
if opts:
    b, cid, uid = opts[0]["cmd"]
    t0 = env.tick
    print("press", t0, env.eng.act(side=0, ability_button=b))
    for k in range(5, 81, 5):
        env.advance_to(t0 + k)
        st = env.core.state()
        e = next((e for e in st.entities if e.uid == uid), None)
        print("k", k, None if e is None else (e.status_flags, e.hp, e.x // 18, e.y // 18, [x[0] for x in e.buffs]),
              "elixir", st.players[0].elixir_milli, "row", st.players[0].abilities,
              "spells", [(s.card_id, s.motion) for s in st.spells if s.team == 0])

"""F1c-1: hero ability presses, RoyaleSim fin16 vs the crforge facade (same script, ROYALE_ENGINE picks the engine).
Per census match (ours: icebow with hero Ice Wizard; the opponent's heroes / champions too), random affordable plays;
at each tick a side has a ready button (``env.ability_options``: the env's own readiness scan incl.
heroiw.controller_body) it is pressed with probability --p through ``env.eng.act`` (the env's press path). Each
accepted press is then watched tick by tick for its effect: the side's elixir drop, the button row (available / spent /
cooldown), the hero's STATUS_ABILITY_ACTIVE bit, new bodies / spell rows / buffs on any entity named after the hero.
``--dump``: the first press per match also writes every tick's hero entity + button rows (+ debug_units) to stdout.
usage: [ROYALE_ENGINE=crforge] ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I abil_probe.py --n 20
"""
import argparse
import json
import os
import random
import sys
from collections import Counter

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from royalegym.protocol import HAND_SIZE, DeployCommand  # noqa: E402

SFX = {0: "", 1: "@evolution", 2: "@hero"}


def census():
    """accept_f1.census: the S3 census deck pairs (ours, forms, theirs, forms)."""
    out = []
    for line in open("/workspace/cfspeed/decks.tsv").read().splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[1].split(","), [int(v) for v in f[2].split(",")], f[3].split(","),
                        [int(v) for v in f[4].split(",")]))
    return out

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--p", type=float, default=0.2)
ap.add_argument("--watch", type=int, default=60)
ap.add_argument("--dump", action="store_true")
a = ap.parse_args()
ENGINE = os.environ.get("ROYALE_ENGINE", "royalesim")


def hero_row(e, types):
    return dict(uid=e.uid, team=e.team, card=e.card_id, flags=e.status_flags, hp=e.hp,
                type=types[e.unit_type] if types and 0 <= e.unit_type < len(types) else None,
                buffs=[b[0] for b in e.buffs])


def signals(env, st, side, cid, uid, types):
    """What a press can change, as a set of strings (compared with the set at the press)."""
    out = set()
    me = st.players[side]
    for b, r in enumerate(me.abilities):
        if r[3] == cid:
            out.add(f"row{b}:{list(r[:5])}")
    for e in st.entities:
        t = types[e.unit_type] if types and 0 <= e.unit_type < len(types) else str(e.unit_type)
        if e.uid == uid:
            out.add(f"hero_active:{bool(e.status_flags >= 0 and e.status_flags & 128)}")
        if e.card_id == cid and e.team == side and e.uid != uid:
            out.add(f"body:{t}:{e.uid}")
        for bn, _ in e.buffs:
            if "Hero" in bn and env.names[cid] in bn and "Slow" not in bn:   # not the hero's shot slow
                out.add(f"buff:{bn}:{e.uid}")
    for s in st.spells:
        if s.card_id == cid and s.team == side:
            out.add(f"spell:{s.motion}")
    return out


pairs = census()
tot = Counter()
onsets = Counter()       # (card, signal kind) -> Counter(offset)
offs = {}
for i in range(a.n):
    pair = pairs[i % len(pairs)]
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6, hero_abilities=True,
                            ability_policy="v2")
    env.reset([n + SFX[f] for n, f in zip(pair[0], pair[1])], [n + SFX[f] for n, f in zip(pair[2], pair[3])], seed=i)
    rng, dumped = random.Random(1000 + i), set()
    if i == 0 or a.dump:
        st = env.core.state()
        print(json.dumps(dict(match=i, engine=ENGINE, tick=st.tick, hero_ids={s: [env.names[c] for c in env._hero_ids[s]]
                                                                              for s in (0, 1)},
                              champ_ids={s: [env.names[c] for c in env._champ_ids[s]] for s in (0, 1)},
                              rows0=[p.abilities for p in st.players])), flush=True)
    while not env.done:
        side = rng.randrange(2)
        env.act(side, rng.randrange(8), rng.randrange(2000, 16000), 6000 if side == 0 else 26000)
        for _ in range(10):
            if env.done:
                break
            st_c, types_c = env.core.state(), env.core.unit_types()
            for e in st_c.entities:
                if e.card_id in env._hero_ids[e.team]:
                    hero = int(e.status_flags >= 0 and bool(e.status_flags & 16))
                    tot[f"seen_{env.names[e.card_id]}_{types_c[e.unit_type]}_hero{hero}"] += 1
            for p_ in st_c.players:
                for r_ in p_.abilities:
                    tot[f"row_{env.names.get(r_[3], r_[3])}_avail{r_[0]}_spent{r_[1]}"] += 1
            for s in (0, 1):
                opts = env.ability_options(s)
                tot["ready_ticks"] += bool(opts)
                if not opts or rng.random() >= a.p:
                    continue
                button, cid, uid = opts[0]["cmd"]
                types = env.core.unit_types()
                st0 = env.core.state()
                base = signals(env, st0, s, cid, uid, types)
                e0 = st0.players[s].elixir_milli
                t0 = env.tick
                r = env.eng.act(side=s, ability_button=button)
                tot[f"press_{env.names[cid]}_{'ok' if r['accepted'] else r['result_code']}"] += 1
                if not r["accepted"]:
                    continue
                dump = (env.names[cid], s) not in dumped and (a.dump or i == 0)
                dumped.add((env.names[cid], s))
                first, prev = {}, e0
                for k in range(1, a.watch + 1):
                    env.advance_to(t0 + k)
                    if env.done:
                        break
                    st = env.core.state()
                    sig = signals(env, st, s, cid, uid, env.core.unit_types())
                    if st.players[s].elixir_milli < prev - 500 and "elixir" not in first:
                        first["elixir"] = k            # a one-tick drop (regen is +18..+54 milli a tick)
                    prev = st.players[s].elixir_milli
                    if k <= 21:                        # a second press while the first waits to run
                        tot[f"repress_k{'le20' if k <= 20 else '21'}_"
                            f"{env.core.check_deploy(DeployCommand(s, HAND_SIZE + button, 0, 0))}"] += 1
                    for x in sig - base:
                        kind = x.split(":")[0]
                        first.setdefault(kind, k)
                    if dump:
                        hero = [hero_row(e, env.core.unit_types()) for e in st.entities if e.uid == uid]
                        du = None
                        if hasattr(env.core._battle, "debug_units"):
                            du = [list(r)[:2] for r in env.core._battle.debug_units() if r[0] == uid]
                        print(json.dumps(dict(match=i, card=env.names[cid], side=s, k=k, tick=env.tick, hero=hero,
                                              rows=st.players[s].abilities, pending=st.players[s].pending,
                                              elixir=st.players[s].elixir_milli, new=sorted(sig - base), du=du)),
                              flush=True)
                for kind, k in first.items():
                    offs.setdefault(f"{env.names[cid]}:{kind}", Counter())[k] += 1
            env.advance_to(env.tick + 1)
print(json.dumps(dict(engine=ENGINE, matches=a.n, totals=dict(tot),
                      onset={k: dict(sorted(v.items())) for k, v in sorted(offs.items())})), flush=True)

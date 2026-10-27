"""F1c-1: ability button ORDER on two-button decks (two heroes, or a hero + a champion), per engine: the deck as the env
loaded it (deal order, forms) and PlayerState.abilities' card per button at the first state. Census pairs, both sides.
usage: [ROYALE_ENGINE=crforge] ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I abil_order.py
"""
import json
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402

SFX = {0: "", 1: "@evolution", 2: "@hero"}


def census():
    """accept_f1.census: the S3 census deck pairs (ours, forms, theirs, forms)."""
    return [(f[1].split(","), [int(v) for v in f[2].split(",")], f[3].split(","), [int(v) for v in f[4].split(",")])
            for f in (ln.split("\t") for ln in open("/workspace/cfspeed/decks.tsv").read().splitlines()
                      if ln.strip() and not ln.startswith("#"))]


out = []
for i, pair in enumerate(census()):
    if sum(f == 2 for f in pair[3]) + sum(pair[2].count(c) for c in (
            "ArcherQueen", "GoldenKnight", "SkeletonKing", "MightyMiner", "Monk", "LittlePrince", "BossBandit",
            "Goblinstein")) < 2:
        continue
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6, hero_abilities=True,
                            ability_policy="v2")
    for seed in (i, i + 1000):
        env.reset([n + SFX[f] for n, f in zip(pair[0], pair[1])], [n + SFX[f] for n, f in zip(pair[2], pair[3])],
                  seed=seed)
        st = env.core.state()
        out.append(dict(i=i, seed=seed, deck=[f"{env.names[c]}:{f}" for c, f in zip(env.deck_ids[1], env.loaded_forms[1])],
                        dealt=[f"{env.names[c]}:{f}" for c, f in zip(getattr(st.players[1], "deck", []) or [], getattr(st.players[1], "forms", []) or [])],
                        buttons=[env.names.get(r[3], r[3]) for r in st.players[1].abilities]))
print(json.dumps(dict(engine=os.environ.get("ROYALE_ENGINE", "royalesim"), rows=out)))

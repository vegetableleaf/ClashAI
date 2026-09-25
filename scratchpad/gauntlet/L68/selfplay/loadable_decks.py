"""L68 T12a: which census decks can the self-play env actually play? -> loadable_decks.json

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/selfplay/loadable_decks.py [--top 1000]

Stage 1 (icebow venv, polars): rank base decks by deck-sides exactly as generalist/deck_census.py does (the 52 local
IL_Replay parts, forms -ev1/-hero stripped). Stage 2 (re-runs this file in the Royale venv, which has royalegym but no
polars): ``RoyaleSelfPlayEnv().reset(deck, icebow, seed=0)`` for each of the top-N plus icebow and the owner's
live-account starter deck; loadable = no UnsupportedDeck. RoyaleAPI slugs -> engine names via royalesim_cards.json
(name / display_name) and the ghost pool's (slug, name) pairs; a slug with no engine spelling is passed as-is, so
reset refuses it.
"""
import glob
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[3]
ROYALE_PY = REPO / "research/ext/Royale/.venv/Scripts/python.exe"
FORM = re.compile(r"-(ev\d+|hero)$")
slug = (lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-"))
ICEBOW = ["Tornado", "Tesla", "IceWizard", "Xbow", "Rocket", "Knight", "Log", "Skeletons"]
STARTER = ["Knight", "GoblinHut", "Goblins", "Arrows", "Fireball", "Giant", "Musketeer", "MiniPekka"]


def slug_to_engine() -> dict:
    m = {}
    for c in json.load(open(HERE.parent / "generalist/royalesim_cards.json")):
        m[slug(c["name"])] = c["name"]
        m[slug(c.get("display_name") or c["name"])] = c["name"]
    for line in open(REPO / "icebow/data/ghost_pool/pool_env_v1.jsonl"):
        e = json.loads(line)
        for it in e["icebow_deck"] + e["ghost_deck"]:
            m.setdefault(it["slug"], it["name"])
    return m


def census():
    import polars as pl
    sides = Counter()
    for f in sorted(glob.glob(str(REPO / "scratchpad/gauntlet/L67/hf/replays/*.parquet"))):
        for pj in pl.read_parquet(f, columns=["payload_json"])["payload_json"]:
            b = json.loads(pj)["battle"]
            for who in ("team", "opponent"):
                for p in b[who]["players"]:
                    sides[tuple(sorted(FORM.sub("", c["card_key"]) for c in p["deck"]))] += 1
    return sides


def reset_all(job: Path) -> None:
    """Stage 2 (Royale venv): add ``loadable`` / ``blocker`` to every deck in the job file, in place."""
    sys.path.insert(0, str(REPO))
    from pipeline.royale_env import RoyaleSelfPlayEnv, UnsupportedDeck
    d = json.load(open(job))
    env = RoyaleSelfPlayEnv()
    t0 = time.perf_counter()
    for x in d["decks"]:
        try:
            env.reset(x["engine"], ICEBOW, seed=0)
            x["loadable"], x["blocker"] = True, None
        except UnsupportedDeck as u:
            x["loadable"], x["blocker"] = False, str(u)
    d["reset_seconds"] = round(time.perf_counter() - t0, 2)
    d["resets_per_s"] = round(len(d["decks"]) / max(d["reset_seconds"], 1e-9), 1)
    json.dump(d, open(job, "w"))


def main(top: int) -> None:
    t0 = time.perf_counter()
    sides = census()
    total = sum(sides.values())
    m = slug_to_engine()
    decks = [{"rank": r, "sides": n, "slugs": list(k), "engine": [m.get(s, s) for s in k]}
             for r, (k, n) in enumerate(sides.most_common(top), 1)]
    decks += [{"rank": None, "sides": None, "name": "icebow", "engine": ICEBOW},
              {"rank": None, "sides": None, "name": "starter", "engine": STARTER}]
    job = HERE / "_reset_job.json"
    json.dump({"decks": decks}, open(job, "w"))
    subprocess.run([str(ROYALE_PY), __file__, "--reset", str(job)], check=True)
    d = json.load(open(job))
    job.unlink()
    ranked = [x for x in d["decks"] if x["rank"]]
    ok = [x for x in ranked if x["loadable"]]
    blockers = Counter(x["blocker"] for x in ranked if not x["loadable"])
    out = {
        "top_n": top, "census_deck_sides": total, "census_distinct_base_decks": len(sides),
        "loadable_in_top_n": len(ok),
        "loadable_sides_share_of_census": round(sum(x["sides"] for x in ok) / total, 4),
        "top_n_sides_share_of_census": round(sum(x["sides"] for x in ranked) / total, 4),
        "top_blockers": blockers.most_common(15),
        "resets_per_s": d["resets_per_s"], "wall_s": round(time.perf_counter() - t0, 1),
        "extra": [{k: x[k] for k in ("name", "engine", "loadable", "blocker")} for x in d["decks"] if not x["rank"]],
        "decks": [{k: x[k] for k in ("rank", "sides", "engine", "slugs")} for x in ok],
    }
    json.dump(out, open(HERE / "loadable_decks.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "decks"}, indent=1))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--reset"]:
        reset_all(Path(sys.argv[2]))
    else:
        main(int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 1000)

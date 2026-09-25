"""Which engine entity `kind` values mark a FRESH card deploy vs a spawned / long-lived body?

Source: corpus_v6 play_frames (the only engine frames that carry `kind`, 7th entity field), both decks.
For every non-tower entity in a play_frame at tick t, it is 'fresh' if the SAME side had an accepted log play
of the same base card in [t-40, t) (2 s), else 'old'. A spawned body carrying its parent's name right after
its parent was played would be mislabelled 'fresh' -- so spawner parents are also broken out by name.
Output: counts of kind by (fresh/old), and by name for known spawners."""
import collections, glob, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import vocab

by = collections.Counter(); by_age = collections.defaultdict(collections.Counter); by_name = collections.defaultdict(collections.Counter)
SPAWNERS = {"witch", "night_witch", "goblin_hut", "tombstone", "furnace", "barbarian_hut", "golem", "lava_hound",
            "elixir_golem", "graveyard", "goblin_drill", "mother_witch", "skeleton_barrel", "goblin_barrel",
            "barbarian_barrel", "royal_delivery", "phoenix", "goblin_giant", "goblinstein", "skeleton_king"}
n = 0
for deck in ("icebow", "hogeq"):
    for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json")))[:600]:
        d = json.load(open(f))
        plays = [(e["tick"], e["side"], e["card"].replace("-", "_")) for e in d["log"] if e.get("accepted")]
        for pf in d.get("play_frames", []):
            t = pf["tick"]
            for e in pf["entities"]:
                if len(e) < 7 or str(e[3]) == "-1":
                    continue
                side, name, kind = e[0], str(e[3]), e[6]
                k = vocab.base_key(vocab.engine_key(name) or name)
                ages = [t - pt for pt, ps, pc in plays if ps == side and pc == k and 0 <= t - pt < 400]
                age = min(ages) if ages else None
                fresh = age is not None and age < 40
                by[(fresh, kind)] += 1; n += 1
                by_age["none" if age is None else min(age // 10 * 10, 100)][kind] += 1
                if k in SPAWNERS:
                    by_name[k][(fresh, kind)] += 1
print("entities", n)
print("kind by fresh(<40 ticks since same-side same-card play):", sorted(by.items(), key=str))
print("kind by ticks since the nearest same-side same-card play (bucket 10; 100 = 100-399; none = no play in 400):")
for a in sorted(by_age, key=lambda x: (x == "none", x if x != "none" else 0)):
    print("  ", a, dict(by_age[a]))
print("spawner cards (fresh, kind) counts:")
for k in sorted(by_name):
    print("  ", k, dict(by_name[k]))

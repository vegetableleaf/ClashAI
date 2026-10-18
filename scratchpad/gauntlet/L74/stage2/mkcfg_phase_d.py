"""S2-09 (prepared, NOT launched): Phase D = the S2-08 winner recipe trained on ALL deck styles as ONE deck-conditioned
opponent checkpoint. From cfg/s2_hog_<arm>.yaml change exactly: league_decks = mix/decks_live_train.json (the full TRAIN pool,
895 decks), max_updates 130, seed A = 74 / B = 75. Writes both inits (the lead keeps the S2-08 winner):
    python mkcfg_phase_d.py   -> cfg/s2_all_{e4,il}_s{A,B}.yaml (+ the diff check)"""
import os
import yaml
H = os.path.dirname(os.path.abspath(__file__))
for arm in ("e4", "il"):
    base = yaml.safe_load(open(os.path.join(H, f"cfg/s2_hog_{arm}.yaml")))
    for tag, seed in (("A", 74), ("B", 75)):
        c = {**base, "league_decks": "scratchpad/gauntlet/L74/mix/decks_live_train.json", "max_updates": 130, "seed": seed}
        diff = sorted(k for k in set(c) | set(base) if c.get(k) != base.get(k))
        assert diff == (["league_decks", "max_updates"] if seed == 74 else ["league_decks", "max_updates", "seed"]), diff
        yaml.safe_dump(c, open(os.path.join(H, f"cfg/s2_all_{arm}_s{tag}.yaml"), "w", newline="\n"), sort_keys=False)
        print(f"cfg/s2_all_{arm}_s{tag}.yaml: vs s2_hog_{arm} {diff}")

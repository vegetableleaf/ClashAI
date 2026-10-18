# Presence of core cards / owner's six in a deck file with P(deck) ~ sides (rl_royale alpha 1, floor 0).
import json, os, sys
import numpy as np
sys.path.insert(0, r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend")
import archetypes as A
CORE = ["megaknight", "witch", "firecracker", "hogrider", "electrogiant", "elixirgolem", "goldenknight"]
for f in sys.argv[1:]:
    d = json.load(open(f, encoding="utf-8")); D = d["decks"] if isinstance(d, dict) else d
    w = np.array([float(x.get("sides", 1)) for x in D]); p = w / w.sum()
    cards = [{A.canon(n) for n in x["engine"]} for x in D]
    six = np.array([A.unfavorable(A.classify(x["engine"])) for x in D])
    anyc = np.array([bool(c & set(CORE)) for c in cards])
    print(os.path.basename(f), "decks", len(D), "six %.1f%%" % (100 * p[six].sum()), "any core %.1f%%" % (100 * p[anyc].sum()),
          " ".join("%s %.1f" % (c, 100 * p[[c in s for s in cards]].sum()) for c in CORE))

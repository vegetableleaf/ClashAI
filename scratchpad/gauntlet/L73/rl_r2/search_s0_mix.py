"""What search_s0 --census does with a deck file: its opp_deck_for (deck_weights alpha .5 floor .5, hard-coded) ->
full-distribution class mix and the first draw for gen-opponent seeds 0..47 (redraws for unseen cards not simulated)."""
import os, sys, collections
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # below normal
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/rl_r2")
from build_ladder import cls, trs, TRAITS
from pipeline.rl_royale import league_decks, deck_weights
from pipeline.search_s0 import opp_deck_for
for f in ("scratchpad/gauntlet/L70/pool_forms/loadable_decks.json", "scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json"):
    c = league_decks(f); w = deck_weights([d["sides"] for d in c], 0.5, 0.5)
    full = collections.defaultdict(float)
    for d, p in zip(c, w): full[cls(d["engine"])] += p
    first = collections.Counter(cls(opp_deck_for(s * 1000, c)["engine"]) for s in range(48))
    tr = {k: sum(p for d, p in zip(c, w) if trs(d["engine"])[k]) for k in TRAITS}
    print(f)
    for k in sorted(full, key=lambda k: -full[k]):
        print(f"  {k:30s} dist {100 * full[k]:5.1f}%  seeds0:48 first draw {first.get(k, 0):2d}/48")
    print("  traits (dist):", {k: round(100 * v, 1) for k, v in tr.items()})

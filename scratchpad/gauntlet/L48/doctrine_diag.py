"""L48: WHY does the doctrine lose whole matches? Per-decision ledger on the L43 instrument
(ladder, DR off, seeds 5000000+). Records: elixir, quiet?, nominated card, had cell?, action,
elixir leaked (time at 10), hand composition. argv: matches [override_module]"""
import sys, collections, importlib
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np
from rollout_search import play_match
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim import drill_env, doctrine
n_matches = int(sys.argv[1])
if len(sys.argv) > 2:
    importlib.import_module(sys.argv[2]).install()      # monkeypatch the doctrine in-process
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None; env.scenario = None
K = list(env.deck_keys)
C = collections.Counter(); nom_nocell = collections.Counter(); nom_played = collections.Counter(); hold_rich_hand = collections.Counter()
class D:
    def act(self, i):
        e = float(env.eng.elixir[0]); hand = list(env._hand_ids())
        pri = doctrine.doctrine_cards(env) or {}
        a = drill_env.doctrine_policy(None, env)
        enemies = doctrine._enemies(env)
        committed = [u for u in enemies if u.y > 0.42 and u.spec.kind != "spell"]
        C["dec"] += 1; C["at10"] += e >= 9.95; C["rich"] += e >= 9
        C["quiet"] += not committed
        if pri:
            top = max(pri, key=pri.get); C["nominated"] += 1
            if a[0] == 1: nom_played[K[a[1]]] += 1
            else:
                nom_nocell[K[top]] += 1; C["nom_hold"] += 1
                if e >= 9: hold_rich_hand[tuple(sorted(K[c] for c in hand))] += 1
        else:
            C["nothing_nominated"] += 1
            if committed: C["nothing_but_committed"] += 1
        return tuple(int(x) for x in a), False
s = D(); wins = 0; td = 0.0
for m in range(n_matches):
    r = play_match(env, s, 5000000 + m); wins += r["outcome"] == "win"
    td += r["tower_delta"]
print("matches", n_matches, "wins", wins, "towerdelta", round(td / n_matches, 3))
print({k: v for k, v in C.items()})
print("share of decisions at 10 elixir (leaking):", round(C["at10"] / C["dec"], 3))
print("nominated but HELD (no cell), by top card:", nom_nocell.most_common())
print("nominated and PLAYED, by card:", nom_played.most_common())
print("held while rich, hand:", hold_rich_hand.most_common(6))

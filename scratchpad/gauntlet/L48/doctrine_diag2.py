"""L48: where does the doctrine's DEFENCE fail? At every decision with committed enemies and no
nomination: is the group triaged ignorable? what is it? elixir? Also the bow ledger."""
import sys, collections, importlib
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
from rollout_search import play_match
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim import drill_env, doctrine
from clashrl import threat_value
n = int(sys.argv[1])
if len(sys.argv) > 2: importlib.import_module(sys.argv[2]).install()
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None; env.scenario = None
K = list(env.deck_keys); bow = K.index("x_bow")
C = collections.Counter(); groups = collections.Counter(); notign_e = collections.Counter()
class D:
    def act(self, i):
        e = float(env.eng.elixir[0]); hand = list(env._hand_ids())
        pri = doctrine.doctrine_cards(env) or {}
        a = drill_env.doctrine_policy(None, env)
        committed = [u for u in doctrine._enemies(env) if u.y > 0.42 and u.spec.kind != "spell"]
        C["dec"] += 1
        if bow in hand: C["bow_in_hand"] += 1
        if bow in hand and e >= 6: C["bow_hand_ge6"] += 1
        if bow in hand and e >= 6 and not committed: C["bow_hand_ge6_empty"] += 1
        if bow in pri: C["bow_nominated"] += 1
        if a[0] == 1 and a[1] == bow: C["bow_played"] += 1
        if bow in pri and not (a[0] == 1 and a[1] == bow): C["bow_nom_not_played"] += 1; C["bow_nom_lost_to_" + (K[a[1]] if a[0] else "HOLD")] += 1
        if committed and not pri:
            cost = threat_value.bodies_ignore_frac(env.db, [u.spec.base for u in committed], tower_level=doctrine._tower_level(env), enemy_level=doctrine._enemy_level(env))
            ign = cost < threat_value.IGNORE_FRAC
            C["committed_nopri"] += 1; C["committed_nopri_ignorable"] += ign
            if not ign:
                groups[tuple(sorted(set(u.spec.base for u in committed)))] += 1
                notign_e["e>=%d" % min(int(e), 6)] += 1
                C["nonign_deepest_y>0.6"] += any(u.y > 0.6 for u in committed)
        return tuple(int(x) for x in a), False
s = D(); w = 0; td = 0
for m in range(n):
    r = play_match(env, s, 5000000 + m); w += r["outcome"] == "win"; td += r["tower_delta"]
print("wins", w, "/", n, "towerdelta", round(td / n, 3)); print(dict(C))
print("non-ignorable committed groups with NO nomination:", groups.most_common(12))
print("elixir at those:", sorted(notign_e.items()))

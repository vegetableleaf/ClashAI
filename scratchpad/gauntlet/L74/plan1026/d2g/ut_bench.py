"""D2-T item 1 microbenchmark: per-decision cost of the unit-type calls a crforge actor makes (royale_env.raw ->
core.unit_types(); sim_unit_state._unit_names -> _battle.unit_types_digest()), old (rebuilt every call) vs cached."""
import hashlib, json, random, time, sys
sys.path.insert(0, "/workspace/d2t/cbH")
from pipeline import crforge_core as C
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode
ICE = ["Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]
OPP = ["Witch", "Golem", "Tombstone", "DarkWitch", "GoblinGiant", "FirespiritHut", "GoblinBarrel", "Graveyard"]
core = C.CrforgeCore()
old_ns = new_ns = n = 0
for seed in range(8):
    core.reset(seed, MatchSetup(decks=[[core.ids[c] for c in ICE], [core.ids[c] for c in OPP]], shuffle=ShuffleMode.NONE,
                                forms=[[1, 2, 1, 0, 0, 0, 0, 0], [0] * 8]))
    rng = random.Random(seed)
    for _ in range(300):
        core.step([DeployCommand(s, rng.randrange(4), 18 * rng.randrange(500, 17500), 18 * rng.randrange(500, 31500))
                   for s in (0, 1) if rng.random() < 0.3], 10)
        t = time.perf_counter_ns()
        a = [str(s) for s in core._cf.unitTypesNow()]                     # old raw(): unit_types()
        d = hashlib.sha256(json.dumps([str(s) for s in core._cf.unitTypesNow()]).encode()).hexdigest()  # old digest
        old_ns += time.perf_counter_ns() - t
        t = time.perf_counter_ns()
        b = core.unit_types()
        e = core._battle.unit_types_digest()
        new_ns += time.perf_counter_ns() - t
        assert a == b and d == e
        n += 1
print(f"calls {n}  old {old_ns / n / 1e3:.1f} us/decision  new {new_ns / n / 1e3:.1f} us/decision  table {len(b)} names")

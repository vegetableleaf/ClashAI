"""L57: the L56 Tesla-outcome probe with the L52 `hidden_pull` mechanic patch applied (a hidden Tesla is a
pathing target for building-targeters, as the real engine record shows). Same arms/seeds/tau as L56.
Question: does the sim's flat corner-vs-centre landscape come from the missing pull?"""
import sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L56")
import tesla_probe as T
import clashrl.sim.engine as E
_orig = E.SimEngine._valid_foe
def _valid_foe(self, u, e):
    if u.spec.building_only and e.hidden and e.spec.kind == "building":
        return e.hp > 0 and e.invis_left <= 0.0 and not e.ghost
    return _orig(self, u, e)
E.SimEngine._valid_foe = _valid_foe
if __name__ == "__main__":
    sys.argv[0] = "tesla_probe_pull"
    import runpy, json, numpy as np, torch, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt"); ap.add_argument("--arms", default="own,corner,lane,centre")
    ap.add_argument("--matches", type=int, default=24); ap.add_argument("--seeds", default="1234,5678")
    ap.add_argument("--tau", type=float, default=0.25); ap.add_argument("--out", default=None)
    a = ap.parse_args(); outs = []
    for s in [int(x) for x in a.seeds.split(",")]:
        for arm in a.arms.split(","):
            np.random.seed(s); torch.manual_seed(s)
            o = T.run(a.ckpt, arm, a.matches, s, a.tau); outs.append(o); print(T.summarize(o), flush=True)
    if a.out: json.dump(outs, open(a.out, "w"))

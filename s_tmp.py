"""GREEDY vs SAMPLED: is the evaluated policy the trained one?

Training optimises a SAMPLED policy -- the gate is a probability and the rollout flips a coin on it.
Both tools/wr_eval.py and the trainer's own evaluate() instead THRESHOLD that probability at
sim.ppo_gate_threshold (0.25). If the gate is calibrated around 0.2, thresholding turns "play a fifth
of the time" into "almost never play", and the policy being scored is not the policy being trained.

This plays the same matches both ways.
"""
import sys, numpy as np, torch, torch.nn as nn
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
cfg = Config.load("config/config.yaml"); cfg.data.setdefault("action", {})["grid"] = [18, 24]
st = torch.load("data/policy_ppo_drill.pt", map_location="cpu", weights_only=False)
tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))

def run(mode, seed0):
    pool = [SimMatchEnv(cfg, seed=seed0 + i) for i in range(6)]
    e0 = pool[0]
    ich = int(st.get("in_ch") or 12); td = int(st.get("threat_dim") or e0.threat_dim)
    class M(nn.Module):
        def __init__(s):
            super().__init__()
            s.policy = PolicyNet(ich, e0.n_cards, e0.n_cells, threat_dim=td)
            s.gate = nn.Linear(s.policy.embed_dim, 2)
    net = M(); net.policy.load_state_dict(st["model"])
    if "gate" in st: net.gate.load_state_dict(st["gate"])
    net.eval()
    mask = np.asarray(e0.actions.deployable_mask(False), dtype=bool)
    obs = [e.reset() for e in pool]; w=l=d=0; plays=0; steps=0
    rng = np.random.default_rng(7)
    with torch.no_grad():
        while w+l+d < N:
            xb = torch.stack([torch.from_numpy(np.asarray(o)[:, :, :ich]).float().permute(2,0,1)/255.0 for o in obs])
            hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
            nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
            eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
            tb = torch.stack([torch.from_numpy(np.pad(np.asarray(e.threat_vec, np.float32),(0,max(0,td-len(e.threat_vec))))[:td]) for e in pool])
            z, cq, ceq = net.policy.forward_parts(xb, hb, nb, eb, tb); gq = net.gate(z)
            pg = torch.softmax(gq, dim=1)[:, 1].numpy()
            pc = torch.softmax(cq, dim=1).numpy()
            for i, e in enumerate(pool):
                steps += 1
                aff = [c for c in e._hand_ids() if 0 <= c < len(e.specs) and e.eng.elixir[0] >= e.specs[c].elixir]
                go = (pg[i] > tau) if mode == "greedy" else (rng.random() < pg[i])
                if aff and go:
                    plays += 1
                    if mode == "greedy":
                        ci = max(aff, key=lambda c: float(cq[i, c]))
                        row = ceq[i, ci].numpy().copy()
                        if ci not in getattr(e, "anywhere_ids", set()): row[~mask] = -1e9
                        cell = int(np.argmax(row))
                    else:
                        wts = np.array([pc[i][c] for c in aff]); wts = wts/wts.sum()
                        ci = int(rng.choice(aff, p=wts))
                        row = ceq[i, ci].numpy().copy()
                        if ci not in getattr(e, "anywhere_ids", set()): row[~mask] = -1e9
                        p = np.exp(row - row.max()); p = p/p.sum()
                        cell = int(rng.choice(len(p), p=p))
                    a = (1, ci, cell)
                else:
                    a = (0, 0, 0)
                o, _r, done, info = e.step(a)
                if done:
                    oc = (info or {}).get("outcome")
                    if oc == "win": w += 1
                    elif oc == "loss": l += 1
                    else: d += 1
                    o = e.reset()
                obs[i] = o
    tot = max(1, w+l+d)
    print("  %-8s seeds@%-6d %2dW-%2dL-%2dD  winrate %5.1f%%   plays %4.1f%% of steps"
          % (mode, seed0, w, l, d, 100.0*w/tot, 100.0*plays/max(1,steps)))

print("matches=%s  gate tau=%.2f" % (st.get("matches"), tau))
for s0 in (31337, 555):
    run("greedy", s0)
    run("sampled", s0)

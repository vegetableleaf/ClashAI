import sys, numpy as np, torch, torch.nn as nn
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv
CK = sys.argv[1]; N = int(sys.argv[2]); ENVS = 6
cfg = Config.load("config/config.yaml"); cfg.data.setdefault("action", {})["grid"] = [18, 24]
st = torch.load(CK, map_location="cpu", weights_only=False)
tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
pool = [SimMatchEnv(cfg, seed=31337 + i) for i in range(ENVS)]
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
obs = [e.reset() for e in pool]; w=l=d=0; nplay=0; nstep=0
with torch.no_grad():
    while w+l+d < N:
        xb = torch.stack([torch.from_numpy(np.asarray(o)[:, :, :ich]).float().permute(2,0,1)/255.0 for o in obs])
        hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
        nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
        eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
        tb = torch.stack([torch.from_numpy(np.pad(np.asarray(e.threat_vec, np.float32),(0,max(0,td-len(e.threat_vec))))[:td]) for e in pool])
        z, cq, ceq = net.policy.forward_parts(xb, hb, nb, eb, tb); gq = net.gate(z)
        pg = torch.softmax(gq, dim=1)[:, 1].numpy()
        for i, e in enumerate(pool):
            nstep += 1
            aff = [c for c in e._hand_ids() if 0 <= c < len(e.specs) and e.eng.elixir[0] >= e.specs[c].elixir]
            if aff and pg[i] > tau:
                nplay += 1
                ci = max(aff, key=lambda c: float(cq[i, c]))
                row = ceq[i, ci].numpy().copy()
                if ci not in getattr(e, "anywhere_ids", set()): row[~mask] = -1e9
                a = (1, ci, int(np.argmax(row)))
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
print("%-34s matches=%-6s %2dW-%2dL-%2dD  winrate %5.1f%%   played %4.1f%% of steps"
      % (CK, st.get("matches"), w, l, d, 100.0*w/tot, 100.0*nplay/max(1,nstep)))

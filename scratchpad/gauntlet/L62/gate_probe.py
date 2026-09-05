"""Gate-probability probe: is the low play rate a COLLAPSED GATE, or cards being masked out?
Drives SimMatchEnv with the checkpoint's own greedy policy (sim_view's exact rule) and records
p(play) = sigmoid(g1-g0) at every decision, plus the elixir at that moment. Read-only."""
import sys, numpy as np, torch
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.model import PolicyNet

from clashrl.gate_rule import GateRule
ck_path = sys.argv[1]; n_match = int(sys.argv[2]) if len(sys.argv) > 2 else 3
cfg = Config.load("config/config.yaml")
cfg.data.setdefault("action", {})["grid"] = [18, 24]
if len(sys.argv) > 3:                      # optional override: sample | threshold (5cs.49 ruling)
    cfg.data.setdefault("sim", {})["ppo_gate_rule"] = sys.argv[3]
ck = torch.load(ck_path, map_location="cpu", weights_only=False)
rule = GateRule(cfg, seed=4242); tau = rule.tau
net = PolicyNet(int(ck.get("in_ch", 3)), int(ck["n_cards"]), int(ck["n_cells"]), int(ck["threat_dim"]))
net.load_state_dict(ck["model"]); net.eval()
gate = torch.nn.Linear(net.embed_dim, 2); gate.load_state_dict(ck["gate"]); gate.eval()
env = SimMatchEnv(cfg, seed=4242)
ps, affordable, plays = [], [], 0
for m in range(n_match):
    env.reset(); done = False; n = 0
    while not done and n < 500:
        with torch.no_grad():
            x = torch.from_numpy(env._last_obs).float().div(255).permute(2, 0, 1).unsqueeze(0)
            z, cq_b, ceq_b = net.forward_parts(x, torch.from_numpy(env.hand_vec).unsqueeze(0),
                                               torch.from_numpy(env.next_vec).unsqueeze(0),
                                               torch.from_numpy(env.elixir_vec).unsqueeze(0),
                                               torch.from_numpy(env.threat_vec).unsqueeze(0))
            cq, ceq, gq = cq_b[0], ceq_b[0], gate(z)[0]
            p = float(torch.sigmoid(gq[1] - gq[0]))
            ok = torch.tensor([bool(v >= 0.5 and env.specs[i].elixir <= env.eng.elixir[0])
                               for i, v in enumerate(env.hand_vec)])
        ps.append(p); affordable.append(int(ok.sum()))
        act = (0, 0, 0)
        if bool(ok.any()):
            card = int(cq.masked_fill(~ok, -1e9).argmax())
            cm = torch.tensor(env.actions.deployable_mask(card in env.anywhere_ids))
            cell = int(ceq[card].masked_fill(~cm, -1e9).argmax())
            play = rule.play(gq)
            plays += int(play)
            act = (int(play), card, cell)
        _, _, done, _ = env.step(act); n += 1
a, af = np.array(ps), np.array(affordable)
print(f"{ck_path.split('/')[-1]:18s} [{rule.rule}] dec={len(a):5d} plays={plays:4d} | p(play) mean {a.mean():.4f} "
      f"p50 {np.percentile(a,50):.4f} p90 {np.percentile(a,90):.4f} max {a.max():.4f} | frac>tau {(a>tau).mean():.4f} "
      f"| mean affordable cards {af.mean():.2f}, frac with >=1 {(af>0).mean():.3f}")

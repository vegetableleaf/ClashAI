"""OFFLINE sim->live seam test (HANDOFF 5cr): the first 16 threat slots mean different things in sim (view.threat_vector:
slots 0-5 filled, 6-15 always 0) and live (threats.Threat.vector: all 16 filled, slot 12 = 0.5 whenever no projectile).
Take the sim obs dump (states the policy was trained on), rewrite the base block the way LIVE would present the same
board, and measure how often the policy's greedy decision CHANGES. Decision rule = sim greedy (tau 0.25)."""
import os, sys, numpy as np, torch
ROOT = r"C:\Users\benpe\ClashBot\icebow"; os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad")
from rollout_search import load_net, _NEG
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
ck, npz = sys.argv[1], sys.argv[2]
env = SimMatchEnv(Config.load(), seed=1); net = load_net(ck, env, torch.device("cpu"))
yourhalf = torch.tensor(env.actions.deployable_mask(False), dtype=torch.bool); allcells = torch.ones(env.n_cells, dtype=torch.bool)
costs = torch.tensor([float(s.elixir) for s in env.specs]); anywhere = set(env.anywhere_ids)
d = np.load(npz); N = len(d["t"]); print("decisions", N)

def decide(thr):
    out = []
    B = 256
    for i in range(0, N, B):
        obs = torch.from_numpy(d["obs"][i:i+B]).float().permute(0, 3, 1, 2) / 255.0
        v = lambda x: torch.from_numpy(np.asarray(x, np.float32))
        with torch.no_grad():
            cq, ceq, gq, _, _ = net(obs, v(d["hand"][i:i+B]), v(d["next"][i:i+B]), v(d["elixir_vec"][i:i+B]), v(thr[i:i+B]))
        elixir = v(d["elixir_vec"][i:i+B]) * 10.0
        playable = (v(d["hand"][i:i+B]) > 0.5) & (costs.view(1, -1) <= elixir + 1e-6)
        cq_m = cq.masked_fill(~playable, _NEG); p = torch.sigmoid(gq[:, 1] - gq[:, 0])
        for j in range(cq.shape[0]):
            if not bool(playable[j].any()) or float(p[j]) <= 0.25:
                out.append((0, -1, -1, float(p[j]))); continue
            ci = int(cq_m[j].argmax()); msk = allcells if ci in anywhere else yourhalf
            out.append((1, ci, int(ceq[j, ci].masked_fill(~msk, _NEG).argmax()), float(p[j])))
    return out

base = decide(d["threat"])
def report(name, alt):
    g = np.mean([a[0] == b[0] for a, b in zip(base, alt)]); 
    both = [(a, b) for a, b in zip(base, alt) if a[0] == 1 and b[0] == 1]
    card = np.mean([a[1] == b[1] for a, b in both]) if both else float("nan")
    cell = np.mean([a[2] == b[2] for a, b in both]) if both else float("nan")
    play_b = np.mean([a[0] for a in base]); play_a = np.mean([a[0] for a in alt])
    dp = np.mean([b[3] - a[3] for a, b in zip(base, alt)])
    print(f"{name:34s} gate agree {g:.3f} | card agree (both play) {card:.3f} | cell agree {cell:.3f} | play rate {play_b:.3f}->{play_a:.3f} | mean dP(play) {dp:+.3f}")

T = d["threat"].copy()
# V1: only the guaranteed constant -- live slot 12 (projectile-x) defaults to 0.5 when no projectile is seen.
T1 = T.copy(); T1[:, 12] = 0.5; report("V1 slot12=0.5 only", decide(T1))
# V2: live SEMANTICS for the same board, approximated from the sim block: sim[0]=mass ->live 0 (mass) and 1 (my_side_mass);
# sim[2]=biggest ->live 2 (largest_blob); sim[1]=count/6 -> live 3 = count/12 (half); sim lane flags 3/4 -> live lanes 7/9
# (mass in that lane); sim depth 5 -> live 6; live 4/5 (green/purple) 0; live 12 = 0.5; rest 0.
T2 = np.zeros_like(T); T2[:, 16:] = T[:, 16:]
T2[:, 0] = T[:, 0]; T2[:, 1] = T[:, 0]; T2[:, 2] = T[:, 2]; T2[:, 3] = T[:, 1] * 0.5
T2[:, 7] = T[:, 0] * T[:, 3]; T2[:, 9] = T[:, 0] * T[:, 4]; T2[:, 8] = T[:, 0] * (1 - T[:, 3]) * (1 - T[:, 4]); T2[:, 6] = T[:, 5]; T2[:, 12] = 0.5
report("V2 live-semantics remap", decide(T2))
# V3: base block zeroed except slot 12 -- what the policy sees when the live red-mask finds nothing at all.
T3 = T.copy(); T3[:, :16] = 0; T3[:, 12] = 0.5; report("V3 base block empty (+0.5)", decide(T3))
# CONTROL: base block zeroed entirely (a sim quiet board) -- how much the block matters at all.
T4 = T.copy(); T4[:, :16] = 0; report("CONTROL base block all-zero", decide(T4))
# CONTROL 2: identity block + memory zeroed (slots 16..) to rank which block carries the decision.
T5 = T.copy(); T5[:, 16:] = 0; report("CONTROL slots16+ all-zero", decide(T5))
nz = (T[:, :16] != 0).mean(0); print("sim base-block nonzero rate per slot:", np.round(nz, 3).tolist())

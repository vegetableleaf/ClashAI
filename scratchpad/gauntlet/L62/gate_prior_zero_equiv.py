"""L62 v2: prove `--gate_prior_coef 0.0` is byte-for-byte the OLD trainer.

Runs the PRE-PATCH `Trainer.update()` (a copy of engine_ppo.py as it was before today's edit, kept at
scratchpad/gauntlet/L62/engine_ppo_launched_20260905.py -- the file engA actually ran) and the PATCHED
`Trainer.update()` with gprior = None, on the SAME rollout, from the SAME init, with the numpy RNG
reseeded identically before each, and compares every parameter tensor with torch.equal.

No engine, no VM: the rollout comes from a real SimMatchEnv, as in gate_prior_offline_smoke.py.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "icebow" / "src"))

import engine_ppo as NEW                                  # noqa: E402
from clashrl.config import Config                         # noqa: E402
from clashrl.sim.env import SimMatchEnv                   # noqa: E402
from clashrl.model import PolicyNet                       # noqa: E402

spec = importlib.util.spec_from_file_location("engine_ppo_old", str(HERE / "engine_ppo_launched_20260905.py"))
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

N = 512
INIT = ROOT / "icebow" / "data" / "bc_pro" / "models" / "bc_bias_native_s0.pt"
base = dict(port=0, kl_coef=0.3, matches=2000, seed=41, rollout=N, save_every=250, threads=2,
            decision_ticks=10, gamma=0.994, lam=0.95, clip=0.2, lr=0.00025, ent=0.02, cell_ent=0.05,
            cell_ent_floor=0.008, cell_ent_anneal=3000, epochs=4, minibatch=512, vf_coef=0.5,
            max_grad=0.5, head_norm_mult=2.0, value_warmup=8)
a_old = argparse.Namespace(**base)                                   # the pre-patch file has no kl_in_warmup
a_new = argparse.Namespace(**base, kl_in_warmup=0, gate_prior_coef=0.0,
                           gate_prior_path=str(ROOT / "icebow" / "config" / "gate_prior.json"))

torch.manual_seed(41); np.random.seed(41); torch.set_num_threads(2)
cfg = Config.load("config/config.yaml")
cfg.data.setdefault("action", {})["grid"] = [18, 24]
env = SimMatchEnv(cfg, seed=4242)
ck = torch.load(str(INIT), map_location="cpu", weights_only=False)


def make(mod, args, with_gprior_attr):
    T = mod.Trainer.__new__(mod.Trainer)
    T.a = args
    T.n_cards, T.n_cells = int(ck["n_cards"]), int(ck["n_cells"])
    T.net = mod.PPONet(int(ck["in_ch"]), T.n_cards, T.n_cells, int(ck["threat_dim"]))
    assert not PolicyNet.load_compat(T.net.policy, ck["model"])
    T.net.gate.load_state_dict(ck["gate"])
    T.ref = mod.PPONet(int(ck["in_ch"]), T.n_cards, T.n_cells, int(ck["threat_dim"]))
    T.ref.load_state_dict(T.net.state_dict()); T.ref.eval()
    for p in T.ref.parameters():
        p.requires_grad_(False)
    T.opt = torch.optim.Adam(T.net.parameters(), lr=args.lr, eps=1e-5)
    with torch.no_grad():
        T._card_ref = float(T.net.policy.card_head.weight.norm())
        T._cell_ref = float(T.net.policy.cell_conv[-1].weight.norm())
    T.warm_left = int(args.value_warmup); T.matches = 0; T.updates = 0
    if with_gprior_attr:
        T.gprior = None
    return T


T_old = make(OLD, a_old, False)
T_new = make(NEW, a_new, True)
# the FRESH value / value_d heads are drawn from the global torch RNG, so two constructions differ by
# construction order alone. Force identical weights, then rebuild the optimiser on them.
T_new.net.load_state_dict(T_old.net.state_dict())
T_new.ref.load_state_dict(T_old.ref.state_dict())
T_new.opt = torch.optim.Adam(T_new.net.parameters(), lr=a_new.lr, eps=1e-5)
assert all(torch.equal(p, q) for p, q in zip(T_old.net.parameters(), T_new.net.parameters())), "nets differ at t0"

# ---- one rollout, shared by both -------------------------------------------------------------------
costs = torch.tensor([float(s.elixir) for s in env.specs], dtype=torch.float32)
anywhere = set(env.anywhere_ids)
gen = torch.Generator().manual_seed(41)
B = {k: [] for k in ("obs", "hand", "nxt", "elx", "thr", "cm", "g", "c", "cell", "lp", "val", "rew",
                     "done", "trunc", "playable", "gp", "pg", "pgm")}
env.reset()
with torch.no_grad():
    T_old.net.eval()
    for i in range(N):
        obs = env._last_obs
        x = torch.from_numpy(np.asarray(obs)).unsqueeze(0).permute(0, 3, 1, 2).contiguous().float() / 255.0
        hand = torch.from_numpy(env.hand_vec).unsqueeze(0); nxt = torch.from_numpy(env.next_vec).unsqueeze(0)
        elx = torch.from_numpy(env.elixir_vec).unsqueeze(0); thr = torch.from_numpy(env.threat_vec).unsqueeze(0)
        cards, cells, _, gq, val = T_old.net(x, hand, nxt, elx, thr)
        playable = (hand > 0.5) & (costs.view(1, -1) <= elx * 10.0 + 1e-6)
        cq_m = cards.masked_fill(~playable, NEW._NEG)
        gq_m = gq.clone()
        if not bool(playable.any()):
            gq_m[0, 1] = NEW._NEG
        lp_g = F.log_softmax(gq_m, 1)[0]
        g = int(torch.multinomial(lp_g.exp(), 1, generator=gen)); c = cell = 0; lp = float(lp_g[g])
        if g == 1:
            lp_c = F.log_softmax(cq_m, 1)[0]
            c = int(torch.multinomial(lp_c.exp(), 1, generator=gen))
            cm = torch.tensor(env.actions.deployable_mask(c in anywhere), dtype=torch.bool)
            lp_cell = F.log_softmax(cells[0, c].masked_fill(~cm, NEW._NEG), 0)
            cell = int(torch.multinomial(lp_cell.exp(), 1, generator=gen))
            lp += float(lp_c[c]) + float(lp_cell[cell])
        else:
            c_r = int(cq_m.argmax()) if bool(playable.any()) else 0
            cm = torch.tensor(env.actions.deployable_mask(c_r in anywhere), dtype=torch.bool)
        _, r, done, _ = env.step((g, c, cell))
        B["obs"].append(np.asarray(obs)); B["hand"].append(hand[0].numpy()); B["nxt"].append(nxt[0].numpy())
        B["elx"].append(elx[0].numpy()); B["thr"].append(thr[0].numpy()); B["cm"].append(cm.numpy())
        B["g"].append(g); B["c"].append(c); B["cell"].append(cell); B["lp"].append(lp)
        B["val"].append(float(val[0])); B["rew"].append(float(r)); B["done"].append(bool(done))
        B["trunc"].append(False); B["playable"].append(playable[0].numpy())
        B["gp"].append(0.0); B["pg"].append(0.5); B["pgm"].append(bool(playable.any()))
        if done:
            env.reset()
B["boot"] = 0.0

# ---- two updates each, RNG reseeded identically before each call ------------------------------------
for step in (1, 2):
    np.random.seed(1234 + step); u_old = T_old.update(B); T_old.updates += 1
    np.random.seed(1234 + step); u_new = T_new.update(B); T_new.updates += 1
    same = [k for k in u_old if k in u_new and float(u_old[k]) == float(u_new[k])]
    diff = [(k, u_old[k], u_new[k]) for k in u_old if k in u_new and float(u_old[k]) != float(u_new[k])]
    pd = [(n, float((p - q).abs().max())) for (n, p), (_, q)
          in zip(T_old.net.named_parameters(), T_new.net.named_parameters()) if not torch.equal(p, q)]
    print(f"update {step}: shared output fields identical {len(same)}/{len(same)+len(diff)}"
          + (f"  DIFFER {diff}" if diff else "")
          + f" | parameter tensors differing: {len(pd)}" + (f" {pd[:3]}" if pd else ""))
    assert not diff and not pd, "gate_prior_coef 0.0 is NOT equivalent to the pre-patch trainer"
    print(f"  new-only fields: {sorted(set(u_new) - set(u_old))} "
          f"(gp_ce {u_new['gp_ce']} gp_target {u_new['gp_target']} gp_rows {u_new['gp_rows']})")

print("PASS: --gate_prior_coef 0.0 reproduces engine_ppo_launched_20260905.py exactly "
      "(all %d parameter tensors torch.equal after 2 updates)" % len(list(T_new.net.parameters())))

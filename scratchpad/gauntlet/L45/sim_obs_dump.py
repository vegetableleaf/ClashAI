"""Sim-side twin of the live obs dump (HANDOFF 5cr): run a checkpoint GREEDY in SimMatchEnv (same rule as
train_sim_ppo.choose_greedy, gate tau 0.25) and record every decision's observation + gate probability, in the
same npz layout the live launcher writes -- so live and sim distributions can be compared slot by slot.
Also records what train-rl's rule (WAIT iff g_wait >= g_play, i.e. tau 0.5) would have done on the same state."""
import argparse, os, sys, time
import numpy as np, torch
ROOT = r"C:\Users\benpe\ClashBot\icebow"; os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad")
from rollout_search import load_net, _NEG  # noqa: E402
from clashrl.config import Config  # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", required=True); ap.add_argument("--matches", type=int, default=16)
ap.add_argument("--seed0", type=int, default=7000000); ap.add_argument("--out", required=True)
ap.add_argument("--config", default=None); ap.add_argument("--tau", type=float, default=0.25)
a = ap.parse_args()
cfg = Config.load(a.config) if a.config else Config.load()
env = SimMatchEnv(cfg, seed=12345)
dev = torch.device("cpu"); net = load_net(a.ckpt, env, dev)
yourhalf = torch.tensor(env.actions.deployable_mask(False), dtype=torch.bool); allcells = torch.ones(env.n_cells, dtype=torch.bool)
costs = torch.tensor([float(s.elixir) for s in env.specs]); anywhere = set(env.anywhere_ids)
D = {k: [] for k in ("obs", "hand", "next", "elixir_vec", "threat", "chosen", "exec", "reward", "elixir", "t", "match", "p_play", "chosen_tau05")}
recs = []
for m in range(a.matches):
    seed = a.seed0 + m; env.rng.seed(seed); env.reset(); t0 = time.time(); plays = 0; steps = 0
    for i in range(2000):
        obs = torch.from_numpy(env._last_obs).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        v = lambda x: torch.from_numpy(np.asarray(x, np.float32)).unsqueeze(0)
        with torch.no_grad():
            cq, ceq, gq, _, _ = net(obs, v(env.hand_vec), v(env.next_vec), v(env.elixir_vec), v(env.threat_vec))
        elixir = v(env.elixir_vec) * 10.0
        playable = (v(env.hand_vec) > 0.5) & (costs.view(1, -1) <= elixir + 1e-6)
        cq_m = cq.masked_fill(~playable, _NEG)
        p_play = float(torch.sigmoid(gq[0, 1] - gq[0, 0])) if bool(playable.any()) else 0.0
        if not bool(playable.any()) or p_play <= a.tau:
            act = (0, 0, 0)
        else:
            ci = int(cq_m.argmax()); msk = allcells if ci in anywhere else yourhalf
            act = (1, ci, int(ceq[0, ci].masked_fill(~msk, _NEG).argmax()))
        if not bool(playable.any()) or p_play <= 0.5:
            act05 = (0, 0, 0)
        else:
            ci = int(cq_m.argmax()); msk = allcells if ci in anywhere else yourhalf
            act05 = (1, ci, int(ceq[0, ci].masked_fill(~msk, _NEG).argmax()))
        D["obs"].append(env._last_obs.copy()); D["hand"].append(env.hand_vec.copy()); D["next"].append(env.next_vec.copy())
        D["elixir_vec"].append(env.elixir_vec.copy()); D["threat"].append(env.threat_vec.copy()); D["elixir"].append(float(env.eng.elixir[0]))
        D["chosen"].append(np.array(act)); D["exec"].append(np.array(act)); D["p_play"].append(p_play); D["chosen_tau05"].append(np.array(act05))
        D["match"].append(m); D["t"].append(float(env.eng.t))
        _o, r, done, info = env.step(act); D["reward"].append(float(r)); plays += act[0]; steps += 1
        if done:
            break
    recs.append((seed, info.get("outcome"), steps, plays, round(time.time() - t0, 1)))
    print("match", m, recs[-1], flush=True)
np.savez_compressed(a.out, **{k: np.array(v) for k, v in D.items()})
print("saved", a.out, len(D["t"]), "decisions")

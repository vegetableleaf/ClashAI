"""L59 arm E: cell-head temperature T applied as resume-time weight surgery on the LAST cell conv
(cell_conv.4 weight+bias / T): pre-tanh cell logits scale by exactly 1/T, ranking unchanged (greedy
argmax identical), the suppressed cells move from the tanh rails (|raw| median 17-33, tanh' ~0.01)
into the linear region so the entropy bonus and the policy gradient can move them. Writes to the
scratchpad only. Verifies argmax identity + entropy change on the same 1047 states as cell_sat_probe."""
import sys, collections
from pathlib import Path
import numpy as np, torch
_ROOT = Path("C:/Users/benpe/ClashBot/icebow"); sys.path.insert(0, str(_ROOT / "src"))
T = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
src = Path("C:/Users/benpe/ClashBot/icebow/data/bench/c2r_best_36k_backup.pt")
dst = Path(f"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/c2r_best_cellT{T:g}.pt")
state = torch.load(src, map_location="cpu", weights_only=False)
keys = [k for k in state["model"] if k.startswith("cell_conv.4.")]
assert keys == ["cell_conv.4.weight", "cell_conv.4.bias"], keys
for k in keys: state["model"][k] = state["model"][k] / T
state["lineage_note"] = f"L59 arm E: cell_conv.4 / {T} from c2r_best_36k_backup.pt"
torch.save(state, dst)
print("wrote", dst, "size", dst.stat().st_size)
# verify
import importlib.util
_s = importlib.util.spec_from_file_location("tp", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L56/tesla_probe.py")
TP = importlib.util.module_from_spec(_s); _s.loader.exec_module(TP)
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
cfg = Config.load(_ROOT / "config" / "config.yaml"); cfg.data.setdefault("action", {})["grid"] = [18, 24]
env = SimMatchEnv(cfg, seed=5)
if getattr(env, "domain_rand", None) is not None: env.domain_rand.enabled = False; env.domain_rand.resample()
netA, in_ch, thr_dim = TP.load(str(src), env); netB, _, _ = TP.load(str(dst), env)
names = [str(getattr(sp, "key", i)) for i, sp in enumerate(env.specs)]
own = np.zeros(env.n_cells, bool); own[12*18:] = True
def obs_t(o):
    x = np.asarray(o)
    if x.shape[2] > in_ch: x = x[:, :, :in_ch]
    return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0
def thr_t(v):
    t = np.asarray(v, np.float32); return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim else np.pad(t, (0, thr_dim - t.shape[0])))
same = 0; tot = 0; entA = collections.defaultdict(list); entB = collections.defaultdict(list); topA = collections.defaultdict(list)
obs = env.reset(); done_n = 0
with torch.no_grad():
    while done_n < 3:
        args = (obs_t(obs)[None], torch.from_numpy(np.asarray(env.hand_vec, np.float32))[None],
                torch.from_numpy(np.asarray(env.next_vec, np.float32))[None], torch.from_numpy(np.asarray(env.elixir_vec, np.float32))[None], thr_t(env.threat_vec)[None])
        cA, ceA, gA = netA(*args); cB, ceB, gB = netB(*args)
        assert torch.allclose(cA, cB) and torch.allclose(gA, gB)
        for c in env._hand_ids():
            if not (0 <= c < len(names)): continue
            a = ceA[0, c].numpy().copy(); b = ceB[0, c].numpy().copy(); a[~own] = -1e9; b[~own] = -1e9
            tot += 1; same += int(a.argmax() == b.argmax())
            for arr, d in ((a, entA), (b, entB)):
                p = np.exp(arr - arr.max()); p /= p.sum(); d[names[c]].append(float(-(p[p > 0] * np.log(p[p > 0])).sum()))
            p = np.exp(a - a.max()); p /= p.sum(); topA[names[c]].append(float(p.max()))
        pc = torch.softmax(cA, 1)[0].numpy(); elxv = float(env.eng.elixir[0])
        hand_ok = [c for c in env._hand_ids() if 0 <= c < len(env.specs) and elxv >= env.specs[c].elixir]
        act = (0, 0, 0)
        if hand_ok:
            pick = int(max(hand_ok, key=lambda c: pc[c])); m = ceA[0, pick].numpy().copy(); m[~own] = -1e9
            act = (1, pick, int(m.argmax()))
        obs, _r, d, _i = env.step(act)
        if d: done_n += 1; obs = env.reset()
print(f"T={T}: greedy cell argmax identical {same}/{tot}")
print(f"{'card':12s} {'n':>5s} {'ent T=1':>8s} {'ent T':>8s} {'p_top T=1':>9s}")
for k in sorted(entA):
    print(f"{k:12s} {len(entA[k]):5d} {np.median(entA[k]):8.2f} {np.median(entB[k]):8.2f} {np.median(topA[k]):9.2f}")

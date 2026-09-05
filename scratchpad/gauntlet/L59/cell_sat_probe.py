"""L59: is the cell head at the tanh rails? Pre-tanh cell logits of c2r_best over ~600 real states."""
import sys, collections
from pathlib import Path
import numpy as np, torch
_ROOT = Path("C:/Users/benpe/ClashBot/icebow"); sys.path.insert(0, str(_ROOT / "src"))
import importlib.util
_s = importlib.util.spec_from_file_location("tp", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L56/tesla_probe.py")
TP = importlib.util.module_from_spec(_s); _s.loader.exec_module(TP)
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.model import _LOGIT_CAP
ckpt = "C:/Users/benpe/ClashBot/icebow/data/bench/c2r_best_36k_backup.pt"
cfg = Config.load(_ROOT / "config" / "config.yaml"); cfg.data.setdefault("action", {})["grid"] = [18, 24]
env = SimMatchEnv(cfg, seed=5)
if getattr(env, "domain_rand", None) is not None: env.domain_rand.enabled = False; env.domain_rand.resample()
net, in_ch, thr_dim = TP.load(ckpt, env)
names = [str(getattr(sp, "key", i)) for i, sp in enumerate(env.specs)]
own = np.zeros(env.n_cells, bool); own[12*18:] = True
def obs_t(o):
    x = np.asarray(o)
    if x.shape[2] > in_ch: x = x[:, :, :in_ch]
    return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0
def thr_t(v):
    t = np.asarray(v, np.float32); return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim else np.pad(t, (0, thr_dim - t.shape[0])))
raw_top = collections.defaultdict(list); raw_own = collections.defaultdict(list); ent = collections.defaultdict(list)
tanh_d = collections.defaultdict(list); n_lin = collections.defaultdict(list)
obs = env.reset(); steps = 0; done_n = 0
with torch.no_grad():
    while done_n < 3:
        x = obs_t(obs)[None]; hand = torch.from_numpy(np.asarray(env.hand_vec, np.float32))[None]
        nxt = torch.from_numpy(np.asarray(env.next_vec, np.float32))[None]; elx = torch.from_numpy(np.asarray(env.elixir_vec, np.float32))[None]
        thr = thr_t(env.threat_vec)[None]
        z, cards, cells = net.policy.forward_parts(x, hand, nxt, elx, thr)
        # pre-tanh: invert the cap (cells = CAP*tanh(raw/CAP)) -> raw = CAP*atanh(cells/CAP); clip for numerics
        r = _LOGIT_CAP * torch.atanh(torch.clamp(cells / _LOGIT_CAP, -0.999999, 0.999999))
        for c in env._hand_ids():
            if not (0 <= c < len(names)): continue
            rc = r[0, c].numpy(); cc = cells[0, c].numpy().copy(); cc[~own] = -1e9
            p = np.exp(cc - cc.max()); p /= p.sum()
            ent[names[c]].append(float(-(p[p > 0] * np.log(p[p > 0])).sum()))
            raw_top[names[c]].append(float(rc[own].max()))
            raw_own[names[c]].append(float(np.median(np.abs(rc[own]))))
            n_lin[names[c]].append(float((np.abs(rc[own]) < 2 * _LOGIT_CAP).mean()))
            tanh_d[names[c]].append(float(1 - np.tanh(rc[own].max() / _LOGIT_CAP) ** 2))
        pc = torch.softmax(cards, 1)[0].numpy(); elxv = float(env.eng.elixir[0])
        hand_ok = [c for c in env._hand_ids() if 0 <= c < len(env.specs) and elxv >= env.specs[c].elixir]
        act = (0, 0, 0)
        if hand_ok:
            pick = int(max(hand_ok, key=lambda c: pc[c])); m = cells[0, pick].numpy().copy(); m[~own] = -1e9
            act = (1, pick, int(m.argmax()))
        obs, _r, d, _i = env.step(act); steps += 1
        if d: done_n += 1; obs = env.reset()
print(f"states {steps}, matches {done_n}, CAP {_LOGIT_CAP}")
print(f"{'card':12s} {'n':>5s} {'raw_top med':>11s} {'raw_top max':>11s} {'|raw| med':>9s} {'frac |raw|<16':>13s} {'tanh_d@top':>11s} {'ent med':>8s}")
for k in sorted(ent):
    print(f"{k:12s} {len(ent[k]):5d} {np.median(raw_top[k]):11.1f} {np.max(raw_top[k]):11.1f} {np.median(raw_own[k]):9.1f} {np.median(n_lin[k]):13.2f} {np.median(tanh_d[k]):11.2e} {np.median(ent[k]):8.2f}")

"""5ar: prove the trainer's BATCHED tensor assembly is bit-identical to the per-sample chains.

train_sim_ppo.to_obs_batch / to_vec_batch replaced 512-way torch.stack([...]) chains (12% of a
CPU update; 18 s vs 3 s per update on the GPU). This checks, on CPU and -- if present -- CUDA, that
for real SimMatchEnv observations and for random uint8 boards:
  * values are torch.equal (not allclose) to the per-sample chain,
  * layout is the same contiguous NCHW torch.stack produced (same strides -> same conv kernels),
  * a PolicyNet forward on both inputs is torch.equal (same tensor in, same kernel, same bits).
Exit 0 = identical on every device tried; 1 = a difference, printed.

    .venv/Scripts/python.exe tools/check_batched_assembly.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, torch
from clashrl.model import PolicyNet

torch.manual_seed(0); np.random.seed(0)
fails = 0


def chains(device):
    def to_obs_t(o):
        return torch.from_numpy(o).float().permute(2, 0, 1).to(device) / 255.0

    def to_vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def to_obs_batch(obs_list):
        return (torch.from_numpy(np.stack(obs_list)).to(device).permute(0, 3, 1, 2).contiguous()
                .float() / 255.0)

    def to_vec_batch(vec_list):
        return torch.from_numpy(np.stack([np.asarray(v, np.float32) for v in vec_list])).to(device)
    return to_obs_t, to_vec_t, to_obs_batch, to_vec_batch


def real_obs(n):
    """n observations from a real env so the dtype/shape/strides are the trainer's, not a guess."""
    try:
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        cfg = Config.load(os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml"))
        env = SimMatchEnv(cfg, seed=5)
        o = env.reset(); out = [o]; vecs = [(env.hand_vec.copy(), env.next_vec.copy(), env.elixir_vec.copy(), env.threat_vec.copy())]
        while len(out) < n:
            o, _r, d, _i = env.step((0, 0, 0)) if len(out) % 3 else env.step((1, 0, 200))
            if d:
                o = env.reset()
            out.append(o); vecs.append((env.hand_vec.copy(), env.next_vec.copy(), env.elixir_vec.copy(), env.threat_vec.copy()))
        return out, vecs
    except Exception as e:  # noqa: BLE001
        print("real env unavailable (%s: %s) -- random boards only" % (type(e).__name__, e))
        return None, None


def check(device, obs, vecs, label):
    global fails
    to_obs_t, to_vec_t, to_obs_batch, to_vec_batch = chains(device)
    a = torch.stack([to_obs_t(o) for o in obs]); b = to_obs_batch(obs)
    ok = torch.equal(a, b) and a.stride() == b.stride() and a.is_contiguous() and b.is_contiguous() and a.dtype == b.dtype
    print("%s %-14s obs  dtype in=%s shape %s | equal %s | strides %s vs %s" % (
        device, label, obs[0].dtype, tuple(a.shape), torch.equal(a, b), a.stride(), b.stride()))
    fails += not ok
    if vecs is not None:
        for k, name in enumerate(("hand", "next", "elixir", "threat")):
            va = torch.stack([to_vec_t(v[k]) for v in vecs]); vb = to_vec_batch([v[k] for v in vecs])
            eq = torch.equal(va, vb) and va.stride() == vb.stride()
            fails += not eq
            if not eq:
                print("  %s vec MISMATCH" % name)
    # same bits through the net: same tensor + same kernels must give the same output
    n_ch = obs[0].shape[2]
    net = PolicyNet(n_ch, 10, 432, threat_dim=52).to(device).eval()
    hand = torch.rand(len(obs), 10, device=device); nxt = torch.rand(len(obs), 10, device=device)
    elx = torch.rand(len(obs), 1, device=device); thr = torch.rand(len(obs), 52, device=device)
    with torch.no_grad():
        za, ca, la = net.forward_parts(a, hand, nxt, elx, thr)
        zb, cb, lb = net.forward_parts(b, hand, nxt, elx, thr)
    same = torch.equal(za, zb) and torch.equal(ca, cb) and torch.equal(la, lb)
    print("  forward_parts identical: %s" % same)
    fails += not same


obs_real, vecs_real = real_obs(64)
rand = [np.random.randint(0, 256, (96, 64, 12), dtype=np.uint8) for _ in range(512)]
devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
for d in devices:
    if d == "cuda":
        torch.backends.cudnn.allow_tf32 = False; torch.backends.cuda.matmul.allow_tf32 = False
    if obs_real is not None:
        check(d, obs_real, vecs_real, "real env obs")
    check(d, rand, None, "random uint8")
print("RESULT: %s" % ("IDENTICAL on %s" % ", ".join(devices) if fails == 0 else "%d MISMATCH(ES)" % fails))
sys.exit(1 if fails else 0)

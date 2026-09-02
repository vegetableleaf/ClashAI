"""5ar: the PPO update's compute, CPU (4 threads, as the trainer pins it) vs the idle RTX 5050.

Same net the real run trains (PolicyNet in_ch=12, n_cards=10, n_cells=432, threat_dim=52 + the
PPONet heads), same batch (512), same count per update (96 minibatches = 12,288 samples x 4
epochs), forward + surrogate loss over every head + backward + clip + Adam step. The trainer's
per-minibatch tensor assembly (512 separate from_numpy/float/permute/div chains) is timed
separately against a batched assembly, because the profile put it at 12% of the update.

    CLASHRL_BENCH_DEV=cuda .venv/Scripts/python.exe tools/upd_bench.py
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, torch, torch.nn as nn
from clashrl.model import PolicyNet

dev = torch.device(os.environ.get("CLASHRL_BENCH_DEV", "cpu"))
torch.set_num_threads(4)
if os.environ.get("CLASHRL_BENCH_TF32", "1") == "0":     # the trainer runs the GPU with TF32 OFF (fp32)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
torch.manual_seed(0); np.random.seed(0)
IN_CH, N_CARDS, N_CELLS, THR = 12, 10, 432, 52
MB, N_MB = 512, 96


class PPONet(nn.Module):
    def __init__(self):
        super().__init__()
        self.policy = PolicyNet(IN_CH, N_CARDS, N_CELLS, threat_dim=THR)
        e = self.policy.embed_dim
        self.gate, self.value, self.value_d, self.hazard = nn.Linear(e, 2), nn.Linear(e, 1), nn.Linear(e, 1), nn.Linear(e, 7)

    def forward(self, x, hand, nxt, elx, thr):
        z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
        return cards, cells, self.gate(z), self.value(z).squeeze(-1), self.value_d(z).squeeze(-1), self.hazard(z)


net = PPONet().to(dev)
print("device %s | params %d | threads %d | cudnn TF32 %s" % (dev, sum(p.numel() for p in net.parameters()),
                                                             torch.get_num_threads(), torch.backends.cudnn.allow_tf32), flush=True)
opt = torch.optim.Adam(net.parameters(), lr=2.5e-4)

# one minibatch of synthetic inputs, shaped exactly like the rollout's (obs uint8 HWC 96x64x12)
obs_np = [np.random.randint(0, 255, (96, 64, IN_CH), dtype=np.uint8) for _ in range(MB)]
hand_np = [np.random.rand(N_CARDS).astype(np.float32) for _ in range(MB)]
nxt_np = [np.random.rand(N_CARDS).astype(np.float32) for _ in range(MB)]
elx_np = [np.random.rand(1).astype(np.float32) for _ in range(MB)]
thr_np = [np.random.rand(THR).astype(np.float32) for _ in range(MB)]


def to_obs_t(o):                     # the trainer's per-sample chain, verbatim
    return torch.from_numpy(o).float().permute(2, 0, 1).to(dev) / 255.0


def to_vec_t(v):
    return torch.from_numpy(np.asarray(v, np.float32)).to(dev)


def assemble_trainer():
    obs_t = torch.stack([to_obs_t(o) for o in obs_np])
    return (obs_t, torch.stack([to_vec_t(v) for v in hand_np]), torch.stack([to_vec_t(v) for v in nxt_np]),
            torch.stack([to_vec_t(v) for v in elx_np]), torch.stack([to_vec_t(v) for v in thr_np]))


def assemble_batched():              # one numpy stack + one device copy + one permute/div
    obs_t = torch.from_numpy(np.stack(obs_np)).to(dev).permute(0, 3, 1, 2).float() / 255.0
    return (obs_t, torch.from_numpy(np.stack(hand_np)).to(dev), torch.from_numpy(np.stack(nxt_np)).to(dev),
            torch.from_numpy(np.stack(elx_np)).to(dev), torch.from_numpy(np.stack(thr_np)).to(dev))


def sync():
    if dev.type == "cuda":
        torch.cuda.synchronize()


def step(batch):
    obs_t, hand_t, nxt_t, elx_t, thr_t = batch
    cq, ceq, gq, vm, vd, hz = net(obs_t, hand_t, nxt_t, elx_t, thr_t)
    loss = (torch.log_softmax(gq, 1).mean() + torch.log_softmax(cq, 1).mean() + torch.log_softmax(ceq, 1).mean()
            + vm.pow(2).mean() + vd.pow(2).mean() + torch.log_softmax(hz, 1).mean())
    opt.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
    opt.step()


net.train()
for _ in range(5):                   # warm-up (cudnn autotune, allocator)
    step(assemble_batched())
sync()

t = time.perf_counter()
for _ in range(N_MB):
    b = assemble_trainer()
sync(); t_asm_trainer = time.perf_counter() - t
t = time.perf_counter()
for _ in range(N_MB):
    b = assemble_batched()
sync(); t_asm_batched = time.perf_counter() - t

b = assemble_batched(); sync()
t = time.perf_counter()
for _ in range(N_MB):
    step(b)
sync(); t_compute = time.perf_counter() - t

print("per UPDATE (%d minibatches of %d):" % (N_MB, MB))
print("  tensor assembly  trainer-style %6.1fs | batched %6.1fs" % (t_asm_trainer, t_asm_batched))
print("  fwd+loss+bwd+adam              %6.1fs  (%.0f ms per minibatch)" % (t_compute, 1000 * t_compute / N_MB))
print("  update total (batched asm)     %6.1fs" % (t_asm_batched + t_compute))
if dev.type == "cuda":
    print("  peak VRAM %.2f GB" % (torch.cuda.max_memory_allocated() / 1e9))

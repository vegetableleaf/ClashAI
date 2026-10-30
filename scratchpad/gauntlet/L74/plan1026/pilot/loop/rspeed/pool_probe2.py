"""After a failed capture poisons pool P: does a FRESH pool capture fine, replay correctly, and does memory stay sane?"""
import torch
pool = torch.cuda.graph_pool_handle()
x = torch.ones(256, 256, device="cuda"); (x @ x + 1); torch.cuda.synchronize()

def cap(p, bad):
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g, pool=p, capture_error_mode="thread_local"):
        y = x @ x
        if bad:
            torch.cuda.synchronize()
        z = y + 1
    return g, z

try:
    cap(pool, True)
except Exception as e:
    print("bad:", str(e).splitlines()[0][:100])
p2 = torch.cuda.graph_pool_handle()
g, z = cap(p2, False)
x.fill_(2.0); g.replay(); torch.cuda.synchronize()
print("fresh pool capture OK, replay value", z[0, 0].item(), "(want", 2 * 2 * 256 + 1, ")")
g3, z3 = cap(p2, False); g3.replay(); print("2nd capture into fresh pool OK")
# memory: alloc / free churn outside capture after the stale entry
m0 = torch.cuda.memory_reserved()
for _ in range(200):
    a = torch.empty(64 << 20, device="cuda"); del a
print("reserved MB before/after churn", m0 >> 20, torch.cuda.memory_reserved() >> 20)

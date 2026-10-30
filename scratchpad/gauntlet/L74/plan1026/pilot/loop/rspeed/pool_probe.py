"""Does a failed capture leave a shared graph pool 'recording'? And does _cuda_endAllocateToPool clear it?"""
import sys, torch
torch.cuda.init()
dev = torch.cuda.current_device()
pool = torch.cuda.graph_pool_handle()
x = torch.ones(64, 64, device="cuda"); (x @ x + 1); torch.cuda.synchronize()

def cap(bad):
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g, pool=pool, capture_error_mode="thread_local"):
        y = x @ x
        if bad:
            torch.cuda.synchronize()          # illegal during capture
        z = y + 1
    return g

try:
    cap(True)
    print("bad capture: no error?!")
except Exception as e:
    print("bad capture raised:", type(e).__name__, str(e).splitlines()[0][:160])
try:
    cap(False)
    print("2nd capture (same pool) OK -> pool not poisoned")
except Exception as e:
    print("2nd capture raised:", str(e).splitlines()[0][:200])
    if len(sys.argv) > 1:
        torch._C._cuda_endAllocateToPool(dev, pool)
        try:
            torch.cuda.synchronize()
        except Exception as e2:
            print("sync after:", str(e2)[:100])
        try:
            cap(False); print("3rd capture after _cuda_endAllocateToPool OK")
        except Exception as e3:
            print("3rd capture raised:", str(e3).splitlines()[0][:200])
print("torch", torch.__version__)

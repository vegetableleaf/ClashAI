"""Re-stamp the SIM context of a timing-head opponent checkpoint (opp_sim.ctx band / mode / era) -> a new file.
    python restamp.py --ckpt opp_m10_s0_sim.pt --band 2 --out opp_m10_s0_sim_b2.pt
v0 was trained on bands 1 hf_pol, 2 hf_other, 3 pro only (4/5/6 = live L/M/R have no rows in v0: their embeddings are untrained)."""
import argparse, hashlib, json
import torch

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--band", type=int); ap.add_argument("--mode", type=int); ap.add_argument("--era", type=int)
a = ap.parse_args()
st = torch.load(a.ckpt, map_location="cpu", weights_only=False)
ctx = st["opp_sim"]["ctx"]
n = (st.get("opp") or {}).get("ctx_tokens") or {}
for k in ("band", "mode", "era"):
    v = getattr(a, k)
    if v is not None:
        if k in n and not 1 <= v <= int(n[k]):
            raise SystemExit(f"{k}={v} outside the trained ids 1..{n[k]}")
        ctx[k] = v
torch.save(st, a.out)
print(json.dumps({"out": a.out, "sha256": hashlib.sha256(open(a.out, "rb").read()).hexdigest(), "ctx": ctx, "ctx_tokens": n}))

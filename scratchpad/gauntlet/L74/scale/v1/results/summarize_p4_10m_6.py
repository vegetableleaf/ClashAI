import json
from pathlib import Path

root = Path(__file__).resolve().parent
paths = ["base_ice/eval.json", "base_pre/eval.json", "clxiii_eval.json", "v0_m10_eval.json"]
paths += [f"{name}/eval.json" for name in ("cv1_m2_s0", "cv1_m5_s0", "cv1_m20_s0", "cv1_m10_s1")]
print("| Eval | n_params | SHA256[:8] | heldout_hf NLL | heldout_v32 NLL | ice_hf NLL | p50 ms | p99 ms |")
print("|---|---:|---|---:|---:|---:|---:|---:|")
missing, invalid = [], []
for name in paths:
    path = root / "runs" / name
    if not path.is_file():
        missing.append(name)
        continue
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        invalid.append(f"{name}: {exc}")
        continue
    latency = d.get("latency_ms", {}).get("bs1_fp32", {})
    vals = [d.get(key, {}).get("nll_total") for key in ("heldout_hf", "heldout_v32", "ice_hf")]
    vals += [latency.get("p50_ms"), latency.get("p99_ms")]
    print("| " + " | ".join([name, str(d.get("n_params", "N/A")), d.get("sha256", "N/A")[:8]] + [f"{v:.6f}" if isinstance(v, (float, int)) else "N/A" for v in vals]) + " |")
print("Missing:", missing)
print("Invalid JSON:", invalid)
print("Local .pt files:", [str(p.relative_to(root)) for p in root.rglob("*.pt")])
print("Total file bytes:", sum(p.stat().st_size for p in root.rglob("*") if p.is_file()))
print("CHECKPOINTS.txt bytes:", (root / "CHECKPOINTS.txt").stat().st_size)

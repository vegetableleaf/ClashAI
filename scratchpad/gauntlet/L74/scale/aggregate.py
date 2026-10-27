"""Collect per-run train json + eval json from local copies in ./results/ and print the SCALE.md tables."""
import json, glob, os
rows = []
for f in sorted(glob.glob("results/*/eval.json")):
    d = os.path.dirname(f); e = json.load(open(f))
    fin = json.load(open(glob.glob(d + "/final_gen_*.json")[0])); hist = json.load(open(glob.glob(d + "/hist_gen_*.json")[0]))["hist"]
    rows.append((e["n_params"], os.path.basename(d), e, fin, hist))
rows.sort(key=lambda r: (r[0], r[1]))
def p(x, k=4): return f"{x:.{k}f}"
print("## grid / budget / cost")
print("| run | d x L | params | epoch sel | train s (last ep) | wall s | GPU peak MB (train) | sha256 |"); print("|---|---|---|---|---|---|---|---|")
for n, name, e, fin, h in rows:
    b = fin["best_val"]; print(f"| {name} | {e['d']}x{e['layers']} | {n:,} | {e['epoch_selected']} | {h[-1]['train_seconds']:.0f} | {fin['seconds']} | {b['gpu_peak_mb']} | {e['sha256'][:12]} |")
for split, key in (("HELD-OUT (val minus selection sample)", "heldout_clean"), ("v3val", "v3val"), ("TRAIN subset 100k (eval mode)", "train_sub100k")):
    print(f"\n## {split}"); print("| run | params | NLL cell | NLL card | NLL wait | NLL gate | NLL value | NLL total | top1 cell(tile) | top1 cell(half) | top1 card | top1 wait | gate bal acc |"); print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n, name, e, fin, h in rows:
        r = e[key]; print(f"| {name} | {n/1e6:.2f}M | {p(r['nll_cell'])} | {p(r['nll_card'])} | {p(r['nll_wait'])} | {p(r['nll_gate'])} | {p(r['nll_value'])} | {p(r['nll_total'])} | {p(r['top1_cell_tile'])} | {p(r['top1_cell_half'])} | {p(r['top1_card'])} | {p(r['top1_wait'])} | {p(r['gate_bal_acc'])} |")
print("\n## overfitting gap (held-out minus train, eval mode)"); print("| run | params | d cell | d card | d wait | d gate | d value | d total |"); print("|---|---|---|---|---|---|---|---|")
for n, name, e, fin, h in rows:
    a, b = e["heldout_clean"], e["train_sub100k"]
    print(f"| {name} | {n/1e6:.2f}M | " + " | ".join(f"{a[k]-b[k]:+.4f}" for k in ("nll_cell", "nll_card", "nll_wait", "nll_gate", "nll_value", "nll_total")) + " |")
print("\n## per-epoch selection-sample cell_nll / cell_tile_top1 (val sample 30k)"); 
for n, name, e, fin, h in rows: print(f"- {name}: " + "; ".join(f"ep{x['epoch']} nll {x['cell_nll']:.3f} tile {x['cell_tile_top1']:.4f} trainloss {x['train_loss']:.3f}" for x in h))
print("\n## forward latency on RTX 4090, ms (p50 / p99)"); print("| run | params | bs1 fp32 | bs1 bf16 | bs1024 fp32 | bs1024 bf16 | eval peak MB (bs1024 incl. data) |"); print("|---|---|---|---|---|---|---|")
for n, name, e, fin, h in rows:
    if "latency_ms" not in e: continue
    L = e["latency_ms"]; print(f"| {name} | {n/1e6:.2f}M | " + " | ".join(f"{L[k]['p50_ms']:.2f} / {L[k]['p99_ms']:.2f}" for k in ("bs1_fp32", "bs1_bf16", "bs1024_fp32", "bs1024_bf16")) + f" | {e['latency_gpu_peak_mb_bs1024']} |")

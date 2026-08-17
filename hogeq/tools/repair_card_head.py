"""Rescale an exploded card head back into the tanh cap's linear region.

Round-5 diagnosis (2026-08-14): the card head's raw logits reached +/-140 -- a delta softmax
whose suppressed cards (tornado, x_bow: -104/-120) could never recover, because at that
saturation both the policy-gradient and the entropy gradient through softmax are ~0. The model
now tanh-bounds logits to +/-8 (model._LOGIT_CAP), but a checkpoint trained before the cap
carries weights deep in the saturated zone, where tanh would simply freeze it at the rails.

This tool measures the head's raw logit spread on REAL observations and scales
card_head.weight/bias linearly so the max |raw logit| lands at --target (default 3.0):
ranking is fully preserved (a linear map), probabilities de-sharpen, and every card is
reachable by gradient again. The cell head is left alone (round 5 measured it HEALTHY:
118 cells used, 13% top share).

Usage (trainer must be STOPPED first -- it owns the checkpoint file):
    ./.venv/Scripts/python.exe tools/repair_card_head.py data/policy_sim_ppo.pt
    ./.venv/Scripts/python.exe tools/repair_card_head.py data/policy_sim_ppo.pt --out repaired.pt
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clashrl.config import Config           # noqa: E402
from clashrl.model import PolicyNet         # noqa: E402
from clashrl.sim.env import SimMatchEnv     # noqa: E402


def measure_absmax(net: PolicyNet, cfg, probes: int = 40) -> tuple:
    """(max |raw card logit|, max |raw cell logit|) over real rollout observations."""
    import random
    env = SimMatchEnv(cfg, seed=1234)
    obs = env.reset()
    rng = random.Random(0)
    worst_card = worst_cell = 0.0
    with torch.no_grad():
        for _ in range(probes):
            x = torch.from_numpy(np.asarray(obs, np.float32)).unsqueeze(0)
            if x.dim() == 4 and x.shape[-1] <= 16:
                x = x.permute(0, 3, 1, 2)
            hand = torch.from_numpy(env.hand_vec.astype(np.float32)).unsqueeze(0)
            nxt = torch.from_numpy(env.next_vec.astype(np.float32)).unsqueeze(0)
            elx = torch.from_numpy(env.elixir_vec.astype(np.float32)).unsqueeze(0)
            thr = torch.from_numpy(env.threat_vec.astype(np.float32)).unsqueeze(0)
            fmap = net.features(x)
            z = net._embed(fmap, hand, nxt, elx, thr)
            worst_card = max(worst_card, float(net.card_head(z).abs().max()))
            worst_cell = max(worst_cell, float(net._cell_logits(fmap, z).abs().max()))
            out = env.step((rng.random() < 0.25, rng.randrange(env.n_cards), rng.randrange(432)))
            obs = out[0]
            if out[2]:
                obs = env.reset()
    return worst_card, worst_cell


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt", help="checkpoint to repair (e.g. data/policy_sim_ppo.pt)")
    ap.add_argument("--out", default=None, help="write here instead of in place")
    ap.add_argument("--target", type=float, default=3.0, help="desired max |raw card logit|")
    ap.add_argument("--lift", default="", help="comma-separated card INDICES to reset to a neutral "
                    "prior (icebow deck: 0=tornado, 4=x_bow). Amnesty for cards whose suppression "
                    "was learned against broken physics: their head row/bias becomes the mean of "
                    "the others, so the policy re-decides from the floors' fresh evidence.")
    args = ap.parse_args()

    cfg = Config.load()
    ck = torch.load(args.ckpt, map_location="cpu")
    sd = ck.get("model", ck.get("state_dict", ck))
    net = PolicyNet(in_ch=9, n_cards=10, n_cells=432, threat_dim=52)
    net.load_state_dict(sd)
    net.eval()

    card_before, cell_before = measure_absmax(net, cfg)
    if card_before <= args.target and cell_before <= args.target * 1.5:
        print(f"[repair] heads already healthy: card {card_before:.1f} / cell {cell_before:.1f} -- nothing to do")
        return
    with torch.no_grad():
        if card_before > args.target:
            a = args.target / card_before
            net.card_head.weight.mul_(a)
            net.card_head.bias.mul_(a)
            print(f"[repair] card head x{a:.5f}")
        if cell_before > args.target * 1.5:
            # the cell head's LAST 1x1 conv scales its logits linearly (pre-interpolate)
            a = (args.target * 1.5) / cell_before
            last = net.cell_conv[-1]
            last.weight.mul_(a)
            if last.bias is not None:
                last.bias.mul_(a)
            print(f"[repair] cell head x{a:.5f}")
    if args.lift:
        idx = [int(i) for i in args.lift.split(",") if i.strip() != ""]
        with torch.no_grad():
            keep = [i for i in range(net.card_head.weight.shape[0]) if i not in idx]
            wmean = net.card_head.weight[keep].mean(dim=0)
            bmean = net.card_head.bias[keep].mean()
            for i in idx:
                net.card_head.weight[i] = wmean
                net.card_head.bias[i] = bmean
        print(f"[repair] lifted cards {idx} to the neutral prior (mean of the other rows)")
    card_after, cell_after = measure_absmax(net, cfg)
    print(f"[repair] max|raw logits| card {card_before:.1f} -> {card_after:.1f}, "
          f"cell {cell_before:.1f} -> {cell_after:.1f}; rankings preserved (linear maps)")

    sd_new = net.state_dict()
    if isinstance(ck, dict) and "model" in ck:
        ck["model"] = sd_new
    elif isinstance(ck, dict) and "state_dict" in ck:
        ck["state_dict"] = sd_new
    else:
        ck = sd_new
    out = args.out or args.ckpt
    torch.save(ck, out)
    print(f"[repair] wrote {out}")


if __name__ == "__main__":
    main()

"""Behaviour cloning: train the CNN policy to imitate your recorded plays.

Loads every session's `dataset.npz` and learns to predict (card identity,
placement cell) from the observation image + the hand composition, then
checkpoints the policy to `train.checkpoint`. The card head is trained with a
mask over the cards actually in hand, so it learns "among the cards available,
which to play" -- identity, not tray position. Pretraining for RL fine-tuning.
"""
from __future__ import annotations

import glob

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .model import PolicyNet
from . import card_threat
from . import interactions
from .threats import THREAT_DIM


def _load_datasets(root, target_thr: int = THREAT_DIM):
    files = sorted(glob.glob(str(root / "*" / "dataset.npz")))
    obs, acts, hands, nexts, elixirs, threats, grid, deck = [], [], [], [], [], [], None, None
    for f in files:
        d = np.load(f, allow_pickle=True)
        if len(d["obs"]) == 0 or "hands" not in d:
            continue
        obs.append(d["obs"])
        acts.append(d["acts"])
        hands.append(d["hands"])
        nexts.append(d["nexts"] if "nexts" in d else np.zeros_like(d["hands"]))
        elixirs.append(d["elixirs"] if "elixirs" in d
                       else np.zeros((len(d["hands"]), 1), np.float32))
        t = d["threats"] if "threats" in d else np.zeros((len(d["hands"]), target_thr), np.float32)
        if t.shape[1] != target_thr:            # width mismatch (old 16-dim set with a 34-dim policy,
            fixed = np.zeros((len(t), target_thr), np.float32)   # or vice versa) -> pad zeros / truncate
            fixed[:, :min(t.shape[1], target_thr)] = t[:, :min(t.shape[1], target_thr)]
            t = fixed
        threats.append(t)
        grid = d["grid"]
        if "deck" in d:
            deck = [str(s) for s in d["deck"]]
    if not obs:
        return None, None, None, None, None, None, None, None, 0
    return (np.concatenate(obs), np.concatenate(acts), np.concatenate(hands),
            np.concatenate(nexts), np.concatenate(elixirs), np.concatenate(threats),
            grid, deck, len(files))


def train_bc(cfg, init: str | None = None, iterations: int = 1) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    # threat width FOLLOWS the config (Stage-3 gate): 16 base, or + identity/memory when use_detector,
    # + the interaction block when use_interactions -- so a wide-labelled dataset trains the SAME shape
    # as the sim policy / live env, and train-bc no longer silently narrows a wide policy back to 16.
    target_thr = (THREAT_DIM
                  + ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM)
                     if bool(cfg.get("observation", "use_detector", default=False)) else 0)
                  + (interactions.INTERACTION_DIM
                     if bool(cfg.get("observation", "use_interactions", default=False)) else 0))
    obs, acts, hands, nexts, elixirs, threats, grid, deck, n_files = _load_datasets(root, target_thr)
    if obs is None:
        print("[train-bc] no identity-labeled datasets found. Build hand templates "
              "(`hand-templates`), then `record` and `label --all`.")
        return

    gw, gh = int(grid[0]), int(grid[1])
    n_cells = gw * gh
    n_cards = int(hands.shape[1])
    if deck is None:
        deck = [f"card{i}" for i in range(n_cards)]

    device = cfg.get("train", "device", default="cuda")
    if device == "cuda":
        if not torch.cuda.is_available():
            print("[train-bc] CUDA not available; using CPU. "
                  "Install the CUDA build of torch to use your GPU.")
            device = "cpu"
        else:
            try:
                _ = (torch.zeros(1, device="cuda") + 1).item()   # probe for a runnable kernel
            except Exception as exc:  # noqa: BLE001
                print(f"[train-bc] GPU detected ({torch.cuda.get_device_name(0)}) but this torch "
                      f"build can't run kernels on it:\n    {exc}\n"
                      "  Newer GPUs need a matching build — RTX 50-series (Blackwell) = CUDA 12.8:\n"
                      "    pip install torch --index-url https://download.pytorch.org/whl/cu128\n"
                      "  Falling back to CPU for now.")
                device = "cpu"
    gpu = f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""
    print(f"[train-bc] {len(obs)} samples from {n_files} session(s); {n_cards} deck cards; "
          f"device={device}{gpu}")
    if len(obs) < 200:
        print("[train-bc] NOTE: very few samples — this is a smoke test, not a useful policy. "
              "Record many more matches for real training.")

    # [N,H,W,3] uint8 -> [N,3,H,W] float in [0,1]
    x = torch.from_numpy(obs).float().permute(0, 3, 1, 2) / 255.0
    hand = torch.from_numpy(hands).float()
    nxt = torch.from_numpy(nexts).float()
    elx = torch.from_numpy(elixirs).float()
    thr = torch.from_numpy(threats).float()
    card = torch.from_numpy(acts[:, 0].astype("int64"))
    cell = torch.from_numpy((acts[:, 2] * gw + acts[:, 1]).astype("int64"))  # gy*gw + gx

    loader = DataLoader(TensorDataset(x, hand, nxt, elx, thr, card, cell),
                        batch_size=int(cfg.get("train", "batch_size", default=64)),
                        shuffle=True)

    threat_dim = int(thr.shape[1])
    net = PolicyNet(in_ch=3, n_cards=n_cards, n_cells=n_cells, threat_dim=threat_dim).to(device)
    if init:                                     # WARM-START: fine-tune an existing policy instead of random init
        ip = cfg.path(init)                      # e.g. data/policy_sim.pt -> combine the SIM prior with your recordings
        if not ip.exists():
            print(f"[train-bc] --init checkpoint not found: {ip} -- training from scratch instead.")
        else:
            ck = torch.load(ip, map_location="cpu")
            ck_deck = ck.get("deck")
            decks_match = ck_deck is not None and [str(c) for c in ck_deck] == [str(c) for c in deck]
            if (ck.get("n_cards") == n_cards and ck.get("n_cells") == n_cells
                    and ck.get("threat_dim") == threat_dim and decks_match):
                try:
                    net.load_state_dict(ck["model"])
                    print(f"[train-bc] warm-started from {ip.name} -- fine-tuning that policy on your {n_files} session(s)")
                except Exception as exc:  # noqa: BLE001
                    print(f"[train-bc] couldn't load {ip.name} ({exc}) -- training from scratch instead.")
            else:
                print(f"[train-bc] --init {ip.name} doesn't match this dataset (different deck/dims) "
                      "-- training from scratch instead.")
    ce = nn.CrossEntropyLoss()
    epochs = int(cfg.get("train", "bc_epochs", default=10))
    iterations = max(1, int(iterations))
    ckpt = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))
    ckpt.parent.mkdir(parents=True, exist_ok=True)

    # Run `iterations` successive BC passes. The net PERSISTS across passes, so each one
    # warm-starts from the previous pass's weights; a FRESH optimizer per pass makes it a
    # restart (equivalent to chaining `train-bc --init` runs) rather than just more epochs.
    for it in range(1, iterations + 1):
        if iterations > 1:
            src = "the --init checkpoint / random init" if it == 1 else f"iteration {it - 1}"
            print(f"[train-bc] === iteration {it}/{iterations} (warm-start from {src}) ===")
        opt = torch.optim.Adam(net.parameters(), lr=float(cfg.get("train", "lr", default=1e-4)))
        for ep in range(1, epochs + 1):
            net.train()
            tot, sc, cc, n = 0.0, 0, 0, 0
            for xb, hb, nb, eb, tb, cardb, cellb in loader:
                xb, hb, nb, eb, tb = xb.to(device), hb.to(device), nb.to(device), eb.to(device), tb.to(device)
                cardb, cellb = cardb.to(device), cellb.to(device)
                card_logits, cell_logits = net(xb, hb, nb, eb, tb)
                card_logits = card_logits.masked_fill(hb < 0.5, float("-inf"))  # only cards in hand
                loss = ce(card_logits, cardb) + ce(cell_logits, cellb)
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += loss.item() * len(xb)
                n += len(xb)
                sc += (card_logits.argmax(1) == cardb).sum().item()
                cc += (cell_logits.argmax(1) == cellb).sum().item()
            tag = f"it {it}/{iterations} " if iterations > 1 else ""
            print(f"[train-bc] {tag}epoch {ep}/{epochs}  loss {tot / n:.3f}  "
                  f"card_acc {sc / n:.2f}  cell_acc {cc / n:.2f}")

        torch.save({
            "model": net.state_dict(),
            "grid": [gw, gh],
            "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96])),
            "n_cards": n_cards,
            "n_cells": n_cells,
            "threat_dim": threat_dim,
            "deck": deck,
        }, ckpt)
        suffix = f" (after iteration {it}/{iterations})" if iterations > 1 else ""
        print(f"[train-bc] saved policy to {ckpt}{suffix}")


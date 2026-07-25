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


def _load_datasets(root):
    files = sorted(glob.glob(str(root / "*" / "dataset.npz")))
    obs, acts, hands, nexts, elixirs, grid, deck = [], [], [], [], [], None, None
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
        grid = d["grid"]
        if "deck" in d:
            deck = [str(s) for s in d["deck"]]
    if not obs:
        return None, None, None, None, None, None, None, 0
    return (np.concatenate(obs), np.concatenate(acts), np.concatenate(hands),
            np.concatenate(nexts), np.concatenate(elixirs), grid, deck, len(files))


def train_bc(cfg) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    obs, acts, hands, nexts, elixirs, grid, deck, n_files = _load_datasets(root)
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
    card = torch.from_numpy(acts[:, 0].astype("int64"))
    cell = torch.from_numpy((acts[:, 2] * gw + acts[:, 1]).astype("int64"))  # gy*gw + gx

    loader = DataLoader(TensorDataset(x, hand, nxt, elx, card, cell),
                        batch_size=int(cfg.get("train", "batch_size", default=64)),
                        shuffle=True)

    net = PolicyNet(in_ch=3, n_cards=n_cards, n_cells=n_cells).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=float(cfg.get("train", "lr", default=1e-4)))
    ce = nn.CrossEntropyLoss()
    epochs = int(cfg.get("train", "bc_epochs", default=10))

    for ep in range(1, epochs + 1):
        net.train()
        tot, sc, cc, n = 0.0, 0, 0, 0
        for xb, hb, nb, eb, cardb, cellb in loader:
            xb, hb, nb, eb = xb.to(device), hb.to(device), nb.to(device), eb.to(device)
            cardb, cellb = cardb.to(device), cellb.to(device)
            card_logits, cell_logits = net(xb, hb, nb, eb)
            card_logits = card_logits.masked_fill(hb < 0.5, float("-inf"))  # only cards in hand
            loss = ce(card_logits, cardb) + ce(cell_logits, cellb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(xb)
            n += len(xb)
            sc += (card_logits.argmax(1) == cardb).sum().item()
            cc += (cell_logits.argmax(1) == cellb).sum().item()
        print(f"[train-bc] epoch {ep}/{epochs}  loss {tot / n:.3f}  "
              f"card_acc {sc / n:.2f}  cell_acc {cc / n:.2f}")

    ckpt = cfg.path(cfg.get("train", "checkpoint", default="data/policy.pt"))
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": net.state_dict(),
        "grid": [gw, gh],
        "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96])),
        "n_cards": n_cards,
        "n_cells": n_cells,
        "deck": deck,
    }, ckpt)
    print(f"[train-bc] saved policy to {ckpt}")


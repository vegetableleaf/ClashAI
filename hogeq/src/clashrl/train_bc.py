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
from torch.utils.data import DataLoader, Subset, TensorDataset

from .model import PolicyNet
from . import card_threat
from . import interactions
from .sim import view
from .threats import THREAT_DIM


def _load_datasets(root, target_thr: int = THREAT_DIM):
    files = sorted(glob.glob(str(root / "*" / "dataset.npz")))
    obs, acts, hands, nexts, elixirs, threats, grid, deck = [], [], [], [], [], [], None, None
    groups = []                     # per-sample SESSION index -- the split has to be group-wise
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
        groups.append(np.full(len(d["obs"]), len(groups), np.int64))
        grid = d["grid"]
        if "deck" in d:
            deck = [str(s) for s in d["deck"]]
    if not obs:
        return None, None, None, None, None, None, None, None, 0, None
    return (np.concatenate(obs), np.concatenate(acts), np.concatenate(hands),
            np.concatenate(nexts), np.concatenate(elixirs), np.concatenate(threats),
            grid, deck, len(files), np.concatenate(groups))



def _demonstrated_cell_logits(all_cell_logits, card_targets):
    """(B, n_cards, n_cells) + the demonstrated card -> that card's placement map, (B, n_cells).

    The cell head emits ONE MAP PER CARD (see PolicyNet.cell_conv). A demonstration has a single
    card and a single cell, so the loss has to be taken against the map of the card that was
    actually played. Without this the 3-D tensor went straight into cross_entropy against a 1-D
    target, and `argmax(1)` -- reported as `cell_acc` -- was an argmax over the CARD axis, so the
    number printed as placement accuracy was not measuring placement at all.

    Every RL, play and eval path was updated when the head changed; this one was missed, and it
    fails quietly rather than loudly, which is why it needs the explicit shape check below.
    """
    if all_cell_logits.dim() != 3:
        raise ValueError("expected per-card cell logits [B, n_cards, n_cells], got %s"
                         % (tuple(all_cell_logits.shape),))
    if card_targets.dim() != 1 or card_targets.shape[0] != all_cell_logits.shape[0]:
        raise ValueError("card targets must be [B] matching the logits batch, got %s vs %s"
                         % (tuple(card_targets.shape), tuple(all_cell_logits.shape)))
    rows = torch.arange(card_targets.shape[0], device=card_targets.device)
    return all_cell_logits[rows, card_targets]


def train_bc(cfg, init: str | None = None, iterations: int = 1, data: str | None = None,
             val_frac: float = 0.0, patience: int = 3, seed: int = 0) -> None:
    # `data` points BC at an alternative dataset root -- notably data/replay_bc, the pro-replay
    # samples mined by `run.py replay-bc`. Same .npz schema, so nothing else changes.
    root = cfg.path(data) if data else cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    # threat width FOLLOWS the config (Stage-3 gate): 16 base, + identity/memory when use_detector,
    # + the interaction block when use_interactions, + the per-tower HP block when use_tower_hp -- so a
    # wide-labelled dataset trains the SAME shape as the sim policy / live env, and train-bc no longer
    # silently narrows a wide policy back down. The tower term MUST match sim/env.py: without it train-bc
    # truncated the replay-mined 52-dim threats to 46 and every BC policy came out shape-incompatible
    # with the (tower-HP-on) simulator, so `train-sim-ppo --init data/policy.pt` could never warm-start.
    target_thr = (THREAT_DIM
                  + ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM)
                     if bool(cfg.get("observation", "use_detector", default=False)) else 0)
                  + (interactions.INTERACTION_DIM
                     if bool(cfg.get("observation", "use_interactions", default=False)) else 0)
                  + (view.TOWER_DIM
                     if bool(cfg.get("observation", "use_tower_hp", default=True)) else 0))
    obs, acts, hands, nexts, elixirs, threats, grid, deck, n_files, groups = _load_datasets(root, target_thr)
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

    # --- ANTI-OVERFIT SPLIT ---------------------------------------------------------------------
    # Mined replay sets are SMALL and detector-noisy, so a big net will happily memorise them and
    # report a beautiful train accuracy while learning a pro's frames rather than a pro's habits.
    # A held-out split makes that visible (the train/val gap is printed) and, with early stopping
    # below, stops the run at the point where the policy still GENERALISES.
    ds = TensorDataset(x, hand, nxt, elx, thr, card, cell)
    batch_size = int(cfg.get("train", "batch_size", default=64))
    val_frac = float(max(0.0, min(0.9, val_frac)))
    n_val = int(len(ds) * val_frac)
    if n_val >= 1 and len(ds) - n_val >= 1:
        # SPLIT BY SESSION, NOT BY FRAME. A random per-sample split puts adjacent frames of the
        # SAME match on both sides: the val set then contains near-duplicates of training frames,
        # val accuracy reads high, and none of it survives contact with a new match. Whole
        # sessions go to one side or the other.
        rng = np.random.default_rng(int(seed))
        uniq = np.unique(groups)
        rng.shuffle(uniq)
        va_groups, taken = set(), 0
        for gid in uniq:                       # take whole sessions until the val fraction is met
            if taken >= n_val or len(va_groups) >= max(1, len(uniq) - 1):
                break
            va_groups.add(int(gid))
            taken += int((groups == gid).sum())
        va_idx = [i for i in range(len(ds)) if int(groups[i]) in va_groups]
        tr_idx = [i for i in range(len(ds)) if int(groups[i]) not in va_groups]
        if not va_idx or not tr_idx:           # single session -> a group split cannot hold out
            tr_idx, va_idx = list(range(len(ds))), []
        print(f"[train-bc] group split: {len(va_groups)} of {len(uniq)} session(s) held out")
        loader = DataLoader(Subset(ds, tr_idx), batch_size=batch_size, shuffle=True)
        val_loader = (DataLoader(Subset(ds, va_idx), batch_size=batch_size, shuffle=False)
                      if va_idx else None)
        print(f"[train-bc] split: {len(tr_idx)} train / {len(va_idx)} val "
              f"({val_frac:.0%} held out, early stop patience {patience})")
    else:
        loader, val_loader = DataLoader(ds, batch_size=batch_size, shuffle=True), None
        if val_frac > 0:
            print("[train-bc] too few samples to hold out a val split -- training without one "
                  "(treat the result as a warm start only).")

    # --- SOFT PLACEMENT TARGETS (spatial_targets.py) --------------------------------------------
    # Exact one-hot on a 432-cell grid calls an equivalent neighbour completely wrong, which is how
    # the placement head keeps collapsing onto one tile. Legal masks are per CARD (rocket/miner may
    # go anywhere; everything else is your half), and the tolerance is per card KIND.
    from .actions import ActionSpace
    from . import spatial_targets as _st
    from .cards import CardDB as _CardDB
    _acts = ActionSpace(cfg)
    _any_ids = {i for i, k in enumerate(deck)
                if (str(k)[:-4] if str(k).endswith("_evo") else str(k)) in ("rocket", "miner")}
    _half = torch.tensor(_acts.deployable_mask(False), dtype=torch.bool)
    _all = torch.tensor(_acts.deployable_mask(True), dtype=torch.bool)
    legal_by_card = torch.stack([_all if i in _any_ids else _half for i in range(n_cards)]).to(device)
    try:
        _sig = _st.sigma_for(_CardDB(cfg), deck)
    except Exception:                                    # noqa: BLE001  (deck not in the KB)
        _sig = [1.0] * n_cards
    sigma_by_card = torch.tensor(_sig, dtype=torch.float32, device=device)
    w_exact = float(cfg.get("train", "exact_cell_loss_weight", default=0.25))
    w_soft = float(cfg.get("train", "soft_cell_loss_weight", default=0.75))
    print(f"[train-bc] placement loss: {w_exact:.2f} exact + {w_soft:.2f} soft "
          f"(sigma by kind, legal-masked)")

    threat_dim = int(thr.shape[1])
    # BC learns from RECORDED frames, so the image width comes from the DATASET rather than the
    # config: a dataset labelled before the obs-canvas flip is still 3-channel and must train a
    # 3-channel net (re-run `label` to rebuild it wide).
    in_ch = int(x.shape[1])
    net = PolicyNet(in_ch=in_ch, n_cards=n_cards, n_cells=n_cells, threat_dim=threat_dim).to(device)
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
        # WEIGHT DECAY: the second anti-overfit lever. On a few hundred detector-noisy replay
        # samples an unregularised net drives train loss to ~0 by memorising individual frames;
        # decay keeps the weights small enough that it has to find the general rule instead.
        opt = torch.optim.Adam(net.parameters(), lr=float(cfg.get("train", "lr", default=1e-4)),
                               weight_decay=float(cfg.get("train", "bc_weight_decay", default=1e-4)))
        best_val, best_state, bad_epochs = float("inf"), None, 0
        for ep in range(1, epochs + 1):
            net.train()
            tot, sc, cc, n = 0.0, 0, 0, 0
            for xb, hb, nb, eb, tb, cardb, cellb in loader:
                xb, hb, nb, eb, tb = xb.to(device), hb.to(device), nb.to(device), eb.to(device), tb.to(device)
                cardb, cellb = cardb.to(device), cellb.to(device)
                card_logits, all_cell_logits = net(xb, hb, nb, eb, tb)
                card_logits = card_logits.masked_fill(hb < 0.5, float("-inf"))  # only cards in hand
                cell_logits = _demonstrated_cell_logits(all_cell_logits, cardb)
                soft = _st.gaussian_spatial_target(cellb, legal_by_card[cardb], gw, gh,
                                                   sigma_by_card[cardb])
                cell_loss = w_exact * ce(cell_logits, cellb) + w_soft * _st.soft_cell_loss(
                    cell_logits, soft)
                loss = ce(card_logits, cardb) + cell_loss
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += loss.item() * len(xb)
                n += len(xb)
                sc += (card_logits.argmax(1) == cardb).sum().item()
                cc += (cell_logits.argmax(1) == cellb).sum().item()
            tag = f"it {it}/{iterations} " if iterations > 1 else ""
            line = (f"[train-bc] {tag}epoch {ep}/{epochs}  loss {tot / n:.3f}  "
                    f"card_acc {sc / n:.2f}  cell_acc {cc / n:.2f}")
            if val_loader is not None:
                net.eval()
                vtot, vsc, vcc, vn = 0.0, 0, 0, 0
                with torch.no_grad():
                    for xb, hb, nb, eb, tb, cardb, cellb in val_loader:
                        xb, hb, nb, eb, tb = (xb.to(device), hb.to(device), nb.to(device),
                                              eb.to(device), tb.to(device))
                        cardb, cellb = cardb.to(device), cellb.to(device)
                        cl, all_ll = net(xb, hb, nb, eb, tb)
                        cl = cl.masked_fill(hb < 0.5, float("-inf"))
                        ll = _demonstrated_cell_logits(all_ll, cardb)   # SAME selection as training
                        vtot += (ce(cl, cardb) + ce(ll, cellb)).item() * len(xb)
                        vn += len(xb)
                        vsc += (cl.argmax(1) == cardb).sum().item()
                        vcc += (ll.argmax(1) == cellb).sum().item()
                vloss = vtot / max(1, vn)
                line += (f"  |  val {vloss:.3f}  card {vsc / max(1, vn):.2f}  "
                         f"cell {vcc / max(1, vn):.2f}  gap {vloss - tot / n:+.3f}")
                print(line)
                # EARLY STOPPING on the held-out loss: the moment val stops improving the net has
                # started fitting this footage rather than learning from it, so we keep the best
                # weights and stop -- the single most important guard when cloning a small set.
                if vloss < best_val - 1e-4:
                    best_val, bad_epochs = vloss, 0
                    best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
                else:
                    bad_epochs += 1
                    if bad_epochs >= int(patience):
                        print(f"[train-bc] early stop at epoch {ep} "
                              f"(val loss has not improved for {patience} epochs; "
                              f"restoring the best weights, val {best_val:.3f})")
                        if best_state is not None:
                            net.load_state_dict(best_state)
                        break
            else:
                print(line)
        if val_loader is not None and best_state is not None:
            net.load_state_dict(best_state)      # always ship the best-generalising weights

        torch.save({
            "model": net.state_dict(),
            "grid": [gw, gh],
            "arena_size": list(cfg.get("observation", "arena_size", default=[64, 96])),
            "n_cards": n_cards,
            "n_cells": n_cells,
            "threat_dim": threat_dim,
            "in_ch": in_ch,
            "deck": deck,
        }, ckpt)
        suffix = f" (after iteration {it}/{iterations})" if iterations > 1 else ""
        print(f"[train-bc] saved policy to {ckpt}{suffix}")


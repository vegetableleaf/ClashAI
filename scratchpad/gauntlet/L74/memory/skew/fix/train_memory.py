"""Plan A S3 (scratchpad/gauntlet/L74/memory/PLAN_A.md): imitation warm-start of ONLY the match-memory adapter.

    python -m pipeline.train_memory --init CKPT --memory v1|v2 --memory-tables gen_dataset_v32_fv5_memory_v1.npz \
        --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --trainable memory --out-dir DIR [--epochs 2] [--amp bf16]

Lead 10-25: the init (an RL policy, e.g. CLXIII) keeps EVERY weight FROZEN; only the new memory parameters (model_gen
MemoryEncoder: event encoder, summary MLP, the zero-init output projection) learn, on the pro rows, how pros' decisions
depend on match history -- a residual on top of the init (S5 RL later fine-tunes everything). So:
  * model = model_gen.load_model(init, memory="v1") (a fresh zero-output encoder: step 0 = the init, asserted on the first
    val batch); requires_grad only for ``mem.*``; the optimizer holds only those (AdamW, linear warm-up + cosine);
  * the model stays in eval() mode the whole run: the frozen trunk runs exactly as in RL / live inference (no dropout);
    gradients still flow THROUGH the trunk to the adapter;
  * loss = train_gen.losses on gate / card / cell (train_gen's weights and masks; wait / value are reported, not trained:
    they are not policy heads), mirror p 0.5 (memory mirrored too: match_memory.mirror_ev);
  * ``--memory v2`` (S1c): the same v1 tables; the summary adds match_memory.S1C_FIELDS (counter priors, cycle, king,
    margin, the frozen lock head), computed from them at feature time;
  * memory inputs per batch: match_memory.rows_features over the per-match tables (dataset_gen memory_tables) at each row's
    tick -- identical to the pro replay's MatchMemory.features (tested), built on CPU in a prefetch thread;
  * after training every frozen tensor (parameters AND buffers) is asserted bit-identical to the init.
Val = the dataset's split 1 (by replay tag), a fixed seed-0 sample of --val-sample rows; every --val-every steps and at the
end: eval_gen.evaluate (the pro-agreement definitions) + the gate / card / cell val loss, each WITH memory, with the memory
inputs ZEROED (an empty memory, same weights) and for the init; best-by-val = lowest val loss with memory. Checkpoints: the
init's own checkpoint dict with the trained weights, ``memory: "v1"`` and an ``s3`` block (mem_best.pt, mem_latest.pt, and
mem_s{step}.pt every --ckpt-every steps). End: two association probes on the val rows of icebow-deck sides (``probes``).
``--head-rows N`` reads only the first N rows of --data (a streamed prefix: laptop tests; the full set needs a pod).

S3-aux (lead 10-25; ``--trainable memory_encoder --aux v1``): the S3 imitation moved the POLICY (its coupling trained) and
that model played far worse in SIM, so this mode trains ONLY the memory encoder (minus the zero-init coupling ``mem.out``)
and the model_gen.MemoryAux prediction heads on future-outcome labels (``AuxLabels``: per own card outcome / cycle, the
opponent's next card / hand / elixir, threat, X-Bow lock, Rocket damage), loss = the sum of each head's loss / its trivial
loss. ``mem.out`` and every base tensor are asserted at init at the end and the policy outputs on the val rows = the init's;
RL (rl_royale ``memory_encoder_frozen``) then freezes the encoder and trains the coupling. No mirror augmentation here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import threading
import time
import zipfile
from pathlib import Path

import numpy as np
import torch

from . import match_memory as MM
from .dataset_gen import checkpoint_gid, load_memory_tables
from .eval_gen import evaluate, val_rows
from .model_gen import load_model
from .train_gen import GenRows, losses

REPO = Path(__file__).resolve().parents[1]
HEADS = ("gate", "card", "cell")
PER_TOKEN = ("tok", "unit_form")
ICEBOW = ("x-bow", "tesla", "ice-wizard", "tornado", "rocket", "knight", "the-log", "skeletons")
REPEAT_T = 400                            # probe (b): "again within 20 s" of the card's last play (ticks)


def npz_head(path: Path, n: int) -> tuple[dict, dict]:
    """The first n rows of a dataset_gen npz (per-token members: their first off[n] tokens), decompressing only each
    member's prefix -- the full fv5 set does not fit a laptop (projectiles alone are 7.2 GB)."""
    z = zipfile.ZipFile(path)

    def read(name, rows):
        with z.open(name + ".npy") as f:
            ver = np.lib.format.read_magic(f)
            shape, fortran, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0)
                                  else np.lib.format.read_array_header_2_0(f))
            rows = shape[0] if rows is None else min(rows, shape[0])
            per = int(np.prod(shape[1:], dtype=np.int64))
            return np.frombuffer(f.read(rows * per * dt.itemsize), dt).reshape((rows,) + tuple(shape[1:])).copy()
    off = read("off", n + 1)
    arrs = {"off": off}
    for k in (i.filename[:-4] for i in z.infolist()):
        if k not in ("off", "meta", "tags"):
            arrs[k] = read(k, int(off[-1]) if k in PER_TOKEN else n)
    with z.open("meta.npy") as f:
        meta = json.loads(str(np.load(f)))
    return arrs, meta


def freeze(model) -> dict:
    """Only ``mem.*`` trains; -> a copy of every other tensor (parameters + buffers) for the bit-identity check."""
    for k, p in model.named_parameters():
        p.requires_grad_(k.startswith("mem."))
    return {k: v.detach().clone() for k, v in model.state_dict().items() if not k.startswith("mem.")}


def frozen_unchanged(model, snap: dict) -> list:
    """The frozen tensors that differ from the snapshot (bitwise) -- must be []."""
    sd = model.state_dict()
    return [k for k, v in snap.items() if not torch.equal(sd[k], v)]


def batches(rows, perm, bs, prefetch):
    """rows.batch over ``perm`` in order, built ``prefetch`` batches ahead in a thread (CPU table features overlap the GPU)."""
    chunks = [perm[s:s + bs] for s in range(0, len(perm) - bs + 1, bs)]
    if prefetch <= 0:
        for c in chunks:
            yield rows.batch(c)
        return
    q: queue.Queue = queue.Queue(maxsize=prefetch)

    def work():
        try:
            for c in chunks:
                q.put(rows.batch(c))
        except BaseException as exc:                              # surfaced in the consumer
            q.put(exc)
        q.put(None)
    threading.Thread(target=work, daemon=True).start()
    while (b := q.get()) is not None:
        if isinstance(b, BaseException):
            raise b
        yield b


@torch.no_grad()
def val_loss(model, rows, bs=512, rocket_context_weight=1.0) -> dict:
    tot, parts, n = 0.0, {}, 0
    for s in range(0, len(rows.idx), bs):
        b = rows.batch(rows.idx[s:s + bs])
        loss, p = losses(model, b, mirror=False, grid=rows.grid, rocket_context_weight=rocket_context_weight, heads=HEADS)
        k = len(b["gate"])
        tot, n = tot + float(loss) * k, n + k
        for key, v in p.items():
            parts[key] = parts.get(key, 0.0) + v * k
    return {"loss": tot / max(n, 1), **{f"loss_{k}": v / max(n, 1) for k, v in parts.items()}}


def scores(model, base, rows, tables, rocket_context_weight=1.0) -> dict:
    """eval_gen.evaluate + val loss for: the memory model WITH memory, with the memory inputs ZEROED, and the init."""
    out = {}
    for name, net, mem in (("memory", model, tables), ("zeroed", model, "empty"), ("init", base, None)):
        rows.memory = mem
        out[name] = {**evaluate(net, rows, grid=rows.grid), **val_loss(net, rows, rocket_context_weight=rocket_context_weight)}
    rows.memory = tables
    return out


@torch.no_grad()
def probes(model, base, rows, tables, arrs, gid, bs=512) -> dict:
    """Two association probes on ``rows`` (val rows; restricted here to icebow-deck sides), for the init, the memory model
    with its memory and with the memory zeroed:
      (a) X-Bow propensity: on PLAY rows whose side has >= 2 FAILED own reach X-Bows earlier in the match (the memory
          summary at the row), mean P(card = X-Bow) (the model's hand-position softmax mass on the X-Bow; 0 if not in
          hand) vs the pros' rate of playing it; the same for rows with 0 failures (contrast);
      (b) repeat after a bad outcome: per own card c, on rows where c is in hand and c's LAST own play (visible at the row)
          is resolved, tower-swing known and played <= 20 s ago: the per-row play propensity of c -- model P(gate) x
          P(card = c), pro 1[played c] -- split by that play's swing < 0 (bad) vs >= 0.
    Per-decision-row rates (wait rows every 40 ticks + play rows), not per-episode probabilities; association only."""
    ice = sorted(gid[k] for k in ICEBOW)
    idx = np.asarray(rows.idx)
    sel = idx[np.all(np.sort(arrs["deck_card"][idx].astype(np.int64), 1) == np.asarray(ice), 1)] if len(idx) else idx
    res = {"rows_icebow": int(len(sel))}
    if not len(sel):
        return res
    xb = gid["x-bow"]
    packed, row_tab, row_t = tables
    E = MM.gather_rows(packed, np.asarray(row_tab)[sel])
    t = np.asarray(row_t)[sel].astype(np.int64)[:, None]
    vals, tick, res1 = E["vals"], E["tick"].astype(np.int64), E["res"][..., 1].astype(np.int64)
    own = (vals[..., MM._COL["is_play"]] == 1) & (vals[..., MM._COL["mine"]] == 1) & (t >= E["vis"])
    fails = np.round(MM.rows_features(packed, row_tab, row_t, arrs["deck_card"], sel)["mem_summary"][:, 3] * 10)
    hand = arrs["hand_card"][sel].astype(np.int64)
    play = arrs["y_gate"][sel] == 1
    ycard = arrs["y_card"][sel].astype(np.int64)
    outs = {}
    for name, net, mem in (("init", base, None), ("memory", model, tables), ("zeroed", model, "empty")):
        rows.memory = mem
        g, pc = [], []
        for s in range(0, len(sel), bs):
            b = rows.batch(sel[s:s + bs])
            o = net(b)
            g.append(torch.sigmoid(o["gate"]).double().cpu().numpy())
            pc.append(torch.softmax(o["card"].double(), -1).cpu().numpy())
        outs[name] = (np.concatenate(g), np.concatenate(pc))
    rows.memory = tables
    p_xb = {k: (pc * (hand == xb)).sum(1) for k, (_, pc) in outs.items()}
    for grp, m in (("fails_ge2", play & (fails >= 2)), ("fails_0", play & (fails == 0))):
        res[f"xbow_{grp}"] = {"n": int(m.sum()), "pro": float((ycard[m] == xb).mean()) if m.any() else None,
                              **{k: float(v[m].mean()) if m.any() else None for k, v in p_xb.items()}}
    rep = {}
    for c in ice:
        mine = own & (E["card"].astype(np.int64) == c)
        last = np.where(mine, np.arange(mine.shape[1])[None], -1).max(1)
        ok = last >= 0
        li = np.maximum(last, 0)[:, None]
        lt = np.take_along_axis(tick, li, 1)[:, 0]
        known = np.take_along_axis(vals[..., MM._COL["out_tower_known"]], li, 1)[:, 0] == 1
        swing = np.take_along_axis(E["swing"], li, 1)[:, 0]
        inhand = (hand == c).any(1)
        base_m = ok & inhand & known & (t[:, 0] >= np.take_along_axis(res1, li, 1)[:, 0]) & (t[:, 0] - lt <= REPEAT_T)
        name = next(k for k, v in gid.items() if v == c)
        rep[name] = {}
        for grp, m in (("bad", base_m & (swing < 0)), ("not_bad", base_m & (swing >= 0))):
            pro = play & (ycard == c)
            rep[name][grp] = {"n": int(m.sum()), "pro": float(pro[m].mean()) if m.any() else None,
                              **{k: float((g * (pc * (hand == c)).sum(1))[m].mean()) if m.any() else None
                                 for k, (g, pc) in outs.items()}}
    res["repeat_after_bad"] = rep
    return res


def save(path: Path, init_ck: dict, model, info: dict) -> None:
    ver = getattr(model.mem, "version", "v1")
    ck = dict(init_ck, model={k: v.detach().cpu() for k, v in model.state_dict().items()}, memory=ver, s3=info,
              **({"memory_v2": MM.v2_meta()} if ver == "v2" else {}),
              **({"memory_aux": "v1"} if getattr(model, "mem_aux", None) is not None else {}))
    tmp = path.with_name(path.name + ".tmp")
    torch.save(ck, tmp)
    tmp.replace(path)


# ------------------------------------------------------------------------------------------------------------ S3-aux
# --trainable memory_encoder --aux v1: the memory encoder (minus its zero-init coupling mem.out) + the model_gen MemoryAux
# heads learn ONLY the aux prediction losses below; mem.out and every base tensor stay at init, so the policy = the init's.
AUX_W = 200                 # ticks: the 10 s label windows (= match_memory.W_OUT)
KEY = 1 << 23               # event / row sort key = table (or replay-side) x KEY + tick
REG = ("swing", "vpe", "cyc_el", "opp_el10", "opp_el_now", "threat", "commit", "rk_dmg")   # standardised MSE heads
BIN = ("opp_hand", "xb_lock")                                                                  # BCE heads
CLS = ("cyc", "opp_next")                                                                      # CE heads
AUX_HEADS = REG + BIN + CLS


class AuxLabels:
    """S3-aux labels per dataset row (tick t, its side's memory table ``row_tab``), every one from AFTER t; the memory inputs
    see only events visible at t (vis <= t, match_memory causality), so no label is an input. From the tables (TABLE_KEYS) +
    the npz, no rebuild:
      own play at t (PLAY rows: the table's own play with tick t and card y_card; ``slot`` = its deck position): swing / vpe
          (that play's 10 s outcome, where known), xb_lock (an own REACH X-Bow, resolved: xb_locked), rk_dmg (an own Rocket,
          tower damage known: rk_tl);
      cyc / cyc_el [8]: per own deck card, own plays in [t, t') and their elixir, t' = this side's first row at or after t
          whose TRUE hand (npz hand_card) holds the card (0 = in hand now); classes clipped at model_gen.AUX_CYC - 1;
      opp_next: the opponent's first play with tick >= t (card id; 0 = outside the vocabulary: masked);
      opp_hand [8]: per opp_cycle slot (their revealed cards, an input), in the opponent's TRUE hand at t = the other side's
          npz row at the same (replay, tick) (no such row = masked);
      opp_el_now: the opponent's TRUE elixir at t (that row's own sc[3] x 10, where its exact flag sc[4] is set); the
          observer estimate sc[5] is an input, never a label;
      opp_el10 / commit / threat: opponent elixir played in [t, t + 10 s) (all / at own-frame y > 0.5 = on our side) and our
          tower HP lost (recorded tower_damage, HP fractions) in the window; masked when t + 10 s passes the replay's last row.
    Arrays are numpy [rows]; NaN / -1 = no label."""

    def __init__(self, arrs, packed, row_tab, gid, n_cards):
        from .model_gen import AUX_CYC
        C = MM._COL
        self.n_cards = n_cards
        n = len(arrs["tick"])
        t = arrs["tick"].astype(np.int64)
        tab = np.asarray(row_tab[:n], np.int64)
        vals = packed["vals"]
        etick = packed["tick"].astype(np.int64)
        off = np.asarray(packed["off"], np.int64)
        etab = np.repeat(np.arange(len(off) - 1), np.diff(off))
        ekey = etab * KEY + etick                               # chronological per table, tables in order: sorted
        if len(ekey) > 1 and (np.diff(ekey) < 0).any():
            raise ValueError("memory tables are not in (table, tick) order")
        play, mine = vals[:, C["is_play"]] == 1, vals[:, C["mine"]] == 1
        cost = np.round(vals[:, C["cost_10"]].astype(np.float64) * 10, 1)
        ecard = packed["card"].astype(np.int64)
        has = tab >= 0
        lo = np.where(has, tab * KEY + t, -1)

        def wsum(m, x, a, b):                                   # sum of x over the events m with key in [a, b)
            k = ekey[m]
            c = np.concatenate([[0.0], np.cumsum(np.broadcast_to(np.asarray(x, np.float64), m.shape)[m])])
            return c[np.searchsorted(k, b)] - c[np.searchsorted(k, a)]

        rep, side = arrs["rep"].astype(np.int64), arrs["side"].astype(np.int64)
        end = np.full(int(rep.max()) + 1 if n else 1, -1, np.int64)
        np.maximum.at(end, rep, t)
        win = has & (t + AUX_W <= end[rep])
        hi = np.where(has, tab * KEY + t + AUX_W, -1)
        own, opp = play & mine, play & ~mine
        nan = np.full(n, np.nan)
        self.opp_el10 = np.where(win, wsum(opp, cost, lo, hi), nan)
        ys = (vals[:, C["xy_known"]] == 1) & (vals[:, C["y"]] > 0.5)
        self.commit = np.where(win, wsum(opp & ys, cost, lo, hi), nan)
        dmg = (vals[:, C["is_tower_damage"]] == 1) & mine
        self.threat = np.where(win, wsum(dmg, vals[:, C["tower_lost"]], lo, hi), nan)
        ok = np.flatnonzero(opp)                                # the opponent's next play
        self.opp_next = np.full(n, -1, np.int64)
        if len(ok):
            j = np.searchsorted(ekey[ok], lo)
            oi = ok[np.minimum(j, len(ok) - 1)]
            good = has & (j < len(ok)) & (etab[oi] == tab) & (ecard[oi] > 0)
            self.opp_next = np.where(good, ecard[oi], -1)
        y = arrs["y_card"].astype(np.int64)                     # the own play at t (play rows)
        pr = (arrs["y_gate"] == 1) & has
        ow = np.flatnonzero(own)
        ev = np.full(n, -1, np.int64)
        if len(ow):
            j = np.searchsorted(ekey[ow], lo)
            for d in range(4):                                  # same-tick own plays: the one with this card
                e = ow[np.minimum(j + d, len(ow) - 1)]
                hit = pr & (ev < 0) & (j + d < len(ow)) & (ekey[e] == lo) & (ecard[e] == y)
                ev = np.where(hit, e, ev)
        dc = arrs["deck_card"].astype(np.int64)
        ind = dc == y[:, None]
        ev = np.where(ind.any(1), ev, -1)
        self.slot = np.where(ev >= 0, ind.argmax(1), -1)
        self.play_rows, self.play_found = int(pr.sum()), int((ev >= 0).sum())
        e = np.maximum(ev, 0)
        v = vals[e]
        f = ev >= 0
        self.swing = np.where(f & (v[:, C["out_tower_known"]] == 1) & win, packed["swing"][e], nan)
        self.vpe = np.where(f & (v[:, C["out_value_known"]] == 1) & (cost[e] > 0) & win, packed["vpe"][e], nan)
        xb, rk = gid.get("x-bow", -9), gid.get("rocket", -9)
        self.xb_lock = np.where(f & (y == xb) & (v[:, C["xb_reach"]] == 1) & (v[:, C["xb_done"]] == 1),
                                v[:, C["xb_locked"]].astype(np.float64), nan)
        self.rk_dmg = np.where(f & (y == rk) & (v[:, C["rk_done"]] == 1) & (v[:, C["rk_tower_known"]] == 1),
                               packed["rk_tl"][e], nan)
        # own cycle: this side's first row at / after t whose true hand holds the card
        hand = arrs["hand_card"].astype(np.int64)
        order = np.lexsort((np.arange(n), t, tab))
        ts, tbs = t[order], tab[order]
        last = np.r_[tbs[1:] != tbs[:-1], True] if n else np.zeros(0, bool)
        gend = np.minimum.accumulate(np.where(last, np.arange(n), n)[::-1])[::-1] + 1     # group end (exclusive)
        self.cyc = np.full((n, 8), -1, np.int8)
        self.cyc_el = np.full((n, 8), np.nan)
        for k in range(8):
            ih = ((dc[:, k:k + 1] == hand).any(1) & (dc[:, k] > 0))[order]
            nx = np.minimum.accumulate(np.where(ih, np.arange(n), n)[::-1])[::-1]
            okk = (nx < gend) & (tbs >= 0) & (dc[order, k] > 0)
            a = tbs * KEY + ts
            b = np.where(okk, tbs * KEY + ts[np.minimum(nx, n - 1)], a)
            self.cyc[order, k] = np.where(okk, np.minimum(wsum(own, 1.0, a, b), AUX_CYC - 1), -1)
            self.cyc_el[order, k] = np.where(okk, wsum(own, cost, a, b), np.nan)
        # opponent truth: the other side's row at the same (replay, tick)
        kself = (rep * 2 + side) * KEY + t
        so = np.argsort(kself, kind="stable")
        kopp = (rep * 2 + 1 - side) * KEY + t
        pair = np.full(n, -1, np.int64)
        if n:
            j = np.minimum(np.searchsorted(kself[so], kopp), n - 1)
            pair = np.where(kself[so][j] == kopp, so[j], -1)
        self.pair_rows = int((pair >= 0).sum())
        pp = np.maximum(pair, 0)
        sc = arrs["sc"]
        self.opp_el_now = np.where((pair >= 0) & (sc[pp, 4] > 0.5), sc[pp, 3].astype(np.float64) * 10, nan)
        oc = arrs["opp_cycle"][..., 0].astype(np.int64)
        inh = (oc[:, :, None] == hand[pp][:, None, :]).any(-1)
        self.opp_hand = np.where((pair >= 0)[:, None] & (oc > 0), inh, -1).astype(np.int8)

    def batch(self, ids, dev) -> dict:
        ids = np.asarray(ids)
        out = {}
        for k in REG + BIN + CLS + ("slot",):
            v = getattr(self, k)[ids]
            out["aux_" + k] = torch.as_tensor(v.astype(np.float32) if v.dtype.kind == "f" else v.astype(np.int64)).to(dev)
        return out

    def coverage(self) -> dict:
        c = {k: int(np.isfinite(getattr(self, k)).sum()) for k in REG + ("xb_lock",)}
        c.update(cyc=int((self.cyc >= 0).sum()), opp_hand=int((self.opp_hand >= 0).sum()),
                 opp_next=int((self.opp_next >= 0).sum()), play_rows=self.play_rows, play_found=self.play_found,
                 pair_rows=self.pair_rows, rows=int(len(self.slot)))
        return c

    def stats(self, ids) -> dict:
        """Train-row label statistics: mean / std (REG), base rate (BIN), class prior (CLS) -> the trivial predictors and the
        loss normalisers (a head's loss / its trivial loss, so every head starts near 1)."""
        from .model_gen import AUX_CYC
        st = {}
        for k in REG:
            x = getattr(self, k)[ids].ravel()
            x = x[np.isfinite(x)]
            st[k] = {"n": int(len(x)), "mean": float(x.mean()) if len(x) else 0.0,
                     "std": max(float(x.std()) if len(x) > 1 else 1.0, 1e-6)}
        for k in BIN:
            x = getattr(self, k)[ids].ravel().astype(np.float64)
            x = x[np.isfinite(x) & (x >= 0)]
            p = float(np.clip(x.mean() if len(x) else 0.5, 1e-4, 1 - 1e-4))
            st[k] = {"n": int(len(x)), "p": p, "H": float(-(p * np.log(p) + (1 - p) * np.log(1 - p)))}
        for k, nc in (("cyc", AUX_CYC), ("opp_next", self.n_cards)):
            x = getattr(self, k)[ids].ravel().astype(np.int64)
            x = x[x >= 0]
            pri = np.bincount(x, minlength=nc)[:nc].astype(np.float64)
            st[k] = {"n": int(len(x)), "majority": int(pri.argmax())}
            pri = (pri + 0.5) / (pri + 0.5).sum()
            st[k]["H"] = float(-(pri * np.log(pri)).sum())
        return st


def _pred(out, b):
    """The prediction tensor of every REG / BIN head for this batch (own-card heads at the played card's slot)."""
    from .model_gen import AUX_OWN
    io = {k: i for i, k in enumerate(AUX_OWN)}
    slot = b["aux_slot"]
    r = torch.arange(len(slot), device=slot.device)
    p = {k: out["own"][r, slot.clamp(min=0), io[k]] for k in ("swing", "vpe")}
    p["cyc_el"] = out["own"][..., io["cyc_el"]]
    p.update({k: out[k] for k in ("opp_el10", "opp_el_now", "threat", "commit", "rk_dmg", "xb_lock", "opp_hand")})
    p["cyc"] = out["own"][..., io["cyc0"]:io["cyc0"] + sum(k.startswith("cyc") and k[3:].isdigit() for k in AUX_OWN)]
    p["opp_next"] = out["opp_next"]
    return p


def _mask(b, k):
    y = b["aux_" + k]
    if k in REG or k == "xb_lock":
        m = torch.isfinite(y)
        return m & (b["aux_slot"] >= 0) if k in ("swing", "vpe") else m
    return y >= 0


def aux_terms(out: dict, b: dict, st: dict) -> dict:
    """Per head: the normalised loss (None = no labelled target in the batch). REG: MSE on the standardised target (trivial
    = 1); BIN: BCE / H(train base rate); CLS: CE / H(train prior). Labels are masked, never imputed."""
    import torch.nn.functional as Fn
    p = _pred(out, b)
    terms = {}
    for k in AUX_HEADS:
        m = _mask(b, k)
        if not m.any():
            terms[k] = None
            continue
        y, q = b["aux_" + k][m], p[k][m].float()
        if k in REG:
            terms[k] = ((q - (y - st[k]["mean"]) / st[k]["std"]) ** 2).mean()
        elif k in BIN:
            terms[k] = Fn.binary_cross_entropy_with_logits(q, y.float()) / st[k]["H"]
        else:
            terms[k] = Fn.cross_entropy(q, y) / st[k]["H"]
    return terms


def aux_forward(model, base, b):
    """ctx = the frozen base trunk's global output (no grad; = the memory model's own: its coupling is zero), then the heads."""
    with torch.no_grad():
        ctx = base.encode_gen(b)["g"]
    return model.memory_aux_out(b, ctx)


def aux_loss(model, base, b, st):
    terms = aux_terms(aux_forward(model, base, b), b, st)
    use = [v for v in terms.values() if v is not None]
    return (sum(use) if use else None), {k: (float(v.detach()) if v is not None else None) for k, v in terms.items()}


def _auc(score, y):
    """Mann-Whitney AUC (ties averaged); None without both classes."""
    from scipy.stats import rankdata
    y = np.asarray(y) > 0.5
    if y.all() or not y.any():
        return None
    r = rankdata(score)
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


@torch.no_grad()
def aux_eval(model, base, rows, lab, st, bs=512) -> dict:
    """Per-head val metrics vs the trivial predictor (train mean / base rate / majority class): REG r2 (trivial 0); BIN auc
    (trivial 0.5) and acc vs trivial_acc; CLS acc vs trivial_acc, cyc also on the QUEUE cards (not in hand, not next: the
    part the hand flags do not give away). ``loss`` = the mean over batches of the summed normalised losses."""
    got = {k: [] for k in AUX_HEADS}
    queue = []
    tot, nb = 0.0, 0
    for s in range(0, len(rows.idx), bs):
        ids = rows.idx[s:s + bs]
        b = rows.batch(ids)
        b.update(lab.batch(ids, rows.dev))
        out = aux_forward(model, base, b)
        tot += sum(float(v) for v in aux_terms(out, b, st).values() if v is not None)
        nb += 1
        p = _pred(out, b)
        for k in AUX_HEADS:
            m = _mask(b, k)
            q = p[k][m].float()
            got[k].append(((q.argmax(-1) if k in CLS else q).cpu().numpy(), b["aux_" + k][m].cpu().numpy()))
        dc = b["deck_card"]
        q = ~((dc.unsqueeze(-1) == b["hand_card"].unsqueeze(1)).any(-1) | (dc == b["next_card"].unsqueeze(-1)))
        queue.append(q[_mask(b, "cyc")].cpu().numpy())
    res = {"loss": tot / max(nb, 1)}
    for k in AUX_HEADS:
        p = np.concatenate([g[0] for g in got[k]]) if got[k] else np.zeros(0)
        y = np.concatenate([g[1] for g in got[k]]) if got[k] else np.zeros(0)
        r = {"n": int(len(y))}
        if len(y) and k in REG:
            z = (y - st[k]["mean"]) / st[k]["std"]
            mse, triv = float(((p - z) ** 2).mean()), float((z ** 2).mean())
            r.update(mse_std=mse, trivial_mse_std=triv, r2=1 - mse / triv if triv > 0 else None)
        elif len(y) and k in BIN:
            r.update(auc=_auc(p, y), acc=float(((p > 0) == (y > 0.5)).mean()),
                     trivial_acc=float(((st[k]["p"] > 0.5) == (y > 0.5)).mean()))
        elif len(y):
            r.update(acc=float((p == y).mean()), trivial_acc=float((y == st[k]["majority"]).mean()))
            if k == "cyc":
                qq = np.concatenate(queue)
                if qq.any():
                    maj = int(np.bincount(y[qq].astype(np.int64)).argmax())   # the VAL majority: a generous baseline
                    r.update(queue_n=int(qq.sum()), queue_acc=float((p[qq] == y[qq]).mean()),
                             queue_trivial_acc=float((y[qq] == maj).mean()))
        res[k] = r
    return res


def _aux_trainable(k: str) -> bool:
    return (k.startswith("mem.") and not k.startswith("mem.out.")) or k.startswith("mem_aux.")


def freeze_aux(model) -> dict:
    """S3-aux: only mem.* minus the coupling mem.out.*, and mem_aux.*, train; -> a copy of every other tensor."""
    for k, p in model.named_parameters():
        p.requires_grad_(_aux_trainable(k))
    return {k: v.detach().clone() for k, v in model.state_dict().items() if not _aux_trainable(k)}


@torch.no_grad()
def policy_identity(model, base, rows, bs=512) -> dict:
    """Max |memory model - base| over gate / card / value / cell on ``rows`` (zero coupling: exactly 0 on CPU)."""
    diff, scale = 0.0, 0.0
    for s in range(0, len(rows.idx), bs):
        b = rows.batch(rows.idx[s:s + bs])
        o1, o0 = model(b, card=b["card"], form=b["form"]), base(b, card=b["card"], form=b["form"])
        for k in ("gate", "card", "value", "cell"):
            f = torch.isfinite(o0[k])
            if not torch.equal(f, torch.isfinite(o1[k])):
                return {"max_diff": float("inf"), "scale": scale, "rows": int(len(rows.idx))}
            if f.any():
                diff = max(diff, float((o1[k][f] - o0[k][f]).abs().max()))
                scale = max(scale, float(o0[k][f].abs().max()))
    return {"max_diff": diff, "scale": scale, "rows": int(len(rows.idx))}


def _brief(ev):
    keep = ("r2", "auc", "acc", "trivial_acc", "queue_acc", "queue_trivial_acc")
    return {k: {m: (round(x, 4) if isinstance(x, float) else x) for m, x in (ev.get(k) or {}).items() if m in keep}
            for k in AUX_HEADS}


def train_aux(a, model, base, rows, va, va_idx, tr, tables, arrs, meta, init_ck, rng, dev, t0) -> int:
    from .dataset_gen import checkpoint_gid
    if a.aux != "v1":
        raise SystemExit("--trainable memory_encoder needs --aux v1")
    model.add_memory_aux()
    snap = freeze_aux(model)
    if float(model.mem.out.weight.abs().max()) != 0 or float(model.mem.out.bias.abs().max()) != 0:
        raise SystemExit("the memory coupling mem.out is not zero at start")
    tl0 = time.time()
    lab = AuxLabels(arrs, tables[0], tables[1], checkpoint_gid(meta["card_vocab"]), model.n_cards)
    st = lab.stats(tr)
    cov = {**lab.coverage(), "seconds": round(time.time() - tl0, 1)}
    nx = (lab.cyc >= 0) & (arrs["deck_card"] == arrs["next_card"][:, None]) & (arrs["deck_card"] > 0)
    cov["next_card_cyc1_share"] = float((lab.cyc[nx] == 1).mean()) if nx.any() else None      # sanity: ~1
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=a.wd)
    steps = a.steps if a.steps > 0 else max(int(round(a.epochs * (len(tr) // a.bs))), 1)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(a.warmup, 1)) * 0.5 * (
        1 + math.cos(math.pi * min(s, steps) / steps)))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    info = {"init": str(a.init), "init_sha256": hashlib.sha256(a.init.read_bytes()).hexdigest(),
            "memory_tables": str(a.memory_tables), "data": str(a.data), "head_rows": a.head_rows, "train_rows": int(len(tr)),
            "val_rows": int(len(va_idx)), "steps": steps, "bs": a.bs, "lr": a.lr, "wd": a.wd, "warmup": a.warmup,
            "amp": a.amp, "trainable": "memory_encoder", "aux": a.aux, "n_trainable": int(sum(p.numel() for p in params)),
            "seed": a.seed, "memory": a.memory, "mirror": False, "label_stats": st, "label_coverage": cov,
            # the loss is sum_h loss_h / trivial_h: REG already standardised (weight 1), BIN / CLS divided by H
            "head_weights": {k: (1.0 if k in REG else round(1.0 / st[k]["H"], 5)) for k in AUX_HEADS}}
    log = (a.out_dir / "s3_log.jsonl").open("a", encoding="utf-8")

    def emit(rec):
        print(json.dumps(rec), flush=True)
        log.write(json.dumps(rec) + "\n")
        log.flush()
    emit({"step": 0, "label_coverage": cov, "head_weights": info["head_weights"], "n_trainable": info["n_trainable"]})
    if len(va_idx):
        emit({"step": 0, "policy_identity": policy_identity(model, base, va.view(va_idx[:min(256, len(va_idx))]))})
    amp = a.amp == "bf16" and dev.type == "cuda"

    class _Rows:                                              # rows.batch + this batch's labels (in the prefetch thread)
        def batch(self, ids):
            b = rows.batch(ids)
            b.update(lab.batch(ids, dev))
            return b
    best, step, ep, hist = math.inf, 0, 0, []
    tl, sl = time.time(), 0
    while step < steps:
        for b in batches(_Rows(), rng.permutation(tr), a.bs, a.prefetch):
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                loss, parts = aux_loss(model, base, b, st)
            if loss is None:
                continue
            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
            opt.step()
            sched.step()
            step += 1
            if step % 50 == 0 or step == steps:
                emit({"step": step, "epoch": ep, "loss": float(loss.detach()),
                      **{f"p_{k}": (round(v, 5) if v is not None else None) for k, v in parts.items()},
                      "grad_norm": round(gn, 4), "lr": sched.get_last_lr()[0],
                      "s_per_step": round((time.time() - tl) / max(step - sl, 1), 4)})
                tl, sl = time.time(), step
            if len(va_idx) and (step % a.val_every == 0 or step == steps):
                ev_m = aux_eval(model, base, va, lab, st)
                va.memory = "empty"                           # the same heads with an EMPTY memory: what memory adds
                ev_z = aux_eval(model, base, va, lab, st)
                va.memory = tables
                hist.append({"step": step, "memory": ev_m, "zeroed": ev_z})
                emit({"step": step, "val_loss": {"memory": round(ev_m["loss"], 5), "zeroed": round(ev_z["loss"], 5)},
                      "val": _brief(ev_m), "val_zeroed": _brief(ev_z)})
                if ev_m["loss"] < best:
                    best = ev_m["loss"]
                    save(a.out_dir / "mem_best.pt", init_ck, model, {**info, "step": step, "val": ev_m, "val_zeroed": ev_z})
                tl, sl = time.time(), step
            if step % a.ckpt_every == 0:
                save(a.out_dir / f"mem_s{step}.pt", init_ck, model, {**info, "step": step})
                tl, sl = time.time(), step
            if step >= steps:
                break
        ep += 1
    save(a.out_dir / "mem_latest.pt", init_ck, model, {**info, "step": step})
    bad = frozen_unchanged(model, snap)
    if bad:
        raise SystemExit(f"FROZEN WEIGHTS CHANGED: {bad[:5]} (+{max(0, len(bad) - 5)})")
    if float(model.mem.out.weight.abs().max()) != 0 or float(model.mem.out.bias.abs().max()) != 0:
        raise SystemExit("the zero-init coupling mem.out moved off zero")
    pid = policy_identity(model, base, va) if len(va_idx) else {}
    if pid and pid["max_diff"] > 1e-6 * max(1.0, pid["scale"]):     # GPU: a few ulp (see main's step-0 check); CPU: 0
        raise SystemExit(f"policy outputs differ from the base on the val rows: {pid}")
    final = {"FINAL": True, "steps": step, "frozen_tensors_unchanged": len(snap), "coupling_zero": True,
             "policy_identity_val": pid, "best_val_loss": best, "hist": hist, "seconds": round(time.time() - t0, 1), **info}
    (a.out_dir / "s3_final.json").write_text(json.dumps(final, indent=1), encoding="utf-8")
    emit({k: v for k, v in final.items() if k not in ("hist", "label_stats")})
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--init", type=Path, required=True, help="a feature_version >= 4 generalist checkpoint (e.g. CLXIII)")
    ap.add_argument("--memory", choices=("v1", "v2"), required=True)
    ap.add_argument("--memory-tables", type=Path, required=True, help="dataset_gen memory_tables' file for --data")
    ap.add_argument("--data", type=Path, default=REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--trainable", choices=("memory", "memory_encoder"), required=True,
                    help="memory = S3 imitation (gate / card / cell) of every mem.* weight; memory_encoder (with --aux v1) = "
                         "S3-aux: the encoder minus its zero-init coupling + the aux heads, aux losses only (policy = init)")
    ap.add_argument("--aux", choices=("v1",), default=None, help="S3-aux heads (model_gen.MemoryAux); needs memory_encoder")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--steps", type=int, default=0, help="> 0 overrides --epochs")
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--wd", type=float, default=0.01)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--amp", choices=("none", "bf16"), default="none")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--zero-empty", action="store_true", help="the adapter's no-offset form (model_gen MemoryEncoder "
                    "zero_empty): an EMPTY memory adds exactly 0, so no memory-independent offset is learned (skew 10-25)")
    ap.add_argument("--val-sample", type=int, default=30000)
    ap.add_argument("--val-every", type=int, default=2000)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--prefetch", type=int, default=4)
    ap.add_argument("--head-rows", type=int, default=0, help="read only the first N rows of --data (laptop tests)")
    ap.add_argument("--limit-rows", type=int, default=0, help="a seeded random N of the train rows")
    ap.add_argument("--probe-rows", type=int, default=0, help="cap the val rows the probes read (0 = every val row)")
    ap.add_argument("--rocket-context-weight", type=float, default=None)
    ap.add_argument("--rocket-context-artifact", type=Path, default=None)
    ap.add_argument("--device", default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if (a.trainable == "memory_encoder") != (a.aux is not None):
        raise SystemExit("--trainable memory_encoder and --aux v1 go together")
    t0 = time.time()
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device(a.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if a.head_rows:
        arrs, meta = npz_head(a.data, a.head_rows)
    else:
        from .dataset import load as load_ds
        arrs, meta = load_ds(a.data)
    if int(meta.get("feature_version", 1)) < 4:
        raise SystemExit(f"memory {a.memory} needs a feature_version >= 4 dataset")
    packed, row_tab, mmeta = load_memory_tables(a.memory_tables)
    if mmeta["card_vocab"] != meta["card_vocab"]:
        raise SystemExit("--memory-tables were built for another dataset (card_vocab differs)")
    n = len(arrs["y_gate"])
    if len(row_tab) < n or (not a.head_rows and len(row_tab) != n):
        raise SystemExit(f"--memory-tables hold {len(row_tab)} rows, --data {n}: not this dataset")
    row_tab = row_tab[:n]
    rcw = a.rocket_context_weight or 1.0
    if a.rocket_context_artifact is not None:
        from .rocket_context import load_weight_artifact
        arrs["rocket_context_probability"], meta["rocket_context"] = load_weight_artifact(a.rocket_context_artifact, a.data)
    elif rcw != 1.0:
        raise SystemExit("--rocket-context-weight > 1 needs --rocket-context-artifact")
    init_ck = torch.load(a.init, map_location="cpu", weights_only=False)
    if list(init_ck["card_vocab"]) != list(meta["card_vocab"]):
        raise SystemExit("the init's card_vocab differs from the dataset's: card ids would not line up")
    grid = str(init_ck["args"].get("grid", "lattice"))
    model = load_model(a.init, dev, memory=a.memory)[0].eval()
    if a.zero_empty:
        model.mem.register_buffer("zero_empty", torch.ones((), device=dev))
    base = load_model(a.init, dev)[0].eval()
    if getattr(base, "mem", None) is not None:
        raise SystemExit("--init already has memory weights: S3 starts from a model without them")
    snap = freeze(model)
    for p in base.parameters():
        p.requires_grad_(False)
    gid = checkpoint_gid(meta["card_vocab"])
    tables = (packed, row_tab, arrs["tick"])
    tr = np.flatnonzero(arrs["split"] == 0)
    if a.limit_rows and a.limit_rows < len(tr):
        tr = np.sort(rng.choice(tr, size=a.limit_rows, replace=False))
    va_idx = val_rows(arrs, a.val_sample)
    rows = GenRows(arrs, tr, dev)
    rows.memory, rows.grid = tables, grid
    rows.memory_version, rows.memory_gid = a.memory, gid              # v2: + S1C_FIELDS (the tables' vocabulary)
    va = rows.view(va_idx)
    if a.trainable == "memory_encoder":                   # S3-aux (freeze_aux re-sets every requires_grad flag)
        return train_aux(a, model, base, rows, va, va_idx, tr, tables, arrs, meta, init_ck, rng, dev, t0)
    params = [p for k, p in model.named_parameters() if k.startswith("mem.")]
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=a.wd)
    if len(tr) < a.bs:
        raise SystemExit(f"{len(tr)} train rows < one batch of {a.bs}")
    per_epoch = len(tr) // a.bs
    steps = a.steps if a.steps > 0 else max(int(round(a.epochs * per_epoch)), 1)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(a.warmup, 1)) * 0.5 * (
        1 + math.cos(math.pi * min(s, steps) / steps)))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    info = {"init": str(a.init), "init_sha256": hashlib.sha256(a.init.read_bytes()).hexdigest(),
            "memory_tables": str(a.memory_tables), "data": str(a.data), "head_rows": a.head_rows, "train_rows": int(len(tr)),
            "val_rows": int(len(va_idx)), "steps": steps, "bs": a.bs, "lr": a.lr, "wd": a.wd, "warmup": a.warmup,
            "heads": list(HEADS), "mirror": not a.no_mirror, "amp": a.amp, "rocket_context_weight": rcw,
            "trainable": "memory", "n_trainable": int(sum(p.numel() for p in params)), "seed": a.seed,
            "memory": a.memory, "zero_empty": a.zero_empty}
    log = (a.out_dir / "s3_log.jsonl").open("a", encoding="utf-8")

    def emit(rec):
        print(json.dumps(rec), flush=True)
        log.write(json.dumps(rec) + "\n")
        log.flush()
    if len(va_idx):                                       # step 0: the memory model IS the init (zero-output encoder)
        b = va.batch(va_idx[:min(256, len(va_idx))])
        with torch.no_grad():
            o1, o0 = model(b, card=b["card"], form=b["form"]), base(b, card=b["card"], form=b["form"])
            o0b = base(b, card=b["card"], form=b["form"])
        ks = ("gate", "card", "value", "cell")
        diff = max(float((o1[k] - o0[k]).abs().max()) for k in ks)
        noise = max(float((o0b[k] - o0[k]).abs().max()) for k in ks)
        scale = max(float(o0[k].abs().max()) for k in ks)
        # GPU fp32 kernels round by a few ulp (1 ulp = 7.6e-6 at |x| ~ 60); the exact-0 check is the CPU test
        if diff > 1e-6 * max(1.0, scale):
            raise SystemExit(f"step-0 identity failed: max |diff| {diff} (base-vs-base {noise}, max |out| {scale})")
        emit({"step": 0, "identity_max_diff": diff, "base_noise": noise, "out_scale": scale})
    amp = a.amp == "bf16" and dev.type == "cuda"
    best, step, ep, hist = math.inf, 0, 0, []
    tl, sl = time.time(), 0
    while step < steps:
        perm = rng.permutation(tr)
        for b in batches(rows, perm, a.bs, a.prefetch):
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=grid,
                                     rocket_context_weight=rcw, heads=HEADS)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = float(torch.nn.utils.clip_grad_norm_(params, 1.0))
            opt.step()
            sched.step()
            step += 1
            if step % 50 == 0 or step == steps:
                emit({"step": step, "epoch": ep, "loss": float(loss.detach()), **{f"p_{k}": round(v, 5) for k, v in parts.items()},
                      "grad_norm": round(gn, 4), "lr": sched.get_last_lr()[0],
                      "s_per_step": round((time.time() - tl) / (step - sl), 4)})
                tl, sl = time.time(), step
            if len(va_idx) and (step % a.val_every == 0 or step == steps):
                sc = scores(model, base, va, tables, rcw)
                hist.append({"step": step, **sc})
                emit({"step": step, "val": {k: {m: round(v[m], 5) for m in ("loss", "card_top1", "cell_tile_top1",
                                                                             "cell_half_top1", "gate_bal_acc") if m in v}
                                            for k, v in sc.items()}})
                if sc["memory"]["loss"] < best:
                    best = sc["memory"]["loss"]
                    save(a.out_dir / "mem_best.pt", init_ck, model, {**info, "step": step, "val": sc})
            if step % a.ckpt_every == 0:
                save(a.out_dir / f"mem_s{step}.pt", init_ck, model, {**info, "step": step})
                tl = time.time()                          # (validation / saving time is not step time)
                sl = step
            if step >= steps:
                break
        ep += 1
    save(a.out_dir / "mem_latest.pt", init_ck, model, {**info, "step": step})
    bad = frozen_unchanged(model, snap)
    if bad:
        raise SystemExit(f"FROZEN WEIGHTS CHANGED: {bad[:5]} (+{max(0, len(bad) - 5)})")
    pidx = val_rows(arrs, 0)                              # the probes read EVERY val row (the >= 2 failures group is rare)
    pv = va.view(pidx if not a.probe_rows else pidx[:a.probe_rows])
    pr = probes(model, base, pv, tables, arrs, gid) if len(pidx) else {}
    final = {"FINAL": True, "steps": step, "frozen_tensors_unchanged": len(snap), "best_val_loss": best, "probes": pr,
             "hist": hist, "seconds": round(time.time() - t0, 1), **info}
    (a.out_dir / "s3_final.json").write_text(json.dumps(final, indent=1), encoding="utf-8")
    emit({k: v for k, v in final.items() if k != "hist"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

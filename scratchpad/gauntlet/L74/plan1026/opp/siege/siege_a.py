"""OPP-SIEGE test 1 (per decision): does the opponent model give the human's actual response inside X-Bow windows as much
probability as elsewhere?  Held-out human rows only (live_cal = humans vs CLXIII, split 2; HF test split 2).

    CB=/workspace/opp/cb python siege_a.py --ckpt OPP_sim.pt --data ROWS_DIR --memory-tables M.npz --out OUT.json [--split 2]

Window = the rows of a seat at ticks (t_x, t_x + 200] after an ENEMY reach X-Bow placed at t_x (memory table events: is_play,
mine 0, xb_reach 1); 'early' = (t_x, t_x + 80] (match_memory's X-Bow answer window), 'late' = (t_x + 80, t_x + 200].
'outside' = the same seats' other rows (seats that face >= 1 reach X-Bow), so deck matchups are held equal.
ponytail: fixed 10-s window, not "until lock / X-Bow death" (the rows carry no lock tick); a lock-timed window needs the board.
Per group: card / cell top-1 + NLL on play rows, slot hazard vs event rate + slot ECE + timing NLL on slot rows, and per X-Bow
window the model's P(no play in the first 80 ticks) = prod(1 - h) over its slots vs the human share with no play."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

CB = Path(os.environ["CB"]) if "CB" in os.environ else Path(__file__).resolve().parents[6]
sys.path[:0] = [str(CB), str(CB / "scratchpad/gauntlet/L74/plan1026/opp")]
from level_a import ece                                  # noqa: E402
from pipeline import match_memory as MM                  # noqa: E402
from pipeline.model_gen import load_model, slot_nll      # noqa: E402
from pipeline.model_v3 import cell_label                 # noqa: E402
from pipeline.train_gen import GenRows, load_dir         # noqa: E402

W_EARLY, W_ALL = 80, 200
OTHER = {}            # table -> ticks of enemy plays that are not reach X-Bows, >= 4 s before / 10 s after any reach X-Bow


def first_response(h, ev, tick, tab, wins, rng):
    """Per window (tab, t0): the seat's slot rows in (t0, t0 + W_EARLY], in tick order. Randomised PIT of the human's FIRST
    play under the model's discrete hazard: u = 1 - S_before + r * S_before * h_play (U(0, 1) if the model is calibrated);
    a window with no play is censored (u ~ U(1 - S_end, 1)). Pre-play slots = up to and including the first play's slot:
    their mean h vs their event rate tests the urgency; post-play slots the same."""
    order = np.lexsort((tick, tab))
    ts, tt = tab[order], tick[order]
    U, pre_h, pre_e, post_h, post_e, nop, n = [], [], [], [], [], 0, 0
    for t, t0 in wins:
        a, b = np.searchsorted(ts, t, "left"), np.searchsorted(ts, t, "right")
        lo, hi = a + np.searchsorted(tt[a:b], t0, "right"), a + np.searchsorted(tt[a:b], t0 + W_EARLY, "right")
        r = order[lo:hi]
        if len(r) < 6:
            continue
        n += 1
        hh, ee = np.clip(h[r], 0, 1 - 1e-9), ev[r]
        j = int(np.argmax(ee)) if ee.any() else None
        S = np.concatenate([[1.0], np.cumprod(1 - hh)])
        if j is None:
            nop += 1
            U.append(1 - S[-1] + rng.random() * S[-1])
            pre_h += list(hh); pre_e += list(ee)
        else:
            U.append(1 - S[j] + rng.random() * S[j] * hh[j])
            pre_h += list(hh[:j + 1]); pre_e += list(ee[:j + 1]); post_h += list(hh[j + 1:]); post_e += list(ee[j + 1:])
    U = np.sort(np.asarray(U))
    ks = float(np.abs(U - (np.arange(len(U)) + 0.5) / len(U)).max()) if len(U) else None
    f = lambda x: float(np.mean(x)) if len(x) else None
    return {"windows": n, "human_no_play_4s": nop / n if n else None, "pit_mean": f(U), "pit_ks": ks,
            "pit_below_0.25": f(U < 0.25), "pre_slots": len(pre_h), "pre_h": f(pre_h), "pre_event_rate": f(pre_e),
            "post_slots": len(post_h), "post_h": f(post_h), "post_event_rate": f(post_e)}


def windows(packed, row_tab, tick):
    """Per row: 0 outside, 1 early, 2 late window; -1 = a seat that never faces a reach X-Bow; + per-row window id (-1 none)
    and per window (table, t_x, locked)."""
    off = packed["off"]
    C = MM._COL
    vals, ttick = packed["vals"], packed["tick"]
    xb = {}
    for t in np.unique(row_tab):
        if t < 0:
            continue
        a, b = int(off[t]), int(off[t + 1])
        v = vals[a:b]
        m = (v[:, C["is_play"]] > 0) & (v[:, C["mine"]] == 0) & (v[:, C["xb_reach"]] > 0)
        xb[int(t)] = [(int(ttick[a + i]), int(v[i, C["xb_locked"]] > 0)) for i in np.where(m)[0]]
        o = (v[:, C["is_play"]] > 0) & (v[:, C["mine"]] == 0) & ~m
        xt = np.array([q[0] for q in xb[int(t)]])
        OTHER[int(t)] = [int(ttick[a + i]) for i in np.where(o)[0]
                         if not len(xt) or not ((ttick[a + i] - xt >= -W_EARLY) & (ttick[a + i] - xt <= W_ALL)).any()]
    grp = np.full(len(row_tab), -1, np.int8)
    wid = np.full(len(row_tab), -1, np.int64)
    W = []
    order = np.argsort(row_tab, kind="stable")
    tabs_sorted = row_tab[order]
    starts = np.searchsorted(tabs_sorted, np.unique(row_tab))
    for s, e in zip(starts, list(starts[1:]) + [len(order)]):
        rows = order[s:e]
        t = int(row_tab[rows[0]])
        ev = xb.get(t, [])
        if not ev:
            continue
        grp[rows] = 0
        for tx, lk in ev:
            k = len(W)
            W.append((t, tx, lk))
            dt = tick[rows] - tx
            m = (dt > 0) & (dt <= W_ALL)
            r = rows[m]
            wid[r] = np.where(wid[r] < 0, k, wid[r])          # overlapping windows: the earlier X-Bow keeps the row
            grp[r] = np.where(grp[r] == 1, 1, np.where(dt[m] <= W_EARLY, 1, 2))   # early beats late on overlaps
    return grp, wid, W


def selftest():
    """Planted check: slots drawn from a known hazard -> PIT mean ~0.5, KS small; the same data scored with h / 3 (a model too
    slow to answer) -> PIT mean well below 0.5."""
    rng = np.random.default_rng(1)
    n, k = 4000, 8
    h = rng.uniform(0.1, 0.5, (n, k))
    ev = np.zeros((n, k), bool)
    for i in range(n):
        for j in range(k):
            if rng.random() < h[i, j]:
                ev[i, j] = True
                break
    tick = np.tile(np.arange(1, k + 1) * 10, n)
    tab = np.repeat(np.arange(n), k)
    wins = [(i, 0) for i in range(n)]
    good = first_response(h.ravel(), ev.ravel(), tick, tab, wins, np.random.default_rng(2))
    slow = first_response(h.ravel() / 3, ev.ravel(), tick, tab, wins, np.random.default_rng(2))
    ok = abs(good["pit_mean"] - 0.5) < 0.02 and good["pit_ks"] < 0.03 and slow["pit_mean"] < 0.4
    print(json.dumps({"good": good, "slow": slow, "SELFTEST": "OK" if ok else "FAIL"}))
    return 0 if ok else 1


@torch.no_grad()
def main(argv=None):
    if (argv or sys.argv[1:])[:1] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--memory-tables", type=Path, required=True)
    ap.add_argument("--split", type=int, default=2)
    ap.add_argument("--bs", type=int, default=1024)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dump", type=Path, default=None, help="npz of per-row h, hand-slot card probs, labels, window ids")
    a = ap.parse_args(argv)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, st = load_model(a.ckpt, dev)
    model.eval()
    arrs, meta = load_dir(a.data)
    assert (meta.get("row_builder") or {}).get("keep_wait") == 1, "needs every slot (keep_wait 1)"
    assert meta["card_vocab"] == st["card_vocab"]
    from pipeline.dataset_gen import checkpoint_gid, load_memory_tables
    packed, row_tab, _ = load_memory_tables(a.memory_tables)
    tick = np.asarray(arrs["tick"])
    grp_all, wid_all, W = windows(packed, np.asarray(row_tab), tick)
    idx = np.where((np.asarray(arrs["split"]) == a.split) & (grp_all >= 0))[0]
    rows = GenRows(arrs, idx, dev)
    rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, arrs["tick"]), st.get("memory"), checkpoint_gid(st["card_vocab"])
    K = ("h", "card_top", "card_lp", "card_ok", "cell_top", "cell_lp", "play", "tnll", "pred_card", "card_p4")
    R = {k: [] for k in K}
    hand = np.asarray(arrs["hand_card"])
    for s0 in range(0, len(idx), a.bs):
        ids = idx[s0:s0 + a.bs]
        b = rows.batch(ids)
        o = model(b, card=b["card"], form=b["form"])
        play = b["gate"] > 0.5
        lab = cell_label(b["xy"].clamp(0, 1), "lattice")
        cl, ck = Fn.log_softmax(o["cell"].float(), -1), Fn.log_softmax(o["card"].float(), -1)
        cok = play & (b["card_ok"] > 0) & (b["slot"] >= 0)
        s = b["slot_ok"] > 0
        R["h"].append(torch.sigmoid(o["hazard"].float()).cpu().numpy())
        R["card_top"].append((ck.argmax(-1) == b["slot"]).cpu().numpy())
        R["card_lp"].append(ck.gather(1, b["slot"].clamp(min=0)[:, None])[:, 0].cpu().numpy())
        R["card_ok"].append(cok.cpu().numpy())
        R["cell_top"].append((cl.argmax(-1) == lab).cpu().numpy())
        R["cell_lp"].append(cl.gather(1, lab.clamp(min=0)[:, None])[:, 0].cpu().numpy())
        R["play"].append(play.cpu().numpy())
        R["tnll"].append(torch.where(s, slot_nll(o["hazard"].float(), o["tick"].float(), b["slot_ev"], b["slot_tick"]),
                                     torch.zeros_like(o["hazard"].float())).cpu().numpy())
        R["card_p4"].append(ck.exp()[:, :hand.shape[1]].cpu().numpy().astype(np.float32))
        R["pred_card"].append(hand[ids, ck.argmax(-1).cpu().numpy().clip(0, hand.shape[1] - 1)])
    R = {k: np.concatenate(v) for k, v in R.items()}
    grp, wid = grp_all[idx], wid_all[idx]
    slot_ok, slot_ev = np.asarray(arrs["slot_ok"])[idx] > 0, np.asarray(arrs["slot_ev"])[idx] > 0
    ycard = np.asarray(arrs["y_card"])[idx]
    voc = st["card_vocab"]

    def summ(m):
        co, eo, so = m & R["card_ok"], m & R["play"], m & slot_ok
        return {"play_rows": int(eo.sum()), "card_n": int(co.sum()),
                "card_top1": float(R["card_top"][co].mean()) if co.any() else None,
                "card_nll": float(-R["card_lp"][co].mean()) if co.any() else None,
                "cell_top1": float(R["cell_top"][eo].mean()) if eo.any() else None,
                "cell_nll": float(-R["cell_lp"][eo].mean()) if eo.any() else None,
                "slots": int(so.sum()), "hazard_mean": float(R["h"][so].mean()) if so.any() else None,
                "event_rate": float(slot_ev[so].mean()) if so.any() else None,
                "slot_ece_pp": 100 * ece(R["h"][so], slot_ev[so]) if so.any() else None,
                "timing_nll": float(R["tnll"][so].mean()) if so.any() else None}

    res = {"ckpt": str(a.ckpt), "data": str(a.data), "split": a.split, "rows": int(len(idx)), "windows": len(W),
           "groups": {"outside": summ(grp == 0), "early_0_4s": summ(grp == 1), "late_4_10s": summ(grp == 2), "window_0_10s": summ(grp >= 1)}}
    # first response after the window opens: X-Bow windows (all / locked / failed) vs the control (other enemy plays)
    tabv = np.asarray(row_tab)[idx]
    so = slot_ok
    rng = np.random.default_rng(0)
    fr = {}
    for name, wins in (("xbow_all", [(t, tx) for t, tx, _ in W]), ("xbow_locked", [(t, tx) for t, tx, lk in W if lk]),
                       ("xbow_failed", [(t, tx) for t, tx, lk in W if not lk]),
                       ("other_enemy_play", [(t, tx) for t, v in OTHER.items() for tx in v])):
        fr[name] = first_response(R["h"][so], slot_ev[so], tick[idx][so], tabv[so], wins, rng)
    res["first_response_4s"] = fr
    # inside the window: which cards humans played, and the model's top-1 / probability on them
    inw = (grp >= 1) & R["card_ok"]
    cc = defaultdict(lambda: [0, 0, 0.0, 0])
    for i in np.where(inw)[0]:
        q = cc[voc[int(ycard[i])]]
        q[0] += 1; q[1] += int(R["card_top"][i]); q[2] += float(np.exp(R["card_lp"][i]))
    for i in np.where(inw)[0]:
        cc[voc[int(R["pred_card"][i])]][3] += 1
    res["window_cards"] = {k: {"human_n": v[0], "top1": v[1] / v[0] if v[0] else None, "mean_p": v[2] / v[0] if v[0] else None,
                               "model_top_n": v[3]} for k, v in sorted(cc.items(), key=lambda kv: -kv[1][0])[:20]}
    if a.dump:
        np.savez_compressed(a.dump, idx=idx, h=R["h"].astype(np.float32), p4=R["card_p4"], hand=hand[idx], y_card=ycard,
                            play=R["play"], card_ok=R["card_ok"], slot_ok=slot_ok, slot_ev=slot_ev, grp=grp, wid=wid,
                            tab=np.asarray(row_tab)[idx], tick=tick[idx], vocab=np.array(voc))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("rows", "windows", "groups", "first_response_4s")}, indent=1))


if __name__ == "__main__":
    raise SystemExit(main())

"""L74 pipeline_decisions: offline replay on live logs -- how often would the model's OWN gate want a second play inside the pending
window, and with which cards?

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/pipeline_decisions/pd_replay.py [--logs GLOB] [--max N] [--out FILE]

Method (public information only, read-only on the logs): for every live PLAY decision A (public-audit `decision` event with play) the
batch of A's decision state is rebuilt EXACTLY as L73/lethal_rocket/rebuild.py does (the model's own input), then turned into "the
state right after A, A pending" by the SAME rules the live pilot / SIM use (pipeline.e1_eval.pending_hand's idea):
  * A's hand position holds the next card in the view (unknown -> the pad card) and is masked (never choosable)
  * my elixir minus A's cost, in the sc token and in the affordability mask (int floor, as live_decide)
  * A is the newest past play at its landing (dt = 0 at the look-ahead tick)
NOT changed: the bodies / spell A would put on the look-ahead board (rebuilt logs carry no pending objects), and the board itself --
the state is the one A was decided on, ~2 ticks apart in the real second decision, 24 ticks apart at the window's end. So this
measures the GATE'S REACTION TO THE PENDING PLAY ALONE (what the earlier SIM failures blamed: the gate fires 2-3x the pro rate when
the lock is gone), not the board's evolution.
Per A: p (gate) under tau_phase (0.35 / 0.45 / 0.55 by phase) and the top card among the allowed slots. 'wants' = p > tau (a threshold play
at the first decision of the window; the deployed hazard decoder only adds plays at >= 9 elixir, which A's cost makes rare).
Pros: pairs with gap <= 24 ticks (1.2 s) from the defence worker's normalised pros (mistakes.py's load_pros, read only).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:                                       # the laptop is shared with live play
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass

REPO = Path(__file__).resolve().parents[4]
MAIN = Path(r"C:\Users\benpe\ClashBot")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scratchpad/gauntlet/L73/lethal_rocket"))
import numpy as np  # noqa: E402
import torch  # noqa: E402

CKPT = str(MAIN / "icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt")   # live, sha 41b52a83
TAU = (0.35, 0.45, 0.55)
LAND_TICKS = 24                                                           # deployed: decision -> landing
WINDOW = 24                                                               # the pending window (1.2 s) in ticks


def pidx(tick):
    return 0 if tick < 2400 else (1 if tick < 3600 else 2)


def load_rebuild():
    import rebuild as rb
    from pipeline.model_gen import load_model
    cache = {}

    def cached(path, device):
        if path not in cache:
            cache[path] = load_model(path, device)
        return cache[path]
    rb.load_model = cached
    return rb


def replay(logs, rb, limit):
    from pipeline.dataset_gen import card_key
    rows = []
    for li, log in enumerate(logs[:limit]):
        try:
            m = rb.Match(log, CKPT)
        except Exception as exc:             # a log without public-audit decisions / a different deck
            print(f"skip {Path(log).name}: {exc!r}", file=sys.stderr)
            continue
        for i, d in enumerate(m.dec):
            if not d["decision"].get("play") or d["decision"].get("why") in ("lethal_rocket", "lethal_log"):
                continue
            p = d["public"]
            try:
                b, info = m.batch(i)
            except Exception as exc:
                print(f"skip decision {i} of {Path(log).name}: {exc!r}", file=sys.stderr)
                continue
            names, hand = info["names"], info["hand"]
            pos = int(d["decision"]["hand_pos"])
            if not 0 <= pos < 4 or hand[pos][0] <= 0:
                continue
            cost = float(p["own_hand"][pos]["cost"])
            nd = m.next_index(i)
            pad = (0, rb.FORM_PAD)
            b2 = {k: v.clone() for k, v in b.items()}
            # (1) the view's hand: A's position shows the next card (unknown -> pad), and the next card becomes unknown
            nxt = (m.gid[rb.card_key(m.deck[nd][0])], m.deck[nd][1]) if nd >= 0 else pad
            b2["hand_card"][0, pos], b2["hand_form"][0, pos] = nxt
            b2["next_card"], b2["next_form"] = torch.tensor([pad[0]]), torch.tensor([pad[1]])
            # (2) elixir minus A's cost: rebuild the tokens from the board with the lower elixir
            from dataclasses import replace
            from pipeline.dataset_gen import SC_SLOT_COLS
            from pipeline.obs_contract import to_tokens, to_unit_forms
            from pipeline.train_s1 import MAX_U
            bs = replace(m.board(i), my_elixir=max(0.0, float(p["model_own_elixir"]) - cost))
            tok, mask, sc = to_tokens(bs, MAX_U)
            sc = sc.copy()
            sc[SC_SLOT_COLS] = 0.0
            b2["tok"], b2["mask"], b2["sc"] = (torch.as_tensor(tok, dtype=torch.float32).unsqueeze(0),
                                               torch.as_tensor(mask, dtype=torch.bool).unsqueeze(0),
                                               torch.as_tensor(sc, dtype=torch.float32).unsqueeze(0))
            # (3) A is the newest past play at its landing
            past = b2["past"].clone()
            past[0, 1:] = past[0, :-1].clone()
            x, y = d["decision"]["xy"]
            past[0, 0] = torch.tensor([hand[pos][0], hand[pos][1], x, y, 0.0])
            b2["past"] = past
            # (4) the mask: A's position never choosable, the rest by the lower elixir
            costs = [float("inf") if k == pos else float(h["cost"]) for k, h in enumerate(p["own_hand"])]
            from pipeline.e1_eval import allowed_slots
            allowed = allowed_slots(np.array([c > 0 for c in b2["hand_card"][0].tolist()]), costs, int(bs.my_elixir))
            with torch.no_grad():
                out = m.model(b2)
                pg = float(torch.sigmoid(out["gate"][0]))
                lg = out["card"][0].clone()
                if allowed.any():
                    lg[~torch.from_numpy(allowed)] = -torch.inf
                    top = int(lg.argmax())
                    top_name = names[top] if top < len(names) and np.isfinite(float(lg[top])) else None
                else:
                    top_name = None
            tick = int(p["raw_tick"])
            tau = TAU[pidx(int(p["model_tick"]))]
            rows.append(dict(log=Path(log).name, tick=tick, a=names[pos], a_cost=cost, p=pg, tau=tau, phase=pidx(tick),
                             el_after=float(bs.my_elixir), any_allowed=bool(allowed.any()), top=top_name,
                             p_orig=float(d["decision"]["p_play"])))
        print(f"[{li + 1}/{min(len(logs), limit)}] {Path(log).name}: {len(rows)} A rows so far", file=sys.stderr)
    return rows


def pros_pairs(window):
    """Consecutive-play pairs of the pros with gap <= window ticks (execution ticks; both plays carry the same delay)."""
    import gzip
    import pickle
    path = MAIN / ".claude/worktrees/agent-af3c232b452e8ef86/scratchpad/gauntlet/L74/defense/data/pros.pkl.gz"
    if not path.is_file():
        return None
    with gzip.open(path) as fh:
        ms = pickle.load(fh)
    plays = pairs = 0
    mix, second = Counter(), Counter()
    for m in ms:
        P = sorted((p[1], p[2]) for p in m["P"])
        plays += max(0, len(P) - 1)
        for (t0, a), (t1, b) in zip(P, P[1:]):
            if t1 - t0 <= window:
                pairs += 1
                mix[f"{a}->{b}"] += 1
                second[b] += 1
    return dict(sides=len(ms), plays=plays, pairs_le_window=pairs, share=pairs / max(1, plays),
                top=[(k, round(v / max(1, pairs), 3)) for k, v in mix.most_common(14)],
                second=[(k, round(v / max(1, pairs), 3)) for k, v in second.most_common(10)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=str(MAIN / "scratchpad/gauntlet/L68/live_reader/live_play_2026100[89]_*.jsonl"))
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--out", default=str(Path(__file__).with_name("pd_replay.out")))
    a = ap.parse_args()
    logs = sorted(glob.glob(a.logs))
    # only logs of the deployed bundle (one A deck, public audit decisions): the rebuild itself skips the rest
    rb = load_rebuild()
    rows = replay(logs, rb, a.max)
    lines = []
    emit = lambda s="": (print(s), lines.append(s))               # noqa: E731
    n = len(rows)
    emit(f"logs {min(len(logs), a.max)} of {len(logs)}; play decisions rebuilt: {n}")
    if n:
        want = [r for r in rows if r["any_allowed"] and r["p"] > r["tau"]]
        emit(f"model gate p on 'A pending' states: median {np.median([r['p'] for r in rows]):.3f} (the same decisions before A: "
             f"{np.median([r['p_orig'] for r in rows]):.3f}); tau by phase {TAU}")
        emit(f"share with p > tau (a threshold second play at the first window decision): {len(want) / n:.3f}  [n={len(want)}]")
        for ph, name in enumerate(("1x", "2x", "OT")):
            sel = [r for r in rows if r["phase"] == ph]
            if sel:
                w = sum(r["any_allowed"] and r["p"] > r["tau"] for r in sel)
                emit(f"  {name}: {w / len(sel):.3f} of {len(sel)}   (median elixir left after A: {np.median([r['el_after'] for r in sel]):.1f})")
        by = defaultdict(list)
        for r in rows:
            by[r["a"]].append(r)
        emit("by first card (A): share wanting a second play now | top second cards among those")
        for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
            w = [r for r in v if r["any_allowed"] and r["p"] > r["tau"]]
            emit(f"  {k:10s} n={len(v):4d} wants {len(w) / len(v):.3f}   second: "
                 + ", ".join(f"{c} {x}" for c, x in Counter(r['top'] for r in w).most_common(4)))
        emit("top ordered pairs among 'wants': " + ", ".join(f"{k}->{c}: {v}" for (k, c), v in Counter(
            (r['a'], r['top']) for r in want).most_common(10)))
        # window probability: 12 frame decisions; p is near-constant over the window (same state), so P(any) ~ 1 if p > tau
    emit("")
    pros = pros_pairs(WINDOW)
    if pros:
        emit(f"PROS (icebow, {pros['sides']} sides): consecutive plays <= {WINDOW} ticks apart: {pros['pairs_le_window']} of "
             f"{pros['plays']} = {pros['share']:.3f} per play")
        emit("  top pairs (share of those): " + ", ".join(f"{k} {v}" for k, v in pros["top"]))
        emit("  second card mix: " + ", ".join(f"{k} {v}" for k, v in pros["second"]))
    else:
        emit("PROS: pros.pkl.gz not found")
    Path(a.out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

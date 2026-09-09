"""L67i: find REAL live states where the gate pins at ~0, then bisect the input until it recovers.

Five hypotheses for the live p=0.00 are dead (overtime, tower loss, every live-only scalar flag, stale past
ages, unmapped hand cards) -- and every scalar mutation tried so far RAISES p rather than lowering it. That
leaves the unit tokens, the one part of the input never tested, and it also leaves a possibility worth taking
seriously: that p~0 is not a blowup at all. On clean ENGINE rows 11.6% already sit under 0.005, so a run of
p=0.00 is only a defect if the same board would score high on the engine side.

This works on the 835 cached live BoardStates (real detector output, `live_states.pkl`) instead of waiting for
another live run. For every state with p below the threshold it walks one field at a time back to its training
value and reports which single change restores the gate -- and, as the control that matters, what an ENGINE
state with the same elixir and unit count scores.

usage: python scratchpad/gauntlet/L67/bisect_low_gate.py --ckpt <pt> --cache <live_states.pkl> --out <json>
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--thresh", type=float, default=0.02)
    a = ap.parse_args()

    import torch
    from pipeline.model_v3 import S1Model, hand_mask_from_sc
    from pipeline.obs_contract import to_tokens

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()
    states = pickle.loads(a.cache.read_bytes())
    print(f"cached live states: {len(states)}", flush=True)

    def score(bs):
        tok, mask, sc = to_tokens(bs)
        tt = torch.from_numpy(np.asarray(tok)[None])
        mm = torch.from_numpy(np.asarray(mask)[None])
        ss = torch.from_numpy(np.asarray(sc)[None])
        with torch.no_grad():
            enc = model.encode(tt, mm, ss, torch.full((1, 3, 4), -1.0))
            h = model.heads(enc, hand_mask_from_sc(ss))
            return float(torch.sigmoid(h["gate"][0]).item())

    rep = dataclasses.replace
    scored = [(score(bs), el, bs) for el, bs in states]
    low = [(p, el, bs) for p, el, bs in scored if p < a.thresh]
    allp = np.array([p for p, _, _ in scored])
    print(f"p distribution: mean {allp.mean():.3f}  frac<0.02 {float((allp < 0.02).mean()):.3f}  "
          f"frac<0.005 {float((allp < 0.005).mean()):.3f}", flush=True)
    print(f"low-gate states (p<{a.thresh}): {len(low)}", flush=True)

    def fixes(bs):
        """Each entry: one field pushed back to its TRAINING value."""
        out = {}
        out["units removed"] = rep(bs, units=(), spells=())
        out["spells removed"] = rep(bs, spells=())
        out["sides resolved to enemy"] = rep(bs, units=tuple(rep(u, side=(1 if u.side < 0 else u.side))
                                                             for u in bs.units))
        out["all units -> ENEMY"] = rep(bs, units=tuple(rep(u, side=1) for u in bs.units))
        out["all units -> MINE"] = rep(bs, units=tuple(rep(u, side=0) for u in bs.units))
        out["conf 1.0"] = rep(bs, units=tuple(rep(u, conf=1.0) for u in bs.units))
        out["hp known 1.0"] = rep(bs, units=tuple(rep(u, hp_frac=1.0) for u in bs.units))
        out["elixir exact"] = rep(bs, my_elixir_exact=True)
        out["opp elixir 5"] = rep(bs, opp_elixir=5.0)
        out["towers full+alive"] = rep(bs, towers=tuple(rep(t, hp_frac=1.0, alive=True) for t in bs.towers))
        return out

    agg = {}
    rows = []
    for p, el, bs in low[:40]:
        rec = {"p": round(p, 4), "elixir": el, "units": len(bs.units), "spells": len(bs.spells),
               "unknown_side": sum(1 for u in bs.units if u.side < 0),
               "mine": sum(1 for u in bs.units if u.side == 0),
               "enemy": sum(1 for u in bs.units if u.side == 1), "fixes": {}}
        for name, alt in fixes(bs).items():
            q = score(alt)
            rec["fixes"][name] = round(q, 4)
            agg.setdefault(name, []).append(q - p)
        rows.append(rec)

    summary = {k: {"mean_delta_p": round(float(np.mean(v)), 4), "n": len(v)}
               for k, v in sorted(agg.items(), key=lambda kv: -float(np.mean(kv[1])))}
    print(json.dumps(summary, indent=1), flush=True)
    a.out.write_text(json.dumps({"n_low": len(low), "summary": summary, "rows": rows}, indent=1),
                     encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

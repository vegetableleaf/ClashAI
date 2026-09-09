"""L67i: bisect the REAL captured p~0 states field by field until the gate recovers.

Six hypotheses died to engine-side mutation, and every single-field change there RAISED p. That means the
collapse is a combination only the bot's own frames produce -- so these are those frames: tok/mask/sc/past
captured live by student_live whenever p<0.02 (data/low_gate_states.jsonl).

Each field is pushed back to its TRAINING value one at a time, then in the "all scalars"/"all tokens" groups,
and the gate is re-read. Whatever restores p names the cause. The past-array variants matter because the live
`past` is wall-clock and is never reset between matches.

usage: python scratchpad/gauntlet/L67/bisect_capture.py --ckpt <pt> --capture <jsonl> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

H0, H1, N0, N1 = 7, 43, 43, 52
THP0, THP1, HPK0, HPK1, ALV0, ALV1 = 52, 58, 58, 64, 64, 70


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--capture", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    import torch
    from pipeline.model_v3 import S1Model, hand_mask_from_sc

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()

    recs = [json.loads(l) for l in a.capture.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"captured states: {len(recs)}", flush=True)

    def score(tok, mask, sc, past):
        tt = torch.from_numpy(np.asarray(tok, dtype=np.float32)[None])
        mm = torch.from_numpy(np.asarray(mask, dtype=bool)[None])
        ss = torch.from_numpy(np.asarray(sc, dtype=np.float32)[None])
        pp = torch.from_numpy(np.asarray(past, dtype=np.float32)[None])
        with torch.no_grad():
            enc = model.encode(tt, mm, ss, pp)
            return float(torch.sigmoid(model.heads(enc, hand_mask_from_sc(ss))["gate"][0]).item())

    def variants(tok, mask, sc, past):
        tok = np.asarray(tok, dtype=np.float32)
        mask = np.asarray(mask, dtype=bool)
        sc = np.asarray(sc, dtype=np.float32)
        past = np.asarray(past, dtype=np.float32)
        v = {}
        # --- past ---
        p1 = past.copy(); p1[:] = -1.0
        v["past -> empty"] = (tok, mask, sc, p1)
        p2 = past.copy()
        m = p2[:, 0] >= 0
        p2[m, 3] = 5.0
        v["past ages -> 5s"] = (tok, mask, sc, p2)
        # --- scalars, one at a time ---
        for name, mut in (("elixir -> 10", lambda s: s.__setitem__(3, 1.0)),
                          ("exact -> 1", lambda s: s.__setitem__(4, 1.0)),
                          ("opp -> 5 known", lambda s: (s.__setitem__(5, 0.5), s.__setitem__(6, 1.0))),
                          ("t -> 60s", lambda s: s.__setitem__(0, 0.2))):
            s2 = sc.copy(); mut(s2)
            v[name] = (tok, mask, s2, past)
        s2 = sc.copy(); s2[THP0:THP1] = 1.0; s2[HPK0:HPK1] = 1.0; s2[ALV0:ALV1] = 1.0
        v["towers -> full+alive"] = (tok, mask, s2, past)
        s2 = sc.copy()
        h = s2[H0:H1].reshape(4, 9)
        for k in range(4):
            if h[k, 8] > 0.5:
                h[k, :] = 0.0
                h[k, k] = 1.0                      # a readable deck card instead of "unmapped"
        s2[H0:H1] = h.reshape(36)
        v["hand -> all mapped"] = (tok, mask, s2, past)
        # --- tokens ---
        m0 = mask.copy(); m0[:] = False
        v["all units removed"] = (tok, m0, sc, past)
        t2 = tok.copy(); t2[:, 13] = 0.0
        v["spell flag cleared"] = (t2, mask, sc, past)
        t2 = tok.copy(); t2[:, 1] = 0.0; t2[:, 2] = 1.0; t2[:, 3] = 0.0
        v["all units -> ENEMY"] = (t2, mask, sc, past)
        t2 = tok.copy(); t2[:, 1] = 1.0; t2[:, 2] = 0.0; t2[:, 3] = 0.0
        v["all units -> MINE"] = (t2, mask, sc, past)
        t2 = tok.copy(); t2[:, 12] = 1.0
        v["conf -> 1.0"] = (t2, mask, sc, past)
        t2 = tok.copy(); t2[:, 6] = 1.0; t2[:, 7] = 1.0
        v["unit hp -> known 1.0"] = (t2, mask, sc, past)
        # --- groups ---
        s3 = sc.copy(); s3[3] = 1.0; s3[4] = 1.0; s3[5] = 0.5; s3[6] = 1.0
        s3[THP0:THP1] = 1.0; s3[HPK0:HPK1] = 1.0; s3[ALV0:ALV1] = 1.0
        v["ALL scalars -> training"] = (tok, mask, s3, past)
        t3 = tok.copy(); t3[:, 12] = 1.0; t3[:, 6] = 1.0; t3[:, 7] = 1.0; t3[:, 13] = 0.0
        v["ALL tokens -> training"] = (t3, mask, sc, past)
        v["EVERYTHING -> training"] = (t3, mask, s3, p2)
        return v

    agg = {}
    base = []
    for r in recs:
        p0 = score(r["tok"], r["mask"], r["sc"], r["past"])
        base.append(p0)
        for name, (t, m, s, pa) in variants(r["tok"], r["mask"], r["sc"], r["past"]).items():
            agg.setdefault(name, []).append(score(t, m, s, pa) - p0)
    base = np.array(base)
    print(f"captured p: mean {base.mean():.4f}  max {base.max():.4f}", flush=True)
    out = {k: {"mean_delta_p": round(float(np.mean(v)), 4), "max_delta_p": round(float(np.max(v)), 4)}
           for k, v in sorted(agg.items(), key=lambda kv: -float(np.mean(kv[1])))}
    for k, v in out.items():
        print(f"  {k:28s} mean {v['mean_delta_p']:+.4f}   max {v['max_delta_p']:+.4f}", flush=True)
    a.out.write_text(json.dumps({"n": len(recs), "base_mean_p": round(float(base.mean()), 4), "fixes": out},
                                indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

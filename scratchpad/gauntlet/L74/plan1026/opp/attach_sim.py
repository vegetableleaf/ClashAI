"""P2-OPP: a timing-head opponent checkpoint -> the same weights + ``opp_sim`` (what e1_eval.GenPolicy needs to PLAY it
in the SIM): the context token ids to play under (REPORT_opponents 3.4 step (a), the band token) and the training
deck-id table (rows_to_npz ``deck_keys``: id i = row i - 1; a deck outside it plays as 0 = unknown, trained by the
DeckEncoder's 20% id-dropout).

    python attach_sim.py --ckpt opp_m10_s0.pt --data /workspace/opp/v0/hf_slot_v0 --out opp_m10_s0_sim.pt [--band 1 --mode 1 --era 1]

Ids (rows_to_npz meta): band 1 hf_pol, 2 hf_other, 3 pro, 4/5/6 live L/M/R; mode 1 = pathOfLegend / Ranked; era 1 = hf.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True, help="the TRAINING rows (npz or extracted dir) the deck ids came from")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--band", type=int, default=1)
    ap.add_argument("--mode", type=int, default=1)
    ap.add_argument("--era", type=int, default=1)
    a = ap.parse_args(argv)
    st = torch.load(a.ckpt, map_location="cpu")
    opp = st.get("opp") or {}
    if not opp.get("timing"):
        raise SystemExit(f"{a.ckpt}: not a timing-head opponent checkpoint (opp={opp})")
    dk = np.load(a.data / "deck_keys.npy") if a.data.is_dir() else np.load(a.data)["deck_keys"]
    if opp.get("deck_enc") and len(dk) != int(opp["n_decks"]):
        raise SystemExit(f"deck_keys has {len(dk)} decks, the model {opp['n_decks']}: not the training rows")
    ctx = {"band": a.band, "mode": a.mode, "era": a.era}
    for k, n in (opp.get("ctx_tokens") or {}).items():
        if not 1 <= ctx[k] <= int(n):
            raise SystemExit(f"ctx {k}={ctx[k]} outside the trained ids 1..{n}")
    st["opp_sim"] = {"ctx": {k: ctx[k] for k in opp.get("ctx_tokens") or {}}, "deck_keys": np.asarray(dk).astype(int).tolist(),
                     "deck_keys_sha256": hashlib.sha256(np.ascontiguousarray(dk).tobytes()).hexdigest(),
                     "source_ckpt": str(a.ckpt), "source_ckpt_sha256": hashlib.sha256(a.ckpt.read_bytes()).hexdigest(),
                     "data": str(a.data)}
    torch.save(st, a.out)
    print(json.dumps({"out": str(a.out), "sha256": hashlib.sha256(a.out.read_bytes()).hexdigest(), "decks": len(dk),
                      "ctx": st["opp_sim"]["ctx"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

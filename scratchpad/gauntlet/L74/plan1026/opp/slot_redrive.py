"""P2-OPP1: the HF re-drive with SLOT rows for the opponent model's timing head (plan1026 Pillar 2, REPORT_opponents 1.4).

Pass 1 (redrive.py) built rows with S1's sampler: wait rows every 40 ticks and none in the 20 ticks before a play
(wait_stride 40, play_window 20). That drops exactly the no-play slots just before each play, so a per-slot hazard
fitted on them is biased upward where it matters, and slots 0-1 before a play are never observed (the "sampling
artefact" the plan names). This wrapper runs the SAME driving code (redrive.py of the pass-1 code copy, imported
unchanged) and overrides only:
  * the row builder: ``dataset_gen.build(wait_stride=10, play_window=0)`` (record_every is 10 -> a row on every frame
    that is not one of this side's play ticks; play rows unchanged);
  * a sidecar per shard, ``rows/<sid>.slot.npz`` aligned with the parquet rows: ``frame_gap`` (next frame tick - row
    tick when the row sits on a recorded frame, else -1: a slot row needs gap 10), ``ab_dt`` (ticks to this side's
    next ACCEPTED ability press, -1 none), ``play_dt`` (ticks to this side's next accepted card play, -1 none);
  * memory tables per shard, ``mem/<sid>.npz`` (dataset_gen.memory_tables, card ids in the GLOBAL vocab file
    ``--vocab``), so memory v2 can be trained jointly.
Run (pod 33308, code copy = the pass-1 copy, see run_slot.sh):
    OPP_VOCAB=VOCAB.json python slot_redrive.py run --data /workspace/hf_il_replay/data --out /ABS/OUT --limit N --workers W
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

RD_DIR = Path(os.environ.get("RD_DIR", Path(__file__).resolve().parents[1] / "redrive"))
sys.path.insert(0, str(RD_DIR))
import redrive as RD                       # noqa: E402  (the pass-1 driver, unchanged)
import pipeline.dataset_gen as DG          # noqa: E402

SLOT = dict(wait_stride=10, play_window=0)
VOCAB = json.loads(Path(os.environ["OPP_VOCAB"]).read_text()) if os.environ.get("OPP_VOCAB") else None
_build, _n2p = DG.build, RD.npz_to_parquet


def _slot_build(*a, **k):
    k.update(SLOT)
    return _build(*a, **k)


def sidecar(npz: Path) -> dict:
    """Per-row frame_gap / ab_dt / play_dt from the shard's corpus recordings (the rows' own source)."""
    z = np.load(npz, allow_pickle=False)
    tags, rep, side, tick = z["tags"], z["rep"], z["side"].astype(np.int64), z["tick"].astype(np.int64)
    corpus = npz.parent / "corpus"
    n = len(tick)
    gap, ab, pl = np.full(n, -1, np.int16), np.full(n, -1, np.int32), np.full(n, -1, np.int32)
    for r in np.unique(rep):
        rec = json.loads((corpus / f"replay_{tags[r]}.json").read_text())
        ft = np.array(sorted({int(f["tick"]) for f in rec.get("frames") or []}), np.int64)
        idx = np.where(rep == r)[0]
        t = tick[idx]
        k = np.searchsorted(ft, t)
        on = (k < len(ft)) & (ft[np.minimum(k, len(ft) - 1)] == t) & (k + 1 < len(ft))
        gap[idx[on]] = (ft[k[on] + 1] - t[on]).astype(np.int16)
        for col, pick in ((ab, lambda e: e.get("ability")), (pl, lambda e: not e.get("ability") and "card" in e)):
            for s in (0, 1):
                ev = np.array(sorted(int(e["tick"]) for e in rec["log"]
                                     if e.get("accepted") and int(e.get("side", -1)) == s and pick(e)), np.int64)
                m = idx[side[idx] == s]
                if not len(ev) or not len(m):
                    continue
                j = np.searchsorted(ev, tick[m])            # next event at or after the row tick
                ok = j < len(ev)
                col[m[ok]] = (ev[j[ok]] - tick[m[ok]]).astype(np.int32)
    return dict(frame_gap=gap, ab_dt=ab, play_dt=pl)


def _slot_n2p(npz: Path, out: Path, grades: dict) -> int:
    n = _n2p(npz, out, grades)
    sc = sidecar(npz)
    if any(len(v) != n for v in sc.values()):
        raise ValueError(f"sidecar rows {[len(v) for v in sc.values()]} != parquet rows {n}")
    np.savez(out.with_suffix(".slot.npz"), **sc)
    if VOCAB is not None:                                        # memory tables, card ids in the global vocab
        z = np.load(npz, allow_pickle=False)
        meta = json.loads(str(z["meta"]))
        meta.update(card_vocab=VOCAB, corpora=[str((npz.parent / "corpus").resolve())])
        tmp = npz.with_name("mem_in.npz")
        np.savez(tmp, meta=json.dumps(meta), tags=z["tags"], rep=z["rep"], side=z["side"])
        mem = out.parent.parent / "mem" / (out.name[:-len(".parquet")] + ".npz")
        DG.memory_tables(tmp, mem, workers=1, log=None)
    return n


DG.build = _slot_build                 # run_shard imports build from pipeline.dataset_gen at call time
RD.npz_to_parquet = _slot_n2p          # looked up in redrive's globals at call time
_orig_manifest = RD.manifest


def _manifest(out, args):
    m = _orig_manifest(out, args)
    m.update(schema="p2opp1-slot-rows.v1", row_builder={"fn": "pipeline.dataset_gen.build", "feature_version": 5,
             "grid": "lattice", "val_pct": 10, "record_every": 10, **SLOT},
             sidecars=["rows/<sid>.slot.npz: frame_gap, ab_dt, play_dt", "mem/<sid>.npz: memory_tables (global vocab)"],
             vocab_sha256=__import__("hashlib").sha256(Path(os.environ["OPP_VOCAB"]).read_bytes()).hexdigest()
             if os.environ.get("OPP_VOCAB") else None)
    (Path(out) / "manifest.json").write_text(json.dumps(m, indent=1))
    return m


RD.manifest = _manifest

if __name__ == "__main__":
    sys.exit(RD.main())

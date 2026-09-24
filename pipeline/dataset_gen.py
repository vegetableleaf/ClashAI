"""GENERALIST (multi-deck) imitation dataset: driven engine corpora -> one ``.npz`` of rows for BOTH sides of
every replay, any deck, with card-IDENTITY features and labels instead of S1's 8-deck-slot ones.

Spec: ``scratchpad/gauntlet/L68/generalist/plan.md`` ("Design").

Row construction is S1's, unchanged: for each side, a throwaway 8-card ``Deck`` is made from that side's engine
deck (``final_decks``) and handed to ``dataset.build_replay`` -- so play rows (``_as_compact`` frames, §5cs.61),
wait-row sampling, past plays, crowns and the (x, y) labels are byte-for-byte S1's. The deck-slot one-hots that
S1 writes into ``sc`` are then DECODED into card identities (slot -> that side's card) and ZEROED in ``sc``:
``sc`` keeps S1's 70-column layout (so the S1 trunk's input width is unchanged), columns ``SC_SLOT_COLS``
(``hand_slot_onehot_4x9`` + ``next_slot_onehot_9``, 7..51) are always 0.

Card identity: key = RoyaleAPI base slug (``vocab.base_key(vocab.engine_key(name))`` with ``_`` -> ``-``, e.g.
``x-bow``, ``the-log``); id 0 = pad, cards 1..V sorted by key (meta ``card_vocab``). Form = 0 base / 1 evo /
2 hero / 3 pad, read from the side's ``final_decks`` entry (``Knight@evolution`` -> 1, ``@hero`` -> 2): it is the
form the card is DECKED in, applied to that card wherever it appears (hand, next, deck, played, past).

Label grid: ``y_xy`` is S1's continuous board (x, y); ``y_cell`` is ``model_v3.cell_label(y_xy, grid)`` (-1 on
wait rows), so ``--grid lattice`` = §5cs.70. The i=1 rotation (§5cs.67) is applied upstream by the crawl; the
driven corpora are already in one frame. Replays without ``frames`` give no wait rows (§5cs.69) -- counted.

usage: icebow/.venv/Scripts/python.exe -m pipeline.dataset_gen --corpus DIR [DIR ...] --out PATH.npz
       [--grid lattice] [--limit N] [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import vocab
from .dataset import PAST_K, _Rows, _tag_split, build_replay, deck_sides
from .obs_contract import F, S, Deck, load_deck

REPO = Path(__file__).resolve().parents[1]
SC_SLOT_COLS = slice(7, 52)          # to_tokens: hand_slot_onehot_4x9 (7..42) + next_slot_onehot_9 (43..51)
CARD_PAD = 0
FORM_BASE, FORM_EVO, FORM_HERO, FORM_PAD = 0, 1, 2, 3
_FORMS = {"": FORM_BASE, "evolution": FORM_EVO, "hero": FORM_HERO}
V3VAL_NPZ = REPO / "icebow" / "data" / "pipeline" / "s1_dataset.npz"
_ICEBOW: Optional[Deck] = None


def card_key(engine_name: str) -> Optional[str]:
    """Engine deck/hand name -> RoyaleAPI base slug (forms stripped); None for placeholders."""
    k = vocab.engine_key(engine_name)
    return vocab.base_key(k).replace("_", "-") if k else None


def card_form(engine_name: str) -> int:
    """``Knight@evolution`` -> 1, ``@hero`` -> 2, plain -> 0; an unknown suffix raises."""
    return _FORMS[str(engine_name).split("@", 1)[1] if "@" in str(engine_name) else ""]


def side_deck(names: list[str]) -> Optional[Deck]:
    """A throwaway 8-slot ``Deck`` of this side's cards (vocab base keys, engine order) for ``build_replay``.
    ``card_ids`` are placeholders: they only feed the sc slot one-hots, which this module decodes and zeroes."""
    keys = [vocab.base_key(vocab.engine_key(n) or "") for n in names]
    if len(names) != 8 or "" in keys or len(set(keys)) != 8:
        return None
    return Deck(name="gen", cards=tuple(keys), card_ids=tuple(range(1_000_000, 1_000_008)), config=Path(),
                src_dir=Path(), crawl_dir=Path(), data_dir=Path())


def replay_rows(path: str, wait_stride: int = 40, play_window: int = 20) -> dict[str, Any]:
    """One replay file -> its rows with card identities as indices into the returned local ``keys`` (-1 = pad)."""
    global _ICEBOW
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        st: dict[str, Any] = {}
        if not rec.get("frames"):
            st["no_frames"] = 1                                  # §5cs.69: play-only replay, no wait rows
        fd = rec.get("final_decks") or {}
        decks = {s: side_deck(fd.get(str(s)) or []) for s in (0, 1)}
        mirror = decks[0] is not None and decks[1] is not None and set(decks[0].cards) == set(decks[1].cards)
        if mirror:
            decks[1] = decks[0]      # build_replay emits BOTH sides with ONE deck: its slot order decodes both
        keys: list[str] = []
        ktbl = np.full((2, 9), -1, np.int32)                     # [side, slot] -> local key index; slot 8 = unknown
        ftbl = np.full((2, 9), FORM_PAD, np.int16)
        for s in (0, 1):
            if decks[s] is None:
                st["bad_deck_side"] = st.get("bad_deck_side", 0) + 1
                continue
            form = {vocab.base_key(vocab.engine_key(n)): card_form(n) for n in fd[str(s)]}   # this side's forms
            for j, c in enumerate(decks[s].cards):
                k = c.replace("_", "-")
                if k not in keys:
                    keys.append(k)
                ktbl[s, j], ftbl[s, j] = keys.index(k), form[c]
        rows = _Rows()
        for s in ((0,) if mirror else (0, 1)):                   # a mirror match is built once, both sides
            if decks[s] is not None:
                build_replay(rec, decks[s], rows, 0, wait_stride=wait_stride, play_window=play_window, val_pct=0,
                             stats=st)
        a = rows.arrays()
        n = len(a["sc"])
        side = a["side"].astype(np.int64)
        sc = a["sc"]
        hs = sc[:, 7:43].reshape(n, 4, 9).argmax(-1)
        ns = sc[:, 43:52].argmax(-1)
        ys = np.where(a["y_slot"] < 0, 8, a["y_slot"]).astype(np.int64)
        ws = np.where(a["y_wait_slot"] < 0, 8, a["y_wait_slot"]).astype(np.int64)
        ps = np.where(a["past"][:, :, 0] < 0, 8, a["past"][:, :, 0]).astype(np.int64)
        pos = np.where((hs == ys[:, None]).any(1), (hs == ys[:, None]).argmax(1), -1)
        pos[a["y_gate"] == 0] = -1
        sc = sc.copy()
        sc[:, SC_SLOT_COLS] = 0.0
        if _ICEBOW is None:
            _ICEBOW = load_deck("icebow")
        return {
            "path": path, "tag": str(rec["tag"]), "keys": keys, "stats": st,
            "deck_keys": {s: sorted(keys[i] for i in ktbl[s, :8]) for s in (0, 1) if decks[s] is not None},
            "icebow_sides": deck_sides(rec, _ICEBOW),
            "tok": a["tok"], "n_tok": np.diff(a["off"]), "sc": sc,
            "hand_card": ktbl[side[:, None], hs], "hand_form": ftbl[side[:, None], hs],
            "next_card": ktbl[side, ns], "next_form": ftbl[side, ns],
            "deck_card": ktbl[side, :8], "deck_form": ftbl[side, :8],
            "y_card": ktbl[side, ys], "y_hand_pos": pos.astype(np.int8),
            "y_wait_card": ktbl[side, ws],
            "past_card": ktbl[side[:, None], ps], "past_form": ftbl[side[:, None], ps], "past_xydt": a["past"][:, :, 1:],
            **{k: a[k] for k in ("y_xy", "y_gate", "y_wait_dt", "tick", "side", "y_crowns", "y_slot")},
        }
    except Exception as ex:                                      # a corrupt / partial file is counted, not fatal
        return {"path": path, "error": f"{type(ex).__name__}: {ex}"}


def _job(args: tuple) -> dict[str, Any]:
    return replay_rows(*args)


def v3val_tags(npz: Path = V3VAL_NPZ) -> set[str]:
    """Replay tags of S1's v3 VAL instrument: ``s1_dataset.npz`` rows with split == 1, via their ``rep``."""
    if not npz.is_file():
        return set()
    z = np.load(npz, allow_pickle=False)
    return {str(t) for t in z["tags"][np.unique(z["rep"][z["split"] == 1])]}


def build(corpora: list[Path], out: Path, *, grid: str = "lattice", limit: int = 0, workers: int = 4,
          wait_stride: int = 40, play_window: int = 20, val_pct: int = 10, v3val_npz: Path = V3VAL_NPZ,
          log=sys.stderr) -> dict[str, Any]:
    t0 = time.time()
    files, seen = [], set()
    for c in corpora:
        for f in sorted(Path(c).glob("replay_*.json")):
            if f.name not in seen:                               # the same replay in two corpora is read once
                seen.add(f.name)
                files.append(str(f))
    if limit:
        files = files[:limit]
    keep_val = v3val_tags(v3val_npz)
    jobs = [(f, wait_stride, play_window) for f in files]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = []
            for i, r in enumerate(ex.map(_job, jobs, chunksize=8)):
                res.append(r)
                if log and (i + 1) % 200 == 0:
                    print(f"[dataset_gen] {i + 1}/{len(jobs)} {time.time() - t0:.0f}s", file=log, flush=True)
    else:
        res = [_job(j) for j in jobs]
    failed = [(r["path"], r["error"]) for r in res if "error" in r]
    res = [r for r in res if "error" not in r]

    vocab_keys = sorted({k for r in res for k in r["keys"]})
    gid = {k: i + 1 for i, k in enumerate(vocab_keys)}          # 0 = pad
    deck_ix: dict[tuple, int] = {}
    parts: dict[str, list[np.ndarray]] = {}
    tags: list[str] = []
    st: Counter = Counter()
    unmapped: set = set()
    sides_per_deck: Counter = Counter()
    for r in res:
        for k, v in r["stats"].items():
            if isinstance(v, set):
                unmapped |= v
            else:
                st[k] += v
        n = len(r["sc"])
        if not n:
            st["replays_no_rows"] += 1
            continue
        rep = len(tags)
        tags.append(r["tag"])
        lut = np.asarray([gid[k] for k in r["keys"]] + [CARD_PAD], np.int16)   # local -1 -> pad
        side = r["side"].astype(np.int64)
        dk = {s: tuple(sorted(gid[k] for k in ks)) for s, ks in r["deck_keys"].items()}
        for s in sorted(set(side.tolist())):                    # deck-sides that produced rows
            deck_ix.setdefault(dk[s], len(deck_ix))
            sides_per_deck[deck_ix[dk[s]]] += 1
        deck_card = lut[r["deck_card"]]
        order = np.argsort(deck_card, 1, kind="stable")           # canonical deck order: by card id
        split = 1 if (_tag_split(r["tag"], val_pct) or r["tag"] in keep_val) else 0
        past = np.concatenate([lut[r["past_card"]][..., None].astype(np.float32),
                               r["past_form"][..., None].astype(np.float32), r["past_xydt"]], -1)
        cols = {
            "tok": r["tok"], "n_tok": r["n_tok"], "sc": r["sc"],
            "hand_card": lut[r["hand_card"]], "hand_form": r["hand_form"],
            "next_card": lut[r["next_card"]], "next_form": r["next_form"],
            "deck_card": np.take_along_axis(deck_card, order, 1),
            "deck_form": np.take_along_axis(r["deck_form"], order, 1),
            "past": past, "y_gate": r["y_gate"], "y_card": lut[r["y_card"]], "y_hand_pos": r["y_hand_pos"],
            "y_xy": r["y_xy"], "y_wait_card": lut[r["y_wait_card"]], "y_wait_dt": r["y_wait_dt"],
            "y_crowns": r["y_crowns"], "tick": r["tick"], "side": r["side"],
            "rep": np.full(n, rep, np.int32), "split": np.full(n, split, np.int8),
            "deck_id": np.asarray([deck_ix[dk[int(s)]] for s in side], np.int32),
            "v3val": np.asarray([int(r["tag"] in keep_val and int(s) in r["icebow_sides"]) for s in side], np.int8),
        }
        for k, v in cols.items():
            parts.setdefault(k, []).append(v)

    arrs = {k: np.concatenate(v) for k, v in parts.items()}
    n = len(arrs.get("sc", []))
    if not n:
        raise SystemExit(f"no rows from {len(files)} files ({len(failed)} failed)")
    arrs["off"] = np.concatenate([[0], np.cumsum(arrs.pop("n_tok"))]).astype(np.int64)
    for k in ("hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "y_card", "y_wait_card"):
        arrs[k] = arrs[k].astype(np.int16)
    import torch                                                 # only for the shared label-grid helper
    from .model_v3 import cell_label
    cell = cell_label(torch.from_numpy(arrs["y_xy"].astype(np.float32)), grid).numpy().astype(np.int16)
    arrs["y_cell"] = np.where(arrs["y_gate"] == 1, cell, -1).astype(np.int16)

    play = arrs["y_gate"] == 1
    card_play = Counter(arrs["y_card"][play].tolist())
    card_decks = Counter(int(c) for key in deck_ix for c in key)
    rows_per_deck = np.bincount(arrs["deck_id"], minlength=len(deck_ix))
    decks = [{"id": i, "cards": [vocab_keys[c - 1] for c in key], "sides": int(sides_per_deck[i]),
              "rows": int(rows_per_deck[i])} for key, i in deck_ix.items()]
    meta = {
        "kind": "generalist", "corpora": [str(c) for c in corpora], "files_seen": len(files), "replays": len(tags),
        "failed": failed, "grid": grid, "wait_stride": wait_stride, "play_window": play_window, "val_pct": val_pct,
        "v3val_npz": str(v3val_npz), "v3val_tags": len(keep_val), "F": F, "S": S, "PAST_K": PAST_K,
        "sc_zeroed_cols": [SC_SLOT_COLS.start, SC_SLOT_COLS.stop],
        "past_cols": ["card", "form", "x", "y", "dt_s"], "card_pad": CARD_PAD,
        "forms": {"0": "base", "1": "evo", "2": "hero", "3": "pad"},
        "card_vocab": ["<pad>"] + vocab_keys,
        "card_counts": {k: {"plays": int(card_play[gid[k]]), "decks": int(card_decks[gid[k]])} for k in vocab_keys},
        "decks": decks, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {**dict(st), "unmapped": sorted(unmapped)},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, tags=np.asarray(tags), meta=json.dumps(meta), **arrs)
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    top = sorted(decks, key=lambda d: -d["rows"])[:20]
    return {"out": str(out), "files": len(files), "replays": len(tags), "failed": len(failed),
            "rows": n, "play_rows": int(play.sum()), "wait_rows": int((~play).sum()),
            "val_rows": int((arrs["split"] == 1).sum()), "v3val_rows": int(arrs["v3val"].sum()),
            "decks": len(deck_ix), "card_vocab": len(vocab_keys), "seconds": round(time.time() - t0, 1),
            "top20_decks": [(d["rows"], d["sides"], ",".join(d["cards"])) for d in top],
            "stats": meta["stats"]}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--corpus", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--grid", choices=("floor", "lattice"), default="lattice")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--wait-stride", type=int, default=40)
    ap.add_argument("--play-window", type=int, default=20)
    ap.add_argument("--val-pct", type=int, default=10)
    ap.add_argument("--v3val-npz", type=Path, default=V3VAL_NPZ)
    a = ap.parse_args(argv)
    s = build(a.corpus, a.out, grid=a.grid, limit=a.limit, workers=a.workers, wait_stride=a.wait_stride,
              play_window=a.play_window, val_pct=a.val_pct, v3val_npz=a.v3val_npz)
    print(json.dumps(s, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

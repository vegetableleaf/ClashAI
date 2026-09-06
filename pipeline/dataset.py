"""S1 dataset builder: corpus_v3 replays -> one compact ``.npz`` per deck of (state, target) rows.

Input: ``replay_<tag>.json`` written by ``research/sandbox_tools/replay_batch.py --record-plays``
(``play_frames`` = the FULL engine observation immediately before every driven play of either side,
with both players' hand/next; ``frames`` = a compact observation every ``record_every`` ticks, no
hands; ``log`` = one entry per driven play with ``accepted`` and ``hand_before``).

Rows, all in MY board frame (``obs_contract`` docstring; me at the bottom):
  * PLAY rows -- one per ACCEPTED play of a deck-matching side: the state before it, the deck slot
    played and the continuous cell (x, y) in [0, 1]. gate = 1.
  * WAIT rows -- every ``wait_stride // record_every``-th compact frame where that side had no accepted play within
    ``play_window`` ticks. gate = 0. Their hand/next are reconstructed exactly: a hand only changes
    when its owner plays, so between my plays k and k+1 the hand is ``hand_before`` of play k+1 and
    ``next`` is play k+1's recorded ``next``. Frames after my last play are dropped (hand unknown).
    ``wait_slot`` / ``wait_dt`` = the slot I play next and how many seconds until then (the
    "wait for card X" target of the S1 spec).
  * every row also carries ``past`` (my last PAST_K accepted plays: slot, x, y, seconds ago; -1 = none)
    and ``y_crowns`` (the REAL RoyaleAPI result for my side: mine, theirs) for the value head.
Units are stored variable-length (``tok`` rows + ``off`` offsets) in the ``to_tokens`` ranking, so the
trainer pads per batch; ``sc`` is the ``to_tokens`` scalar vector.

Split: by replay tag (``crc32(tag) % 100 < val_pct`` -> val), so no replay leaks across the split.
Both decks share this file unchanged (owner ruling: hogeq inherits every change).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import vocab
from .obs_contract import Deck, F, S, _engine_xy, from_engine, load_deck, to_tokens

REPO = Path(__file__).resolve().parents[1]
PAST_K = 3          # past-actions channel: my last K accepted plays as (slot, x, y, seconds ago); slot -1 = none
CORPUS = REPO / "scratchpad" / "gauntlet" / "ext" / "corpus_v3"


def deck_sides(rec: dict, deck: Deck) -> list[int]:
    """Sides whose engine deck is exactly this deck (8 distinct slots matched on base key)."""
    out = []
    for s in (0, 1):
        names = (rec.get("final_decks") or {}).get(str(s)) or []
        slots = sorted(deck.slot_of(vocab.engine_key(n)) for n in names)
        if len(names) == 8 and slots == list(range(8)):
            out.append(s)
    return out


def crawl_slot(deck: Deck, crawl_name: str) -> int:
    """Deck slot of a RoyaleAPI crawl card name (``the-log``, ``x-bow``, ``ice-wizard`` -> vocab keys)."""
    return deck.slot_of(str(crawl_name).strip().lower().replace("-", "_").replace(" ", "_"))


def _past(done: list[tuple[int, int, float, float]], t: int) -> np.ndarray:
    """``done`` = my accepted plays so far as (tick, slot, x, y), tick ascending; the last PAST_K before t."""
    out = np.full((PAST_K, 4), -1.0, np.float32)
    prev = [d for d in done if d[0] < t][-PAST_K:]
    for i, (tk, sl, x, y) in enumerate(reversed(prev)):
        out[i] = (sl, x, y, (t - tk) * 0.05)
    return out


def _crowns(rec: dict, side: int) -> tuple[int, int]:
    """Real result of the replay for this side (RoyaleAPI crowns, not the engine's)."""
    c = (rec.get("expected") or {}).get("crowns_by_side") or {}
    return int(c.get(str(side), 0)), int(c.get(str(1 - side), 0))


def _tag_split(tag: str, val_pct: int) -> int:
    return 1 if (zlib.crc32(tag.encode()) % 100) < val_pct else 0


class _Rows:
    def __init__(self) -> None:
        self.tok: list[np.ndarray] = []
        self.off: list[int] = [0]
        self.sc: list[np.ndarray] = []
        self.slot: list[int] = []
        self.xy: list[tuple[float, float]] = []
        self.gate: list[int] = []
        self.wait_slot: list[int] = []
        self.wait_dt: list[float] = []
        self.tick: list[int] = []
        self.rep: list[int] = []
        self.side: list[int] = []
        self.split: list[int] = []
        self.past: list[np.ndarray] = []
        self.crowns: list[tuple[int, int]] = []

    def add(self, bs, *, slot: int, xy: tuple[float, float], gate: int, wait_slot: int, wait_dt: float,
            tick: int, rep: int, side: int, split: int, past: np.ndarray, crowns: tuple[int, int]) -> None:
        toks, mask, sc = to_tokens(bs)
        kept = toks[mask]
        self.tok.append(kept)
        self.off.append(self.off[-1] + len(kept))
        self.sc.append(sc)
        self.slot.append(slot); self.xy.append(xy); self.gate.append(gate)
        self.wait_slot.append(wait_slot); self.wait_dt.append(wait_dt)
        self.tick.append(tick); self.rep.append(rep); self.side.append(side); self.split.append(split)
        self.past.append(past); self.crowns.append(crowns)

    def arrays(self) -> dict[str, np.ndarray]:
        n = len(self.sc)
        return {
            "tok": np.concatenate(self.tok).astype(np.float32) if self.tok else np.zeros((0, F), np.float32),
            "off": np.asarray(self.off, np.int64),
            "sc": np.stack(self.sc).astype(np.float32) if n else np.zeros((0, S), np.float32),
            "y_slot": np.asarray(self.slot, np.int8), "y_xy": np.asarray(self.xy, np.float32).reshape(n, 2),
            "y_gate": np.asarray(self.gate, np.int8), "y_wait_slot": np.asarray(self.wait_slot, np.int8),
            "y_wait_dt": np.asarray(self.wait_dt, np.float32), "tick": np.asarray(self.tick, np.int32),
            "rep": np.asarray(self.rep, np.int32), "side": np.asarray(self.side, np.int8),
            "split": np.asarray(self.split, np.int8),
            "past": np.stack(self.past).astype(np.float32) if n else np.zeros((0, PAST_K, 4), np.float32),
            "y_crowns": np.asarray(self.crowns, np.int8).reshape(n, 2),
        }


def build_replay(rec: dict, deck: Deck, rows: _Rows, rep_index: int, *, wait_stride: int = 40,
                 play_window: int = 20, val_pct: int = 15, stats: Optional[dict] = None) -> None:
    st = stats if stats is not None else {}
    split = _tag_split(str(rec["tag"]), val_pct)
    pframes = {int(p["play_index"]): p for p in rec.get("play_frames") or []}
    for side in deck_sides(rec, deck):
        engine_deck = rec["final_decks"][str(side)]
        mirror = side == 1
        # every driven play of this side (accepted or not) in tick order; accepted ones become PLAY rows
        plays = sorted((e for e in rec["log"] if int(e.get("side", -1)) == side and "tick" in e),
                       key=lambda e: (int(e["tick"]), int(e["play_index"])))
        if not plays:
            st["no_plays"] = st.get("no_plays", 0) + 1
            continue
        crowns = _crowns(rec, side)
        done: list[tuple[int, int, float, float]] = []
        for e in plays:
            pf = pframes.get(int(e["play_index"]))
            if not e.get("accepted") or pf is None:
                st["play_skipped"] = st.get("play_skipped", 0) + 1
                continue
            slot = crawl_slot(deck, e["card"])
            if slot < 0:
                st["unmapped_card:" + str(e["card"])] = st.get("unmapped_card:" + str(e["card"]), 0) + 1
                continue
            bs = from_engine(pf, side, deck, engine_deck=engine_deck, unmapped=st.setdefault("unmapped", set()))
            xy = _engine_xy(float(e["x"]), float(e["y"]), mirror)
            rows.add(bs, slot=slot, xy=xy, gate=1, wait_slot=slot, wait_dt=0.0, tick=int(pf["tick"]),
                     rep=rep_index, side=side, split=split, past=_past(done, int(pf["tick"])), crowns=crowns)
            done.append((int(e["tick"]), slot, xy[0], xy[1]))
            st["play_rows"] = st.get("play_rows", 0) + 1
        # WAIT rows from compact frames. Only ACCEPTED plays count: the engine's hand changes only on an
        # accepted play, so between accepted plays k and k+1 the hand is exactly hand_before(k+1).
        plays = [e for e in plays if e.get("accepted")]
        acc_ticks = [int(e["tick"]) for e in plays]
        j = 0
        every = max(1, wait_stride // max(1, int(rec.get("record_every") or 20)))
        for k, fr in enumerate(rec.get("frames") or []):
            t = int(fr["tick"])
            if k % every:
                continue
            while j < len(plays) and int(plays[j]["tick"]) <= t:
                j += 1
            if j >= len(plays):
                break                                   # after my last play: hand unknown
            nxt = plays[j]
            if any(t < a <= t + play_window for a in acc_ticks):
                st["wait_in_window"] = st.get("wait_in_window", 0) + 1
                continue
            pf_next = pframes.get(int(nxt["play_index"]))
            me = next((p for p in (pf_next or {}).get("players") or [] if int(p["side"]) == side), None)
            hand = list(nxt.get("hand_before") or (me or {}).get("hand") or [])
            if len(hand) != 4:
                st["wait_no_hand"] = st.get("wait_no_hand", 0) + 1
                continue
            obs = dict(fr)
            obs["players"] = [{"side": side, "hand": hand, "next": (me or {}).get("next")}]
            bs = from_engine(obs, side, deck, engine_deck=engine_deck, unmapped=st.setdefault("unmapped", set()))
            wslot = crawl_slot(deck, nxt["card"])
            rows.add(bs, slot=-1, xy=(-1.0, -1.0), gate=0, wait_slot=wslot,
                     wait_dt=(int(nxt["tick"]) - t) * 0.05, tick=t, rep=rep_index, side=side, split=split,
                     past=_past(done, t), crowns=crowns)
            st["wait_rows"] = st.get("wait_rows", 0) + 1


def build(deck_name: str, corpus: Optional[Path] = None, out: Optional[Path] = None, *, wait_stride: int = 40,
          play_window: int = 20, val_pct: int = 15, limit: int = 0, log=sys.stderr) -> dict[str, Any]:
    deck = load_deck(deck_name)
    corpus = corpus or (CORPUS / deck_name)
    out = out or (deck.data_dir / "pipeline" / "s1_dataset.npz")
    files = sorted(corpus.glob("replay_*.json"))
    if limit:
        files = files[:limit]
    rows, tags, st = _Rows(), [], {}
    t0 = time.time()
    for i, f in enumerate(files):
        rec = json.loads(f.read_text(encoding="utf-8"))
        sides = deck_sides(rec, deck)
        if not sides:
            st["no_deck_side"] = st.get("no_deck_side", 0) + 1
            continue
        st["mirror_matches"] = st.get("mirror_matches", 0) + (len(sides) == 2)
        tags.append(str(rec["tag"]))
        build_replay(rec, deck, rows, len(tags) - 1, wait_stride=wait_stride, play_window=play_window,
                     val_pct=val_pct, stats=st)
        if log and (i + 1) % 50 == 0:
            print(f"[dataset] {deck_name} {i + 1}/{len(files)} rows={len(rows.sc)} {time.time() - t0:.0f}s",
                  file=log, flush=True)
    arrs = rows.arrays()
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"deck": deck_name, "corpus": str(corpus), "replays": len(tags), "files_seen": len(files),
            "wait_stride": wait_stride, "play_window": play_window, "val_pct": val_pct, "F": F, "S": S,
            "cards": list(deck.cards), "card_ids": list(deck.card_ids), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": {k: (sorted(v) if isinstance(v, set) else v) for k, v in st.items()}}
    np.savez_compressed(out, tags=np.asarray(tags), meta=json.dumps(meta), **arrs)
    n = int(len(arrs["sc"]))
    summary = {"out": str(out), "rows": n, "play_rows": int((arrs["y_gate"] == 1).sum()),
               "wait_rows": int((arrs["y_gate"] == 0).sum()), "val_rows": int((arrs["split"] == 1).sum()),
               "replays": len(tags), "units_total": int(len(arrs["tok"])), "seconds": round(time.time() - t0, 1),
               "stats": meta["stats"]}
    return summary


def load(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    z = np.load(path, allow_pickle=False)
    arrs = {k: z[k] for k in z.files if k not in ("meta",)}
    return arrs, json.loads(str(z["meta"]))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("deck")
    ap.add_argument("--corpus", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--wait-stride", type=int, default=40)
    ap.add_argument("--play-window", type=int, default=20)
    ap.add_argument("--val-pct", type=int, default=15)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    s = build(a.deck, a.corpus, a.out, wait_stride=a.wait_stride, play_window=a.play_window, val_pct=a.val_pct,
              limit=a.limit)
    print(json.dumps(s, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

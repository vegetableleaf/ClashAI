"""GENERALIST (multi-deck) imitation dataset: driven engine corpora -> one ``.npz`` of rows for BOTH sides of
every replay, any deck, with card-IDENTITY features and labels instead of S1's 8-deck-slot ones.

Spec: ``scratchpad/gauntlet/L68/generalist/plan.md`` ("Design").

Row construction is S1's, unchanged: for each side, a throwaway 8-card ``Deck`` is made from that side's engine
deck (``final_decks``) and handed to ``dataset.build_replay`` -- so play rows (``_as_compact`` frames, §5cs.61),
wait-row sampling, past plays, crowns and the (x, y) labels are byte-for-byte S1's. The deck-slot one-hots that
S1 writes into ``sc`` are then DECODED into card identities (slot -> that side's card) and ZEROED in ``sc``:
``sc`` keeps S1's 70-column layout (so the S1 trunk's input width is unchanged), columns ``SC_SLOT_COLS``
(``hand_slot_onehot_4x9`` + ``next_slot_onehot_9``, 7..51) are always 0.

V3 opt-in (``--feature-version 3``) adds parallel ``unit_form`` and ``opp_past`` arrays.
Legacy versions retain every existing feature, including decked-form own past. Recording
forms without stable ids use conservative isolated cohorts; see ``tag_recording``.

Card identity: key = RoyaleAPI base slug (``vocab.base_key(vocab.engine_key(name))`` with ``_`` -> ``-``, e.g.
``x-bow``, ``the-log``); id 0 = pad, cards 1..V sorted by key (meta ``card_vocab``). Form = 0 base / 1 evo /
2 hero / 3 pad, read from the side's ``final_decks`` entry (``Knight@evolution`` -> 1, ``@hero`` -> 2): it is the
form the card is DECKED in, applied to that card wherever it appears (hand, next, deck, played, past).

Label grid: ``y_xy`` is S1's continuous board (x, y); ``y_cell`` is ``model_v3.cell_label(y_xy, grid)`` (-1 on
wait rows), so ``--grid lattice`` = §5cs.70. The i=1 rotation (§5cs.67) is applied upstream by the crawl; the
driven corpora are already in one frame. Replays without ``frames`` give no wait rows (§5cs.69) -- counted.

usage: icebow/.venv/Scripts/python.exe -m pipeline.dataset_gen --corpus DIR [DIR ...] --out PATH.npz
       [--grid lattice] [--limit N] [--workers 4] [--shift-ticks 26]
``--shift-ticks S``: latency-shifted play rows (board ~S ticks before the play executed; ``dataset.build_replay``).
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


def evolution_cycles() -> dict[str, int]:
    """RoyaleSim card.rs:10941: per-card evo_cycles, absent -> 2 basic plays.

    state.rs:6545 / 8738 / 24065: independent (side, card) counters start at
    zero, increment on accepted base plays and reset after an evolved play.
    """
    if not hasattr(evolution_cycles, "cache"):
        path = REPO / "research/ext/Royale/RoyaleSim/data/derived/cards.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        evolution_cycles.cache = {card_key(c["form_of"]): int(c.get("evo_cycles") or 2)
                                  for c in data["evolutions"]}
    return evolution_cycles.cache


def played_forms(rec: dict) -> list[dict]:
    """Accepted public plays, chronological, with ACTUAL form; never change own past."""
    cycles = evolution_cycles()
    decks = {(int(s), card_key(n)): card_form(n)
             for s, ns in rec["final_decks"].items() for n in ns}
    counters: Counter = Counter()
    out = []
    for e in sorted(rec["log"], key=lambda e: (int(e.get("tick", 0)), int(e.get("play_index", 0)))):
        if not e.get("accepted") or e.get("ability") or "card" not in e:
            continue
        key = card_key(e["card"])
        pair = (int(e["side"]), key)
        decked = decks.get(pair, 0)
        form = 2 if decked == 2 else 0
        if decked == 1:
            form = int(counters[pair] >= cycles.get(key, 2))
            counters[pair] = 0 if form else counters[pair] + 1
        # SIM replay logs may supply the directly observed actual form.
        form = int(e.get("actual_form", form))
        out.append(dict(e, card=key, form=form))
    return out


def opponent_past(plays: list[dict], tick: int, side: int, gid: dict[str, int]) -> np.ndarray:
    """Public accepted opponent plays strictly before tick; newest first, in MY frame."""
    from .dataset import OPP_PAST_K
    from .obs_contract import _engine_xy, TICK_S
    out = np.tile(np.array([0, FORM_PAD, -1, -1, -1], np.float32), (OPP_PAST_K, 1))
    prev = [e for e in plays if e.get("accepted", True) and int(e["side"]) != side and int(e["tick"]) < tick]
    prev.sort(key=lambda e: (int(e["tick"]), int(e.get("play_index", 0))))
    for i, e in enumerate(reversed(prev[-OPP_PAST_K:])):
        c = gid.get(card_key(e["card"]), 0)
        if c:
            x, y = _engine_xy(float(e["x"]), float(e["y"]), side == 1)
            out[i] = (c, int(e["form"]), x, y, (tick - int(e["tick"])) * TICK_S)
    return out


def tag_recording(rec: dict, plays: list[dict], stats: dict) -> dict:
    """Conservative, causal attribution. Never treat the seventh (kind) column as an id.

    Stable ids (dict entity_id, frame entity_ids, or explicit entity_fields) retain
    birth attribution. Legacy six/seven-column frames have NO ids: only isolated
    cohorts born on a previously empty board for that side/card within 60 ticks
    and 3 tiles of exactly one play are attributable. A later play while a cohort
    is alive makes it ambiguous, hence base until the board empties. No future
    frame or future play can change a row's form. Parent-labelled hero summons
    (including Goblins' 2560-HP flag) inherit their parent's hero form.
    """
    from .obs_contract import entity_form
    deck_forms = {(int(s), card_key(n)): card_form(n)
                  for s, ns in rec["final_decks"].items() for n in ns}
    for (side, key), form in deck_forms.items():
        if form == FORM_EVO:
            stats["evo_deck_sides:" + key] = stats.get("evo_deck_sides:" + key, 0) + 1
    by_card = {}
    for e in plays:
        by_card.setdefault((int(e["side"]), e["card"]), []).append(e)
        k = f"actual_plays:{e['card']}:{e['form']}"
        stats[k] = stats.get(k, 0) + 1
    frames = [(int(f["tick"]), source, i, f) for source in ("frames", "play_frames")
              for i, f in enumerate(rec.get(source) or [])]
    frames.sort(key=lambda v: v[0])
    out = dict(rec)
    for source in ("frames", "play_frames"):
        out[source] = list(rec.get(source) or [])
    active, ids = {}, {}
    counted_births = set()
    previous_tick = None
    snapshot = {}
    for tick, source, index, frame in frames:
        # Multiple pre-act observations at a tick must use the same prior snapshot.
        if tick != previous_tick:
            snapshot = dict(active)
            previous_tick = tick
        groups = {}
        ents = frame.get("entities") or []
        forms = [0] * len(ents)
        for j, e in enumerate(ents):
            raw = isinstance(e, dict)
            side, x, y, name, hp = ((e["side"], e["x"], e["y"], e.get("name", "-1"), e["hp"])
                                    if raw else e[:5])
            if str(name) == "-1" or hp <= 0:
                continue
            pair = (int(side), card_key(name))
            eid = e.get("entity_id") if raw else None
            if not raw and frame.get("entity_ids"):
                eid = frame["entity_ids"][j]
            fields = rec.get("entity_fields", [])
            if not raw and "entity_id" in fields:
                eid = e[fields.index("entity_id")]
            groups.setdefault(pair, []).append((j, e, eid, float(x), float(y)))
        active = {}
        for pair, bodies in groups.items():
            decked = deck_forms.get(pair, 0)
            before = [e for e in by_card.get(pair, []) if int(e["tick"]) < tick]
            recent = [e for e in before if tick - int(e["tick"]) <= 60]
            last_tick = int(before[-1]["tick"]) if before else -1
            cohort = snapshot.get(pair)
            if cohort is None:
                near = [e for e in recent if all((x - float(e["x"]))**2 + (y - float(e["y"]))**2 <= 3000**2
                                                 for _, _, _, x, y in bodies)]
                cohort = (int(near[0]["form"]), last_tick, "isolated") if len(near) == 1 else (0, last_tick, "no_birth_evidence")
                if cohort[0] and (tick, pair) not in counted_births:
                    counted_births.add((tick, pair))
                    k = f"tag_birth:{pair[1]}:{cohort[0]}"
                    stats[k] = stats.get(k, 0) + len(bodies)
            elif last_tick != cohort[1]:
                cohort = (0, last_tick, "overlapping_plays")
            active[pair] = cohort
            for j, e, eid, x, y in bodies:
                f = 2 if decked == 2 else cohort[0] if decked == 1 else 0
                if isinstance(e, dict) and "status_flags" in e:
                    f = entity_form(e)
                elif eid is not None:
                    ident = (pair, eid)
                    if ident not in ids:
                        near = [p for p in recent if (x-float(p["x"]))**2 + (y-float(p["y"]))**2 <= 3000**2]
                        ids[ident] = 2 if decked == 2 else int(near[0]["form"]) if len(near) == 1 else 0
                    f = ids[ident]
                forms[j] = f
                if decked and not f:
                    k = f"tag_base_observations:{pair[1]}"
                    stats[k] = stats.get(k, 0) + 1
                if decked == 1 and not f and cohort[2] != "isolated":
                    k = f"tag_ambiguous:{pair[1]}:{cohort[2]}"
                    stats[k] = stats.get(k, 0) + 1
                if f:
                    k = f"tag_observations:{pair[1]}:{f}"
                    stats[k] = stats.get(k, 0) + 1
                    hp = e["max_hp"] if isinstance(e, dict) else e[5]
                    k = f"tag_max_hp:{pair[1]}:{f}:{hp}"
                    stats[k] = stats.get(k, 0) + 1
        out[source][index] = dict(frame, unit_forms=forms)
    return out


class _PublicRows(_Rows):
    def add(self, bs, **kwargs):
        from dataclasses import replace
        from .public_observation import body_only_board
        # The caller fills these scalars from the causal public timeline later.
        super().add(body_only_board(replace(bs, opp_elixir=None)), **kwargs)


def replay_rows(path: str, wait_stride: int = 40, play_window: int = 20, shift_ticks: int = 0, feature_version: int = 1) -> dict[str, Any]:
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
        actual_plays = played_forms(rec) if feature_version == 3 else []
        if feature_version == 3:
            rec = tag_recording(rec, actual_plays, st)
        observers = None
        if feature_version >= 4:
            from .native_recording import tag_native_recording
            from .public_observation import recording_observers
            rec = tag_native_recording(rec, st)
            unknown = {k: v for k, v in st.items() if k.startswith('native_unknown_card_id:') and v}
            if unknown:
                raise ValueError(f'gen_v3.1 exact forms require catalog coverage: {unknown}')
            observers = recording_observers(rec)
            actual_plays = sorted([e for o in observers for e in o.plays], key=lambda e: (e['tick'], e['side'], e['card']))
        rows = (_PublicRows if feature_version >= 4 else _Rows)(feature_version)
        for s in ((0,) if mirror else (0, 1)):                   # a mirror match is built once, both sides
            if decks[s] is not None:
                build_replay(rec, decks[s], rows, 0, wait_stride=wait_stride, play_window=play_window, val_pct=0,
                             stats=st, shift_ticks=shift_ticks, feature_version=feature_version)
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
        if observers is not None:
            # Opponent truth in generic engine rows is never a gen_v3.1 input.
            sc[:, 5] = [observers[int(s)].estimate_at(int(t))/10 for s, t in zip(side, a['tick'])]
            sc[:, 6] = 1.0
        if _ICEBOW is None:
            _ICEBOW = load_deck("icebow")
        extra = {}
        if feature_version >= 4:
            from .projectile_observation import recording_tokens
            extra = recording_tokens(rec, a['tick'], side, keys, st)
            gid = {key: i+1 for i, key in enumerate(keys)}
            from .own_ability import tokens
            from bisect import bisect_right
            extra['own_ability'] = np.stack([tokens(
                observers[int(s)].ability_rows[bisect_right(observers[int(s)].ability_ticks, int(t))-1]
                if bisect_right(observers[int(s)].ability_ticks, int(t)) else [], gid, observers[int(s)].own_events, int(t))
                for s, t in zip(side, a['tick'])])
        return {
            **extra,
            "path": path, "tag": str(rec["tag"]), "keys": keys, "stats": st,
            "deck_keys": {s: sorted(keys[i] for i in ktbl[s, :8]) for s in (0, 1) if decks[s] is not None},
            "icebow_sides": deck_sides(rec, _ICEBOW),
            **({"unit_form": a["unit_form"], "actual_plays": actual_plays} if feature_version >= 3 else {}),
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
          shift_ticks: int = 0, feature_version: int = 1, log=sys.stderr) -> dict[str, Any]:
    t0 = time.time()
    files, seen = [], set()
    for c in corpora:
        paths = list(Path(c).glob('replay_*.json'))
        if feature_version >= 4:
            paths += list(Path(c).glob('j*/replay_*.json'))
        for f in sorted(paths):
            if f.name not in seen:                               # the same replay in two corpora is read once
                seen.add(f.name)
                files.append(str(f))
    if limit:
        files = files[:limit]
    keep_val = v3val_tags(v3val_npz)
    jobs = [(f, wait_stride, play_window, shift_ticks, feature_version) for f in files]
    spool = None
    if feature_version >= 4 and workers == 1:
        # Full projectile arrays must not compete with the live reader for RAM.
        import uuid
        from .dataset_spool import ReplaySpool, ArraySpool
        out.parent.mkdir(parents=True, exist_ok=True)
        spool = out.parent / ('v4_build_' + uuid.uuid4().hex)
        spool.mkdir()
        res = ReplaySpool(spool)
        for i, job in enumerate(jobs):
            row = _job(job)
            if 'error' in row:
                raise ValueError(f'gen_v3.1 build refuses failed recordings: {row}')
            res.append(row)
            if log and (i+1) % 100 == 0:
                print(f'[dataset_gen] {i+1}/{len(jobs)} {time.time()-t0:.0f}s', file=log, flush=True)
        if jobs:
            del row
    elif workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = []
            for i, r in enumerate(ex.map(_job, jobs, chunksize=8)):
                res.append(r)
                if log and (i + 1) % 200 == 0:
                    print(f"[dataset_gen] {i + 1}/{len(jobs)} {time.time() - t0:.0f}s", file=log, flush=True)
    else:
        res = [_job(j) for j in jobs]
    failed = [(r["path"], r["error"]) for r in res if "error" in r]
    if feature_version >= 4 and failed:
        raise ValueError(f'gen_v3.1 build refuses failed recordings: {len(failed)}; first={failed[0]}')
    if spool is None:
        res = [r for r in res if "error" not in r]

    vocab_keys = sorted({k for r in res for k in r["keys"]})
    gid = {k: i + 1 for i, k in enumerate(vocab_keys)}          # 0 = pad
    deck_ix: dict[tuple, int] = {}
    parts: dict[str, list[np.ndarray]] = {}
    disk_parts = ArraySpool(spool) if spool is not None else None
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
        if feature_version >= 3:
            cols["unit_form"] = r["unit_form"]
            cols["opp_past"] = np.stack([opponent_past(r["actual_plays"], int(t), int(s), gid)
                                          for t, s in zip(r["tick"], side)])
        if feature_version >= 4:
            from .public_observation import opponent_cycle
            cols['opp_cycle'] = np.stack([opponent_cycle(r['actual_plays'], int(t), int(s), gid)
                                         for t, s in zip(r['tick'], side)])
            for key in ('projectiles', 'effects', 'own_ability'):
                cols[key] = r[key].copy()
                local = cols[key][..., 0].astype(np.int64)-1
                cols[key][..., 0] = lut[local]
        for k, v in cols.items():
            if disk_parts is not None:
                disk_parts.append(k, v)
            else:
                parts.setdefault(k, []).append(v)

    arrs = disk_parts.arrays() if disk_parts is not None else {k: np.concatenate(v) for k, v in parts.items()}
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
        "shift_ticks": shift_ticks, "v3val_npz": str(v3val_npz), "v3val_tags": len(keep_val), "F": F, "S": S, "PAST_K": PAST_K,
        "sc_zeroed_cols": [SC_SLOT_COLS.start, SC_SLOT_COLS.stop],
        "past_cols": ["card", "form", "x", "y", "dt_s"], "card_pad": CARD_PAD,
        "forms": {"0": "base", "1": "evo", "2": "hero", "3": "pad"},
        "card_vocab": ["<pad>"] + vocab_keys,
        "card_counts": {k: {"plays": int(card_play[gid[k]]), "decks": int(card_decks[gid[k]])} for k in vocab_keys},
        "decks": decks, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {**dict(st), "unmapped": sorted(unmapped)},
    }
    if feature_version >= 3:
        meta.update(feature_version=feature_version, OPP_PAST_K=PAST_K, evolution_cycles=evolution_cycles(),
                    new_features={"unit_form_shape": list(arrs["unit_form"].shape),
                                  "opp_past_shape": list(arrs["opp_past"].shape),
                                  "evo_share": float(np.mean(arrs["unit_form"] == 1)),
                                  "hero_share": float(np.mean(arrs["unit_form"] == 2)),
                                  "opponent_rows_share": float(np.mean((arrs["opp_past"][..., 0] > 0).any(1)))})
    if feature_version >= 4:
        from .projectile_observation import PROJECTILE_COLS, EFFECT_COLS
        meta.pop('evolution_cycles', None)
        meta.update(projectile_cols=list(PROJECTILE_COLS), effect_cols=list(EFFECT_COLS))
        from .projectile_observation import unavailable_area_timers
        meta.update(public_timing_contract='R6_catalog_distance_speed_all_frames_v1',
                    area_timer_unknown_cards=sorted(unavailable_area_timers()))
        from .own_ability import ABILITY_COLS
        meta['own_ability_cols'] = list(ABILITY_COLS)
        meta['own_ability_readiness'] = 'own_accepted_deploy_and_press_history_plus_catalog; unknown_without_history'
        meta.update(public_observation='periodic_native_bodies_and_spell_sightings_v1',
                    opponent_elixir='public_counter_strictly_prior_sightings',
                    opp_cycle_cols=['card', 'form', 'subsequent_detected_plays', 'age_s'],
                    opp_cycle_shape=list(arrs['opp_cycle'].shape))
    if feature_version >= 5:
        from .body_identity import FAMILIES
        meta.update(body_identity_contract='catalog_spawner_bodies_v2_l73', body_identity_families=sorted(FAMILIES))
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
    ap.add_argument("--feature-version", type=int, choices=(1, 2, 3, 4, 5), default=1)
    ap.add_argument("--corpus", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--grid", choices=("floor", "lattice"), default="lattice")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--wait-stride", type=int, default=40)
    ap.add_argument("--play-window", type=int, default=20)
    ap.add_argument("--val-pct", type=int, default=10)
    ap.add_argument("--v3val-npz", type=Path, default=V3VAL_NPZ)
    ap.add_argument("--shift-ticks", type=int, default=0)
    a = ap.parse_args(argv)
    s = build(a.corpus, a.out, grid=a.grid, limit=a.limit, workers=a.workers, wait_stride=a.wait_stride,
              play_window=a.play_window, val_pct=a.val_pct, v3val_npz=a.v3val_npz,
              shift_ticks=a.shift_ticks, feature_version=a.feature_version)
    print(json.dumps(s, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

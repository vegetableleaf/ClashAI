"""E1 option B: ghost pool v1 (from corpus v6), its frozen held-out split, and the engine env that plays it.

    icebow/.venv/Scripts/python.exe -m pipeline.e1_pool build                  # writes the 3 NEW files, never overwrites
    icebow/.venv/Scripts/python.exe -m pipeline.e1_pool build --out-dir <dir>  # same build into another (empty) dir
    icebow/.venv/Scripts/python.exe -m pipeline.e1_pool verify                 # sha + re-derive the split, compare

Design: scratchpad/gauntlet/L67/e1_engine_rl_design.md section 2.2. Build log: scratchpad/gauntlet/L67/e1_baseline_build.md.
Nothing here touches the engine except ``PoolV1Env`` (constructed only by the eval harness, never by the builder).

POOL v1 ROW = pool v0's schema (scratchpad/gauntlet/L62/build_ghost_pool.py docstring; ``icebow_*`` = OUR deck's side)
with two differences and these additions:
  * ``icebow_deck`` / ``ghost_deck`` are stored in the corpus's FINAL engine order (``deck_order: "final"``), so
    ``deck_index`` of every command indexes the final order and ``PoolV1Env._resolve_decks`` needs no probe reset;
    ``engine_play.engine_deck_names(deck) == final_decks[side]`` is asserted at build AND at reset.
  * commands come from the corpus v6 drive log (both sides, ``play_index`` kept, ``src: "corpus"``) plus the
    ghost-script TAIL the drive never reached (plays after the engine episode ended, ``src: "crawl_tail"``), read
    from the replay's own crawl ``plays_ext.csv`` with replay_drive.load_battle's rules -- only when the crawl rows
    reproduce every logged play exactly (tick, side, card, x, y); otherwise no tail and the reason is counted.
  * added: ``pool_version``, ``source`` (crawl2|hf), ``final_decks``, ``s1_split`` (train|val), ``group``, ``split``
    (heldout|train|dropped), ``last_ghost_tick``, ``ghost_plays``, ``ghost_plays_corpus``, ``ghost_distinct_cards``,
    ``script_tail_plays``, ``corpus_final`` (tick, state_hash, terminated, winner, crowns, terminal_tick, reason),
    ``opening_state_hash``, ``corpus_engine_outcome``, ``real_outcome`` / ``real_crowns`` ([ours, theirs], RoyaleAPI),
    ``corpus_grade`` (plays_driven, accepted, rejected_by_reason, elixir_delays_n).

SPLIT RULE (design 2.2, deterministic, no RNG):
  1. candidates = corpus v6 replays with exactly ONE side holding our deck (``dataset.deck_sides``) AND that side's
     forms equal to the live deck's (``pipeline/decks/icebow.yaml`` ``_evo`` = evolution, else base; cross-checked
     against ``icebow/config/cards.yaml`` ``evolved: true``);
  2. ``s1_split = val`` iff ``dataset._tag_split(tag, 15) == 1`` (crc32(tag) % 100 < 15, the S1 dataset's own rule);
  3. group = the GHOST's tag from ``icebow/data/royaleapi/crawl2/battles.csv`` (``opponent_tags`` when our side is the
     team side 1, ``team_tags`` when it is side 0), else ``"tag:" + tag``;
  4. a group with ANY s1-val member is a held-out group: its s1-val members -> heldout, its s1-train members ->
     dropped; every other group -> train.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import vocab                                   # noqa: E402
from pipeline.dataset import _tag_split, deck_sides          # noqa: E402
from pipeline.obs_contract import load_deck                  # noqa: E402

CORPUS_V6 = REPO / "scratchpad" / "gauntlet" / "ext" / "corpus_v6" / "icebow"
CRAWL2 = REPO / "icebow" / "data" / "royaleapi" / "crawl2"
CRAWL_HF = REPO / "scratchpad" / "gauntlet" / "ext" / "crawl_hf_icebow"
GHOST_POOL_DIR = REPO / "icebow" / "data" / "ghost_pool"
POOL_NAME, SPLIT_NAME, BUILD_NAME = "pool_env_v1.jsonl", "pool_env_v1_split.json", "pool_env_v1_build.json"
POOL_V1 = GHOST_POOL_DIR / POOL_NAME
SPLIT_V1 = GHOST_POOL_DIR / SPLIT_NAME
S1_DATASET = REPO / "icebow" / "data" / "pipeline" / "s1_dataset_v6.npz"
LIVE_CARDS_YAML = REPO / "icebow" / "config" / "cards.yaml"
VAL_PCT = 15                       # dataset.build default val_pct, the S1 split
LEVEL = 11
GHOST_TAGS_COL = {1: "opponent_tags", 0: "team_tags"}    # our engine side -> the column holding the GHOST's tag
RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 13: "not_enough_elixir", 1014: "ability_exhausted",
                     1050: "not_enough_elixir"}           # engine_env.RESULT_CODE_NAMES (used when the module is absent)


# ------------------------------------------------------------------------------------------------------
# small helpers (pure, tested)
# ------------------------------------------------------------------------------------------------------
def ours(entry: dict, what: str):
    """engine_env.ours without importing it: OUR side's field (``our_*`` or the v0 ``icebow_*`` spelling)."""
    k = f"our_{what}"
    return entry[k] if k in entry else entry[f"icebow_{what}"]


def s1_split_of(tag: str) -> str:
    return "val" if _tag_split(str(tag), VAL_PCT) == 1 else "train"


def deck_forms(deck) -> dict[str, str]:
    """{base key: form} the live deck yaml declares (``_evo`` suffix = evolution) -- engine_play --own-forms rule."""
    return {vocab.base_key(c): ("evolution" if str(c).endswith("_evo") else "base") for c in deck.cards}


def live_config_forms(path: Path = LIVE_CARDS_YAML) -> dict[str, str]:
    """{base key: form} from the live bot's own deck block (icebow/config/cards.yaml ``deck.cards``)."""
    import yaml
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out = {}
    for c in (d.get("deck") or {}).get("cards") or []:
        form = "hero" if c.get("hero") else ("evolution" if c.get("evolved") else "base")
        out[vocab.base_key(str(c["card"]))] = form
    return out


def final_forms(names: Iterable[str]) -> dict[str, str]:
    """``final_decks[side]`` names (``Knight@evolution``, ``Xbow``) -> {base key: form}."""
    out = {}
    for n in names:
        n = str(n)
        k = vocab.engine_key(n)
        out[vocab.base_key(k) if k else n] = n.split("@", 1)[1] if "@" in n else "base"
    return out


def deck_names(order: list[dict]) -> list[str]:
    """engine_play.engine_deck_names (replay_drive.py:332 naming), copied to keep this module torch-free."""
    return [f"{it['name']}@{it['form']}" if it["form"] != "base" else str(it["name"]) for it in order]


def assign_split(cands: list[dict]) -> dict[str, str]:
    """Rule steps 3-4 over [{tag, group, s1_split}] -> {tag: heldout|train|dropped}."""
    held_groups = {c["group"] for c in cands if c["s1_split"] == "val"}
    out = {}
    for c in cands:
        if c["group"] in held_groups:
            out[c["tag"]] = "heldout" if c["s1_split"] == "val" else "dropped"
        else:
            out[c["tag"]] = "train"
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_pool_v1(path: Path = POOL_V1) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def select_split(pool: list[dict], split: str) -> list[dict]:
    """Entries of one split in POOL FILE ORDER (sorted by tag) -- the order ``e1_eval --entries a:b`` indexes."""
    return [r for r in pool if r.get("split") == split]


def screen_tags(pool: list[dict], n: int = 60, split: str = "heldout") -> list[str]:
    """The fixed screen subset (design 3.6): the ``n`` entries of ``split`` with the lowest crc32(tag), in that order."""
    import zlib
    rows = sorted(select_split(pool, split), key=lambda r: (zlib.crc32(str(r["tag"]).encode()), r["tag"]))
    return [r["tag"] for r in rows[:n]]


def verify_split(pool_path: Path = POOL_V1, split_path: Path = SPLIT_V1) -> dict:
    """Frozen split vs (a) the pool file's sha256 and (b) the rule re-derived from the pool rows."""
    frozen = json.loads(Path(split_path).read_text(encoding="utf-8"))
    pool = load_pool_v1(pool_path)
    sha_ok = sha256_file(pool_path) == frozen["pool_sha256"]
    rederived = assign_split([{"tag": r["tag"], "group": r["group"], "s1_split": s1_split_of(r["tag"])} for r in pool])
    tags = frozen["tags"]
    mismatch = [t for t, s in rederived.items() if tags.get(t, {}).get("split") != s]
    row_mismatch = [r["tag"] for r in pool if r["split"] != tags.get(r["tag"], {}).get("split")]
    counts = Counter(rederived.values())
    by_group = defaultdict(set)
    for r in pool:
        by_group[r["group"]].add(r["split"])
    leak = sorted(g for g, ss in by_group.items() if "heldout" in ss and "train" in ss)
    return {"sha_ok": sha_ok, "n_pool": len(pool), "n_frozen": len(tags), "rule_mismatch": len(mismatch),
            "row_vs_frozen_mismatch": len(row_mismatch), "counts": dict(counts), "groups_heldout_and_train": leak,
            "frozen_counts": frozen.get("counts")}


# ------------------------------------------------------------------------------------------------------
# crawl reading (replay_drive.load_battle's rules, grouped once per file instead of one scan per tag)
# ------------------------------------------------------------------------------------------------------
def read_battles(crawl: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with (crawl / "battles.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["replay_tag"], row)          # one crawl2 tag has 2 identical rows (build log)
    return out


PLAYS_FILES = {"crawl2": ("plays_ext_i1.csv", "plays_ext.csv"), "hf": ("plays_ext.csv",)}   # tried in this order


def read_plays(crawl: Path, keep: Optional[set] = None, name: str = "plays_ext.csv") -> dict[str, list[tuple]]:
    """{tag: [(tick, play_index, side, ability, card, x, y)]} sorted (tick, play_index); x/y None when unpositioned.
    Side from ``attr_s`` (replay_drive.SIDE_OF), ``attr_i == "1"`` rows rotated 180 degrees (replay_drive.py:163-165)."""
    side_of = {"red": 0, "blue": 1}
    out: dict[str, list[tuple]] = defaultdict(list)
    if not (crawl / name).exists():
        return out
    with (crawl / name).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            tag = r["replay_tag"]
            if keep is not None and tag not in keep:
                continue
            if r["tick"] in ("", "None") or r["play_index"] in ("", "None") or r["attr_ability"] in ("", "None"):
                out[tag].append((None, None, None, None, None, None, None))
                continue
            ab = int(r["attr_ability"])
            x = y = None
            if not ab and r["x_units"] not in ("", "None") and r["y_units"] not in ("", "None"):
                x, y = int(r["x_units"]), int(r["y_units"])
                if r.get("attr_i") == "1":
                    x, y = 18000 - x, 32000 - y
            out[tag].append((int(r["tick"]), int(r["play_index"]), side_of.get(r["attr_s"]), ab, r["attr_card"], x, y))
    for tag in out:
        if any(p[0] is None for p in out[tag]):
            out[tag] = [p for p in out[tag] if p[0] is not None] + [("BAD",)]
        else:
            out[tag].sort(key=lambda p: (p[0], p[1]))
    return out


# ------------------------------------------------------------------------------------------------------
# one corpus record -> one pool row (or a refusal reason)
# ------------------------------------------------------------------------------------------------------
def _cmd(tick: int, card: Optional[str], item: Optional[dict], deck_index: Optional[int], x, y, ability: int,
         play_index: int, src: str, **extra) -> dict:
    d = {"tick": int(tick), "seconds": round(int(tick) * 0.05, 2), "card": card,
         "name": item["name"] if item else None, "card_id": int(item["card_id"]) if item else None,
         "deck_index": deck_index, "x": x, "y": y, "ability": int(ability), "play_index": int(play_index), "src": src}
    d.update(extra)
    return d


def build_row(rec: dict, deck, want_forms: dict, battles: dict[str, dict], plays: dict[str, list], rd,
              source: str, stats: Counter) -> tuple[Optional[dict], Optional[str]]:
    tag = str(rec["tag"])
    sides = deck_sides(rec, deck)
    if len(sides) != 1:
        return None, "deck_not_on_exactly_one_side"
    me = sides[0]
    gh = 1 - me
    fd = rec.get("final_decks") or {}
    forms = final_forms(fd[str(me)])
    if forms != want_forms:
        sig = ",".join(sorted(f"{k}:{v}" for k, v in forms.items() if v != "base"))
        stats["other_forms_sig:" + sig] += 1
        return None, "our_forms_not_live_deck"
    battle = battles.get(tag)
    if battle is None:
        return None, "no_battle_row"
    items = {}
    for s in (0, 1):
        try:
            canon = rd.deck_for_side(battle, s)
        except (SystemExit, KeyError) as exc:
            stats["deck_unresolvable:" + type(exc).__name__] += 1
            return None, "deck_unresolvable"
        by_name = {n: it for n, it in zip(deck_names(canon), canon)}
        want = [str(n) for n in fd[str(s)]]
        if sorted(by_name) != sorted(want) or len(set(want)) != 8:
            return None, "final_decks_do_not_match_battle_deck"
        items[s] = [{"slug": by_name[n]["slug"], "name": by_name[n]["name"], "card_id": int(by_name[n]["card_id"]),
                     "form": by_name[n]["form"], "cost": int(by_name[n]["cost"]), "level": LEVEL} for n in want]
        assert deck_names(items[s]) == want
    idx = {s: {it["slug"]: i for i, it in enumerate(items[s])} for s in (0, 1)}
    cmds: dict[int, list] = {0: [], 1: []}
    logged = []
    for e in rec.get("log") or []:
        s = int(e.get("side", -1))
        if s not in (0, 1):
            continue
        if "skipped" in e:
            if "ability" in str(e["skipped"]):
                cmds[s].append(_cmd(e["tick"], None, None, None, None, None, 1, e["play_index"], "corpus"))
                logged.append(("ab", int(e["play_index"])))
            else:
                stats["log_skipped_terminal"] += 1        # no position recorded: comes back as crawl tail
            continue
        slug = str(e["card"])
        if slug not in idx[s]:
            return None, "log_card_outside_deck"
        cmds[s].append(_cmd(e["tick"], slug, items[s][idx[s][slug]], idx[s][slug], int(e["x"]), int(e["y"]), 0,
                            e["play_index"], "corpus", corpus_accepted=bool(e.get("accepted")),
                            corpus_delay_ticks=int(e.get("delay_ticks") or 0)))
        logged.append((int(e["tick"]), int(e["play_index"]), s, slug, int(e["x"]), int(e["y"])))
    # ghost-script tail from the crawl, only if a crawl plays file reproduces every logged play (files tried in
    # PLAYS_FILES order; ``plays`` maps tag -> [rows per file])
    tail_n = 0
    n_logged = len(logged)
    crawl_rows = None
    candidates = [rows for rows in (plays.get(tag) or []) if rows and rows[-1] != ("BAD",)]
    for rows in candidates:
        head_sig = [("ab", p[1]) if p[3] else (p[0], p[1], p[2], p[4], p[5], p[6]) for p in rows[:n_logged]]
        if head_sig == logged:
            crawl_rows = rows
            break
    if not candidates:
        stats["tail_none:no_clean_crawl_rows"] += 1
    elif crawl_rows is None:
        stats["tail_none:crawl_differs_from_log"] += 1
    else:
        stats["tail_source_matched"] += 1
        for p in crawl_rows[n_logged:]:
            tick, pi, s, ab, card, x, y = p
            if s not in (0, 1):
                stats["tail_cut:bad_side"] += 1
                break
            if ab:
                cmds[s].append(_cmd(tick, None, None, None, None, None, 1, pi, "crawl_tail"))
                continue
            if x is None or card not in idx[s]:
                stats["tail_cut:unpositioned_or_outside_deck"] += 1
                break
            cmds[s].append(_cmd(tick, card, items[s][idx[s][card]], idx[s][card], x, y, 0, pi, "crawl_tail"))
            tail_n += 1
    for s in (0, 1):
        cmds[s].sort(key=lambda c: (c["tick"], c["play_index"]))
    ghost_pos = [c for c in cmds[gh] if not c["ability"]]
    exp = rec.get("expected") or {}
    cbs = exp.get("crowns_by_side") or {}
    real = [int(cbs.get(str(me), cbs.get(me, 0))), int(cbs.get(str(gh), cbs.get(gh, 0)))]
    real_outcome = "win" if real[0] > real[1] else ("loss" if real[0] < real[1] else "draw")
    fin = rec.get("final") or {}
    w = fin.get("winner")
    eng_out = ("draw" if (w is None or int(w) < 0) else ("win" if int(w) == me else "loss"))
    grade = rec.get("grade") or {}
    ghost_tag = (battle.get(GHOST_TAGS_COL[me]) or "").strip() if source == "crawl2" else ""
    row = {
        "tag": tag, "result": real_outcome, "raw_result": exp.get("result"),
        "rating": battle.get("rating", ""),
        "icebow_side": me, "ghost_side": gh,
        "icebow_deck": items[me], "ghost_deck": items[gh],
        "icebow_commands": cmds[me], "ghost_commands": cmds[gh],
        "final_crowns": [real[0], real[1]] if me == 0 else [real[1], real[0]],
        "duration_ticks": max([c["tick"] for c in cmds[0] + cmds[1]] or [0]),
        "plays": len(cmds[0]) + len(cmds[1]),
        "deal_candidates": {str(s): int(((rec.get("deal_inference") or {}).get(str(s)) or {}).get("consistent", 0))
                            for s in (0, 1)},
        "battle_type": battle.get("battle_type", ""),
        "battle_timestamp": battle.get("battle_time", battle.get("battle_timestamp", "")),
        "player_tag": battle.get("player_tag", ""), "opponent_tag": ghost_tag,
        # --- v1 additions ---
        "pool_version": 1, "deck_order": "final", "source": source,
        "final_decks": {str(s): [str(n) for n in fd[str(s)]] for s in (0, 1)},
        "s1_split": s1_split_of(tag),
        "group": ghost_tag if ghost_tag else "tag:" + tag,
        "split": None,
        "last_ghost_tick": max([c["tick"] for c in ghost_pos] or [0]),
        "ghost_plays": len(ghost_pos),
        "ghost_plays_corpus": sum(1 for c in ghost_pos if c["src"] == "corpus"),
        "ghost_distinct_cards": len({c["card"] for c in ghost_pos}),
        "script_tail_plays": tail_n,
        "corpus_final": {k: fin.get(k) for k in ("tick", "state_hash", "terminated", "winner", "crowns",
                                                 "terminal_tick", "termination_reason")},
        "opening_state_hash": rec.get("opening_state_hash"),
        "corpus_engine_outcome": eng_out,
        "real_outcome": real_outcome, "real_crowns": real,
        "corpus_grade": {"plays_driven": grade.get("plays_driven"), "accepted": grade.get("accepted"),
                         "rejected_by_reason": grade.get("rejected_by_reason") or {},
                         "elixir_delays_n": (grade.get("elixir_delays") or {}).get("n", 0)},
    }
    return row, None


# ------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------
def _rd():
    for p in (REPO / "research" / "ext" / "cr-native-sandbox", REPO / "research" / "sandbox_tools", REPO / "icebow" / "src"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import replay_drive as RD          # noqa: E402  (imports native_core.env; opens no connection)
    return RD


def _s1_dataset_check(tags_split: dict[str, str], path: Path = S1_DATASET) -> dict:
    """(a) check: the crc rule vs the split stored in the S1 v6 dataset for every candidate tag it contains."""
    import numpy as np
    if not Path(path).exists():
        return {"dataset": str(path), "missing": True}
    z = np.load(path, allow_pickle=False)
    tags = [str(t) for t in z["tags"]]
    rep = z["rep"]
    split = z["split"]
    uniq, first = np.unique(rep, return_index=True)
    stored = {tags[int(r)]: ("val" if int(split[int(i)]) == 1 else "train") for r, i in zip(uniq, first)}
    inter = [t for t in tags_split if t in stored]
    agree = sum(1 for t in inter if stored[t] == tags_split[t])
    return {"dataset": str(path.relative_to(REPO)).replace("\\", "/"), "dataset_replays": len(tags),
            "candidates_in_dataset": len(inter), "candidates_not_in_dataset": len(tags_split) - len(inter),
            "split_agree": agree, "split_disagree": len(inter) - agree}


def build(out_dir: Path = GHOST_POOL_DIR, corpus: Path = CORPUS_V6, *, limit: int = 0, log=sys.stderr) -> dict:
    out_dir = Path(out_dir)
    outs = [out_dir / POOL_NAME, out_dir / SPLIT_NAME, out_dir / BUILD_NAME]
    existing = [str(p) for p in outs if p.exists()]
    if existing:
        raise SystemExit(f"REFUSING to overwrite existing pool v1 file(s): {existing}")
    if not out_dir.is_dir():
        raise SystemExit(f"output dir does not exist: {out_dir}")
    t0 = time.time()
    deck = load_deck("icebow")
    want = deck_forms(deck)
    live = live_config_forms()
    if live != want:
        raise SystemExit(f"deck yaml forms {want} != live cards.yaml forms {live}")
    rd = _rd()
    files = sorted(Path(corpus).glob("replay_*.json"))
    if limit:
        files = files[:limit]
    corpus_tags = {f.stem[len("replay_"):] for f in files}
    battles = {"crawl2": read_battles(CRAWL2), "hf": read_battles(CRAWL_HF)}
    plays: dict[str, dict[str, list]] = {}
    for src, crawl in (("crawl2", CRAWL2), ("hf", CRAWL_HF)):
        per_file = [read_plays(crawl, corpus_tags, name) for name in PLAYS_FILES[src]]
        plays[src] = {t: [pf[t] for pf in per_file if t in pf] for t in corpus_tags}
    refused: Counter = Counter()
    stats: Counter = Counter()
    rows: list[dict] = []
    for i, f in enumerate(files):
        rec = json.loads(f.read_text(encoding="utf-8"))
        tag = str(rec["tag"])
        source = "crawl2" if tag in battles["crawl2"] else ("hf" if tag in battles["hf"] else None)
        if source is None:
            refused["no_battle_row"] += 1
            continue
        row, why = build_row(rec, deck, want, battles[source], plays[source], rd, source, stats)
        del rec
        if why:
            refused[why] += 1
        else:
            rows.append(row)
        if log and (i + 1) % 250 == 0:
            print(f"[e1_pool] {i + 1}/{len(files)} rows={len(rows)} {time.time() - t0:.0f}s", file=log, flush=True)
    rows.sort(key=lambda r: r["tag"])
    split = assign_split(rows)
    for r in rows:
        r["split"] = split[r["tag"]]
    with (out_dir / POOL_NAME).open("x", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    pool_sha = sha256_file(out_dir / POOL_NAME)
    counts = Counter(split.values())

    def _sub(sp: str) -> dict:
        rs = [r for r in rows if r["split"] == sp]
        gp = [r["ghost_plays"] for r in rs]
        return {"n": len(rs), "with_opponent_tag": sum(1 for r in rs if r["opponent_tag"]),
                "source": dict(Counter(r["source"] for r in rs)),
                "ghost_plays_median": statistics.median(gp) if gp else None, "ghost_plays_min": min(gp) if gp else None,
                "ghost_plays_le5": sum(1 for g in gp if g <= 5), "ghost_plays_0": sum(1 for g in gp if g == 0),
                "ghost_distinct_le3": sum(1 for r in rs if r["ghost_distinct_cards"] <= 3),
                "real_wins_for_our_pro": sum(1 for r in rs if r["real_outcome"] == "win"),
                "corpus_engine_wins": sum(1 for r in rs if r["corpus_engine_outcome"] == "win"),
                "with_script_tail": sum(1 for r in rs if r["script_tail_plays"] > 0),
                "corpus_rows_with_refusals": sum(1 for r in rs if r["corpus_grade"]["rejected_by_reason"]),
                "corpus_rows_with_elixir_delay": sum(1 for r in rs if r["corpus_grade"]["elixir_delays_n"]),
                "our_side": dict(Counter(str(r["icebow_side"]) for r in rs)),
                "groups": len({r["group"] for r in rs})}

    split_doc = {"schema": 1, "pool": POOL_NAME, "pool_sha256": pool_sha, "val_pct": VAL_PCT,
                 "rule": "design 2.2: candidates -> s1_split crc32(tag)%100<15 -> group = ghost tag else tag:<tag> -> "
                         "group with any s1-val member: val->heldout, train->dropped; else train",
                 "counts": {k: counts.get(k, 0) for k in ("heldout", "train", "dropped")},
                 "tags": {r["tag"]: {"split": r["split"], "group": r["group"], "s1_split": r["s1_split"]} for r in rows}}
    with (out_dir / SPLIT_NAME).open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(split_doc, indent=0))
    meta = {"n": len(rows), "corpus": str(Path(corpus).relative_to(REPO)).replace("\\", "/"), "files_seen": len(files),
            "refused_by_reason": dict(refused), "stats": dict(stats),
            "counts": split_doc["counts"], "by_split": {sp: _sub(sp) for sp in ("heldout", "train", "dropped")},
            "candidates_s1": dict(Counter(r["s1_split"] for r in rows)),
            "distinct_groups": len({r["group"] for r in rows}),
            "groups_with_gt1": sum(1 for g, n in Counter(r["group"] for r in rows).items() if n > 1),
            "live_forms": want, "pool_sha256": pool_sha,
            "split_sha256": sha256_file(out_dir / SPLIT_NAME),
            "battles_sha256": {"crawl2": sha256_file(CRAWL2 / "battles.csv"), "hf": sha256_file(CRAWL_HF / "battles.csv")},
            "s1_dataset_check": _s1_dataset_check({r["tag"]: r["s1_split"] for r in rows}),
            "builder": "pipeline/e1_pool.py", "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - t0, 1)}
    with (out_dir / BUILD_NAME).open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(meta, indent=1))
    return meta


# ------------------------------------------------------------------------------------------------------
# the env: EngineMatchEnv playing pool v1 (engine_play.RawEngineEnv's overrides + pool-v1 decks + parity driving)
# ------------------------------------------------------------------------------------------------------
class PoolV1Mixin:
    """Overrides layered on ``EngineMatchEnv`` (scratchpad/gauntlet/L62/engine_env.py). Unchanged semantics except:
      * ``_resolve_decks``: the entry's decks ARE the final order (asserted against ``final_decks``); no probe reset.
      * ``_render``: the raw ``observe()`` dict (engine_play.RawEngineEnv), ``raw_state`` kept.
      * ``_fire_ghosts_at``: the base loop (engine_env.py:366-393) with the retried refusal codes as a parameter
        (``retry_codes``, base (13, 1050)), a per-command ``side`` (default the ghost), and delivered-card counts.
      * ``drive_our_commands=True`` (PARITY): our side's recorded commands are merged into the same scheduler at the
        first ``_advance_to`` after reset, ordered (tick, play_index) like replay_drive.drive."""

    drive_our_commands = False
    retry_codes: tuple = (13, 1050)
    _code_names = RESULT_CODE_NAMES

    def _resolve_decks(self, entry):
        final = {int(ours(entry, "side")): list(ours(entry, "deck")), int(entry["ghost_side"]): list(entry["ghost_deck"])}
        fd = entry.get("final_decks")
        if entry.get("deck_order") != "final" or not fd:
            raise RuntimeError(f"{entry.get('tag')}: not a pool v1 row (deck_order/final_decks missing)")
        for s in (0, 1):
            if deck_names(final[s]) != [str(n) for n in fd[str(s)]]:
                raise RuntimeError(f"{entry['tag']}: side {s} deck {deck_names(final[s])} != final_decks {fd[str(s)]}")
        self.final_decks = final
        return final, True

    def _render(self, state):
        self.raw_state = state
        return state

    def reset(self, entry=None, *, index=None):
        self.our_cmd_ok = 0
        self.our_cmd_refused = 0
        self.our_cmd_reasons = {}
        self.ghost_cards_delivered = Counter()
        self._merge_pending = bool(self.drive_our_commands)
        return super().reset(entry, index=index)

    def _advance_to(self, target):
        if getattr(self, "_merge_pending", False):
            self._merge_pending = False
            self._merge_our_commands()
        return super()._advance_to(target)

    def _merge_our_commands(self):
        if self._gi != 0 or self._pending:
            raise RuntimeError("parity merge after a command already fired")
        idx = {s: {it["slug"]: i for i, it in enumerate(self.final_decks[s])} for s in (0, 1)}
        cmds = []
        for s, src in ((self.opp, self.entry["ghost_commands"]), (self.side, ours(self.entry, "commands"))):
            for c in src:
                if c.get("ability"):
                    continue
                cmds.append({"tick": int(c["tick"]), "sched": int(c["tick"]), "deck_index": idx[s][c["card"]],
                             "x": int(c["x"]), "y": int(c["y"]), "card": c["card"], "side": s,
                             "play_index": int(c.get("play_index", -1))})
        cmds.sort(key=lambda g: (g["tick"], g["play_index"]))
        self._ghosts = cmds

    def _fire_ghosts_at(self, tick: int):
        while self._gi < len(self._ghosts) and self._ghosts[self._gi]["tick"] <= tick:
            self._pending.append(self._ghosts[self._gi])
            self._gi += 1
        still = []
        for g in self._pending:
            if g["sched"] > tick:
                still.append(g)
                continue
            side = int(g.get("side", self.opp))
            mine = side == self.side
            r = self.eng.act(side=side, deck_index=g["deck_index"], x=g["x"], y=g["y"])
            if r["accepted"]:
                if mine:
                    self.our_cmd_ok += 1
                else:
                    self.ghost_ok += 1
                    self.ghost_events.append((g["tick"], 1, "accepted"))
                    self.ghost_cards_delivered[g["card"]] += 1
                continue
            code = int(r["result_code"])
            if code in self.retry_codes and (tick - g["tick"]) < self.elixir_slack:
                g["sched"] = tick + 1
                still.append(g)
                continue
            name = self._code_names.get(code, f"native_{code}")
            if r.get("placement_valid") is False:
                name = f"{name}/{r.get('placement_reason')}"
            if mine:
                self.our_cmd_refused += 1
                self.our_cmd_reasons[name] = self.our_cmd_reasons.get(name, 0) + 1
            else:
                self.ghost_rejected += 1
                self.ghost_reject_reasons[name] = self.ghost_reject_reasons.get(name, 0) + 1
                self.ghost_events.append((g["tick"], 0, name))
        self._pending = still

    # readouts the eval writes
    def ghost_undelivered(self) -> int:
        return sum(1 for g in self._ghosts[self._gi:] if int(g.get("side", self.opp)) != self.side) + \
            sum(1 for g in self._pending if int(g.get("side", self.opp)) != self.side)


_CLASSES: dict[int, type] = {}


def engine_env_module():
    """The L62 engine_env module, loaded ONCE per process (engine_play._load_engine_env re-executes it per call)."""
    mod = sys.modules.get("l62_engine_env")
    if mod is None:
        from pipeline import engine_play
        mod = engine_play._load_engine_env()
    return mod


class PoolV1Env:
    """``PoolV1Env(port=38031, ...)`` -> an ``EngineMatchEnv`` with ``PoolV1Mixin`` (same factory pattern as
    engine_play.RawEngineEnv, whose closure class cannot be subclassed). ``deal_cache`` is forced False."""

    def __new__(cls, *, drive_our_commands: bool = False, retry_codes: tuple = (13, 1050), pool=None, **kw):
        if kw.get("deal_cache"):
            raise ValueError("pool v1 has the final deck order; the L62 deal cache must stay off")
        kw["deal_cache"] = False
        mod = engine_env_module()
        klass = _CLASSES.get(id(mod))
        if klass is None:
            klass = type("PoolV1EngineEnv", (PoolV1Mixin, mod.EngineMatchEnv), {"_code_names": dict(mod.RESULT_CODE_NAMES)})
            _CLASSES[id(mod)] = klass
        env = klass(pool=[] if pool is None else pool, **kw)
        env.drive_our_commands = bool(drive_our_commands)
        env.retry_codes = tuple(int(c) for c in retry_codes)
        return env


# ------------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out-dir", type=Path, default=GHOST_POOL_DIR)
    b.add_argument("--corpus", type=Path, default=CORPUS_V6)
    b.add_argument("--limit", type=int, default=0)
    v = sub.add_parser("verify")
    v.add_argument("--pool", type=Path, default=POOL_V1)
    v.add_argument("--split", type=Path, default=SPLIT_V1)
    sc = sub.add_parser("screen", help="write the N lowest-crc32 tags of a split (the fixed screen subset), one per line")
    sc.add_argument("--pool", type=Path, default=POOL_V1)
    sc.add_argument("--split", default="heldout")
    sc.add_argument("--n", type=int, default=60)
    sc.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        meta = build(a.out_dir, a.corpus, limit=a.limit)
        print(json.dumps({k: meta[k] for k in ("n", "counts", "refused_by_reason", "s1_dataset_check", "seconds")}, default=str))
    elif a.cmd == "screen":
        if a.out.exists():
            raise SystemExit(f"REFUSING to overwrite {a.out}")
        tags = screen_tags(load_pool_v1(a.pool), a.n, a.split)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(tags) + "\n")
        print(json.dumps({"screen": str(a.out), "n": len(tags), "split": a.split}))
    else:
        print(json.dumps(verify_split(a.pool, a.split), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

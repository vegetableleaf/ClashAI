"""The shared observation contract: one ``BoardState`` that both the engine and the live screen fill.

Spec: ``scratchpad/gauntlet/L63/s0/obs_contract_spec.md``; implementation record + measured facts:
``scratchpad/gauntlet/L63/s0/obs_contract_impl.md``.

Board frame (the ONE frame every coordinate lives in): the 18 x 32-tile board normalised to [0, 1],
x across, y DOWN THE SCREEN with ME AT THE BOTTOM -- exactly ``build_bc_v2.py:111-116`` for engine side 0
(``nx = x/18000``, ``ny = 1 - y/32000``; side 1 is mirrored ``18000-x, 32000-y`` first) and exactly the
board side of ``clashrl.actions.BoardWarp``. So my king's row is ``ny = 1 - 3/32 = 0.90625`` (bottom),
my princess row 0.796875, the river 0.5, the enemy princess row 0.203125, the enemy king 0.09375.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import yaml

from . import vocab

REPO = Path(__file__).resolve().parents[1]

# --- geometry (engine units: 1000 per tile; board 18 x 32 tiles; measured, obs_audit_engine.md 1.6) ---
TILES_X, TILES_Y = 18.0, 32.0
ENGINE_X, ENGINE_Y = 18000.0, 32000.0
KING_TILE = (9.0, 3.0)              # tiles from the side wall / from the back wall (sim.board.king_tile)
PRINCESS_TILE = (3.5, 6.5)          # sim.board.princess_tile
MY_KING_Y = 1.0 - KING_TILE[1] / TILES_Y          # 0.90625
MY_PRINCESS_Y = 1.0 - PRINCESS_TILE[1] / TILES_Y  # 0.796875
OPP_KING_Y = KING_TILE[1] / TILES_Y               # 0.09375
OPP_PRINCESS_Y = PRINCESS_TILE[1] / TILES_Y       # 0.203125
PRINCESS_X_L = PRINCESS_TILE[0] / TILES_X         # 0.1944
PRINCESS_X_R = 1.0 - PRINCESS_X_L                 # 0.8056
KING_X = KING_TILE[0] / TILES_X                   # 0.5
RIVER_Y = 0.5

# --- clock (accept_match_rules.py:96-99: 20 Hz; double elixir tick 2400 = 120 s; overtime from tick 3600 = 180 s) ---
TICK_S = 0.05
DOUBLE_ELIXIR_S = 120.0
OVERTIME_S = 180.0

# --- engine entity ``kind``: 12/14 = deploying (build_bc_v2.py:151; inferred from recordings, no decoder table) ---
DEPLOYING_KINDS = (12, 14)

TOWER_ORDER = (("king", None), ("princess", "L"), ("princess", "R"))   # x3 per side: my K, L, R, opp K, L, R
_ANCHOR_XY = {("king", None): (KING_X, MY_KING_Y), ("princess", "L"): (PRINCESS_X_L, MY_PRINCESS_Y),
              ("princess", "R"): (PRINCESS_X_R, MY_PRINCESS_Y)}


# ------------------------------------------------------------------------------------------------------
# deck
# ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Deck:
    name: str
    cards: tuple[str, ...]          # 8 class names, deck order
    card_ids: tuple[int, ...]       # their vocab ids
    config: Path                    # the deck's config.yaml (BoardWarp anchors)
    src_dir: Path                   # clashrl source dir BoardWarp is imported from
    crawl_dir: Path
    data_dir: Path

    def slot_of(self, name: Optional[str]) -> int:
        """Deck slot of a class name (matched on BASE key so ``tesla`` and ``tesla_evo`` agree); -1 if absent."""
        if not name:
            return -1
        b = vocab.base_key(str(name))
        for i, c in enumerate(self.cards):
            if vocab.base_key(c) == b:
                return i
        return -1

    def card_id_of(self, name: Optional[str]) -> int:
        """Vocab id of the DECK'S class for a hand/next name (evo class when the deck runs the evo); -1 if absent."""
        s = self.slot_of(name)
        return self.card_ids[s] if s >= 0 else -1

    def slot_of_id(self, cls_id: int) -> int:
        return self.card_ids.index(cls_id) if cls_id in self.card_ids else -1


def load_deck(name_or_path: str | Path) -> Deck:
    p = Path(name_or_path)
    if not p.suffix:
        p = REPO / "pipeline" / "decks" / f"{p.name}.yaml"
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    cards = tuple(str(c) for c in d["cards"])
    if len(cards) != 8:
        raise ValueError(f"{p}: deck needs 8 cards, got {len(cards)}")
    return Deck(name=str(d["name"]), cards=cards, card_ids=tuple(vocab.unit_id(c) for c in cards),
                config=REPO / d["config"], src_dir=REPO / d["src_dir"],
                crawl_dir=REPO / d["crawl_dir"], data_dir=REPO / d["data_dir"])


# ------------------------------------------------------------------------------------------------------
# the contract
# ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Unit:
    cls: int                        # vocab id
    side: int                       # 0 = mine, 1 = enemy, -1 = unknown (live only; engine never emits -1)
    x: float
    y: float                        # board frame (module docstring)
    hp_frac: Optional[float]        # engine: hp/max_hp; live: None
    deploying: Optional[bool]       # engine: kind in DEPLOYING_KINDS; live: None
    age_sec: Optional[float]        # engine: (tick - first_seen_tick) * TICK_S when fed a history, else None
    conf: float                     # engine 1.0; live detector conf


@dataclass(frozen=True)
class Tower:
    side: int
    kind: str                       # 'king' | 'princess'
    lane: Optional[str]             # 'L' | 'R' for princess (in MY frame: L = x < 0.5), None for king
    hp_frac: Optional[float]
    alive: bool


@dataclass(frozen=True)
class BoardState:
    source: str                     # 'engine' | 'live' | 'degraded'
    t_sec: float
    t_source: str                   # 'tick' | 'clock' | 'timer'
    double_elixir: bool             # t >= DOUBLE_ELIXIR_S
    overtime: bool                  # t >= OVERTIME_S
    my_elixir: float
    my_elixir_exact: bool           # engine exact (1e-4); live integer from the bar
    opp_elixir: Optional[float]     # engine exact; live None
    my_hand: tuple[int, int, int, int]   # vocab ids in deck-slot order as the game shows them; -1 = unknown slot
    my_next: int                    # vocab id or -1
    towers: tuple[Tower, ...]       # exactly 6: my K, my L, my R, opp K, opp L, opp R
    units: tuple[Unit, ...]
    spells: tuple[Unit, ...]        # spell/effect instances (engine effects + detector _aoe/spell classes)
    deck: tuple[int, ...] = ()      # ADDITION to the spec: the 8 deck vocab ids, so to_tokens can one-hot
                                    # hand/next by deck slot without a second argument

    @property
    def n_tokens(self) -> int:
        return len(self.units) + len(self.spells)


class UnmappedName(KeyError):
    """An engine name with no vocab id (pass ``unmapped=set()`` to from_engine to collect instead)."""


def _phase(t: float) -> tuple[bool, bool]:
    return t >= DOUBLE_ELIXIR_S, t >= OVERTIME_S


def _lane_of(x: float) -> str:
    return "L" if x < 0.5 else "R"


def _tower_slots(found: dict[tuple[int, str, Optional[str]], Tower]) -> tuple[Tower, ...]:
    """Fixed 6-slot order; a tower missing from the engine list is destroyed (L62/engine_env.py:188-190)."""
    out = []
    for side in (0, 1):
        for kind, lane in TOWER_ORDER:
            out.append(found.get((side, kind, lane)) or Tower(side, kind, lane, 0.0, False))
    return tuple(out)


# ------------------------------------------------------------------------------------------------------
# engine adapter
# ------------------------------------------------------------------------------------------------------
_CATALOG_NAMES: Optional[dict[int, str]] = None


def _catalog_names() -> dict[int, str]:
    """card_id -> display_name from the live catalog (evolution/hero form ids fold to the base card),
    the same naming ``native_core.env.CARD_NAMES`` gives entities. Data file only; no service."""
    global _CATALOG_NAMES
    if _CATALOG_NAMES is None:
        p = REPO / "research" / "ext" / "cr-native-sandbox" / "native_core" / "data" / "live_card_catalog.json"
        names: dict[int, str] = {}
        if p.exists():
            for c in json.loads(p.read_text(encoding="utf-8")).get("cards", []):
                names[int(c["card_id"])] = str(c["display_name"])
                for k in ("evolution_form_id", "hero_form_id"):
                    if c.get(k) is not None:
                        names[int(c[k])] = str(c["display_name"])
        _CATALOG_NAMES = names
    return _CATALOG_NAMES


def _engine_xy(x: float, y: float, mirror: bool) -> tuple[float, float]:
    if mirror:
        x, y = ENGINE_X - x, ENGINE_Y - y
    return x / ENGINE_X, 1.0 - y / ENGINE_Y


def _next_name(next_index: Any, engine_deck: Optional[Sequence[str]]) -> Optional[str]:
    if engine_deck is None or next_index is None:
        return None
    i = int(next_index)
    return str(engine_deck[i]) if 0 <= i < len(engine_deck) else None


def _hand_ids(deck: Deck, names: Sequence[Optional[str]]) -> tuple[int, int, int, int]:
    ids = [deck.card_id_of(vocab.engine_key(n) if n else None) for n in list(names)[:4]]
    while len(ids) < 4:
        ids.append(-1)
    return tuple(ids)  # type: ignore[return-value]


def from_engine(obs: Mapping[str, Any], my_side: int, deck: Deck, *, history: Optional[dict] = None,
                engine_deck: Optional[Sequence[str]] = None, unmapped: Optional[set] = None) -> BoardState:
    """Engine state -> BoardState in MY frame (me at the bottom). Accepts BOTH the raw ``observe()`` dict
    (native_core/env.py:187-255: tick, players, entities, projectiles, effects, episode) and the
    list-encoded frame on disk (entities ``[side, x, y, name, hp, max_hp(, kind)]``, towers
    ``[side, type, lane, x, y, hp, max_hp]``, ``elixir[2]``, optional ``players`` / ``effects``).

    ``history``: a dict the caller keeps across frames; raw dicts key it by ``entity_id`` and get
    ``age_sec``; list frames carry no stable id, so their units get ``age_sec=None`` even with a history.
    ``engine_deck``: the 8 engine names in the engine's deck order (record ``final_decks[side]``); needed to
    resolve ``next`` (a deck index) -- without it ``my_next = -1``.
    ``unmapped``: when a set is given, entities with no vocab id are dropped and their names collected;
    otherwise ``UnmappedName`` is raised. Crown towers (card_id -1) come from ``episode.crown_towers`` /
    ``towers`` and are DROPPED from ``units``.
    """
    mirror = my_side == 1
    side_of = (lambda s: 0 if int(s) == my_side else 1)
    tick = int(obs["tick"])
    t = tick * TICK_S
    ents = obs.get("entities") or []
    raw = bool(ents) and isinstance(ents[0], Mapping) or ("episode" in obs and "towers" not in obs)

    # --- players: elixir, hand, next ---
    if raw:
        players = {int(p["side"]): p for p in obs.get("players", [])}
        me, them = players.get(my_side, {}), players.get(1 - my_side, {})
        my_el = float(me.get("elixir_exact", me.get("elixir", 0.0)) or 0.0)
        opp_el = float(them.get("elixir_exact", them.get("elixir", 0.0)) or 0.0)
        hand_names: list[Optional[str]] = [None] * 4
        for h in me.get("hand", []):
            hand_names[int(h["hand_index"])] = h.get("name")
        next_nm = _next_name(me.get("next_deck_index"), engine_deck)
    else:
        el = obs.get("elixir") or [0.0, 0.0]
        my_el, opp_el = float(el[my_side] or 0.0), float(el[1 - my_side] or 0.0)
        me = next((p for p in obs.get("players") or [] if int(p.get("side", -9)) == my_side), None)
        hand_names = list(me.get("hand", [])) if me else [None] * 4
        next_nm = _next_name(me.get("next"), engine_deck) if me else None

    # --- towers ---
    found: dict[tuple[int, str, Optional[str]], Tower] = {}
    tower_rows = (obs.get("episode") or {}).get("crown_towers", []) if raw else obs.get("towers") or []
    for tw in tower_rows:
        if raw:
            s, kind, X, Y, hp, mhp = tw["side"], tw.get("type"), tw["x"], tw["y"], tw["hp"], tw["max_hp"]
            destroyed = bool(tw.get("destroyed", False))
        else:
            s, kind, _lane, X, Y, hp, mhp = tw[:7]
            destroyed = False
        x, _y = _engine_xy(float(X), float(Y), mirror)
        kind = "king" if kind == "king" else "princess"
        lane = None if kind == "king" else _lane_of(x)
        frac = float(hp) / float(mhp) if mhp else 0.0
        alive = (hp > 0) and not destroyed
        found[(side_of(s), kind, lane)] = Tower(side_of(s), kind, lane, frac if alive else 0.0, alive)
    towers = _tower_slots(found)

    # --- units ---
    units: list[Unit] = []
    for e in ents:
        if raw:
            if int(e.get("card_id", -1)) < 0 or str(e.get("name", "")) == "-1":
                continue
            s, X, Y, name, hp, mhp = e["side"], e["x"], e["y"], e.get("name", str(e.get("card_id"))), e["hp"], e["max_hp"]
            kind = int(e.get("kind", -1))
            eid = e.get("entity_id", e.get("category"))
        else:
            s, X, Y, name, hp, mhp = e[:6]
            kind = int(e[6]) if len(e) > 6 else -1
            eid = None
            if str(name) == "-1":
                continue
        if hp <= 0:
            continue
        cid = vocab.engine_unit_id(str(name), float(mhp))
        if cid is None:
            if unmapped is None:
                raise UnmappedName(str(name))
            unmapped.add(str(name))
            continue
        x, y = _engine_xy(float(X), float(Y), mirror)
        age = None
        if history is not None and eid is not None:
            first = history.setdefault(eid, tick)
            age = (tick - int(first)) * TICK_S
        units.append(Unit(cid, side_of(s), x, y, float(hp) / float(mhp) if mhp else None,
                          kind in DEPLOYING_KINDS if kind >= 0 else None, age, 1.0))

    # --- spells: engine effects whose card is a spell (unit-attack effects and tower shots are not) ---
    spells: list[Unit] = []
    for q in obs.get("effects") or []:
        if raw:
            s, X, Y = q["side"], q["x"], q["y"]
            name = q.get("name") or _catalog_names().get(int(q.get("card_id", -1)), str(q.get("card_id", -1)))
        else:
            s, X, Y, name = q[:4]
        sid = vocab.engine_spell_id(str(name))
        if sid is None:
            continue
        x, y = _engine_xy(float(X), float(Y), mirror)
        # a rolling Log / Arrows volley can be reported a fraction of a tile past the back wall (measured:
        # 4 effects of 80,668 recorded frames, worst 1.4 tiles); entities never are. Clip spells only.
        spells.append(Unit(sid, side_of(s), min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0), None, None, None, 1.0))

    dbl, ot = _phase(t)
    return BoardState(source="engine", t_sec=t, t_source="tick", double_elixir=dbl, overtime=ot,
                      my_elixir=my_el, my_elixir_exact=True, opp_elixir=opp_el,
                      my_hand=_hand_ids(deck, hand_names),
                      my_next=deck.card_id_of(vocab.engine_key(next_nm)) if next_nm else -1,
                      towers=towers, units=tuple(units), spells=tuple(spells), deck=deck.card_ids)


# ------------------------------------------------------------------------------------------------------
# live adapter
# ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LiveReads:
    """The screen readers' scalars for one frame (everything the detector does not give)."""
    elixir_int: int                                   # own elixir pips (vision.read_elixir, integer)
    hand_names: tuple[Optional[str], ...]             # 4 template keys (tray order), None = unrecognised slot
    next_name: Optional[str]                          # next-card template key or None
    tower_hp: tuple[Optional[float], ...]             # 6 hp fractions, TOWER order (my K, L, R, opp K, L, R); None = not read
    t_sec: float
    t_source: str                                     # 'clock' (wall clock since match start) | 'timer' (on-screen digits)
    tower_alive: tuple[bool, ...] = (True,) * 6       # TowerTracker flags; a king's hp is never printed live


class _Cfg:
    """Minimal stand-in for clashrl.config.Config (only ``get(*keys, default=)`` is what BoardWarp calls)."""

    def __init__(self, data: Mapping[str, Any]):
        self.data = data

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.data
        for k in keys:
            if not isinstance(node, Mapping) or k not in node:
                return default
            node = node[k]
        return node


_WARPS: dict[Path, Any] = {}


def board_warp(deck: Deck):
    """The deck's ``clashrl.actions.BoardWarp`` (imported from ``deck.src_dir``, never copied), built from
    the deck's config.yaml: tower anchors + board_edges + sim.board, arena_box as the affine fallback."""
    if deck.config not in _WARPS:
        src = str(deck.src_dir)
        if src not in sys.path:
            sys.path.insert(0, src)
        from clashrl.actions import BoardWarp  # noqa: E402  -- icebow/src/clashrl/actions.py:55-155
        cfg = _Cfg(yaml.safe_load(deck.config.read_text(encoding="utf-8")) or {})
        box = cfg.get("action", "arena_box", default=None) or cfg.get("env", "arena_region", default=[0.03, 0.10, 0.97, 0.86])
        _WARPS[deck.config] = BoardWarp(cfg, *[float(v) for v in box])
    return _WARPS[deck.config]


_TEAM_SIDE = {"mine": 0, "enemy": 1, "unknown": -1}


def from_live(detections: Sequence[Any], reads: LiveReads, deck: Deck, *, warp: Any = None) -> BoardState:
    """Detector output + screen reads -> BoardState. ``detections`` are ``replay_mine.Detection`` (duck-typed:
    cls, cx, gy, conf, team); frame -> board goes through ``BoardWarp.frame_to_board`` on ``(cx, gy)`` --
    ``gy`` is the shadow-corrected y for flyers. ``team == 'unknown'`` -> side -1, KEPT."""
    warp = warp or board_warp(deck)
    units: list[Unit] = []
    spells: list[Unit] = []
    for d in detections:
        cid = vocab.unit_id(str(d.cls))
        x, y = warp.frame_to_board(float(d.cx), float(d.gy))
        u = Unit(cid, _TEAM_SIDE.get(str(d.team), -1), float(x), float(y), None, None, None, float(d.conf))
        (spells if vocab.is_spell(cid) else units).append(u)
    towers = []
    for i, (side, (kind, lane)) in enumerate([(s, kl) for s in (0, 1) for kl in TOWER_ORDER]):
        hp = reads.tower_hp[i] if i < len(reads.tower_hp) else None
        alive = bool(reads.tower_alive[i]) if i < len(reads.tower_alive) else True
        if hp is not None and hp <= 0.0:
            alive = False
        towers.append(Tower(side, kind, lane, (None if hp is None else float(hp)) if alive else 0.0, alive))
    dbl, ot = _phase(float(reads.t_sec))
    hand = [deck.card_id_of(n) for n in list(reads.hand_names)[:4]]
    while len(hand) < 4:
        hand.append(-1)
    return BoardState(source="live", t_sec=float(reads.t_sec), t_source=str(reads.t_source),
                      double_elixir=dbl, overtime=ot, my_elixir=float(int(reads.elixir_int)),
                      my_elixir_exact=False, opp_elixir=None, my_hand=tuple(hand),  # type: ignore[arg-type]
                      my_next=deck.card_id_of(reads.next_name), towers=tuple(towers),
                      units=tuple(units), spells=tuple(spells), deck=deck.card_ids)


# ------------------------------------------------------------------------------------------------------
# degrade: engine truth -> live-like
# ------------------------------------------------------------------------------------------------------
# MEASURED detector numbers: presence recall 0.855 / precision 0.886 on the 241-image / 820-box live gate
# (HANDOFF.md:1080-1096, board-24-5). Everything else in here is UNMEASURED and says so.
DEGRADE_RECALL = 0.855
DEGRADE_PRECISION = 0.886
_FP_JITTER_TILES = 1.0          # UNMEASURED: how far a false-positive duplicate sits from its source
_CONF_RANGE = (0.35, 1.0)       # UNMEASURED: live conf distribution; 0.35 is the deploy gate (config detector_conf)


def degrade(bs: BoardState, rng: np.random.Generator, *, recall: float = DEGRADE_RECALL,
            precision: float = DEGRADE_PRECISION, elixir_to_int: bool = True, drop_hp: bool = True,
            drop_deploying: bool = True, unknown_team_rate: Optional[float] = None,
            pos_sigma_tiles: float = 0.0) -> BoardState:
    """Turn an engine state into a live-like one. Units and spells are each kept with p = recall; per KEPT
    unit, with rate (1 - precision) / precision, a false positive is added: a copy with a jittered position
    and a random class of the same kind (troop / building). Live has no unit hp / deploy state / age, so
    those become None; conf is redrawn; elixir is floored to the bar's integer; the opponent's elixir and
    the kings' hp (never printed live) become None.

    ``pos_sigma_tiles`` (gaussian position noise, tiles) and ``unknown_team_rate`` (side -> -1) are
    UNMEASURED -- defaults 0.0 / None leave them off. Deterministic under ``rng``'s seed."""
    fp_rate = (1.0 - precision) / precision
    kinds: dict[str, list[int]] = {"troop": [], "building": [], "spell": []}
    for i in range(vocab.N_DETECTOR):
        kinds[vocab.kind_of(i)].append(i)

    def noisy(u: Unit, cls: Optional[int] = None, jitter: float = pos_sigma_tiles) -> Unit:
        dx = rng.normal(0.0, jitter) / TILES_X if jitter > 0 else 0.0
        dy = rng.normal(0.0, jitter) / TILES_Y if jitter > 0 else 0.0
        side = u.side
        if unknown_team_rate and rng.random() < unknown_team_rate:
            side = -1
        return Unit(u.cls if cls is None else cls, side,
                    float(np.clip(u.x + dx, 0.0, 1.0)), float(np.clip(u.y + dy, 0.0, 1.0)),
                    None if drop_hp else u.hp_frac, None if drop_deploying else u.deploying, None,
                    float(rng.uniform(*_CONF_RANGE)))

    units: list[Unit] = []
    for u in bs.units:
        if rng.random() >= recall:
            continue
        units.append(noisy(u))
        if rng.random() < fp_rate:
            pool = kinds[vocab.kind_of(u.cls)]
            units.append(noisy(u, int(pool[rng.integers(len(pool))]), max(pos_sigma_tiles, _FP_JITTER_TILES)))
    spells = tuple(noisy(s) for s in bs.spells if rng.random() < recall)
    towers = tuple(replace(t, hp_frac=None) if (t.kind == "king" and t.alive) else t for t in bs.towers)
    return replace(bs, source="degraded", t_source="clock",
                   my_elixir=float(int(bs.my_elixir)) if elixir_to_int else bs.my_elixir,
                   my_elixir_exact=bs.my_elixir_exact and not elixir_to_int, opp_elixir=None,
                   towers=towers, units=tuple(units), spells=spells)


# ------------------------------------------------------------------------------------------------------
# tokens
# ------------------------------------------------------------------------------------------------------
# Per-token features (unit_tokens[:, F]):
UNIT_FEATURES = ("cls", "side_mine", "side_enemy", "side_unknown", "x", "y", "hp_frac", "hp_known",
                 "deploying", "deploying_known", "age_30", "age_known", "conf", "is_spell")
F = len(UNIT_FEATURES)   # 14; cls is an int stored as float, to be embedded by the model
# Scalars (scalars[S]):
SCALAR_FEATURES = (("t_300", 1), ("double_elixir", 1), ("overtime", 1), ("my_elixir_10", 1), ("my_elixir_exact", 1),
                   ("opp_elixir_10", 1), ("opp_known", 1), ("hand_slot_onehot_4x9", 36), ("next_slot_onehot_9", 9),
                   ("tower_hp_frac_6", 6), ("tower_hp_known_6", 6), ("tower_alive_6", 6))
S = sum(n for _, n in SCALAR_FEATURES)   # 70
_SIDE_COL = {0: 1, 1: 2, -1: 3}


def _token(u: Unit, spell: bool) -> list[float]:
    row = [0.0] * F
    row[0] = float(u.cls)
    row[_SIDE_COL[u.side]] = 1.0
    row[4], row[5] = u.x, u.y
    if u.hp_frac is not None:
        row[6], row[7] = float(u.hp_frac), 1.0
    if u.deploying is not None:
        row[8], row[9] = float(u.deploying), 1.0
    if u.age_sec is not None:
        row[10], row[11] = float(u.age_sec) / 30.0, 1.0
    row[12] = float(u.conf)
    row[13] = 1.0 if spell else 0.0
    return row


def _slot_onehot(bs: BoardState, cls_id: int) -> list[float]:
    v = [0.0] * 9
    s = bs.deck.index(cls_id) if (cls_id >= 0 and cls_id in bs.deck) else -1
    v[s if s >= 0 else 8] = 1.0
    return v


def to_tokens(bs: BoardState, max_units: int = 64) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(unit_tokens float32[max_units, F], unit_mask bool[max_units], scalars float32[S]).

    Truncation rule (ONE rule, both sources): units and spells are ranked together by distance to the
    river, |y - 0.5| ascending (the fight is at the bridge; a back-row pump matters less than a unit on
    the bridge), ties by conf descending, and the first ``max_units`` are kept. Unranked padding is
    masked False."""
    rows = [(abs(u.y - RIVER_Y), -u.conf, _token(u, False)) for u in bs.units]
    rows += [(abs(u.y - RIVER_Y), -u.conf, _token(u, True)) for u in bs.spells]
    rows.sort(key=lambda r: (r[0], r[1]))
    toks = np.zeros((max_units, F), dtype=np.float32)
    mask = np.zeros(max_units, dtype=bool)
    for i, (_, _, row) in enumerate(rows[:max_units]):
        toks[i] = row
        mask[i] = True
    sc: list[float] = [bs.t_sec / 300.0, float(bs.double_elixir), float(bs.overtime), bs.my_elixir / 10.0,
                       float(bs.my_elixir_exact), (bs.opp_elixir or 0.0) / 10.0, float(bs.opp_elixir is not None)]
    for cid in bs.my_hand:
        sc += _slot_onehot(bs, cid)
    sc += _slot_onehot(bs, bs.my_next)
    sc += [0.0 if t.hp_frac is None else float(t.hp_frac) for t in bs.towers]
    sc += [float(t.hp_frac is not None) for t in bs.towers]
    sc += [float(t.alive) for t in bs.towers]
    assert len(sc) == S
    return toks, mask, np.asarray(sc, dtype=np.float32)

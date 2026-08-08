"""Ingest the `cr-memory-reader` live game-state stream into THIS project's board frame.

WHAT THIS IS
------------
`cr-memory-reader` (github.com/Jason-XII/cr-memory-reader) hooks a running Clash Royale
client with Frida and emits ground-truth battle state as JSON: every arena entity with its
card id, side, tile position, HP and level, plus elixir, battle clock, the visible hand and
the next card. It reads at ~30 Hz with no recognition error, where our YOLO detector runs at
~8 Hz with 0.72 whitelist recall.

WHY IT DROPS STRAIGHT IN
------------------------
Its arena frame is EXACTLY the one this sim was rebuilt on (verified against the repo's own
constants and sample events):

    18 x 32 tiles | 1000 memory units = 1 tile | bridges centred x=3.5 / 14.5 | river rows 15..17

so a position converts with nothing more than ``/1000`` then ``/18, /32``. Decoding its sample
entities through our card KB reproduced their HP to within 0.8% using their level rule
(``level = level_index + 1``), which is a strong end-to-end check that both sides agree.

SCOPE -- READ THIS
------------------
This module is a PARSER for a stream someone else captured. It contains no hooking, no
offsets and no client interaction, and it cannot obtain the data by itself.

The reader it parses targets a PRIVATE-SERVER build (Null's Royale, package
``nullsroyale.rel.free``, game 13.300.6) with offsets hard-bound to that specific
``libg.so`` -- they do not transfer to the official client, and the reader needs a rooted
ARM Android emulator with frida-server.

The intended use is OFFLINE GROUND TRUTH on that private server: auto-labelling detector
frames and validating sim mechanics against real traces. Pointing this at official Clash
Royale to gain an in-match advantage over real opponents would be cheating and a ToS
violation, and is not what this is for.
"""
from __future__ import annotations

import json
import pathlib
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# --- their frame, taken from deploy/minimal_visualizer.py -----------------------------------
UNITS_PER_TILE = 1000.0
TILES_X, TILES_Y = 18.0, 32.0
KIND_TROOP = 15            # their filter: kind_30 == 15 is a live arena troop
KIND_TOWERS = (12, 13)     # crown towers arrive with card_id_ac == -1
MAX_SANE_HP = 30000        # their guard against stale/reused entity objects
STALE_S = 5.0              # ...and their max age for a fresh HP observation
_EVO_ID_BASE = 13000000    # Evo entities stream a truncated id: real = id + 13000000

_CACHE = pathlib.Path("data/card_ids.json")
_API = "https://api.clashroyale.com/v1/cards"


def _key(name: str) -> str:
    return (str(name).strip().lower()
            .replace(" ", "_").replace("-", "_").replace(".", "").replace("'", ""))


def load_card_ids(token: Optional[str] = None, cache: pathlib.Path = _CACHE) -> Dict[int, str]:
    """`data_id -> our card key`, from the OFFICIAL API (cached).

    The reader ships its own cards.json, but the official ``/cards`` endpoint returns the same
    ``{id, name}`` shape -- so this re-imports rather than copying a snapshot that would rot,
    which is the same reason the card KB moved off the abandoned cr-api-data dump.
    """
    if cache.exists():
        try:
            return {int(k): v for k, v in json.loads(cache.read_text(encoding="utf-8")).items()}
        except Exception:  # noqa: BLE001 -- a corrupt cache must not be fatal
            pass
    if token is None:
        return {}
    req = urllib.request.Request(_API, headers={"Authorization": "Bearer " + token})
    items = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())["items"]
    out = {int(c["id"]): _key(c["name"]) for c in items}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({str(k): v for k, v in out.items()}, indent=1), encoding="utf-8")
    return out


def card_key(data_id: int, ids: Dict[int, str]) -> Optional[str]:
    """Their ``card_id_ac`` -> our card key. ``None`` for anything we cannot name."""
    if data_id in ids:
        return ids[data_id]
    # Evo entities stream a TRUNCATED id: the real card is id + 13000000, so Evo Knight
    # arrives as 13000000 and resolves to 26000000. Their visualizer tests
    # `str(id).startswith('13')`, which would also swallow 13, 1300 and 139999999 --
    # a half-open range on the real Evo block is the same rule without the false matches.
    if _EVO_ID_BASE <= data_id < _EVO_ID_BASE + 1000000:
        base = ids.get(data_id + _EVO_ID_BASE)
        if base:
            return base + "_evo"
    return None


@dataclass
class Unit:
    """One arena entity, already in OUR normalised board frame."""
    key: Optional[str]        # our card key ('knight', 'tesla_evo', ...) or None if unnamed
    data_id: int
    mine: bool
    x: float                  # normalised [0,1], same frame as the sim
    y: float
    hp: float
    max_hp: float
    level: int
    is_tower: bool = False


@dataclass
class Snapshot:
    t_ms: int = 0
    units: List[Unit] = field(default_factory=list)
    elixir: float = 0.0
    clock_s: float = 0.0
    hand: List[Optional[str]] = field(default_factory=list)
    next_card: Optional[str] = None


class MemoryFeed:
    """Turns the reader's per-entity event STREAM into coherent whole-board snapshots.

    The reader's own README calls this out as the unsolved problem on the Python side: entities
    are pushed one at a time as the game queries each one's HP, not batched per tick, so a naive
    consumer sees a permanently half-updated board. Resolved here by keying live entities on
    their object pointer and expiring anything not re-observed within ``stale_s`` -- which is also
    what drops the dead/reused objects that linger in memory.

    `local_side` is the side index the LOCAL player occupies. The reader's own visualizer mirrors
    the board when the local player is index 0, so the agent always looks up-field; we do the same
    so `y` is directly comparable with the sim's frame.
    """

    def __init__(self, card_ids: Dict[int, str], local_side: int = 1, stale_s: float = STALE_S):
        self.ids = card_ids
        self.local_side = int(local_side)
        self.stale_ms = int(stale_s * 1000)
        self._live: Dict[str, dict] = {}
        self.snapshot = Snapshot()

    # -- coordinates ------------------------------------------------------------------
    def to_board(self, ux: int, uy: int) -> Tuple[float, float]:
        """Their fixed-point tile units -> our normalised [0,1] board coords."""
        tx, ty = ux / UNITS_PER_TILE, uy / UNITS_PER_TILE
        if self.local_side != 1:                 # mirror so 'our' side is always the bottom
            tx, ty = TILES_X - tx, TILES_Y - ty
        return tx / TILES_X, ty / TILES_Y

    # -- ingest -----------------------------------------------------------------------
    def feed(self, ev: dict) -> None:
        """Consume one event. Unknown event types are ignored rather than raising."""
        kind = ev.get("event")
        if kind == "entity_observed":
            hp = float(ev.get("hp_10") or 0.0)
            k = int(ev.get("kind_30", -1))
            if not (0 < hp <= MAX_SANE_HP) or k not in (KIND_TROOP,) + KIND_TOWERS:
                return
            self._live[str(ev.get("ptr"))] = ev
            self.snapshot.t_ms = max(self.snapshot.t_ms, int(ev.get("t_ms") or 0))
        elif kind in ("snapshot", "state"):
            self.snapshot.elixir = float(ev.get("own_elixir_1e0", ev.get("own_elixir", 0)) or 0)
            self.snapshot.clock_s = float(ev.get("battle_clock_220",
                                                 ev.get("battle_clock", 0)) or 0)
            hand = ev.get("hand") or ev.get("hand_cards") or []
            self.snapshot.hand = [card_key(int(h.get("data_id_40", h.get("data_id", -1))), self.ids)
                                  for h in hand if isinstance(h, dict)]
            nxt = ev.get("next_card") or {}
            if isinstance(nxt, dict) and nxt.get("data_id") is not None:
                self.snapshot.next_card = card_key(int(nxt["data_id"]), self.ids)

    def _expire(self) -> None:
        cutoff = self.snapshot.t_ms - self.stale_ms
        self._live = {p: e for p, e in self._live.items() if int(e.get("t_ms") or 0) >= cutoff}

    def build(self) -> Snapshot:
        """The current coherent board state."""
        self._expire()
        units: List[Unit] = []
        for ev in self._live.values():
            did = int(ev.get("card_id_ac", -1))
            k = int(ev.get("kind_30", -1))
            x, y = self.to_board(int(ev.get("pos_x_7c", 0)), int(ev.get("pos_y_80", 0)))
            units.append(Unit(
                key=card_key(did, self.ids) if did > 0 else None,
                data_id=did, mine=int(ev.get("side_78", -1)) == self.local_side,
                x=x, y=y, hp=float(ev.get("hp_10") or 0.0),
                max_hp=float(ev.get("max_hp_14") or 0.0),
                level=int(ev.get("level_index_120", 0)) + 1,     # their Phase 13 rule
                is_tower=(k in KIND_TOWERS)))
        self.snapshot.units = units
        return self.snapshot

    # -- hand-off to the existing threat pipeline --------------------------------------
    def threat_items(self, river: float = 0.5, king_y: float = 0.90625
                     ) -> List[Tuple[str, float]]:
        """`[(card_key, depth_frac)]` for NAMED ENEMY units on our half.

        This is exactly the input `card_threat.identity_threat_vector` already takes from the
        detector, so the memory feed can substitute for -- or cross-check -- perception without
        touching the policy. depth_frac is 0 at the river and 1 at our king.
        """
        span = max(1e-6, king_y - river)
        out = []
        for u in self.build().units:
            if u.mine or u.is_tower or not u.key or u.y <= river:
                continue
            out.append((u.key, min(1.0, (u.y - river) / span)))
        return out

"""crforge (voonhous/crforge, Java) behind RoyaleSim's engine-core interface (``royalegym.rust_engine.RustEngine``), so
``royale_env`` and everything above it (obs, cues, extrapolation, public observer, opponent-elixir counter, past plays)
runs on crforge unchanged. plan1026 Pillar 1 Stage 2, ticket F1.

    from pipeline.crforge_core import CrforgeCore
    env = RoyaleSelfPlayEnv(); env.core = CrforgeCore()     # the seam (royale_env builds RustEngine today)

What it is
  * One crforge match (``CfCore.java``, scratchpad/gauntlet/L74/crforge/facade) in a long-lived in-process JVM (JPype).
    ``state()`` is RoyaleSim's ``BattleState`` decoded by the same msgspec decoder RustEngine uses, in RoyaleSim's
    units: positions x18 (18,000 subtiles per tile; crforge 1,000), elixir milli, card ids = the active RoyaleSim
    runtime's catalogue (``cards()``), Blue = side 0 at low y in both engines.
  * Body identity: ``body_map.json`` (S3b-1, scratchpad/gauntlet/L74/speed/crforge). A name with one entry maps by
    name; the 9 names RoyaleSim splits by spawning card (Skeleton, Bat, ...) map by the card of the body's ROOT PLAY:
    crforge names each unit after its play ("c5_0", a spawn "c5_0_3"), and this class records each play's card.
    Bodies without an entry (body_map ``_unmatched``) get card_id -1, so ``RoyalePoolEnv.raw`` drops them; they are
    counted in ``unmapped()``.
  * Spell objects (``BattleState.spells``): each spells_other card's Projectile / AreaEffectObject and the objects
    they spawn in crforge's own tables -> that card. Unit and tower shots are ``projectiles`` (firer = the firing
    body's card, -1 a crown tower).
  * ``save_state()`` / ``load_state()``: crforge's DeepCopy of the match (shares only the game tables). A blob is never
    stepped, so N ``load_state(blob)`` give N independent forks (search_s0.fork_into's contract). Blobs live in this
    JVM: they are not bytes and do not cross processes.

What it is not (each raises rather than run something else)
  * crforge runs every command 20 ticks after it is given (Standard1v1Battle.PLAY_DELAY_TICKS: the real client's
    delay), like RustEngine under ``set_command_delay_ticks(20)``: the card stays in hand and the elixir is spent at the
    run. ``command_delay_ticks`` is (20, 20); any other delay is refused.
  * ``ShuffleMode.NONE`` only (the deal is the setup's order: crforge's own shuffle draw is taken, then the hand is put
    back in that order). No ``start_tick`` / ``elixir_milli`` / ``tower_hp`` / ``spawns`` starts, no tower troops.
  * Levels: ``setup.levels`` / ``tower_levels`` when given, else ``level`` (16) everywhere (RoyaleSim's default is 11).
  * Hero abilities (F1c-1): ``PlayerState.abilities`` has one row per button from the deal on, in RoyaleSim's button
    order (heroes, then champions), from crforge's champion slots; a hero body sets STATUS_HERO (16), as RoyaleSim
    fin16 does (its summons and champions do not). A press runs 20 ticks after it is given, like a play.
  * ``_battle`` offers what pipeline code reads off RoyaleSim's Battle: ``state_json``, ``catalogue_json``,
    ``unit_types_json`` / ``unit_types_digest``, ``debug_units`` (uid, name only), and ``save()`` = only the fields
    ``sim_unit_state.extract`` reads.
  * Cue values (F1c-2): each ENTITY_FIELDS / save() value and status bit is read from crforge's own view, targeting,
    buff and movement state and put in RoyaleSim's encoding, measured field by field against fin16 on matched scenarios
    (scratchpad/gauntlet/L74/crforge/facade/cues/cue_ab.py -> facade/results/f1c2); the fields crforge has no
    equivalent for (tower facing, the king tower's footprint, the target of a non-homing shot, ...) are listed there.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path

import msgspec

from pipeline.royale_runtime import activate as _activate_runtime
from pipeline import royale_heroiw as heroiw

_activate_runtime()

from royalegym.protocol import (HAND_SIZE, BattleState, DeployResult, DeployStatus, ShuffleMode)  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CRFORGE_PIN = "ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0"
LIB = Path(os.environ.get("CRFORGE_LIB", "/workspace/cfspeed/crforge/env/build/install/env/lib"))
TABLES = Path(os.environ.get("CRFORGE_TABLES", "/workspace/cfspeed/crforge_cache/tables/16.402.22"))
FACADE_BUILD = Path(os.environ.get("CRFORGE_FACADE_BUILD", "/workspace/f1/build"))   # javac -d of CfCore.java
BODY_MAP = REPO / "scratchpad/gauntlet/L74/speed/crforge/body_map.json"
K = 18                         # RoyaleSim subtiles per crforge game unit
DELAY = 20                     # crforge Standard1v1Battle.PLAY_DELAY_TICKS
LEVEL = 16
# crforge PlayerCommands.Refusal (ordinal order) -> RoyaleSim DeployStatus; 100 = a play crforge does not model
REFUSAL = ("NONE", "MATCH_OVER", "KING_DEAD", "NOT_IN_HAND", "START_COOLDOWN", "CARD_PENDING", "NOT_ENOUGH_ELIXIR",
           "NO_TILE", "NO_CHAMPION", "COOLDOWN", "NO_CHARGES", "NOT_CHAMPION", "ABILITY_PENDING", "CLONE", "FROZEN",
           "ABILITY_DISABLED")
_STATUS = dict(zip(REFUSAL, (DeployStatus.OK, DeployStatus.GAME_OVER, DeployStatus.GAME_OVER, DeployStatus.EMPTY_SLOT,
                             DeployStatus.TOO_EARLY, DeployStatus.CARD_PENDING, DeployStatus.NOT_ENOUGH_ELIXIR,
                             DeployStatus.NO_DEPLOY, DeployStatus.NO_HERO, DeployStatus.ABILITY_NOT_READY,
                             DeployStatus.ABILITY_SPENT, DeployStatus.NO_HERO, DeployStatus.CARD_PENDING,
                             DeployStatus.NO_HERO, DeployStatus.ABILITY_NOT_READY, DeployStatus.ABILITY_NOT_READY)))
_J = {}            # the JVM's classes and shared tables, once per process


def _jvm():
    if not _J:
        import jpype
        if not jpype.isJVMStarted():
            cp = sorted(str(p) for p in LIB.glob("*.jar")) + [str(FACADE_BUILD)]
            jpype.startJVM(f"-Xmx{os.environ.get('CRFORGE_XMX', '4g')}", classpath=cp, convertStrings=True)
        J = jpype.JClass
        _J.update(jpype=jpype, CfCore=J("CfCore"), Path=J("java.nio.file.Path"),
                  tables=J("org.crforge.core.battle.data.GameTables").load(J("java.nio.file.Path").of(str(TABLES))))
        _J["Str"], _J["Int"] = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
        _J["rs"] = RustEngine(**heroiw.engine_options())             # the catalogue only: card ids, CardInfo rows
    return _J


@functools.lru_cache(maxsize=None)
def spell_objects(tables_dir: Path = TABLES) -> dict[str, tuple[str, int]]:
    """crforge object name -> (spell card, RoyaleSim SpellMotion) from the tables: each spells_other card's Projectile /
    AreaEffectObject / CustomFirstProjectile and every projectile / area object those name in their own columns,
    transitively. A projectile reached from another one is ROLLING (the Log), the first FLIGHT; an area object with a
    HitSpeed is PULSING, else AREA. An object two cards reach is left out (ambiguous)."""
    rows = {t: json.loads((tables_dir / f"{t}.json").read_text())["rows"]
            for t in ("spells_other", "projectiles", "area_effect_objects")}
    proj, area = rows["projectiles"], rows["area_effect_objects"]
    out, clash = {}, set()
    for card, r in rows["spells_other"].items():
        todo = [(v, 0) for k in ("Projectile", "CustomFirstProjectile", "AreaEffectObject")
                if isinstance(v := r["columns"].get(k), str) and v]
        seen = set()
        while todo:
            name, depth = todo.pop()
            if name in seen or (name not in proj and name not in area):
                continue
            seen.add(name)
            if name in proj:
                motion = 0 if depth == 0 else 2
                cols = proj[name]["columns"]
            else:
                cols = area[name]["columns"]
                motion = 4 if cols.get("HitSpeed") else 3
            if name in out and out[name][0] != card:
                clash.add(name)
            out[name] = (card, motion)
            todo += [(v, depth + 1) for v in cols.values() if isinstance(v, str) and (v in proj or v in area)]
    return {k: v for k, v in out.items() if k not in clash}


class _Battle:
    """The RoyaleSim ``Battle`` methods pipeline code calls on ``core._battle``."""

    def __init__(self, core: "CrforgeCore"):
        self.core = core

    def state_json(self) -> bytes:
        return str(self.core._cf.state()).encode()

    def save(self) -> bytes:
        return str(self.core._cf.cueSave()).encode()

    def catalogue_json(self):
        return _jvm()["rs"]._battle.catalogue_json()

    def unit_types_json(self) -> str:
        return json.dumps(self.core.unit_types())

    def unit_types_digest(self) -> str:
        return hashlib.sha256(self.unit_types_json().encode()).hexdigest()

    def debug_units(self) -> list:
        """(uid, unit name) per troop, the two columns royale_env reads of RoyaleSim's debug_units (the hero range
        lookup): a hero body (STATUS_HERO) is "<card>_hero", as RoyaleSim names its hero form, else its card. The
        route / speed columns are not given."""
        names = {c.card_id: c.name for c in self.core._cards}
        return [(e.uid, names[e.card_id] + ("_hero" if e.status_flags & 16 else ""))
                for e in self.core.state().entities if e.kind == 0 and e.card_id in names]

    def set_tower_troops(self, blue=None, red=None) -> None:
        if blue is not None or red is not None:
            raise NotImplementedError("crforge facade: tower troops are not wired (Princess towers only)")


class CrforgeCore:
    """``RustEngine``'s interface on one crforge match (module docstring)."""

    command_delay_ticks = (DELAY, DELAY)
    reports_resolved_position = True
    ability_button_count = 2

    def __init__(self, level: int = LEVEL, body_map: Path = BODY_MAP, **_ignored):
        J = _jvm()
        self.level = int(level)
        rs = J["rs"]
        self._cards = rs.cards()
        self.ids = {c.name: c.card_id for c in self._cards}
        self._cf = J["CfCore"](J["tables"])
        self._cf.cardNames = J["Str"]([c.name for c in self._cards])
        raw = Path(body_map).read_bytes()
        self.body_map_sha = hashlib.sha256(raw).hexdigest()
        bm = json.loads(raw)
        self.dropped_by_map = sorted(e["crforge_name"] for e in bm.get("_unmatched", []))
        for name, v in bm.items():
            if name.startswith("_"):
                continue
            for e in v["entries"]:
                if e["rs_card"] not in self.ids:
                    continue
                packed = self.ids[e["rs_card"]] << 8 | (int(e["rs_status_flags"]) & 0xFF)
                if v["by_name_unique"]:
                    self._cf.unique.put(name, J["jpype"].JInt(packed))
                    self._cf.uniqueCard.put(name, e["rs_card"])
                else:
                    self._cf.byRoot.put(f"{name}|{e['rs_card']}", J["jpype"].JInt(packed))
        for obj, (card, motion) in spell_objects().items():
            if card in self.ids:
                self._cf.spellObj.put(obj, J["jpype"].JInt(self.ids[card] << 4 | motion))
        self._battle = _Battle(self)
        self._decode = msgspec.json.Decoder(BattleState)
        self._reset_called = False

    # ------------------------------------------------------------------ catalogue
    def cards(self):
        return self._cards

    def arena(self):
        return _jvm()["rs"].arena()

    def rules(self):
        return _jvm()["rs"].rules()

    def unit_types(self) -> list[str]:
        """crforge body row names, indexed by ``EntityState.unit_type`` (grows as new bodies appear; every body on the
        board has its id once this returns: sim_unit_state.extract reads the names before state_json)."""
        return [str(s) for s in self._cf.unitTypesNow()]

    def card_table_stamp(self) -> dict:
        return {"engine": "crforge", "crforge": CRFORGE_PIN, "tables": str(_jvm()["tables"].version()),
                "tables_sha": str(_jvm()["tables"].contentSha()), "body_map_sha256": self.body_map_sha,
                "catalogue": _jvm()["rs"].card_table_stamp()}

    def set_command_delay_ticks(self, delay) -> None:
        pair = (delay, delay) if isinstance(delay, int) else tuple(delay)
        if pair != (DELAY, DELAY):
            raise NotImplementedError(f"crforge runs every command {DELAY} ticks after it is given; asked {delay!r}")

    # ------------------------------------------------------------------ episode
    def reset(self, seed: int, setup) -> None:
        if int(setup.shuffle) != ShuffleMode.NONE:
            raise NotImplementedError("crforge facade: ShuffleMode.NONE only (the caller deals)")
        if (setup.start_tick or setup.elixir_milli is not None or setup.tower_hp is not None or setup.spawns
                or not setup.crowns_from_destroyed_towers):
            raise NotImplementedError("crforge facade: mid-match starts / spawns are not wired")
        J = _jvm()
        names = {c.card_id: c.name for c in self._cards}
        decks = [[names[int(c)] for c in d] for d in setup.decks]
        forms = setup.forms or [[0] * 8, [0] * 8]
        lv = getattr(setup, "levels", None) or [[self.level] * 8, [self.level] * 8]
        tl = getattr(setup, "tower_levels", None) or [self.level, self.level]
        try:
            self._cf.reset(int(seed) & 0x7FFFFFFF, J["Str"](decks[0]), J["Int"](list(map(int, forms[0]))),
                           J["Str"](decks[1]), J["Int"](list(map(int, forms[1]))), J["Int"](list(map(int, lv[0]))),
                           J["Int"](list(map(int, lv[1]))), int(tl[0]), int(tl[1]),
                           J["Int"](list(map(int, setup.decks[0]))), J["Int"](list(map(int, setup.decks[1]))))
        except J["jpype"].JException as exc:          # an unknown card, or a form its slot cannot hold
            raise ValueError(f"crforge refused the setup: {exc}") from None
        self._reset_called = True

    def check_deploy(self, command) -> int:
        team, slot = int(command.team), int(command.hand_slot)
        if team not in (0, 1):
            return DeployStatus.BAD_TEAM
        if slot >= HAND_SIZE:
            return self._status(self._cf.ability(team, slot - HAND_SIZE, True))
        if not 0 <= slot < HAND_SIZE:
            return DeployStatus.BAD_SLOT
        return self._status(self._cf.check(team, slot))

    def step(self, commands, ticks: int) -> list:
        if ticks < 0:
            raise ValueError("ticks must be >= 0")
        out = []
        for c in commands:
            team, slot, tick = int(c.team), int(c.hand_slot), int(self._cf.tick())
            st = self.state() if team in (0, 1) and 0 <= slot < HAND_SIZE else None
            card = st.players[team].hand[slot] if st is not None else -1
            if team not in (0, 1):
                out.append(DeployResult(team, slot, -1, DeployStatus.BAD_TEAM, tick, c.x, c.y))
            elif slot >= HAND_SIZE:
                out.append(DeployResult(team, slot, -1, self._status(self._cf.ability(team, slot - HAND_SIZE, False)),
                                        tick, c.x, c.y))
            elif slot < 0:
                out.append(DeployResult(team, slot, -1, DeployStatus.BAD_SLOT, tick, c.x, c.y))
            else:
                code, x, y = self._cf.play(team, slot, int(c.x) // K, int(c.y) // K)
                out.append(DeployResult(team, slot, card, self._status(code), tick, int(x) * K, int(y) * K))
        self._cf.step(int(ticks))
        return out

    def state(self) -> BattleState:
        return self._decode.decode(str(self._cf.state()))

    def save_state(self):
        return self._cf.save()

    def load_state(self, blob) -> None:
        self._cf.load(blob)
        self._reset_called = True

    def state_hash(self) -> int:
        return int.from_bytes(hashlib.sha256(str(self._cf.state()).encode()).digest()[:8], "little")

    def unmapped(self) -> dict:
        """Bodies the map could not name ("body|root card", "area:name") -> times seen in state(); plus stats."""
        return {"missing": {str(k): int(v) for k, v in dict(self._cf.missing).items()},
                "unresolved_creations": {str(k): int(v) for k, v in dict(self._cf.unresolved()).items()},
                "stats": {str(k): int(v) for k, v in dict(self._cf.stats).items()}}

    @staticmethod
    def _status(code: int) -> int:
        code = int(code)
        return DeployStatus.NO_DEPLOY if code == 100 else _STATUS[REFUSAL[code]]

"""LOOP-CTX: CfCtx (Java) -> the context kwargs of decision_options.decide, i.e. what decision_options.match_kwargs gives
an e1_eval SelfPlaySide at the live decision config, without a Python Match / BoardState / raw state.

    T = tables(env.names, grid, options)                 # once per JVM (CfCtx.Tables, filled from the production modules)
    st = CfCtx.Seat()                                    # one per match side; st.played(T, land, slot, cell) per ACCEPTED play
    n = CfCtx.build(T, names, facade_match, seat, st, buf, 0)   # right after that FacadeMatch built this seat's obs
    if n == -1: fill_missing(T); build again             # a new tower max HP (my Rocket's tower damage); no state changed
    rows.append(decode(view[:n].tolist()))
    kw = kwargs(rows, options=options_for(cfg), grid=..., card_names=..., card_ids=..., sides=..., pending=..., rngs=...,
                projectiles=...)                         # -> decide(..., **kw) as decide_batch passes it

Inputs the LOOP supplies (bookkeeping, not match state): ``pending`` (a decided play not yet given to the engine:
SelfPlaySide.pending), the accepted-play log (Seat.played: Match._land's landing tick, slot, cell), the per-match RNG
(decision_rng: match_kwargs' stream), the deck (card_names / card_ids) and the obs block's ``projectiles``.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

UNPORTED = ("gate_decode hazard (step_s / elixir / enemy_units / threatened)", "rocket_value_lead on / blend",
            "rocket_value_threat on", "pipeline_decisions", "pipeline_tau_delta")


def options_for(cfg):
    """match_kwargs' options for ``cfg`` (card_levels is LIVE-ONLY: dropped), refusing what CfCtx does not build."""
    from pipeline.decision_options import options_from_config
    o = options_from_config(cfg)
    if o.card_levels is not None:
        o = replace(o, card_levels=None)
    bad = [o.gate_decode != "threshold", o.rocket_value_lead in ("on", "blend"), o.rocket_value_threat == "on",
           bool(cfg.get("pipeline_decisions")), bool(cfg.get("pipeline_tau_delta"))]
    if any(bad):
        raise NotImplementedError(f"CfCtx does not build: {[u for u, b in zip(UNPORTED, bad) if b]}")
    return o


def decision_rng(tag: str, k: int, decision_seed: int = 0) -> np.random.Generator:
    """match_kwargs' per-match decision stream (Match.rng_decision_options)."""
    from pipeline.e1_eval import obs_seed
    return np.random.default_rng(np.random.SeedSequence([obs_seed("decision_options:" + tag, k), int(decision_seed)]))


def tables(env_names: dict, grid: str, options):
    """CfCtx.Tables from the production modules (vocab, catalog, public_geometry, decision_options constants)."""
    import jpype
    from pipeline import decision_options as D, vocab
    from pipeline import obs_contract as OC
    from pipeline.model_v3 import GRID_X, GRID_Y
    from pipeline.public_geometry import constants
    T = jpype.JClass("CfCtx$Tables")()
    n = len(vocab.UNIT_VOCAB)
    has, fly, val = [False] * n, [False] * n, [0.0] * n
    for i, (f, v) in D.log_air_traits().items():
        has[i], fly[i], val[i] = True, bool(f), float(v)
    B, Dbl = jpype.JArray(jpype.JBoolean), jpype.JArray(jpype.JDouble)
    T.has, T.flying, T.value = B(has), B(fly), Dbl(val)
    T.goblin = B([vocab.base_key(vocab.UNIT_VOCAB[i]) in D.BARREL_GOBLIN_KEYS for i in range(n)])
    kids = D.log_air_ground_children()
    for cid, name in env_names.items():                 # raw()'s name of a card id -> its ground-child HPs
        hps = kids.get(vocab.engine_key(str(name)))
        if hps:
            T.putChild(int(cid), jpype.JArray(jpype.JInt)(sorted(int(h) for h in hps)))
    r = constants()["tower_radius"]
    T.kingR, T.princessR = float(r["KingTower"]) / 1000.0, float(r["PrincessTower"]) / 1000.0
    T.anchor = Dbl([c for k in OC.TOWER_ORDER for c in OC._ANCHOR_XY[k]])
    T.enemyTowers = Dbl([c for xy in D.ENEMY_TOWERS_TILES for c in xy])
    T.cellOff = 0.5 if grid == "floor" else 0.0
    T.window, T.radius = D.TAU_THREAT_WINDOW_S, D.TAU_THREAT_RADIUS_TILES
    T.childMatch, T.unknownValue, T.myHalfY = D.LOG_AIR_CHILD_MATCH_TILES, D.LOG_AIR_UNKNOWN_VALUE, D.MY_HALF_Y_TILES
    T.confirm, T.histTicks = D.PRINCESS_DEAD_CONFIRM_TICKS, D.LETHAL_HIST_TICKS
    T.quietTicks = round(options.lethal_quiet / 0.05)   # match_kwargs: recently_hit's window
    T.gx, T.gy = GRID_X, GRID_Y
    return T


def fill_missing(T) -> int:
    """Each (king, my tower max_hp) build() met -> my_rocket_damage on that one row (None -> -1)."""
    from pipeline.decision_options import my_rocket_damage
    keys = list(T.takeMissing())
    for key in keys:
        king, mhp = bool((int(key) >> 32) & 1), int(key) & 0xFFFFFFFF
        mhp = mhp - (1 << 32) if mhp >= 1 << 31 else mhp
        d = my_rocket_damage([{"side": 0, "type": "king" if king else "princess", "max_hp": mhp}], 0)
        T.putDmg(king, mhp, -1 if d is None else int(d))
    return len(keys)


# ---------------------------------------------------------------------------------------------------- decode
HEAD, LANE = 36, {1: "L", 2: "R"}
TOWER_SLOTS = ((0, "king", None), (0, "princess", "L"), (0, "princess", "R"),
               (1, "king", None), (1, "princess", "L"), (1, "princess", "R"))


class Row:
    """One seat-row of CfCtx.build (field names = the production values they stand for)."""
    __slots__ = ("t_sec", "tau_threat", "enemy_alive", "rocket_alive", "kills_king", "my_elixir", "hand", "tw_frac",
                 "tw_alive", "skip", "crown", "units", "bodies", "goblins", "ground", "air", "log_towers", "own")


def decode(v: list) -> Row:
    r = Row()
    r.t_sec, r.tau_threat = v[0], v[1] != 0
    r.enemy_alive = (v[2] != 0, v[3] != 0, v[4] != 0)
    r.rocket_alive = (v[5] != 0, v[6] != 0, v[7] != 0)
    r.kills_king, r.my_elixir = v[8] != 0, v[9]
    r.hand = [int(s) for s in v[10:14]]
    r.tw_frac, r.tw_alive = v[14:20], [a != 0 for a in v[20:26]]
    r.skip = ({"L"} if v[26] else set()) | ({"R"} if v[27] else set())
    nc, nu, nb, ng, ngr, na, nt, no = (int(x) for x in v[28:36])
    w = HEAD
    r.crown = [{"side": int(v[i]), "type": "king" if v[i + 1] else "princess", "x": v[i + 2], "y": v[i + 3],
                "hp": int(v[i + 4]), "max_hp": int(v[i + 5]), "destroyed": v[i + 6] != 0} for i in range(w, w + 7 * nc, 7)]
    w += 7 * nc
    r.units = v[w:w + 6 * nu]
    w += 6 * nu
    r.bodies = tuple(zip(v[w:w + 2 * nb:2], v[w + 1:w + 2 * nb:2]))
    w += 2 * nb
    r.goblins = tuple(zip(v[w:w + 2 * ng:2], v[w + 1:w + 2 * ng:2]))
    w += 2 * ng
    r.ground = tuple(zip(v[w:w + 3 * ngr:3], v[w + 1:w + 3 * ngr:3], v[w + 2:w + 3 * ngr:3]))
    w += 3 * ngr
    r.air = tuple(zip(v[w:w + 2 * na:2], v[w + 1:w + 2 * na:2]))
    w += 2 * na
    r.log_towers = tuple((v[i], v[i + 1], v[i + 2], v[i + 3], LANE.get(int(v[i + 4]))) for i in range(w, w + 5 * nt, 5))
    w += 5 * nt
    r.own = v[w:w + 10 * no]
    return r


class CtxBoard:
    """The obs_contract.BoardState fields decide's Rocket rules read (rocket_value_choice, rocket_tornado_choice,
    elixir_regen_per_tick, enemy_princesses_alive): t_sec, double_elixir, overtime, my_elixir, my_hand, towers, units;
    towers / units are real Tower / Unit objects, built on first read."""
    __slots__ = ("t_sec", "double_elixir", "overtime", "my_elixir", "my_hand", "_row", "_units", "_towers")

    def __init__(self, row: Row, card_ids):
        from pipeline.obs_contract import DOUBLE_ELIXIR_S, OVERTIME_S
        self.t_sec, self.my_elixir, self._row = row.t_sec, row.my_elixir, row
        self.double_elixir, self.overtime = row.t_sec >= DOUBLE_ELIXIR_S, row.t_sec >= OVERTIME_S
        self.my_hand = tuple(int(card_ids[s]) if s < 8 else -1 for s in row.hand)
        self._units = self._towers = None

    @property
    def units(self):
        if self._units is None:
            from pipeline.obs_contract import Unit
            u = self._row.units
            self._units = tuple(Unit(int(u[i]), int(u[i + 1]), u[i + 2], u[i + 3], None if math.isnan(u[i + 4]) else u[i + 4],
                                     None, None, 1.0, int(u[i + 5])) for i in range(0, len(u), 6))
        return self._units

    @property
    def towers(self):
        if self._towers is None:
            from pipeline.obs_contract import Tower
            r = self._row
            self._towers = tuple(Tower(s, k, ln, r.tw_frac[i], r.tw_alive[i]) for i, (s, k, ln) in enumerate(TOWER_SLOTS))
        return self._towers


class Lazy:
    """A per-row list built on first index (decide reads rocket_boards / log_air_boards only on Rocket / Log rows)."""
    __slots__ = ("f", "c")
    _MISS = object()

    def __init__(self, f, n):
        self.f, self.c = f, [Lazy._MISS] * n

    def __len__(self):
        return len(self.c)

    def __getitem__(self, r):
        v = self.c[r]
        if v is Lazy._MISS:
            v = self.c[r] = self.f(int(r))
        return v


def own_plays(row: Row, names) -> list:
    """lethal_log's ``own``: (card, x, y, landing t_sec, hp_after snapshot or None) per accepted play, the last 8."""
    o, out = row.own, []
    for i in range(0, len(o), 10):
        before = {LANE[int(o[i + 6 + 2 * k])]: int(o[i + 7 + 2 * k]) for k in range(int(o[i + 5]))} if o[i + 4] else None
        out.append((names[int(o[i])], o[i + 1], o[i + 2], int(o[i + 3]) * 0.05, before))
    return out


def kwargs(rows, *, options, grid, card_names, card_ids, sides, pending, rngs, projectiles) -> dict:
    """decision_options.match_kwargs' dict for ``rows`` (same keys, same values; rocket_value's holder = None: the
    holder is read only with rocket_value_lead on / blend or rocket_value_threat on, which options_for refuses)."""
    if not options.active:
        return {}
    n = len(rows)
    out = dict(decision_options=options, rngs=rngs, card_names=card_names)
    if options.tau_threatened is not None:
        out["tau_threat"] = [r.tau_threat for r in rows]
    if (options.tau_phase is not None or options.xbow_class != "argmax" or options.xbow_dead_lane != "allow"
            or options.rocket_dead_target != "allow"):
        out.update(t_sec=[r.t_sec for r in rows], grid=grid, enemy_alive=[r.enemy_alive for r in rows])
        if options.rocket_dead_target != "allow":
            out["rocket_boards"] = Lazy(lambda i: (rows[i].rocket_alive, rows[i].bodies, rows[i].kills_king), n)
    if options.lethal_rocket != "off":
        lethal = [(r.crown, int(s), bool(pd)) for r, s, pd in zip(rows, sides, pending)]
        if options.lethal_log == "on":
            lethal = [row + (own_plays(r, nm),) for row, r, nm in zip(lethal, rows, card_names)]
        if options.lethal_quiet > 0:
            lethal = [(row + (None,) if len(row) == 3 else row) + (r.skip,) for row, r in zip(lethal, rows)]
        out.update(t_sec=[r.t_sec for r in rows], grid=grid, lethal=lethal)
    if options.log_air != "off":
        out.update(grid=grid, log_air_boards=Lazy(lambda i: (rows[i].ground, rows[i].air, rows[i].log_towers), n))
    if options.barrel_lane == "on":
        out.update(grid=grid, barrel_goblins=[r.goblins for r in rows])
    if options.rocket_value > 0:
        out.update(grid=grid, rocket_value=[(CtxBoard(r, ids), bool(pd), None) for r, ids, pd in zip(rows, card_ids, pending)])
    if options.uses_barrels:
        out.update(grid=grid, projectiles=list(projectiles))
    return out

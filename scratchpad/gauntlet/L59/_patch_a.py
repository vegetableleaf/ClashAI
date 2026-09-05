from pathlib import Path
p = Path("C:/Users/benpe/ClashBot/icebow/src/clashrl/geometry_reward.py")
s = p.read_text(encoding="utf-8")

def rep(old, new):
    global s
    assert old in s, old[:80]
    assert s.count(old) == 1, ("not unique", old[:80])
    s = s.replace(old, new)

# 1. constants + TERM_KEYS
rep('''TERM_KEYS = (
    "p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
    "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility",
    "bridge_block_detected", "bridge_block_case", "d_threat",
)
''', '''SWARM_ROLE = "swarm"             # L59: P7 is never charged to a swarm card (gate.md 1d.4)
CREDIT_FLOOR = -0.3              # L59: placement_credit floor (the close / fragility penalties are clipped here)
CREDIT_CAP = 1.0                 # L59: placement_credit cap (a pull AND an offensive bow can coincide)

TERM_KEYS = (
    "p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
    "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility",
    "bridge_block_detected", "bridge_block_case", "d_threat",
    # L59 (HANDOFF 5cs.29 decisions): the OLD snapshot P1 pair, kept so the gate rerun reports both.
    # `p1_pull_band` is now PATH-based (band on the distance from the building to the threat's forward
    # march path); `p1_snapshot` / `p1_close_snapshot` are the same formulas on the threat's CURRENT
    # march distance. Both P1 bands are RAW (no P2 factor) -- `placement_credit` applies (0.5 + 0.5 P2).
    "p1_snapshot", "p1_close_snapshot", "d_path",
)
''')

# 2. placement_from_spec: roles
rep('''def placement_from_spec(spec, x: float, y: float, *, siege_sight: float = DEFAULT_SIEGE_SIGHT,
                        tower_range: float = DEFAULT_TOWER_RANGE,
                        king_range: float = DEFAULT_KING_RANGE) -> dict:
    """The `placement` dict :func:`score_placement` takes, from a CardSpec + landing tile."""
    ra, rs = radii_of(spec, siege_sight=siege_sight, tower_range=tower_range, king_range=king_range)
    return dict(
''', '''def placement_from_spec(spec, x: float, y: float, *, siege_sight: float = DEFAULT_SIEGE_SIGHT,
                        tower_range: float = DEFAULT_TOWER_RANGE,
                        king_range: float = DEFAULT_KING_RANGE, db=None,
                        roles: Optional[Sequence[str]] = None) -> dict:
    """The `placement` dict :func:`score_placement` takes, from a CardSpec + landing tile.

    `roles` = the placed card's KB roles (P7 is skipped for a swarm card). Given explicitly, or read
    from `db` through the SAME source `role_average_radii` uses (`card_threat.profile(...).roles()`);
    with neither, the placement carries no roles and P7 is charged as before."""
    ra, rs = radii_of(spec, siege_sight=siege_sight, tower_range=tower_range, king_range=king_range)
    if roles is None and db is not None:
        try:
            from .card_threat import profile as _profile
            roles = tuple(_profile(db, str(spec.base)).roles())
        except Exception:              # noqa: BLE001 -- the KB is advisory here
            roles = ()
    return dict(
        roles=tuple(roles or ()),
''')

# 3. P1 path-based
rep('''        if is_building:
            towers = board.own_towers()
            x = march_gap(board, threat.x, threat.y, px, py, r_body)
            if threat.flying:
                x = max(0.0, tile_dist(threat.x, threat.y, px, py, board.tiles) - r_body)
            tw = _nearest_own_tower_by_march(board, threat, towers)
            d_tower = (march_gap(board, threat.x, threat.y, tw.x, tw.y, tw.r_body)
                       if tw is not None else float("inf"))
            pull_ok = 1.0 if x < d_tower else 0.0
            lo = threat.r_atk + P1_LO_PAD
            raw = band(x, lo, threat.r_sight, P1_W) * pull_ok
            out["p1_pull_band"] = raw * (0.5 + 0.5 * out["p2_cover"])
            if threat.r_atk <= MELEE_REACH_MAX:            # dropped on top of a MELEE wincon
                out["p1_close_penalty"] = -clip01((lo - x) / lo) if lo > 0 else 0.0
''', '''        if is_building:
            towers = board.own_towers()
            # snapshot distance: the threat's CURRENT march distance to the building's hitbox edge
            x = march_gap(board, threat.x, threat.y, px, py, r_body)
            if threat.flying:
                x = max(0.0, tile_dist(threat.x, threat.y, px, py, board.tiles) - r_body)
            tw = _nearest_own_tower_by_march(board, threat, towers)
            d_tower = (march_gap(board, threat.x, threat.y, tw.x, tw.y, tw.r_body)
                       if tw is not None else float("inf"))
            # pull_ok: the building is acquired before the tower (nearer by march distance). A
            # building BEHIND the tower on the threat's path is further by march than the tower.
            pull_ok = 1.0 if x < d_tower else 0.0
            lo = threat.r_atk + P1_LO_PAD
            # L59 PATH-based P1 (HANDOFF 5cs.29 (b)(1)): the band is on `d_path` = the distance from
            # the building's hitbox edge to the FORWARD part of the threat's march path (current
            # position -> its lane's bridge if the river is between -> the own alive tower it would
            # target, or its locked target) -- `_project` clamps to the polyline, so nothing behind
            # the threat counts. The pros pre-place while the threat is still outside the snapshot
            # band; the path band fires as soon as the tile sits beside the lane it will walk.
            if len(path) >= 2:
                d_path = max(0.0, _project(board, path, px, py)[0] - r_body)
            else:
                d_path = x
            out["d_path"] = d_path
            out["p1_pull_band"] = band(d_path, lo, threat.r_sight, P1_W) * pull_ok
            out["p1_snapshot"] = band(x, lo, threat.r_sight, P1_W) * pull_ok
            if threat.r_atk <= MELEE_REACH_MAX:            # dropped on top of a MELEE wincon
                # CHOICE (brief): "unchanged in form but measured on d_path". NOTE this also fires for
                # a building placed IN the lane ahead of the threat (d_path ~ 0 while the threat is
                # still far) -- the snapshot version is kept beside it for the gate to compare.
                out["p1_close_penalty"] = -clip01((lo - d_path) / lo) if lo > 0 else 0.0
                out["p1_close_snapshot"] = -clip01((lo - x) / lo) if lo > 0 else 0.0
''')

# 4. P7 swarm exclusion
rep('''        hp_c = float(placement.get("hp", 0.0) or 0.0)
        if (is_troop and 0.0 < hp_c <= FRAGILE_HP_MAX and not threat.building_only
                and (threat.splash or threat.r_atk <= MELEE_REACH_MAX)):
            out["p7_fragility"] = -band(gap(px, py, threat, board.tiles), 0.0, threat.r_atk, P7_W)
''', '''        hp_c = float(placement.get("hp", 0.0) or 0.0)
        is_swarm = SWARM_ROLE in tuple(placement.get("roles", ()) or ())
        # L59: a SWARM card (skeletons; KB role "swarm") is never charged -- the pros drop skeletons ON
        # the threat to surround it (gate.md 1d.4: 0.1% for / 7.6% against). Kept for ranged low-HP
        # counters (ice wizard).
        if (is_troop and not is_swarm and 0.0 < hp_c <= FRAGILE_HP_MAX and not threat.building_only
                and (threat.splash or threat.r_atk <= MELEE_REACH_MAX)):
            out["p7_fragility"] = -band(gap(px, py, threat, board.tiles), 0.0, threat.r_atk, P7_W)
''')

# 5. P2 buildings only
rep('''    out["p2_cover"] = _p2_cover(board, eng_pt[0], eng_pt[1], r_body)
''', '''    # L59: P2 is a BUILDING term only (gate.md 1d.1/1d.2: on troops it ranks the pros' river-bank
    # skeletons below the behind-the-king cell, on spells the enemy-half cast point has cover 0).
    # The intercept-point cover is still computed for the P3 kite check below, not reported.
    out["p2_cover"] = _p2_cover(board, eng_pt[0], eng_pt[1], r_body) if is_building else 0.0
''')
rep('''        out["p2_cover"] = _p2_cover(board, px, py, 0.0)     # the pull / blast centre's cover
''', '''        out["p2_cover"] = 0.0     # L59: the pull / blast centre's cover is NOT a spell term (gate 1d.1)
''')

# 6. timing extras
rep('''            t_resp = deploy_time + travel
            out["p5_timing"] = band(t_resp, t_cross + P5_LO_PAD, t_hit + P5_HI_PAD, P5_W)
''', '''            t_resp = deploy_time + travel
            out["p5_timing"] = band(t_resp, t_cross + P5_LO_PAD, t_hit + P5_HI_PAD, P5_W)
            # L59 env hooks: the window edges the sim env's timing gate reads (not in TERM_KEYS)
            out["t_cross"], out["t_hit"], out["t_resp"] = t_cross, t_hit, t_resp
''')

# 7. helpers
rep('''def tornado_away(board: Board, u: BoardObj, cx: float, cy: float, towers: Sequence[BoardObj]) -> float:
''', '''def placement_credit(terms: Dict[str, float], kind: str, p7_enabled: bool = False) -> float:
    """The PLACEMENT part of the graded reward (L59 / HANDOFF 5cs.29), per kind:
      building: min(CAP, p1_pull_band * (0.5 + 0.5 * p2_cover) + p6_siege) + max(FLOOR, p1_close_penalty)
      troop:    p3_intercept (+ max(FLOOR, p7_fragility) only when `p7_enabled`)
      spell:    0.0 (P4 is LOGGED only in run 1; the spell ledger is untouched)
    Range: [CREDIT_FLOOR, CREDIT_CAP] = [-0.3, 1.0] for every kind. The cap exists because a placement
    can be BOTH a pull (P1 > 0) and an offensive bow (P6 > 0): an X-Bow on the bank vs a bridge hog."""
    def g(k):
        return float(terms.get(k, 0.0) or 0.0)
    kind = str(kind)
    if kind == "building":
        pos = g("p1_pull_band") * (0.5 + 0.5 * g("p2_cover")) + g("p6_siege")
        return min(CREDIT_CAP, max(0.0, pos)) + max(CREDIT_FLOOR, min(0.0, g("p1_close_penalty")))
    if kind == "troop":
        pos = min(CREDIT_CAP, max(0.0, g("p3_intercept")))
        if p7_enabled:
            pos += max(CREDIT_FLOOR, min(0.0, g("p7_fragility")))
        return pos
    return 0.0


def timing_credit(terms: Dict[str, float]) -> float:
    """The play-TIMING part: P5 (a bridge-block case is already 1.0 inside P5, doc 7.4)."""
    return min(1.0, max(0.0, float(terms.get("p5_timing", 0.0) or 0.0)))


def tornado_away(board: Board, u: BoardObj, cx: float, cy: float, towers: Sequence[BoardObj]) -> float:
''')

# 8. nonzero_terms
rep('''        if isinstance(v, (int, float)) and abs(float(v)) > 1e-9 and k != "d_threat":
''', '''        if isinstance(v, (int, float)) and abs(float(v)) > 1e-9 and k not in ("d_threat", "d_path"):
''')

# 9. docstring
rep('''    side, 0 beyond. Every credit is 0..1 and peaks in the band; the only negative terms are
    `p1_close_penalty` and `p7_fragility`, both bounded in [-1, 0];''',
    '''    side, 0 beyond. Every credit is 0..1 and peaks in the band; the only negative terms are
    `p1_close_penalty` (+ its snapshot twin) and `p7_fragility`, all bounded in [-1, 0];''')

p.write_text(s, encoding="utf-8")
print("edited")

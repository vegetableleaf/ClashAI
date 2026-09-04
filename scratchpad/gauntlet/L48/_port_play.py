p='hogeq/src/clashrl/play.py'
s=open(p,encoding='utf-8').read()
def rep(old,new):
    global s
    assert s.count(old)==1,(old[:70],s.count(old)); s=s.replace(old,new)

rep('''import random
import signal
''','''import math
import random
import signal
''')
rep('''from .reward import TILE as _TILE
''','''from .reward import log_corridor_cell                # 2026-09-04: Log corridor assist (icebow parity, HANDOFF 5cs.18)
from .reward import lead_point, lead_velocity   # 2026-09-03: cast-delay lead for log + rocket
from .reward import TILE as _TILE
''')
# Log ids + corridor geometry + the flyer set, right before the ability block
rep('''    _ability_id = (vision.deck_keys.index(vision.ability_key)
                   if getattr(vision, "ability_key", None) in vision.deck_keys else -1)
''','''    # LOG AIM ASSIST (icebow parity, 2026-09-04). Every other card with geometry that matters
    # (X-Bow, Tesla, rocket) had an assist in this loop and the Log had none -- it was ported into
    # the train-rl env (5bc) but never into play.py, so a pure-play session rolled it wherever the
    # raw cell landed. Distances are the LIVE screen-space normalised ones, not the sim's tiles.
    _log_ids = {i for i, key in enumerate(vision.deck_keys)
                if (key[:-4] if key.endswith("_evo") else key) == "the_log"}
    _log_half_w = float(cfg.get("env", "log_half_width", default=0.064))   # 2.2 tiles of corridor
    _log_roll = float(cfg.get("env", "log_roll_len", default=0.28))        # 9.6 tiles of travel

    class _AirSet:
        """Which detected classes FLY, answered from the card KB rather than a hand-kept list --
        a hardcoded roster silently stops being true the next time a card is released."""

        def __init__(self, db):
            self._db, self._memo = db, {}

        def __contains__(self, base):
            if base is None:
                return False
            hit = self._memo.get(base)
            if hit is None:
                hit = self._memo[base] = bool(card_threat.profile(self._db, base).flying)
            return hit

    _ability_id = (vision.deck_keys.index(vision.ability_key)
                   if getattr(vision, "ability_key", None) in vision.deck_keys else -1)
''')
rep('''    from .cards import CardDB
    _db = CardDB(cfg)
''','''    from .cards import CardDB
    _db = CardDB(cfg)
    _AIR_BASES = _AirSet(_db)          # the Log rolls UNDER flyers -- never aim it at one
''')
rep('''    _opp_elx = OpponentElixirEstimator(_db)     # live estimate from mirrored spend accounting
''','''    _opp_elx = OpponentElixirEstimator(_db)     # live estimate from mirrored spend accounting
    # SIM/LIVE PARITY of opponent-memory slot 5 (HANDOFF 5cr.8, owner ruling 23:4x): the sim wrote OUR elixir into this
    # slot during training (sim/env.py mem[5] = eng.elixir[0]/10) while live wrote the opponent-elixir ESTIMATE (mean
    # 0.035 in a live session) -- the trained gate read "no elixir" and waited. Same switch as train-rl's env:
    # 'opp_estimate' (legacy, default) or 'own_elixir' (what the checkpoint was trained on).
    _mem5_source = str(cfg.get("env", "opp_mem_slot5", default="opp_estimate"))
    if _mem5_source not in ("opp_estimate", "own_elixir"):
        raise ValueError("env.opp_mem_slot5 must be 'opp_estimate' or 'own_elixir', got %r" % _mem5_source)
    print("[play] opp-memory slot 5 source: %s" % _mem5_source)
''')
rep('''    _rocket_rate = float(cfg.get("env", "rocket_travel_rate", default=2.2))
''','''    _rocket_rate = float(cfg.get("env", "rocket_travel_rate", default=2.2))
    _rocket_speed = float(cfg.get("env", "rocket_speed_tiles", default=14.0))
    _spell_eval = float(cfg.get("env", "spell_eval_time", default=4.0))
    # CAST DELAY (owner, 2026-09-03): ~1 s from tap to the spell existing on the board. This path
    # led rockets with the DEPRECATED normalised-rate flight and no cast delay, and never led the
    # Log at all -- the corridor was drawn through the push where it STOOD, 1-2 tiles ahead of
    # where it would be when the log appeared. Same fix as env.py: lead every target by
    # velocity x (cast delay [+ rocket flight]) before aiming, KB walking speed for young tracks.
    _cast_delay = float(cfg.get("env", "spell_cast_delay_s", default=1.0))
''')
rep('''        mem[5] = _opp_elx.update(float(my_elixir), dets, now)                 # normalized opponent-elixir estimate
''','''        _est = _opp_elx.update(float(my_elixir), dets, now)                   # normalized opponent-elixir estimate
        mem[5] = _est if _mem5_source == "opp_estimate" else float(my_elixir) / 10.0
''')
rep('''            if tgt is None and card_id in _rocket_ids:     # no tower/pump snap -> LEAD the tracked troops
                impact = _rocket_base + _rocket_rate * float(np.hypot(cx - _rocket_org[0], cy - _rocket_org[1]))
                tracks = (_ploop.enemy_tracks(time.time()) if _ploop is not None and _ploop.running
                          else _team_tracker.enemy_tracks(time.time()))
                tgt = spell_intercept_cell(cx, cy, tracks, impact, _lead_radius, actions)
''','''            if tgt is None and card_id in _rocket_ids:     # no tower/pump snap -> LEAD the tracked troops
                # cast delay + TRUE tile-distance flight (env.py's _impact_time, same clamp)
                d_tiles = float(np.hypot((cx - _rocket_org[0]) * 18.0, (cy - _rocket_org[1]) * 32.0))
                impact = min(max(max(_rocket_base, _cast_delay) + d_tiles / _rocket_speed, 0.6), _spell_eval)
                tracks = (_ploop.enemy_tracks(time.time(), True) if _ploop is not None and _ploop.running
                          else _team_tracker.enemy_tracks(time.time(), True))
                _lp = lead_point(cx, cy, tracks, impact, _lead_radius * 18.0, _db)
                tgt = actions.cell_at(_lp[0], _lp[1]) if _lp is not None else None
''')
rep('''            depth = xbow_offense_depth_cell(cx, cy, xbow_defense_front, _deploy_top, actions)
            if depth is not None:
                cell = depth
        elif card_id in tesla_ids and _wincon["xy"] is not None:
''','''            depth = xbow_offense_depth_cell(cx, cy, xbow_defense_front, _deploy_top, actions)
            if depth is not None:
                cell = depth
        elif card_id in _log_ids:
            # THE LOG IS A CORRIDOR, NOT A BLAST: line it up with the push instead of beside it.
            gx, gy = cell % gw, cell // gw
            cx, cy = actions.cell_center(gx, gy)
            _tk = (_ploop.enemy_tracks(time.time(), True) if _ploop is not None and _ploop.running
                   else _team_tracker.enemy_tracks(time.time(), True))
            # where each body will be when the log APPEARS, not where it is at the tap
            _tk = [(t[0] + vx * _cast_delay, t[1] + vy * _cast_delay) + tuple(t[2:])
                   for t in _tk for vx, vy in (lead_velocity(t, _db),)]
            aim = log_corridor_cell(cx, cy, _tk, actions, _log_half_w, _log_roll, _AIR_BASES)
            if aim is not None:
                cell = aim
        elif card_id in tesla_ids and _wincon["xy"] is not None:
''')
open(p,'w',encoding='utf-8').write(s); print("play patched")

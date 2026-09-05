"""L59: a scripted scenario to exercise the BUILDING branch under arm G -- an enemy hog sent down the
left lane, our Tesla dropped at the pros' modal tile (9,21) at several moments; prints the terms, the
gate and the credit, and where the env's quiet-board gate (identity_front_y) starts letting geometry pay."""
import sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
from test_geometry_wiring import make_cfg
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import build_spec

def run(enabled, wait_steps, tile=(9.0, 21.0), card="tesla"):
    cfg = make_cfg(enabled)
    cfg.data["sim"]["opponent"] = "idle" if "opponent" in cfg.data.get("sim", {}) else cfg.data["sim"].get("opponent")
    env = SimMatchEnv(cfg, seed=3); env.reset()
    class _Idle:                       # a silent opponent so the only enemy body is OUR scripted hog
        def act(self, eng): pass
    env.opponent = _Idle()
    # bank elixir first: hold ~8 s
    for _ in range(8):
        env.step((0, 0, 0))
    hog = build_spec(env.db, "hog_rider", 11)
    env.eng.elixir[1] = 10.0
    ok = env.eng.deploy(1, hog, 3.5 / 18.0, 8.0 / 32.0)      # global coords (no mirroring): tile y=8 = the ENEMY half, 8 tiles short of the river
    assert ok, "hog deploy failed"
    for _ in range(wait_steps):
        env.step((0, 0, 0))
    hogs = [u for u in env.eng.units if u.team == 1 and u.spec.base == "hog_rider" and u.hp > 0]
    hy = hogs[0].y if hogs else None
    cid = next(i for i, k in enumerate(env.deck_keys) if k.split("-")[0].replace("_", "") in (card.replace("_", ""),) or k.startswith(card))
    gx, gy = env.actions.coords_to_grid(tile[0] / 18.0, tile[1] / 32.0)
    cell = int(gy) * env.gw + int(gx)
    in_hand = cid in env._hand_ids()
    tid = env._threat_id_true
    _o, r, done, _ = env.step((1, cid, cell))
    c = env._geo_cache
    t = c[1] if c is not None else {}
    tr = env.rw_stats.match["threat_response"].total if "threat_response" in env.rw_stats.match else 0.0
    print(f"enabled={enabled} wait={wait_steps:2d} t={env.eng.t:5.1f} hog tile y={(hy*32 if hy is not None else -1):5.1f} tid0={float(tid[0]) if tid is not None else -1:.0f} "
          f"in_hand={in_hand} threat={t.get('threat_base','-'):10s} src={'module' if t.get('threat_module') else 'env'} "
          f"p1={t.get('p1_pull_band',0):.2f} snap={t.get('p1_snapshot',0):.2f} p1c={t.get('p1_close_penalty',0):+.2f} p2={t.get('p2_cover',0):.2f} p5={t.get('p5_timing',0):.2f} "
          f"gate={t.get('gate',0):.2f} t_resp={t.get('t_resp',-1):.1f} t_cross={t.get('t_cross',-1):.1f} t_hit={t.get('t_hit',-1):.1f} credit={t.get('credit',0):+.3f} step_r={r:+.3f}")

for w in (0, 2, 4, 5, 6, 7, 8, 9, 10, 12, 14):
    run(True, w)
print("-- disabled (old binary credit) --")
for w in (0, 4, 6, 8, 10, 12):
    run(False, w)

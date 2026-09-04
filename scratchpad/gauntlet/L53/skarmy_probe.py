"""L53 sim-only probe: an UNANSWERED evo Skeleton Army at the bridge vs the L11 towers (and vs skeleton_army for
comparison). Records per 0.5 s: tower HP, live skeletons, ghosts, Gerry hp/shield/position, and whether the tower
ever targets Gerry. Sim only: says what OUR sim does, not what the real game does."""
import sys, json
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot")
sys.path.insert(0, str(ROOT / "scratchpad/gauntlet/L51"))
import sim_replay_drive as D
from clashrl.sim.engine import SimEngine
from clashrl.config import Config

def run(card, team=0, x=0.194, y=None, defender=None, patches=(), seconds=40.0, quiet=False):
    D.PATCHES.clear(); D.PATCHES.update(patches)
    cfg = Config.load(D.ICEBOW / "config" / "config.yaml"); cfg.data["sim"]["my_tower_troop"] = "princess"
    db = D.shared_db(cfg)
    eng = D.make_engine(cfg, db, 11, seed=424242)
    eng.elixir[0] = eng.elixir[1] = 10.0
    foe = 1 - team
    tw = eng.towers[foe]
    if y is None:
        # just on the attacker's side of the river, left lane
        y = 0.53 if team == 0 else 0.47
    spec = D.build_spec(db, card, 11)
    ok = eng.deploy(team, spec, x, y)
    if defender:
        dspec = D.build_spec(db, defender, 11)
        # defender dropped in front of the foe's left princess tower
        px, py = tw[0].x, tw[0].y
        eng.deploy(foe, dspec, px, py + (0.12 if team == 0 else -0.12))
    rows = []
    gerry_hit_by_tower = None; gerry_death = None; first_tower_dmg = None
    t_next = 0.0
    while eng.t < seconds and not eng.done:
        eng.advance(0.1)
        g = [u for u in eng.units if u.spec.key == "skarmy_general" and u.hp > 0]
        gh = [u for u in eng.units if u.team == team and getattr(u, "ghost", False) and u.hp > 0]
        sk = [u for u in eng.units if u.team == team and u.spec.key != "skarmy_general" and not getattr(u, "ghost", False) and u.hp > 0]
        if g and (g[0].hp < 81 or g[0].shield_left < g[0].spec.shield_hp) and gerry_hit_by_tower is None:
            gerry_hit_by_tower = round(eng.t, 1)
        if not g and gerry_death is None and card == "skeleton_army_evo":
            gerry_death = round(eng.t, 1)
        if first_tower_dmg is None and any(t.hp < t.max_hp for t in tw):
            first_tower_dmg = round(eng.t, 1)
        if eng.t >= t_next - 1e-9:
            t_next += 2.0
            rows.append({"t": round(eng.t, 1), "towers": [round(t.hp) for t in tw], "skel": len(sk), "ghost": len(gh),
                         "gerry": ([round(g[0].hp), round(g[0].shield_left), round(g[0].x * 18, 1), round(g[0].y * 32, 1)] if g else None),
                         "front": (round(min(u.y for u in sk + gh) * 32, 1) if (sk + gh) and team == 0 else None)})
    res = {"card": card, "defender": defender, "patches": sorted(patches), "ok": ok, "tower_xy": [(round(t.x * 18, 1), round(t.y * 32, 1)) for t in tw],
           "first_tower_dmg_t": first_tower_dmg, "gerry_first_damaged_t": gerry_hit_by_tower, "gerry_death_t": gerry_death,
           "end_t": round(eng.t, 1), "towers_end": [round(t.hp) for t in tw], "tower_dmg_total": round(sum(t.max_hp - t.hp for t in tw)),
           "rows": rows}
    if not quiet:
        print(f"== {card} team {team} defender={defender} patches={sorted(patches)} deploy_ok={ok} towers@{res['tower_xy']}")
        print(f"   first tower dmg {first_tower_dmg}s; Gerry first damaged {gerry_hit_by_tower}s, dies {gerry_death}s; end {res['end_t']}s towers {res['towers_end']} total dmg {res['tower_dmg_total']}")
        for r in rows: print("   ", r)
    return res

if __name__ == "__main__":
    out = []
    out.append(run("skeleton_army_evo"))
    out.append(run("skeleton_army"))
    out.append(run("skeleton_army_evo", defender="knight"))
    out.append(run("skeleton_army", defender="knight"))
    out.append(run("skeleton_army_evo", defender="ice_wizard"))
    out.append(run("skeleton_army_evo", team=1))
    (ROOT / "scratchpad/gauntlet/L53/skarmy_probe.json").write_text(json.dumps(out, indent=1))

if __name__ == "__main__" and "--shadow" in sys.argv:
    out = []
    for dfn in (None, "knight"):
        out.append(run("skeleton_army_evo", defender=dfn, patches=("shadow_speed",)))
    (ROOT / "scratchpad/gauntlet/L53/skarmy_probe_shadow.json").write_text(json.dumps(out, indent=1))

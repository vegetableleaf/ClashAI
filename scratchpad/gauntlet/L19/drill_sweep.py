"""L19: do the existing aggro drills GRADE aggro? Sweep every legal knight cell x 3 delays on the
`knight_guards_the_bow` board and cross-tab the drill's own verdict (bow alive at 20 s) against the
oracle's ground truth (did the knight take the Valkyrie's lock before she hit the bow). Same for
`nado_the_sneaky_lock`: every tornado cell at t=1.2 (+ reference knight at 2.4), drill verdict (enemy
tower lost 150 hp by 22 s) vs ground truth (the bow re-locked onto a tower after the pull)."""
import sys, json, time, collections
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, Tower, build_spec
from clashrl.sim.aggro_oracle import AggroOracle, TICK

env = SimMatchEnv(Config.load())

def board(*spawns):
    env.reset(); e = env.eng
    e.units.clear(); e.spells.clear(); e.projectiles.clear()
    out = []
    for key, team, x, y in spawns:
        s = build_spec(e.db, key, 11); u = Unit(spec=s, team=team, x=x, y=y, hp=s.hp)
        e.units.append(u); out.append(u)
    e.advance(0.1)
    return e, out

XS = [round(0.05 * i, 2) for i in range(1, 20)]
def cells(y_lo, y_hi):
    return [(x, round(0.05 * j, 2)) for j in range(int(y_lo * 20), int(y_hi * 20) + 1) for x in XS]

# ---------------- knight_guards_the_bow ----------------
e, (xb, vk) = board(("x_bow", 0, 0.26, 0.56), ("valkyrie", 1, 0.24, 0.42))
o = AggroOracle(e)
rows = []; t0 = time.time()
for delay in (0.6, 1.2, 1.8, 2.4):
    for (x, y) in cells(0.50, 0.95):
        f, back, fwd = o._fork()
        fx, fv = fwd[id(xb)], fwd[id(vk)]
        o._advance(f, delay)
        kn = o._place(f, 0, "knight", x, y, 11)
        took = False; hit_before = fv.last_unit_hit_t >= 0.0 and fx.hp < xb.hp   # already hit before placement
        first_hit = None; t_end = f.t + (20.0 - delay)
        while f.t < t_end and not f.done:
            f.advance(TICK)
            if kn is not None and fv.hp > 0 and fv.target is kn and first_hit is None:
                took = True
            if first_hit is None and fx.hp > 0 and fv.target is fx and fv.locked:
                first_hit = f.t
        bow_alive = fx.hp > 0
        rows.append(dict(delay=delay, x=x, y=y, placed=kn is not None, took_lock=took,
                         bow_alive=bow_alive, valk_dead=fv.hp <= 0, knight_alive=(kn is not None and kn.hp > 0)))
print(f"knight sweep: {len(rows)} forks in {time.time()-t0:.1f}s")
ct = collections.Counter((r["delay"], r["took_lock"], r["bow_alive"]) for r in rows if r["placed"])
print("delay | took_lock | drill PASS(bow alive) | n")
for k in sorted(ct): print("  ", k, ct[k])
by = collections.Counter((r["took_lock"], r["bow_alive"]) for r in rows if r["placed"])
print("all delays: took&pass", by[(True, True)], " took&fail", by[(True, False)],
      " NOTtook&pass", by[(False, True)], " NOTtook&fail", by[(False, False)])
unplaced = sum(1 for r in rows if not r["placed"]); print("unplaced (deploy refused):", unplaced)
# which cells take the lock at delay 0.6 (the reference timing)
took06 = sorted((r["x"], r["y"]) for r in rows if r["delay"] == 0.6 and r["took_lock"])
print("cells that take the lock at delay 0.6:", len(took06), took06[:40])
pass_not_took = collections.Counter(r["y"] for r in rows if r["placed"] and r["bow_alive"] and not r["took_lock"])
print("PASS-without-lock by y:", sorted(pass_not_took.items()))

# ---------------- nado_the_sneaky_lock ----------------
e, (xb, kn1) = board(("x_bow", 0, 0.26, 0.53), ("knight", 1, 0.26, 0.47))
o = AggroOracle(e)
tw_hp0 = sum(t.hp for t in e.towers[1])
rows2 = []; t0 = time.time()
for with_knight in (False, True):
    for (x, y) in cells(0.20, 0.95):
        f, back, fwd = o._fork(); fx, fk = fwd[id(xb)], fwd[id(kn1)]
        o._advance(f, 1.2)
        o._place(f, 0, "tornado", x, y, 11)
        relocked = False; our_kn = None
        while f.t < 22.0 and not f.done:
            f.advance(TICK)
            if with_knight and our_kn is None and f.t >= 2.4:
                our_kn = o._place(f, 0, "knight", 0.26, 0.56, 11)
            if fx.hp > 0 and isinstance(fx.target, Tower):
                relocked = True
        lost = tw_hp0 - sum(t.hp for t in f.towers[1])
        rows2.append(dict(knight=with_knight, x=x, y=y, relocked=relocked, drill_pass=lost >= 150.0,
                          bow_alive=fx.hp > 0, tower_lost=round(lost)))
print(f"\nnado sweep: {len(rows2)} forks in {time.time()-t0:.1f}s")
for wk in (False, True):
    c = collections.Counter((r["relocked"], r["drill_pass"]) for r in rows2 if r["knight"] == wk)
    print(f"knight={wk}: relocked&pass {c[(True,True)]}  relocked&fail {c[(True,False)]}  "
          f"NOTrelocked&pass {c[(False,True)]}  NOTrelocked&fail {c[(False,False)]}")
    ok = sorted((r["x"], r["y"]) for r in rows2 if r["knight"] == wk and r["relocked"])
    print("   relock cells:", len(ok), ok[:30])
json.dump({"knight_guards_the_bow": rows, "nado_the_sneaky_lock": rows2},
          open("../scratchpad/gauntlet/L19/drill_sweep.json", "w"))

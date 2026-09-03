"""LOCK-AWARE AGREEMENT probe (GAUNTLET L27, extends L17's aggro_agreement.py). Grades THREE reads of
`interactions.predict_targets` against the engine's `Unit.target` on the same unit-samples:
  memoryless -- hints=None (what every shipped checkpoint was trained on; L17 baseline 74.2% all)
  truth      -- hints from the engine (`view.interaction_state(..., hints=True)`: Unit.locked/target,
                deploy_left): the UPPER BOUND, what the sim obs would carry with
                observation.lock_aware_targets on
  proxy      -- hints a LIVE tracker could produce with NO engine access: engaged = the unit did not move
                over the last sample (< STILL tiles) AND its nearest attackable foe / tower is inside
                attack_range + slack; deploying = first seen < deploy_time ago. Assumes a perfect
                tracker (identity across frames), which live does not have today -- so this is the
                ceiling of the live proxy, not its live value.
usage (from icebow/): PYTHONHASHSEED=0 .venv/Scripts/python.exe ../scratchpad/gauntlet/L27/lockaware_agreement.py <ckpt> <matches> <seeds,csv> <out.json>"""
import collections, json, os, pathlib, sys, time
_ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(_ROOT / "src")); os.chdir(_ROOT)
import torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS, view
from clashrl.sim.engine import Unit, Tower
from clashrl import interactions, card_threat

DT = 0.6            # agent_dt (config sim.agent_dt)
DEPLOY_MARGIN = float(os.environ.get("DEPLOY_MARGIN", "0.5"))   # in agent steps
STILL = 0.15        # tiles moved per sample below which a unit counts as STATIONARY (agent_dt 0.6 s)
SLACK = 1.0         # tiles added to attack range to stand in for the target's hitbox radius
MODES = ("memoryless", "truth", "proxy")


def proxy_hints(units, my_t, en_t, alive, db, hist, t_now):
    """Live-style hints from position history only (see module doc)."""
    hs = []
    for i, (u, (team, base, x, y)) in enumerate(zip(alive, units)):
        h = hist.get(id(u))
        p = card_threat.profile(db, base)
        if h is None:                                     # a NEW track is a unit that just landed
            hs.append(interactions.Hint(deploying=True)); continue
        first_t, px, py, _keep = h
        spec_deploy = float(getattr(u.spec, "deploy_time", 1.0))
        # first_t is the first SAMPLE, up to one agent step after the real drop: split the difference
        deploying = (t_now - first_t) < spec_deploy - DEPLOY_MARGIN * DT
        engaged = None
        moved = interactions._tdist(x, y, px, py)
        if not deploying and moved < STILL and p.kind != "building" and not p.spell:
            reach = float(db.attack_range_tiles(base)) + SLACK
            foe = "enemy" if team == "mine" else "mine"
            towers = en_t if team == "mine" else my_t
            best = None
            for j, (ft, fb, fx, fy) in enumerate(units):
                if ft != foe:
                    continue
                fp = card_threat.profile(db, fb)
                if fp.spell or (fp.flying and not p.attacks_air):
                    continue
                if p.building_targeting and fp.kind != "building":
                    continue
                d = interactions._tdist(x, y, fx, fy)
                if d <= reach and (best is None or d < best[2]):
                    best = ("unit", j, d)
            for k, (tx, ty, al) in enumerate(towers):
                d = interactions._tdist(x, y, tx, ty)
                if al and d <= reach + 1.0 and (best is None or d < best[2]):   # towers are big bodies
                    best = ("tower", k, d)
            if best is not None:
                engaged = (best[0], best[1])
        hs.append(interactions.Hint(engaged=engaged, deploying=deploying))
    return hs


def run(ckpt, matches, seed):
    cfg = Config.load(); env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    db = env.db
    agree = {m: collections.Counter() for m in MODES}; total = collections.Counter()
    conf = {m: collections.Counter() for m in MODES}
    hist = {}                                            # id(u) -> (first_t, x, y at last sample)
    done = 0; samples = 0
    while done < matches:
        act, _ = sr.act(0)
        _o, _r, d, info = env.step(act)
        e = env.eng
        if d:
            done += 1; env.reset(); hist.clear(); continue
        units, my_t, en_t, th = view.interaction_state(e, 0, None, hints=True)
        alive = [u for u in e.units if u.hp > 0 and getattr(u.spec, "base", None) is not None]
        assert len(alive) == len(units), (len(alive), len(units))
        ph = proxy_hints(units, my_t, en_t, alive, db, hist, e.t)
        preds = {"memoryless": interactions.predict_targets(units, my_t, en_t, db),
                 "truth": interactions.predict_targets(units, my_t, en_t, db, th),
                 "proxy": interactions.predict_targets(units, my_t, en_t, db, ph)}
        for i, u in enumerate(alive):
            if u.spec.kind == "spell":
                continue
            t = getattr(u, "target", None)
            ek, eref = ("unit", t) if isinstance(t, Unit) else ("tower", t) if isinstance(t, Tower) else (None, None)
            state = ("deploying" if getattr(u, "deploy_left", 0.0) > 0.0 else
                     "building" if u.spec.kind == "building" else
                     "bld_only" if u.spec.building_only else
                     "locked" if u.locked else "walking")
            key = (u.team, state)
            total[key] += 1; samples += 1
            for m in MODES:
                pk, pi, _pd = preds[m][i]
                pref = alive[pi] if pk == "unit" else e.towers[1 - u.team][pi] if pk == "tower" else None
                ok = (pk == ek) and (pref is eref)
                if ok:
                    agree[m][key] += 1
                conf[m][(state, pk or "none", ek or "none")] += 1
        # position history for the proxy (after grading: the proxy reads the PREVIOUS sample)
        for u, (_, _, x, y) in zip(alive, units):
            h = hist.get(id(u))
            hist[id(u)] = (h[0] if h else e.t, x, y, u)     # keep a ref: no id() reuse after death
    rate = lambda m, k: (agree[m][k], total[k], round(100.0 * agree[m][k] / max(1, total[k]), 1))
    return {"ckpt": str(ckpt), "matches": matches, "seed": seed, "samples": samples,
            "agree_by_state": {m: {f"team{k[0]}/{k[1]}": rate(m, k) for k in sorted(total)} for m in MODES},
            "confusion": {m: {f"{s}|pred={p}|eng={g}": n for (s, p, g), n in sorted(conf[m].items())} for m in MODES}}


def summarise(out):
    L = [f"== predict_targets vs engine Unit.target, {sum(r['samples'] for r in out)} unit-samples, "
         f"{sum(r['matches'] for r in out)} matches, {len(out)} seeds -- agree % per mode"]
    tot = collections.Counter(); ag = {m: collections.Counter() for m in MODES}
    for r in out:
        for m in MODES:
            for k, (a, n, _) in r["agree_by_state"][m].items():
                ag[m][k] += a
                if m == MODES[0]:
                    tot[k] += n
    L.append(f"   {'state':<18} {'n':>6}  " + "  ".join(f"{m:>10}" for m in MODES) + "   per-seed (truth | proxy)")
    for k in sorted(tot):
        ps = " ".join(f"{r['agree_by_state']['truth'][k][2]:.1f}/{r['agree_by_state']['proxy'][k][2]:.1f}" for r in out)
        L.append(f"   {k:<18} {tot[k]:>6}  " + "  ".join(f"{100*ag[m][k]/max(1,tot[k]):>9.1f}%" for m in MODES) + f"   {ps}")
    N = sum(tot.values())
    L.append(f"   {'ALL':<18} {N:>6}  " + "  ".join(f"{100*sum(ag[m].values())/max(1,N):>9.1f}%" for m in MODES))
    for m in MODES:
        c = collections.Counter()
        for r in out:
            for k, n in r["confusion"][m].items():
                c[k] += n
        L.append(f"   {m} top disagreements: " + ", ".join(
            f"{k} {n}" for k, n in sorted(c.items(), key=lambda kv: -kv[1]) if k.split("|")[1][5:] != k.split("|")[2][4:])[:400])
    return "\n".join(L)


if __name__ == "__main__":
    ck = sys.argv[1]; n = int(sys.argv[2]); seeds = [int(s) for s in sys.argv[3].split(",")]
    out = []
    for s in seeds:
        t0 = time.time(); r = run(ck, n, s); r["wall_s"] = round(time.time() - t0, 1); out.append(r)
        print(f"seed {s}: samples {r['samples']} wall {r['wall_s']}s", flush=True)
    pathlib.Path(sys.argv[4]).write_text(json.dumps(out, indent=1))
    txt = summarise(out); print(txt); pathlib.Path(sys.argv[4]).with_suffix(".txt").write_text(txt)

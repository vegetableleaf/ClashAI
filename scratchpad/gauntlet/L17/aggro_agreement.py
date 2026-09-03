"""AGGRO AGREEMENT probe (GAUNTLET L17). The policy's ONLY aggro concept is `interactions.predict_targets`
(memoryless nearest-target rules) painted into the predictive canvas + the 12-dim interaction vector.
The engine's ground truth is `Unit.target` (sticky lock, hysteresis, resets). This measures, over real
sim boards from a checkpoint's own play, how often the two AGREE per unit-sample, split by the states
where they can differ. Also: how sticky the engine's target actually is (changes per unit-second) and
how often a unit's target change was NOT a death of the old target (i.e. a re-lock / reset / steal).
usage (from icebow/): PYTHONHASHSEED=0 .venv/Scripts/python.exe ../scratchpad/gauntlet/L17/aggro_agreement.py <ckpt> <matches> <seeds,csv> <out.json>"""
import collections, json, os, pathlib, sys, time
_ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(_ROOT / "src")); os.chdir(_ROOT)
import torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim.engine import Unit, Tower
from clashrl import interactions


def run(ckpt, matches, seed):
    cfg = Config.load(); env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    db = env.db
    agree = collections.Counter(); total = collections.Counter(); confusion = collections.Counter()
    disagreements = collections.Counter()
    prev_target = {}                                     # id(u) -> (target obj, t)
    changes = collections.Counter(); unit_seconds = 0.0; last_t = None
    done = 0; samples = 0
    while done < matches:
        act, _ = sr.act(0)
        _o, _r, d, info = env.step(act)
        e = env.eng
        if d:
            done += 1; env.reset(); prev_target.clear(); last_t = None; continue
        dt = (e.t - last_t) if last_t is not None else 0.0
        last_t = e.t
        alive = [u for u in e.units if u.hp > 0 and getattr(u.spec, "base", None) is not None
                 and u.spec.kind != "spell"]
        units = [("mine" if u.team == 0 else "enemy", u.spec.base, u.x, u.y) for u in alive]
        tw = lambda side: [(t.x, t.y, bool(t.alive)) for t in e.towers[side][:3]]
        pred = interactions.predict_targets(units, tw(0), tw(1), db)
        for u, (pk, pi, _pd) in zip(alive, pred):
            t = getattr(u, "target", None)
            if isinstance(t, Unit):
                ek = "unit"; eref = t
            elif isinstance(t, Tower):
                ek = "tower"; eref = t
            else:
                ek = None; eref = None
            if pk == "unit":
                pref = alive[pi]
            elif pk == "tower":
                pref = e.towers[1 - u.team][pi]
            else:
                pref = None
            state = ("deploying" if getattr(u, "deploy_left", 0.0) > 0.0 else
                     "building" if u.spec.kind == "building" else
                     "bld_only" if u.spec.building_only else
                     "locked" if u.locked else "walking")
            key = (u.team, state)
            total[key] += 1; samples += 1
            ok = (pk == ek) and (pref is eref)
            if ok:
                agree[key] += 1
            else:
                disagreements[(state, f"pred={pk} eng={ek}")] += 1
            confusion[(state, pk or "none", ek or "none")] += 1
            # stickiness: engine target changes per unit-second
            if u.spec.kind != "building" and state != "deploying":
                unit_seconds += dt
                pt = prev_target.get(id(u))
                if pt is not None and pt[0] is not eref:
                    old = pt[0]
                    old_dead = (old is None) or (isinstance(old, Unit) and old.hp <= 0) or \
                               (isinstance(old, Tower) and not old.alive)
                    changes["target_change"] += 1
                    changes["old_target_dead" if old_dead else ("old_alive:" + state)] += 1
                prev_target[id(u)] = (eref, e.t)
    rate = lambda k: (agree[k], total[k], round(100.0 * agree[k] / max(1, total[k]), 1))
    return {"ckpt": str(ckpt), "matches": matches, "seed": seed, "samples": samples,
            "agree_by_state": {f"team{k[0]}/{k[1]}": rate(k) for k in sorted(total)},
            "confusion": {f"{s}|pred={p}|eng={g}": n for (s, p, g), n in sorted(confusion.items())},
            "top_disagreements": [(f"{s}|{d}", n) for (s, d), n in disagreements.most_common(10)],
            "stickiness": {**dict(changes), "unit_seconds": round(unit_seconds, 1),
                            "changes_per_unit_min": round(60.0 * changes["target_change"] / max(1e-6, unit_seconds), 2)}}


def summarise(out):
    L = []
    tot = collections.Counter(); ag = collections.Counter(); conf = collections.Counter(); st = collections.Counter()
    for r in out:
        for k, (a, n, _) in r["agree_by_state"].items():
            ag[k] += a; tot[k] += n
        for k, n in r["confusion"].items():
            conf[k] += n
        for k, n in r["stickiness"].items():
            if k != "changes_per_unit_min":
                st[k] += n
    L.append(f"== predict_targets (obs) vs engine Unit.target, {sum(r['samples'] for r in out)} unit-samples, "
             f"{sum(r['matches'] for r in out)} matches, {len(out)} seeds")
    for k in sorted(tot):
        L.append(f"   {k:<18} agree {100*ag[k]/max(1,tot[k]):5.1f}%  (n={tot[k]})")
    A, N = sum(ag.values()), sum(tot.values())
    L.append(f"   ALL                agree {100*A/max(1,N):5.1f}%  (n={N})")
    L.append("   confusion (state | predicted kind | engine kind): " +
             ", ".join(f"{k} {n}" for k, n in sorted(conf.items(), key=lambda kv: -kv[1])[:12]))
    us = st["unit_seconds"]; ch = st["target_change"]
    L.append(f"   engine stickiness: {ch} target changes over {us:.0f} unit-seconds = {60*ch/max(1e-6,us):.2f} per unit-minute; "
             f"old target dead {st['old_target_dead']}, old alive: " +
             ", ".join(f"{k.split(':')[1]} {n}" for k, n in st.items() if k.startswith("old_alive:")))
    return "\n".join(L)


if __name__ == "__main__":
    ck = sys.argv[1]; n = int(sys.argv[2]); seeds = [int(s) for s in sys.argv[3].split(",")]
    out = []
    for s in seeds:
        t0 = time.time(); r = run(ck, n, s); r["wall_s"] = round(time.time() - t0, 1); out.append(r)
        print(f"seed {s}: samples {r['samples']} wall {r['wall_s']}s", flush=True)
    pathlib.Path(sys.argv[4]).write_text(json.dumps(out, indent=1))
    txt = summarise(out); print(txt); pathlib.Path(sys.argv[4]).with_suffix(".txt").write_text(txt)

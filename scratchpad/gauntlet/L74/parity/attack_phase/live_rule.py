"""Live attack-cycle rule around each hit, per attacker and buff state (ATTACK_PHASE_1016.md section 1).

    python live_rule.py P3_FRAMES [P3_FRAMES ...]

Hit instant, two independent markers:
  * load reset (units with LoadTime > 0): the load timer jumps back to LoadTime on the hit tick and then runs -50/tick,
    so the hit tick is EXACT: th = f1.tick - (LoadTime - load@f1) / 50 (when that lands in (f0, f1]).
  * projectile launch (shooters): the launch lies in (f0, f1] of the sample the projectile is first seen.
Per sample pair on one target with progress > 0 on both: step s from the buffs (validate_p3.step_law); the pair is
'linear' when progress@f1 - progress@f0 == s x dt (no reset / snap at the hit). At the hit tick: progress ph = p0 +
s x (th - f0), crossing = ph // HitSpeed > (ph - s) // HitSpeed (the SIM's fire test), remainder = ph % HitSpeed.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reader_val"))
import validate_p3 as vp  # noqa: E402


def state(f0, f1, g):
    b0, b1 = f0.buffs.get(g) or [], f1.buffs.get(g) or []
    if not b0 and not b1:
        return "unbuffed", vp.BASE_STEP
    s0, s1 = vp.step_law(b0), vp.step_law(b1)
    if s0 == s1:
        return ("slowed" if s0 == 35 else f"step{s0}"), s0
    return "mixed", None


def analyse(path):
    frames, _ = vp.load(path)
    defs = {}
    for f in frames:
        for d in f.defs:
            defs.setdefault(d["definition_id"], d)
    name, defid = {}, {}
    for f in frames:
        name.update(f.name)
        defid.update(f.defid)
    seen, launch = set(), collections.defaultdict(set)     # g -> {f1 index of a launch}
    for i, f in enumerate(frames):
        for k, (src, _) in f.proj.items():
            if k not in seen:
                seen.add(k)
                if i and src is not None:
                    launch[src].add(i)
    C = collections.defaultdict(collections.Counter)
    rem = collections.defaultdict(collections.Counter)
    rows = collections.defaultdict(list)
    frozen_at = {}                                   # g -> last tick a -100 buff was seen
    post = collections.defaultdict(list)
    for i in range(1, len(frames)):
        f0, f1 = frames[i - 1], frames[i]
        dt = f1.tick - f0.tick
        for g, bs in f1.buffs.items():
            if any(b["config"]["HitSpeedMultiplier"] <= -100 for b in bs or []):
                frozen_at[g] = f1.tick
        if dt <= 0:
            continue
        for g, a1 in f1.att.items():
            a0 = f0.att.get(g)
            d = defs.get(defid.get(g))
            if not a0 or not a1 or not d or d["HitSpeed"] <= 0:
                continue
            if a0["target_gen"] in (None, "unlisted") or a0["target_gen"] != a1["target_gen"]:
                continue
            p0, p1, hs, lt = a0["progress_raw"], a1["progress_raw"], d["HitSpeed"], d["LoadTime"]
            if p0 <= 0 or p1 < p0:
                continue
            st, s = state(f0, f1, g)
            n = name.get(g)
            key = (n, st)
            hit_ticks = []
            if lt > 0 and a1["load_raw"] > a0["load_raw"]:
                back, r = divmod(lt - a1["load_raw"], 50)
                th = f1.tick - back
                C[key]["load_reset"] += 1
                if r or not f0.tick < th <= f1.tick:
                    C[key]["load_reset_unplaced"] += 1
                else:
                    hit_ticks.append(("load", th))
            if i in launch.get(g, ()):
                C[key]["launch"] += 1
                hit_ticks.append(("launch", None))
            if not hit_ticks:
                continue
            if s is None:
                C[key]["mixed_step"] += 1
                rows[key].append(f"t{f1.tick} {n} p{p0}->{p1} buffs {vp.buff_key(f0.buffs.get(g))}->{vp.buff_key(f1.buffs.get(g))}")
                continue
            lin = p1 - p0 == s * dt
            C[key]["linear" if lin else "nonlinear"] += 1
            if not lin:
                rows[key].append(f"NONLINEAR t{f0.tick}->{f1.tick} {n} p{p0}->{p1} step {s} load {a0['load_raw']}->{a1['load_raw']}")
                continue
            # ticks in (f0, f1] where a HitSpeed multiple is crossed
            cross = [f0.tick + k for k in range(1, dt + 1) if (p0 + s * k) // hs > (p0 + s * (k - 1)) // hs]
            for kind, th in hit_ticks:
                if kind == "load":
                    ph = p0 + s * (th - f0.tick)
                    C[key]["load_hit_on_crossing"] += th in cross
                    rem[key][ph % hs] += 1
                    if th not in cross:
                        rows[key].append(f"OFF t{th} {n} progress at hit {ph} (mod {hs} = {ph % hs}) step {s} "
                                         f"p{p0}@t{f0.tick} p{p1}@t{f1.tick} load {a0['load_raw']}->{a1['load_raw']}")
                    if th - frozen_at.get(g, -10**9) <= 200:
                        post[n].append(f"t{th} {n} first-after-freeze? last frozen t{frozen_at[g]} progress at hit {ph} "
                                       f"step {s} crossing {th in cross}")
                else:
                    C[key]["launch_with_crossing"] += bool(cross)
                    if cross:
                        rem[key][(p0 + s * (cross[0] - f0.tick)) % hs] += 1
                    else:
                        rows[key].append(f"NO-CROSS launch t{f0.tick}..{f1.tick} {n} p{p0}->{p1} step {s} "
                                         f"phases {[(p0 + s * k) % hs for k in range(1, dt + 1)]}")
    return C, rem, rows, post


def main(paths):
    for p in paths:
        C, rem, rows, post = analyse(p)
        print(f"== {os.path.basename(os.path.dirname(p))}")
        for key in sorted(C):
            c = C[key]
            print(f"  {key[0]:<26} {key[1]:<9} " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
            r = rem[key]
            if r:
                print(f"      remainder at the hit tick (progress mod HitSpeed): {dict(sorted(r.items()))}")
            for line in rows[key][:6]:
                print("      " + line)
        for n, ls in post.items():
            for line in ls[:6]:
                print("  POST-FREEZE " + line)


if __name__ == "__main__":
    main(sys.argv[1:])

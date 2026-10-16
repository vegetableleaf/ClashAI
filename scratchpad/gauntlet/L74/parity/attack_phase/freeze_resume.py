"""Live: what a freeze (-100 HitSpeedMultiplier buff) does to the attack cycle, per frozen body.

    python freeze_resume.py P3_FRAMES [...]
For each run of samples where a body carries a -100 buff: the last sample before it (progress, load, target), the
first sample after it, and the next load-reset hit (tick, progress at the hit = crossing?). One line per run.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reader_val"))
import validate_p3 as vp  # noqa: E402


def frozen(f, g):
    return any(b["config"]["HitSpeedMultiplier"] <= -100 for b in f.buffs.get(g) or [])


def main(paths):
    for p in paths:
        frames, _ = vp.load(p)
        defs = {d["definition_id"]: d for f in frames for d in f.defs}
        print(f"== {os.path.basename(os.path.dirname(p))}")
        gens = sorted({g for f in frames for g in f.att if frozen(f, g)})
        for g in gens:
            ser = [f for f in frames if g in f.att]
            k = 0
            while k < len(ser):
                if not frozen(ser[k], g):
                    k += 1
                    continue
                j = k
                while j < len(ser) and frozen(ser[j], g):
                    j += 1
                before = ser[k - 1] if k else None
                after = ser[j] if j < len(ser) else None
                d = defs.get(ser[k].defid.get(g), {})
                fmt = lambda f: "-" if not f else (  # noqa: E731
                    f"t{f.tick} " + ("att=None" if not f.att[g] else
                                     f"tgt{f.att[g]['target_gen']} p{f.att[g]['progress_raw']} L{f.att[g]['load_raw']}")
                    + f" buffs {[b['name'] for b in f.buffs.get(g) or []]}")
                held = [f.att[g] for f in ser[k:j] if f.att[g]]
                hit = None
                if after and after.att[g]:
                    for f0, f1 in zip(ser[j:], ser[j + 1:]):
                        a0, a1 = f0.att[g], f1.att[g]
                        if not a0 or not a1 or a1["target_gen"] != a0["target_gen"]:
                            break
                        dt = f1.tick - f0.tick
                        if d.get("LoadTime", 0) > 0 and a1["load_raw"] > a0["load_raw"] and a0["progress_raw"] > 0:
                            s = (a1["progress_raw"] - a0["progress_raw"]) // dt
                            th = f1.tick - (d["LoadTime"] - a1["load_raw"]) // 50
                            ph = a0["progress_raw"] + s * (th - f0.tick)
                            hit = f"next hit t{th} progress {ph} step {s} crossing {ph // d['HitSpeed'] > (ph - s) // d['HitSpeed']}"
                            break
                print(f"  {ser[k].name.get(g)} g{g} frozen t{ser[k].tick}..t{ser[j - 1].tick} ({ser[j - 1].tick - ser[k].tick} ticks; "
                      f"att rows while frozen {len(held)}{', progress ' + str(sorted({a['progress_raw'] for a in held})) if held else ''}"
                      f"{', load ' + str(sorted({a['load_raw'] for a in held})) if held else ''}) | before {fmt(before)} | "
                      f"after {fmt(after)} | {hit}")
                k = j


if __name__ == "__main__":
    main(sys.argv[1:])

"""Why the validator's Tesla 'fixed phase' support is low: classify its clean-hp-drop events by whether the Tesla's
load timer re-armed (= it fired) inside the same sample interval, and name the victims of the drops that were not hits.

    python tesla_events.py P3_FRAMES [...]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reader_val"))
import validate_p3 as vp  # noqa: E402


def main(paths):
    for p in paths:
        frames, _ = vp.load(p)
        name = {}
        for f in frames:
            name.update(f.name)
        c, victims, drops = collections.Counter(), collections.Counter(), collections.Counter()
        for f0, f1, dt in vp.intervals(frames):
            for g, a1 in f1.att.items():
                if name.get(g) not in ("Tesla", "Tesla_EV1"):
                    continue
                if not vp.linear(f0, f1, dt, g):
                    continue
                v = f0.att[g]["target_gen"]
                e0, e1 = f0.ents.get(v), f1.ents.get(v)
                if not e0 or not e1 or e1["hp"] >= e0["hp"]:
                    continue
                fired = a1["load_raw"] > f0.att[g]["load_raw"]
                c[name[g], "fired" if fired else "no_fire"] += 1
                if not fired:
                    victims[name.get(v)] += 1
                    drops[e0["hp"] - e1["hp"]] += 1
        print(os.path.basename(os.path.dirname(p)), dict(c), "non-hit drop victims", dict(victims),
              "drop sizes", dict(drops.most_common(6)))


if __name__ == "__main__":
    main(sys.argv[1:])

"""Debug: at the first reach-X-Bow play cf fires on, print the cell, my-frame geometry and the engine-frame distances."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
sys.argv = [sys.argv[0], "--n", "1", "--out", "/dev/null"]
import trigger_audit as TA                                                   # noqa: E402
from pipeline import cf_credit as CF                                         # noqa: E402
from pipeline import decision_options as DO                                  # noqa: E402

orig = TA.ref_conditions


def ref(m, s, d, st_ref, c):
    out = orig(m, s, d, st_ref, c)
    if d["play"] and CF.slot_names(s)[int(d["slot"])] == "xbow":
        cell = int(d["cell"])
        x, y = DO.cell_centres_tiles(s.cfg["grid"])
        X, Y = s.ep.cell_to_engine(cell, s.mirror, s.cfg["grid"])
        es = m.env.core.state()
        tw = [(t.team, t.kind, t.x / 18000, t.y / 18000, t.hp) for t in es.entities if int(t.kind) in (2, 3, 4)]
        print("side", s.side, "mirror", s.mirror, "cell", cell, "myframe", x[cell], y[cell], "engine/1000", X, Y,
              "reach", bool(CF.xbow_reach_cells(s, s.cfg["grid"])[cell]), "ref", "xbow" in out, flush=True)
        print("  episode towers", [(t["side"], t.get("type"), t["x"], t["y"], t["hp"]) for t in s.state["episode"]["crown_towers"]])
        print("  engine towers(kind,tiles)", tw[:8])
        print("  my-frame towers", [CF.raw_tiles(t, s.mirror) for t in s.state["episode"]["crown_towers"]])
        raise SystemExit(0)
    return out


TA.ref_conditions = ref
TA.main(["--n", "2", "--out", "/dev/null"])

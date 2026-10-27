"""S1b (3): which opponent policies an update's job list holds (count per checkpoint path / architecture), i.e. how many
server forwards a round needs and whether same-architecture opponents could share one.
    python league_mix.py --cfg CFG --E 512 --G 4"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--E", type=int, default=512)
    ap.add_argument("--G", type=int, default=4)
    ap.add_argument("--out", default="/workspace/speed/league_mix")
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    import torch
    L, base, jobs = build(a.cfg, a.E, a.G, a.set, Path(a.out) / "run")
    by = collections.Counter(j[1]["opp"]["path"] for j in jobs)
    arch = {}
    for pth in by:
        st = torch.load(pth, map_location="cpu")                 # REPO-relative: run from the repo root
        ar = st.get("args", {})
        arch[pth] = {"d": ar.get("d"), "layers": ar.get("layers"), "fv": ar.get("feature_version"),
                     "n_params": st.get("n_params"), "gen": bool(st.get("gen")),
                     "refine": [k.split(".")[0] for k in ("cell_refine.cfg", "tower_refine.cfg") if k in st["model"]],
                     "cue": any(k.startswith("cue_in.") for k in st["model"]), "mem": any(k.startswith("mem.") for k in st["model"])}
    out = {"jobs": len(jobs), "styled": sum("_opp_style" in str(j[1]) for j in jobs),
           "per_path": [{"path": p, "jobs": n, **arch[p]} for p, n in by.most_common()]}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

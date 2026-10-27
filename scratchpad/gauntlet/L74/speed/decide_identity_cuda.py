"""S4b: pipeline/tests/test_decide_identity.py's LIVE checks on CUDA (ticket B verifier note), on a pod without git.

The test module's own functions do the work; two things are swapped:
  * ``load_base`` reads BASE (a76f57e) pipeline/{decision_options,e1_eval,live_gen_v2}.py from ``--base-dir`` (the
    files ``git show a76f57e:...`` gives, copied over) instead of calling git;
  * ``live_pilot`` builds the pilot on ``--device`` (the test hard-codes cpu).
Each (which, device, stress) runs in its own subprocess, as the test does, then the records are compared the test's
way (taps, then whole decision dicts + decision-RNG states).

    python decide_identity_cuda.py --base-dir DIR --out OUT.json [--stress]          (repo root, pod)
"""
import argparse
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def child(which, device, out, stress, base_dir):
    import pipeline.tests.test_decide_identity as T
    if which == "base":
        import pipeline
        for mod in T.MODS:
            src = (Path(base_dir) / f"{mod}.py").read_text(encoding="utf-8")
            m = types.ModuleType(f"pipeline.{mod}")
            m.__package__, m.__file__ = "pipeline", str(ROOT / "pipeline" / f"{mod}.py")
            sys.modules[m.__name__] = m
            setattr(pipeline, mod, m)
            exec(compile(src, f"<{T.BASE} {mod}>", "exec"), m.__dict__)
    from pipeline import live_unit_state as LU
    load0 = LU.load_table

    def load_file(path=LU.TABLE_PATH):            # the laptop's cue table FILE (live's), not this pod's royalesim copy
        sim = sys.modules.pop("royalesim", None)
        try:
            return load0(path)
        finally:
            if sim is not None:
                sys.modules["royalesim"] = sim
    LU.load_table = load_file
    orig = T.SimpleNamespace

    def ns(**kw):                                       # live_pilot's argument namespace, on this device
        if "device" in kw and "ckpt" in kw:
            kw["device"] = device
        return orig(**kw)
    T.SimpleNamespace = ns
    T.live_main(out, stress, list(T.LOGS))


def compare(a, b):
    taps = [(x["log"], x["tick"], x["tap"], y["tap"]) for x, y in zip(a, b) if x["tap"] != y["tap"]]
    diffs = []
    for x, y in zip(a, b):
        if x != y:
            keys = sorted(k for k in set(x["d"]) | set(y["d"]) if x["d"].get(k) != y["d"].get(k))
            diffs.append(dict(log=x["log"], tick=x["tick"], why=(x["d"].get("why"), y["d"].get("why")), keys=keys,
                              rng_differs=x["rng"] != y["rng"]))
    return dict(n=len(a), n_other=len(b), taps=sum(x["tap"] is not None for x in a), tap_diffs=taps[:20],
                n_tap_diffs=len(taps), n_dict_diffs=len(diffs), dict_diffs=diffs[:20])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stress", action="store_true")
    ap.add_argument("--child", nargs=3, metavar=("WHICH", "DEVICE", "OUT"))
    a = ap.parse_args()
    if a.child:
        child(*a.child, a.stress, a.base_dir)
        return
    tmp = Path(a.out).with_suffix("")
    tmp.mkdir(parents=True, exist_ok=True)
    recs = {}
    for which, device in (("base", "cuda"), ("new", "cuda"), ("new", "cpu")):
        o = tmp / f"{which}_{device}{'_stress' if a.stress else ''}.json"
        r = subprocess.run([sys.executable, "-B", __file__, "--base-dir", a.base_dir, "--out", a.out,
                            *(["--stress"] if a.stress else []), "--child", which, device, str(o)],
                           cwd=ROOT, capture_output=True, text=True, timeout=7200)
        if r.returncode:
            print(r.stderr[-3000:])
            raise SystemExit(f"{which} {device} failed")
        recs[(which, device)] = json.loads(o.read_text())
    res = {"stress": a.stress,
           "new_cuda_vs_base_cuda": compare(recs[("base", "cuda")], recs[("new", "cuda")]),
           "new_cuda_vs_new_cpu": compare(recs[("new", "cpu")], recs[("new", "cuda")])}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1)[:4000])


if __name__ == "__main__":
    main()

"""LEARNER-SPEED: real pilot rollouts for the learner identity / speed benches (33920's records are gone). Builds rl_royale's
Learner from a pilot config (fastloop block stripped; k=v overrides), plays ONE rollout wave with its own CPU actors
(B0, pilot conditions, T_gate as configured) and pickles the result records.
    PY gen_recs.py --config CFG --out RES.pkl E=16 G=4 n_actors=8 learner_device=cuda
"""
import argparse
import os
import pickle
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import yaml  # noqa: E402

REPO = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(REPO))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402


def learner(config, overrides, tag):
    raw = yaml.safe_load((REPO / config).read_text(encoding="utf-8"))
    raw.pop("fastloop", None)
    tmp = REPO / f"_lspeed_{tag}.yaml"
    tmp.write_text(yaml.safe_dump(raw), encoding="utf-8")
    try:
        cfg = R.load_config(tmp, list(overrides), smoke=False)
    finally:
        tmp.unlink()
    run = f"lspeed_{tag}_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    LL.adopt_init_ability_head(L)
    return cfg, L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("overrides", nargs="*")
    a = ap.parse_args()
    cfg, L = learner(a.config, a.overrides, "gen")
    L.start_actors()
    t0 = time.time()
    res, info = L.rollout(0)
    a.out.write_bytes(pickle.dumps(res, protocol=4))
    print(f"[gen] {len(res)} matches in {time.time() - t0:.0f} s -> {a.out}", flush=True)
    os._exit(0)                                              # actor pools / JVMs: no orderly teardown needed


if __name__ == "__main__":
    main()

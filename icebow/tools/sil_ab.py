"""Does self-imitation actually make the cell head learn? A controlled A/B.

    python tools/sil_ab.py [episodes] [envs]

`ppo_sil_coef` ships OFF because it was implemented and smoke-tested but never SHOWN to help, and
defaulting a training change on without a measurement is asserting a result nobody has. This runs
the measurement: two drill-only runs, identical seed and identical drills, differing only in
`ppo_sil_coef`, then reports the quantity the whole thing is about --

    how far the CELL HEAD has moved away from an untrained net.

Why drill-only: the cell head is supposed to learn placement from drills, and a drill episode is
~15s of sim against a 3-minute match, so the comparison gets hundreds of the relevant episodes in
the time a handful of matches would take.

The baseline to beat is the live 4000-match run, whose cell head sat at 6.0652 against a fresh
net's 6.0684 -- a 0.003 nat difference out of 6.07, i.e. nothing.
"""
import io
import os
import subprocess
import sys
import math

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
CFG = os.path.join(_ROOT, "config", "config.yaml")
DRILLS = "nado_king_activation,tesla_pulls_the_wincon,log_the_ground_swarm"


def set_sil(value: str) -> None:
    s = io.open(CFG, encoding="utf-8").read()
    import re
    s2 = re.sub(r"(\n  ppo_sil_coef: )[0-9.]+", r"\g<1>" + value, s, count=1)
    assert s2 != s or ("ppo_sil_coef: " + value) in s, "could not set ppo_sil_coef"
    io.open(CFG, "w", encoding="utf-8", newline="\n").write(s2)


def train(out: str, episodes: int, envs: int, seed: int = 11) -> None:
    cmd = [sys.executable, "-u", "run.py", "train-sim-ppo",
           "--matches", str(episodes), "--envs", str(envs), "--workers", "0",
           "--size", "432", "--drill-frac", "0.95", "--drill-only", DRILLS,
           "--seed", str(seed), "--device", "cpu", "--out", out]
    r = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True)
    tail = [l for l in (r.stdout or "").splitlines() if "drills" in l or "stopped" in l][-2:]
    for l in tail:
        print("   " + l.strip()[:150])


def measure(ckpt: str, label: str) -> None:
    import numpy as np
    import torch
    import torch.nn as nn
    from clashrl.config import Config
    from clashrl.model import PolicyNet
    from clashrl.sim import scenarios as sc
    from clashrl.sim import doctrine as doc
    from clashrl.sim.drill_env import DrillEnv

    cfg = Config.load(CFG)
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    st = torch.load(ckpt, map_location="cpu", weights_only=False)
    sc.load_all()
    envs = [DrillEnv(cfg, sc.get(n), seed=4242, level=None) for n in DRILLS.split(",")]
    e0 = envs[0]
    ich = int(st.get("in_ch") or 12)
    td = int(st.get("threat_dim") or e0.threat_dim)

    def net(trained):
        class N(nn.Module):
            def __init__(s):
                super().__init__()
                s.policy = PolicyNet(ich, e0.n_cards, e0.n_cells, threat_dim=td)
        n = N()
        if trained:
            n.policy.load_state_dict(st["model"])
        n.eval()
        return n

    tr, fr = net(True), net(False)

    def ent(p):
        p = np.asarray(p, dtype=np.float64)
        p = p[p > 1e-12]
        return float(-(p * np.log(p)).sum())

    ents, fents, pri = [], [], []
    with torch.no_grad():
        for e in envs:
            o = e.reset()
            for _ in range(15):
                x = torch.from_numpy(np.asarray(o)[:, :, :ich]).float().permute(2, 0, 1).unsqueeze(0) / 255.0
                h = torch.from_numpy(np.asarray(e.hand_vec, np.float32)).unsqueeze(0)
                nx = torch.from_numpy(np.asarray(e.next_vec, np.float32)).unsqueeze(0)
                el = torch.from_numpy(np.asarray(e.elixir_vec, np.float32)).unsqueeze(0)
                t = np.asarray(e.threat_vec, np.float32)
                t = t[:td] if t.shape[0] > td else np.pad(t, (0, td - t.shape[0]))
                th = torch.from_numpy(t).unsqueeze(0)
                for n_, sink in ((tr, ents), (fr, fents)):
                    _z, cq, ceq = n_.policy.forward_parts(x, h, nx, el, th)
                    c = int(torch.argmax(cq[0]))
                    sink.append(ent(torch.softmax(ceq[0, c], dim=0).numpy()))
                _z, cq, ceq = tr.policy.forward_parts(x, h, nx, el, th)
                for cid in [c for c in e._hand_ids() if 0 <= c < len(e.specs)][:2]:
                    try:
                        dc = doc.doctrine_cells(e, cid)
                    except Exception:                     # noqa: BLE001
                        dc = None
                    if not dc:
                        continue
                    pi = torch.softmax(ceq[0, cid], dim=0).numpy()
                    best = max(dc, key=lambda kv: kv[1])[0]
                    if 0 <= int(best) < pi.size:
                        pri.append(float(pi[int(best)]))
                o, _r, d, _i = e.step((0, 0, 0))
                if d:
                    o = e.reset()
    mx = math.log(e0.n_cells)
    gap = float(np.mean(fents)) - float(np.mean(ents))
    print("%-9s cell entropy %.4f of %.4f  (fresh %.4f, gap %.4f)   pi(prior cell) %.5f  x uniform %.1f"
          % (label, float(np.mean(ents)), mx, float(np.mean(fents)), gap,
             float(np.mean(pri)) if pri else float("nan"),
             (float(np.mean(pri)) * e0.n_cells) if pri else float("nan")))


def main() -> int:
    episodes = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    envs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out_dir = os.environ.get("SIL_AB_DIR", _ROOT)
    print("SIL A/B: %d episodes each, %d envs, drills=%s" % (episodes, envs, DRILLS))
    try:
        for label, coef in (("sil_off", "0.0"), ("sil_on", "0.05")):
            set_sil(coef)
            out = os.path.join(out_dir, "%s.pt" % label)
            print("[%s] ppo_sil_coef=%s" % (label, coef))
            train(out, episodes, envs)
            measure(out, label)
    finally:
        set_sil("0.0")                                    # never leave the shared config armed
        print("config restored: ppo_sil_coef 0.0")
    print("")
    print("Reference: the live 4000-match run measured 6.0652 against a fresh net's 6.0684 --")
    print("a gap of 0.003 nats, i.e. the head had not moved. A bigger gap is a head that learned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

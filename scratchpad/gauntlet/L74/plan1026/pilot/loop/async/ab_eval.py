"""LOOP-ASYNC A/B: per-update progress of fastloop runs on a HELD-OUT batch (LEARNER-SCALE lr_sweep's metric).

    cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/loop/async/ab_eval.py --config CFG [k=v ...] \
        --held RECORDS.pkl [RECORDS.pkl ...] --arm NAME=CKPT_DIR [--arm ...] --out OUT.json

held = rl_royale results played by B0 (a run's FASTLOOP_RECORDS records_u0000.pkl, from a run NOT evaluated on it),
v_old = B0's server critic. J(theta) = sum_rows w A (pi_theta / pi_0 - 1) (lr_sweep.surrogate: A = GAE from the stored
B0 V, normalised over the held batch), per-match standard error; plus the mean KL(pi_0 || pi_theta) of gate / card / cell
on the held rows (bern_kl / cat_kl as the PPO monitors). One line per (arm, checkpoint u)."""
import argparse
import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[6]
sys.path[:0] = [str(REPO), str(REPO / "scratchpad/gauntlet/L74/plan1026/pilot/lrn")]
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.allow_tf32 = torch.backends.cuda.matmul.allow_tf32 = False
from pipeline import rl_royale as R  # noqa: E402
from rec_identity import collate_kw  # noqa: E402


@torch.no_grad()
def surrogate(model, Bh, cfg, chunk=1024):
    """= LEARNER-SCALE lr_sweep.surrogate (copied: the pod tree has no lr_sweep.py)."""
    N = len(Bh["A"])
    x = []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=Bh["A"].device)
        t = R.policy_terms(model, Bh, idx, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
        lp = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
        x.append(Bh["w"][idx] * Bh["A"][idx] * (torch.exp(lp - Bh["lp_old"][idx]) - 1))
    x = torch.cat(x).double().cpu().numpy()
    per = np.bincount(Bh["match"].cpu().numpy(), weights=x)
    return {"J": float(per.sum()), "se": float(np.sqrt(len(per)) * per.std(ddof=1))}


@torch.no_grad()
def held_kl(model, ref, Bh, cfg, chunk=1024):
    N, out = len(Bh["A"]), {"gate": [], "card": [], "cell": []}
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=Bh["A"].device)
        t = R.policy_terms(model, Bh, idx, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
        r = R.policy_terms(ref, Bh, idx, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
        gs, pl = Bh["gate_sampled"][idx], Bh["played"][idx]
        if gs.any():
            out["gate"].append(R.bern_kl(r["x"][gs], t["x"][gs]))
        if pl.any():
            out["card"].append(R.cat_kl(r["card_lp"][pl], t["card_lp"][pl]))
            out["cell"].append(R.cat_kl(r["cell_lp"], t["cell_lp"]))
    return {k: float(torch.cat(v).mean()) if v else None for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--held", nargs="+", required=True)
    ap.add_argument("--arm", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("overrides", nargs="*")
    a = ap.parse_args()
    cfg = R.load_config(REPO / a.config, a.overrides, smoke=False)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    held = [r for p in a.held for r in pickle.loads(Path(p).read_bytes())["results"]]
    Bn, _ = R.collate(held, float(cfg["adv_clip"]), **collate_kw(cfg))
    Bh = R.to_device(Bn, dev)
    Bh["v_shared"] = Bh.pop("v_stored")                      # B0's stored V (stored_values semantics)
    init = torch.load(REPO / cfg["init"], map_location="cpu", weights_only=False)
    out = {"config": a.config, "overrides": a.overrides, "held_matches": len(held), "held_rows": int(len(Bh["lp_old"])),
           "arms": {}}
    base_model = None
    for spec in a.arm:
        name, d = spec.split("=", 1)
        cks = sorted(Path(d).glob("*_u[0-9][0-9][0-9][0-9].pt"))
        rows = []
        for ck in cks:
            obj = torch.load(ck, map_location="cpu", weights_only=False)
            if base_model is None:                           # the net class from e1_eval's loader, B0's weights
                from pipeline import e1_eval as E
                pol, _ = E.load_policy(ck, str(dev))
                base_model = pol.model.eval()
                ref_model = __import__("copy").deepcopy(base_model)   # B0 = the run's u0000 (saved before any
                ref_model.load_state_dict(torch.load(cks[0], map_location="cpu", weights_only=False)["model"])  # update;
                assert cks[0].stem.endswith("_u0000")        # the init file lacks the cell_refine.cfg buffer)
                rsd = ref_model.state_dict()
                d = {k: (rsd[k].float().cpu() - init["model"][k].float()).abs().max().item() for k in init["model"]
                     if k in rsd and init["model"][k].is_floating_point()}
                out["u0000_vs_init_maxdiff"] = max(d.values())
                R.gae_batch(ref_model, Bh, cfg)              # A, w from B0's stored V (v_shared)
                out["J_B0"] = surrogate(ref_model, Bh, cfg)
            m = base_model
            m.load_state_dict(obj["model"])
            u = int(ck.stem.rsplit("_u", 1)[1])
            row = {"u": u, "J": surrogate(m, Bh, cfg), "kl_b0": held_kl(m, ref_model, Bh, cfg)}
            rows.append(row)
            print(name, json.dumps(row), flush=True)
        out["arms"][name] = rows
        a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

"""LOOP-OPP: the frozen opponent pool manifest (POOL.json) of a training config, from the files themselves.

  build (pod, repo root = a tree with icebow/data):  python pool_manifest.py --config CFG [k=v ...] --out POOL.json
  mark  (laptop, repo root = the git checkout):      python pool_manifest.py --mark-git POOL.json
  check (anywhere with the files):                   python pool_manifest.py --check POOL.json

Opponents = rl_royale's league for that config: league_exploiters (fixed share, own decode) and league_external (PFSP
over init + learner snapshots + externals); init / snapshots are the learner's own weights (not frozen, listed apart).
Decode = loop_opp.opp_match_cfg at match (seed 0, k 0, update 0) with the style keys shown as ranges (opp_style draws per
match). files = every non-code file an opponent seat reads (checkpoints, deck pools), sha256 + bytes (+ in_git)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO))


def arch(path: Path, learner_vocab) -> dict:
    import torch
    from pipeline import e1_eval as E
    st = torch.load(path, map_location="cpu", weights_only=False)
    a, sd = st.get("args", {}), st.get("model") or st.get("state_dict") or {}
    pol, mi = E.load_policy(path, "cpu")
    m = pol.model
    voc = list(st.get("card_vocab", []))
    return {"gen": bool(st.get("gen")), "loads_as": type(pol).__name__, "feature_version": int(getattr(m, "feature_version", 1)),
            "d": int(a.get("d", 128)), "layers": int(a.get("layers", 4)), "d_c": st.get("d_c"),
            "grid": str(mi.get("grid", "floor")), "n_params": int(sum(p.numel() for p in m.parameters())),
            "cue": getattr(m, "cue_in", None) is not None, "memory": getattr(m, "mem", None) is not None,
            "refine": sorted({k.split(".")[0] for k in sd if k.split(".")[0] in ("cell_refine", "tower_refine")}),
            "gen_row_keys": list(E.gen_row_keys(m)),
            "card_vocab_sha256": hashlib.sha256(json.dumps(voc).encode()).hexdigest(), "card_vocab_n": len(voc),
            "vocab_equals_learner": voc == learner_vocab, "grafted_heads_from": st.get("grafted_heads_from")}


def build(a) -> dict:
    import torch
    from pipeline import adaptive_opponents as AO
    from pipeline import loop_opp as LO
    from pipeline import rl_royale as R
    cfg = R.load_config(Path(a.config), a.overrides, False)
    files = {}

    def f(p):
        p = str(p)
        if p not in files:
            files[p] = {"path": p, "sha256": LO.sha256(REPO / p), "bytes": (REPO / p).stat().st_size}
        return files[p]["sha256"]
    learner_vocab = list(torch.load(REPO / cfg["init"], map_location="cpu", weights_only=False).get("card_vocab", []))
    ex = R.exploiter_league(cfg)
    parts = ([] if ex is None else ex.get("parts") or [ex])
    xs = cfg.get("league_exploiters")
    xs = xs if isinstance(xs, list) else [xs] if xs else []
    opps = []

    def decode(opp, grid, fv):
        c = LO.opp_match_cfg(cfg, opp, grid, 0, 0, 0, fv)
        out = {k: (str(c[k]) if k == "noise" else c[k]) for k in LO.DECISION_KEYS if k in c and k != "_opp_style"
               and k not in ("rollout_index", "update")}
        if "_opp_style" in c:
            out["T"], out["tau"] = float(cfg["T"]) if opp.get("cfg", {}).get("T") is None else float(opp["cfg"]["T"]), \
                float(cfg["tau"]) if opp.get("cfg", {}).get("tau") is None else float(opp["cfg"]["tau"])
            out["style"] = {k: c[k] for k in AO.STYLE_KEYS}
            out["style_rule"] = ("per match (adaptive_opponents.style_config, seed = spec seed, rollout = k): tau - "
                                 "aggression clipped [.01, .99], T x temperature, lane bias on cell logits x T, "
                                 "WAIT while my elixir < bank and no enemy body on my half, spell plays + spell_delay "
                                 "ticks (icebow-card-set decks only: other decks have placeholder slot ids)")
        return out
    for x, part in zip(xs, parts):
        o, ck = part["opp"], part["opp"]["path"]
        ar = arch(REPO / ck, learner_vocab)
        opps.append({"id": o["id"], "type": o["type"], "ckpt": ck, "sha256": f(ck), "arch": ar,
                     "selection": {"rule": "league_exploiters share (first draw of each matchup)", "share": part["share"]},
                     "decks": {"file": x["decks"], "sha256": f(x["decks"]), "weights": cfg.get("league_deck_weights"),
                               "alpha": cfg["league_deck_alpha"], "floor": cfg["league_deck_floor"]},
                     "decode": decode(o, ar["grid"], ar["feature_version"])})
    ext = list(dict.fromkeys(cfg.get("league_external") or []))
    for ck in ext:
        o = {"id": "external:" + ck, "cat": "exploiter", "type": "exploiter", "path": ck}
        ar = arch(REPO / ck, learner_vocab)
        opps.append({"id": o["id"], "type": o["type"], "ckpt": ck, "sha256": f(ck), "arch": ar,
                     "selection": {"rule": "PFSP (adaptive_opponents.sample_opponent) over init + learner snapshots + "
                                           "externals, weight (1 - p_learner_win)^gamma + floor",
                                   "share_of_rest": "1 / pool size at equal ratings", "pfsp_gamma": cfg.get("league_pfsp_gamma"),
                                   "pfsp_floor": cfg.get("league_pfsp_floor")},
                     "decks": {"file": cfg["league_decks"], "sha256": f(cfg["league_decks"]),
                               "weights": cfg.get("league_deck_weights"), "icebow_share": cfg["league_icebow_share"]},
                     "decode": decode(o, ar["grid"], ar["feature_version"])})
    init = {"id": "init", "type": "init", "cat": "init", "path": cfg["init"]}
    ar = arch(REPO / cfg["init"], learner_vocab)
    learner_pool = {"init": {"ckpt": cfg["init"], "sha256": f(cfg["init"]), "arch": ar,
                             "decode": decode(init, ar["grid"], ar["feature_version"])},
                    "snapshots": {"every": cfg["league_snapshot_every"], "keep": cfg["league_snapshot_keep"],
                                  "note": "the learner's own weights at update u (its architecture and inputs, incl. "
                                          "memory / cue); decode as init"}}
    cs = hashlib.sha256(Path(a.config).read_bytes()).hexdigest()
    return {"config": {"path": a.config, "sha256": cs, "overrides": a.overrides, "config_sha": R.config_sha(cfg)},
            "exploiter_share": None if ex is None else ex["share"], "opponents": opps, "learner_pool": learner_pool,
            "files": sorted(files.values(), key=lambda r: r["path"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--mark-git")
    ap.add_argument("--check")
    ap.add_argument("overrides", nargs="*")
    a = ap.parse_args()
    if a.mark_git:
        m = json.loads(Path(a.mark_git).read_text(encoding="utf-8"))
        for r in m["files"]:
            r["in_git"] = subprocess.run(["git", "ls-files", "--error-unmatch", r["path"]], capture_output=True).returncode == 0
        Path(a.mark_git).write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
        return
    if a.check:
        from pipeline import loop_opp as LO
        m = json.loads(Path(a.check).read_text(encoding="utf-8"))
        bad = [r["path"] for r in m["files"] if LO.sha256(REPO / r["path"]) != r["sha256"]]
        print("CHECK", "FAIL " + json.dumps(bad) if bad else f"OK {len(m['files'])} files")
        raise SystemExit(1 if bad else 0)
    Path(a.out).write_text(json.dumps(build(a), indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

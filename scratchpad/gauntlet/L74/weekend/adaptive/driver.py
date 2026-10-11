"""Pod-only orchestration; pure planning/report helpers are tested without SIM.

Invoked by run_adaptive.sh AFTER the wait and both locks. No deployment path.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[5]
WEEKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(WEEKEND))

CKROOT = Path("icebow/data/bench/rl_royale")
FAST = CKROOT / "rseries_r3c/rseries_r3c_u0030_barrel.pt"
OLD = CKROOT / "rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt"
CAL_C = CKROOT / "rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt"
EVO = Path("scratchpad/gauntlet/L70/pool_forms/loadable_decks.json")
LAD = Path("scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json")
DATA = Path("icebow/data/pipeline/gen_dataset_v32_fv5.npz")
LIVE_FLAGS = ["--xbow-class", "class_sample", "--xbow-class-floor", "0.3", "--tau-phase", "0.35", "0.45", "0.55",
              "--spell-aim", "rocket_area", "--own-effects", "--gate-decode", "hazard_below_tau",
              "--gate-hazard-min-elixir", "9", "--log-aim", "log_barrel", "--lethal-rocket", "ot_behind",
              "--xbow-dead-lane", "block", "--gate-hazard-threatened", "2", "--rocket-dead-target", "block",
              "--tau-threatened", "0.2", "--lethal-log", "on"]


def cycle_plan(prefix="wk_adapt", cycles=3, main_updates=20, exploiter_updates=15):
    if min(cycles, main_updates, exploiter_updates) <= 0:
        raise ValueError("cycle budgets must be positive")
    main = f"{prefix}_main"
    return [dict(cycle=c, main_run=main, main_target=c * main_updates,
                 main_start=(c - 1) * main_updates,
                 frozen=str(CKROOT / main / f"frozen_c{c}.pt"),
                 exploiter_run=f"{prefix}_exp{c}", exploiter_target=exploiter_updates,
                 exploiter_init=str(FAST)) for c in range(1, cycles + 1)]


def checkpoint(run):
    return CKROOT / run / f"{run}_latest.pt"


def config_for(base, phase, plan, deck_path, external):
    c = copy.deepcopy(base)
    c.update(init=str(FAST), proagree_data_gen=str(DATA), league=True, league_pfsp="hard", opp_style="on", opp_elixir="counter",
             league_pfsp_gamma=2.0, league_pfsp_floor=.05, league_snapshot_every=5, league_snapshot_keep=12,
             league_external=list(external), league_decks=str(deck_path), league_deck_alpha=1.0,
             league_mix={"latest": .5, "older": .25, "init": .25, "s1": 0.0},
             league_deck_floor=0.0, league_icebow_share=0.0, league_learner_icebow_share=1.0,
             league_opp_policy="sample", noise_off="all", forms_mode="deck", hero_abilities=True,
             ability_policy="v2", action_delay_ticks=26, extrapolate_ticks=26,
             stall_elixir=None, n_actors=20, actor_threads=1, actor_device="cpu", learner_device="cuda",
             E=64, G=4, in_flight=8, branch_gate=False, seed=74,
             advantage="match_loo", shaping="none", save_every=5, max_updates=plan["main_target"])
    if phase == "exploiter":
        c.update(init=plan["exploiter_init"], league_pfsp="off", league_external=[],
                 league_frozen_opponent=plan["frozen"], max_updates=plan["exploiter_target"],
                 league_learner_icebow_share=0.0, seed=7400 + plan["cycle"])
    elif phase != "main":
        raise ValueError(phase)
    return c


def enroll(main_checkpoint, exploiter_path):
    """Preserve optimizer, RNG and ratings; pin exploiters independently of snapshots."""
    ck = copy.deepcopy(main_checkpoint)
    pool = ck["rl"]["league"].setdefault("external", [])
    if str(exploiter_path) not in pool:
        pool.append(str(exploiter_path))
    ck["rl"]["league"].setdefault("ratings", {}).setdefault(
        "external:" + str(exploiter_path), {"p": .5, "games": 0})
    return ck


def weighted_sixty(data):
    """Reuse weekend archetypes, with exactly 60% after RL removes icebow.

    The adaptive driver disables the icebow-only S1 bucket so every main
    opponent draws from this census (including snapshots and exploiters).
    """
    import archetypes as A
    from pipeline.e1_eval import ICEBOW_ENGINE_DECK
    d = copy.deepcopy(data)
    ice = sorted(x.split("@")[0] for x in ICEBOW_ENGINE_DECK)
    rows = [x for x in d["decks"] if sorted(n.split("@")[0] for n in x["engine"]) != ice]
    groups = [[x for x in rows if A.unfavorable(A.classify(x["engine"])) == flag] for flag in (True, False)]
    if any(not g for g in groups):
        raise ValueError("weighted census needs both favourable and unfavourable decks")
    for g, share in zip(groups, (.6, .4)):
        total = sum(x["sides"] for x in g)
        for x in g:
            x["sides"] = max(1, round(share * 1_000_000_000 * x["sides"] / total))
    d["decks"] = rows
    d["adaptive_unfavourable_share"] = sum(x["sides"] for x in groups[0]) / sum(x["sides"] for x in rows)
    if abs(d["adaptive_unfavourable_share"] - .6) > 1e-6:
        raise ValueError("weighted census failed 60% check")
    return d


def run(args, log):
    with Path(log).open("w", encoding="utf-8") as out:
        subprocess.run([str(x) for x in args], cwd=REPO, stdout=out, stderr=subprocess.STDOUT, check=True)


def atomic_json(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_checkpoint(path, obj):
    import torch
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    torch.save(obj, tmp)
    tmp.replace(path)


def train(c, name, out):
    import torch
    import yaml
    from pipeline.rl_royale import RUN_ROOT
    cfg = out / f"{name}.yaml"
    cfg.write_text(yaml.safe_dump(c, sort_keys=False), encoding="utf-8")
    path = REPO / checkpoint(name)
    if path.exists():
        saved = torch.load(path, map_location="cpu", weights_only=True)
        u = saved["rl"]["update"]
        if u > c["max_updates"]:
            raise RuntimeError(f"{name} is ahead of this cycle: {u}")
    else:
        u = -1
    if u < c["max_updates"]:
        cmd = [sys.executable, "-m", "pipeline.rl_royale", "--config", cfg, "--run", name]
        if path.exists():
            cmd.append("--resume")
        run(cmd, out / f"{name}_to{c['max_updates']}.log")
    saved = torch.load(path, map_location="cpu", weights_only=True)
    if saved["rl"]["update"] != c["max_updates"]:
        raise RuntimeError(f"{name} stopped before its update budget; inspect training log")
    log = RUN_ROOT / name / "train_log.jsonl"
    updates = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    if any(r.get("stop") for r in updates):
        raise RuntimeError(f"{name} tripped a training guard; refusing the next cycle")
    return saved


def eval_command(ck, out, census, start, workers=20):
    return [sys.executable, "-m", "pipeline.search_s0", "--out", str(out), "--seeds", f"{start}:{start + 480}",
            "--opps", "gen", "--arms", "plain", "--gen", str(ck), "--opp-gen", str(CAL_C),
            "--forms-mode", "deck", "--device", "cpu", "--workers", str(workers), "--tail-cap", "7200",
            "--tau-plain", "0.35", "--census", str(census), "--hero-abilities", "--ability-policy", "v2",
            "--behaviour-telemetry", "--opp-policy", "sample", "--opp-T", "0.1", *LIVE_FLAGS]


def summary(ev):
    import wk_compare as W
    # Reject skips, duplicates, missing pairs and wrong totals instead of silently
    # comparing a favourable subset. Each arm plays exactly 960 games.
    records = {}
    for arm in ("old", "adaptive"):
        records[arm] = {}
        for census in ("evo", "lad"):
            rows = [json.loads(s) for s in (ev / f"{arm}_{census}" / "matches.jsonl").read_text().splitlines()]
            if len(rows) != 480 or any(r.get("skipped") or r.get("outcome") not in ("win", "draw", "loss") for r in rows):
                raise ValueError(f"incomplete evaluation: {arm}_{census}")
            for r in rows:
                key = (census, r["tag"])
                if key in records[arm] or not r.get("opp_deck"):
                    raise ValueError("duplicate tag or missing opponent deck")
                records[arm][key] = r["opp_deck"]
    if records["old"] != records["adaptive"]:
        raise ValueError("evaluation pairing/decks differ")
    n, _, _, mu, lo, hi = W.diff(str(ev), "old", "adaptive")
    if n != 960:
        raise ValueError(f"expected 960 paired games, got {n}")
    verdict = "Improvement shown" if lo > 0 else "Worse" if hi < 0 else "Improvement not established"
    return (f"VERDICT: {verdict}. Nothing deployed.\n" + W.line(str(ev), "old", "adaptive") + "\n" +
            W.arch_table(str(ev), "old", "adaptive") + "\nFixed opponent: calibrated set c, T=0.1; census decks; S2/CAL live flags.\n")


def execute(out):
    import torch
    import yaml
    out.mkdir(parents=True, exist_ok=True)
    (out / "DONE").unlink(missing_ok=True)
    base = yaml.safe_load((REPO / "pipeline/rl_royale.yaml").read_text())
    for path in (FAST, OLD, CAL_C, EVO, LAD, DATA):
        if not (REPO / path).is_file():
            raise FileNotFoundError(REPO / path)
    deck = out / "decks_rl.json"
    if not deck.exists():
        # Same weekend weighting tool and archetypes; pin the requested 60%.
        run([sys.executable, WEEKEND / "mk_weighted_decks.py", REPO / EVO, deck, "1.0", "0"], out / "decks.log")
        atomic_json(deck, weighted_sixty(json.loads(deck.read_text())))
    manifest = out / "cycles.json"
    state = json.loads(manifest.read_text()) if manifest.exists() else {"completed": [], "external": []}
    plans = cycle_plan()
    for plan in plans:
        if plan["cycle"] in state["completed"]:
            continue
        c = config_for(base, "main", plan, deck, state["external"])
        main = train(c, plan["main_run"], out)
        frozen = REPO / plan["frozen"]
        weights = {k: v for k, v in main.items() if k != "rl"}
        if frozen.exists():
            old = torch.load(frozen, map_location="cpu", weights_only=True)
            if old.keys() != weights.keys() or any(not torch.equal(old["model"][k], v) for k, v in weights["model"].items()):
                raise RuntimeError("frozen main copy changed")
        else:
            save_checkpoint(frozen, weights)
        frozen_hash = hashlib.sha256(frozen.read_bytes()).hexdigest()
        state["active"] = {**plan, "frozen_sha256": frozen_hash}
        atomic_json(manifest, state)
        exp = config_for(base, "exploiter", plan, deck, [])
        train(exp, plan["exploiter_run"], out)
        if hashlib.sha256(frozen.read_bytes()).hexdigest() != frozen_hash:
            raise RuntimeError("exploiter changed the frozen main checkpoint")
        # Pin a completed, immutable filename, never a moving latest path.
        exp_path = CKROOT / plan["exploiter_run"] / f"{plan['exploiter_run']}_u{plan['exploiter_target']:04d}.pt"
        if not (REPO / exp_path).is_file():
            raise FileNotFoundError(exp_path)
        main = enroll(main, exp_path)
        save_checkpoint(REPO / checkpoint(plan["main_run"]), main)
        state["external"] = main["rl"]["league"]["external"]
        state["completed"].append(plan["cycle"])
        state.setdefault("history", []).append(state.pop("active"))
        atomic_json(manifest, state)
    final = CKROOT / plans[-1]["main_run"] / "adaptive_final_grafted.pt"
    run([sys.executable, WEEKEND / "graft_generic.py", checkpoint(plans[-1]["main_run"]), OLD, final], out / "graft.log")
    ev = out / "eval"
    ev.mkdir(exist_ok=True)
    for arm, ck in (("old", OLD), ("adaptive", final)):
        for census, decks, start in (("evo", EVO, 30000), ("lad", LAD, 30480)):
            dest = ev / f"{arm}_{census}"
            if not (dest / "summary.json").exists():
                if dest.exists():
                    # Preserve failed output; search_s0 requires an empty dir.
                    dest.rename(ev / f"{arm}_{census}.partial_{time.time_ns()}")
                run(eval_command(ck, dest, decks, start), ev / f"{arm}_{census}.log")
    (out / "SUMMARY.txt").write_text(summary(ev), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    execute(parser.parse_args().out.resolve())

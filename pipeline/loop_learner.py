"""LOOP-LRN: rl_royale's learner as a standalone process for the fast crforge loop (plan1026 pilot, LOOP_SPEC.md).

    ROYALE_RUNTIME=fin16-linux python -m pipeline.loop_learner --config CFG.yaml --run NAME \
        [--spool /dev/shm/loop/spool] [--weights /dev/shm/loop/weights] [--resume] [key=value ...]

It IS ``rl_royale.Learner``: the same config keys, collate, GAE, residual critic, critic warm-up, PPO loss, KL monitors /
``kl_stop_prev``, ability-head term, guards, checkpoints (``<run>_latest.pt`` / ``_uNNNN.pt``, resumable by either
program). Three things differ:
  * ``rollout(u)`` takes E x G finished-match records from the spool (pipeline/loop_records.py ``take``): newest first,
    every row at version >= u - 1 (staleness <= 1 update; the ratio uses each row's stored lp_old). The producers sample
    the matchups; the learner's rng only draws minibatch orders.
  * after every good update the weights go to the policy servers (``push``, LOOP-SRV): ``learner.v{V:08d}.pt`` =
    torch.save({"version": V, "state_dict": rl_royale's actor weights message (model + "__ability__." head)}), then
    ``learner.latest`` = "V", both written .tmp + os.replace; V = updates done (0 = the start); v{V-3} is deleted.
  * a fresh start has no actor pool: no init screen, no B6 warm start. With ability_head the head comes from the init
    checkpoint's ``rl["ability_head"]`` (B0 = CLXIII as deployed carries its head), else the run is refused. The pro
    agreement baseline is computed only when proagree_every <= max_updates; screen_every must exceed max_updates.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

import torch

from pipeline import rl_royale as R
from pipeline import loop_records as LR
from pipeline import adaptive_opponents as AO


def adopt_init_ability_head(L: R.Learner) -> bool:
    """B0's deployed ability head (init checkpoint rl["ability_head"]) into L.ability_head (strict). -> loaded or not."""
    if getattr(L, "ability_head", None) is None:
        return False
    sd = (torch.load(L.init_path, map_location="cpu", weights_only=False).get("rl") or {}).get("ability_head")
    if sd is None:
        return False
    L.ability_head.load_state_dict(sd)
    return True


class LoopLearner(R.Learner):
    def __init__(self, cfg: dict, run: str, run_dir: Path, ck_dir: Path, log: R.Log, resume: bool,
                 spool: Path, weights: Path):
        if int(cfg["screen_every"]) <= int(cfg["max_updates"]):
            raise SystemExit("loop learner: no actor pool for held-out screens -- set screen_every > max_updates")
        super().__init__(cfg, run, run_dir, ck_dir, log, resume)
        self.spool, self.wdir = Path(spool), Path(weights)
        self.spool.mkdir(parents=True, exist_ok=True)
        self.wdir.mkdir(parents=True, exist_ok=True)

    def rollout(self, u: int) -> tuple[list[dict], dict]:
        n = int(self.cfg.get("matches_per_update") or int(self.cfg["E"]) * int(self.cfg["G"]))   # loop key; absent = E x G
        t = time.perf_counter()
        recs, info = LR.take(self.spool, n, min_wver=self.update - 1, stop=self.run_dir / "STOP")
        res = [LR.to_result(r) for r in recs]
        del recs
        league = getattr(self, "league", None) is not None
        if league and self.cfg.get("league_pfsp") == "hard":          # as rl_royale.rollout's league branch
            AO.update_ratings(self.league, res)
        if league and AO.mode(self.cfg.get("opp_style", "off")) == "on":
            for r in sorted(res, key=lambda r: (r["league"]["tag"], r["k"])):
                self.log.json({"event": "opponent_style", "update": u, "tag": r["league"]["tag"],
                               "k": r["k"], "opp": r["league"]["opp"]["id"], "style": r.get("opp_style")})
        self.log(f"[loop] u{u:04d} took {info['taken']} records (wver {info['wver_min']}-{info['wver_max']}, rows at "
                 f"u-1 {info['rows_at_min_wver_share']}), stale deleted {info['stale_deleted']}, left {info['left']}, "
                 f"waited {info['wait_s']:.1f}s")
        rinfo = {"picked": [], "skipped": 0, "spool": info,
                 "actors": {"spool": {"wall_s": time.perf_counter() - t, "matches": len(res), "gpu_peak_mb": None}}}
        if league:
            rinfo["league"] = [{"opp": r["league"]["opp"]["id"], "learner_deck": r["league"].get("learner_deck_name"),
                                "opp_deck": r["league"].get("opp_deck_name"), "side": r["side"]} for r in res]
        return res, rinfo

    def screen(self, model=None) -> dict:
        raise SystemExit("loop learner: no actor pool for held-out screens (screen_every > max_updates; a proagree "
                         "tripwire that needs a screen cannot run here)")

    def push(self) -> Path:
        """LOOP-SRV weight push (module docstring)."""
        V = int(self.update)
        sd = torch.load(io.BytesIO(self._actor_bytes()), map_location="cpu")   # exactly the actors' message
        path = self.wdir / f"learner.v{V:08d}.pt"
        tmp = path.with_name(path.name + ".tmp")
        torch.save({"version": V, "state_dict": sd}, tmp)
        os.replace(tmp, path)
        lt = self.wdir / "learner.latest.tmp"
        lt.write_text(str(V), encoding="utf-8")
        os.replace(lt, self.wdir / "learner.latest")
        (self.wdir / f"learner.v{V - 3:08d}.pt").unlink(missing_ok=True)
        return path

    def one_update(self, u: int):
        rec, reasons, crash = super().one_update(u)
        if not crash:
            t = time.perf_counter()
            p = self.push()
            self.log(f"[loop] pushed {p.name} ({time.perf_counter() - t:.2f}s)")
        return rec, reasons, crash

    def fresh_start(self) -> None:
        """rl_royale.startup without actors: the init's ability head, the proagree baseline if it is used, u0000."""
        cfg = self.cfg
        if getattr(self, "ability_head", None) is not None:
            if not adopt_init_ability_head(self):
                raise SystemExit("ability_head: the init has no rl.ability_head and the loop learner has no actors for "
                                 "the B6 warm start (start from an rl_royale startup checkpoint with --resume)")
            self.log(f"[loop] ability head = the init's rl.ability_head ({cfg['init']})")
        if int(cfg["proagree_every"]) <= int(cfg["max_updates"]):
            pa = self.proagree(self.model)
            self.base["init_proagree"] = {k: pa[k] for k in R.PA_KEYS + ("cell_tile_top1", "n", "n_play")}
            self.log(f"[loop] init pro agreement: cell {pa['cell_half_top1']:.4f} card {pa['card_top1']:.4f} "
                     f"gate_bal {pa['gate_bal_acc']:.4f}")
        self.log(f"[loop] saved {self.save(self.base.get('init_proagree'), numbered=True)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--spool", type=Path, default=Path("/dev/shm/loop/spool"))
    ap.add_argument("--weights", type=Path, default=Path("/dev/shm/loop/weights"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("overrides", nargs="*", help="key=value config overrides")
    a = ap.parse_args(argv)
    from pipeline.royale_runtime import activate
    runtime = activate()
    cfg = R.load_config(a.config, a.overrides, smoke=False)
    if cfg.get("learner_deterministic") or os.environ.get("RL_DETERMINISTIC"):   # as rl_royale.main, before any CUDA
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.allow_tf32 = False               # as rl_royale.main: TF32 moved lp_cell 1.2e-3 vs the actors
        torch.backends.cuda.matmul.allow_tf32 = False         # (the u0 on-policy assert is 1e-4; loop smoke 10-28)
    run_dir, ck_dir = R.RUN_ROOT / a.run, R.CKPT_ROOT / a.run
    if a.resume and not (ck_dir / f"{a.run}_latest.pt").exists():
        raise SystemExit(f"--resume needs {ck_dir / (a.run + '_latest.pt')}")
    if not a.resume and any(d.exists() and any(d.iterdir()) for d in (run_dir, ck_dir)):
        raise SystemExit(f"REFUSING: {run_dir} or {ck_dir} is not empty (new --run name, or --resume)")
    if (run_dir / "STOP").exists():
        raise SystemExit(f"REFUSING: {run_dir / 'STOP'} exists (delete it first)")
    run_dir.mkdir(parents=True, exist_ok=True)
    ck_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    stamp = f"_{int(time.time())}" if a.resume else ""
    (run_dir / f"runtime{stamp}.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    (run_dir / f"config{stamp}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    log = R.Log(run_dir)
    log(f"[loop] {'RESUME' if a.resume else 'START'} {a.run} pid {os.getpid()} config sha {R.config_sha(cfg)[:12]} "
        f"spool {a.spool} weights {a.weights} deterministic {torch.are_deterministic_algorithms_enabled()}")
    (run_dir / "pid.json").write_text(json.dumps({"learner": os.getpid()}), encoding="utf-8")
    L = None
    try:
        L = LoopLearner(cfg, a.run, run_dir, ck_dir, log, a.resume, a.spool, a.weights)
        if not a.resume:
            L.fresh_start()
        log(f"[loop] pushed {L.push().name} (update {L.update})")
        code, why = L.loop()
        return code
    except SystemExit as exc:                                 # STOP file, refused config: no crash save
        log(f"[loop] STOP: {exc}")
        return 0 if "STOP file" in str(exc) else 2
    except BaseException as exc:
        log(f"[loop] CRASH: {exc!r}\n{traceback.format_exc()}")
        if L is not None:
            try:
                log(f"[loop] crash save {L.crash_save(traceback.format_exc())}")
            except Exception as e2:
                log(f"[loop] crash save failed: {e2!r}")
        return 3
    finally:
        (run_dir / "pid.json").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())

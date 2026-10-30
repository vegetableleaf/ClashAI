"""FAST-LIVEOPP: a compare.py message with the 'live'-policy CLXIII partner (PLATEAU.md's next experiment): a dumped
opponent-arm fastloop message whose base gets the live config's partner keys (league_frozen_opponent, league_opp_policy
live, league_opp_live: read from a run's config.yaml) and whose jobs[:N] all play that frozen CLXIII as rl_royale's
sample_matchups draws it (spec opp = adaptive_opponents.opponent_pool's frozen entry, type "frozen" = the type
live_opp_cfg merges league_opp_live for; opp_deck = ICEBOW_DECK). Run from the repo root (imports pipeline).

    python msg_live.py MSG.pkl CONFIG.yaml OUT.pkl [--jobs 16]
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import yaml

KEYS = ("league_frozen_opponent", "league_opp_policy", "league_opp_live")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("config")
    ap.add_argument("out")
    ap.add_argument("--jobs", type=int, default=16)
    a = ap.parse_args(argv)
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    cfg = yaml.safe_load(Path(a.config).read_text())
    base = {**{k: v for k, v in base.items() if k != "league_exploiters"}, **{k: cfg[k] for k in KEYS}}
    if base.get("opp_init") and not Path(base["opp_init"]).exists():   # the dump pod's absolute path: this tree's copy (sd = its weights)
        base["opp_init"] = str(Path("opp_ckpt", Path(base["opp_init"]).name).resolve())
    stale = {k: v for k, v in base.items() if isinstance(v, str) and v.startswith("/workspace/") and not Path(v).exists()}
    if stale:
        raise SystemExit(f"base paths missing on this pod: {stale}")
    from pipeline.adaptive_opponents import opponent_pool
    from pipeline.rl_royale import ICEBOW_DECK
    opp = opponent_pool([], cfg, {})[0]                      # production's frozen entry (id "frozen:PATH", no cfg)
    out = []
    for job in jobs[:a.jobs]:                                # sample_matchups: a frozen opponent plays ICEBOW_DECK
        i, spec, k, *rest = job
        spec = {**spec, "opp": opp, "opp_deck": ICEBOW_DECK["engine"], "opp_deck_name": ICEBOW_DECK["name"]}
        out.append((i, spec, k, *rest))
    Path(a.out).write_bytes(pickle.dumps((base, update, sd, out)))
    print({k: base[k] for k in KEYS[:2]}, len(out), "jobs; opp", out[0][1]["opp"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

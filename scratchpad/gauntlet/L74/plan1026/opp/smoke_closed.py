"""P2-OPP: a few closed-loop games of ONE opponent vs CLXIII through the exact gap.py D3 worker command run_closed.sh uses
(live stack, all16 levels, the live census file), for a smoke before a 480-game block.  Pod, from the code copy root:

    ROYALE_ENGINE=crforge ... python scratchpad/gauntlet/L74/plan1026/opp/smoke_closed.py --opp opp_ckpt/X.pt --out /abs/dir \
        [--seeds 741200,741201] [--opp-T 1.0] [--extra "..."]

Writes OUT/inputs (gap.prepare) and OUT/D3/00000/matches.jsonl (+ .log); prints the command and a one-line summary per game.
Env = run_closed.sh's (set by the caller)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / "scratchpad/gauntlet/L74/gap")]
import gap  # noqa: E402

G = "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"
EX = ("--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log "
      "--record-board")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opp", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seeds", default="741200,741201")
    ap.add_argument("--opp-T", type=float, default=1.0)
    ap.add_argument("--extra", default="")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    plan = gap.prepare(a.out / "inputs", G, 741200, a.opp, a.opp_T, str(ROOT / "scratchpad/gauntlet/L74/mix/decks_live_eval.json"))
    job = dict(plan["jobs"][0], seeds=[int(s) for s in a.seeds.split(",")])
    dest = a.out / "D3" / "00000"
    (a.out / "D3").mkdir(parents=True)
    cmd = gap.command("D3", job, a.out / "inputs" / plan["censuses"][job["census"]]["path"], dest, a.python,
                      (EX + " " + a.extra).split(), (), (), "all16")
    print(" ".join(map(str, cmd)), flush=True)
    with dest.with_suffix(".log").open("w") as log:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    rows = [json.loads(s) for s in (dest / "matches.jsonl").read_text().splitlines() if s.strip()] if (dest / "matches.jsonl").exists() else []
    for r in rows:
        opp = [p for p in r.get("hab", {}).get("opp", [])]
        print(json.dumps({"seed": r["seed"], "outcome": r["outcome"], "end_tick": r["end_tick"], "plays": r["plays_attempted"],
                          "opp_accepted": r["opp_plays_accepted"], "opp_hab_plays": len(opp), "deck": r.get("opp_deck_name")}))
    print(json.dumps({"rc": rc, "rows": len(rows)}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

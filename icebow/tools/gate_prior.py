"""FIT the WHEN-TO-PLAY prior `P(play in one decision | elixir bucket, phase)` from pro replays.

Owner ruling 2026-09-02 08:20 (HANDOFF 6): the 18k PPO run's elixir>=6 fraction fell 2% -> 0.02%,
three wait-side reward terms are dead at 3 seeds, so the repair is to teach WHEN-NOT-TO-PLAY from a
source that knows. This is v0 of that source: a tabular prior read straight off the crawled
player's own play timeline, consumed by `train_sim_ppo.py` as a KL/cross-entropy term on the GATE
head only (`sim.ppo_gate_prior_coef`, default 0.0 = off).

    python tools/gate_prior.py --report                        # numbers only
    python tools/gate_prior.py --out config/gate_prior.json    # what the trainer reads

HOW THE ELIXIR IS KNOWN. The replay payload carries every play by both sides with its tick, but no
elixir. The crawled player's elixir is RECONSTRUCTED: start at 5, regenerate at the engine's own
four-phase rate (1/2.8, 1/1.4, 1/0.93 per second; `engine.elixir_rate`), cap at 10, subtract the
CardDB cost of each play (champion abilities priced as abilities). Its error is measured, not
assumed: the share of plays where the reconstructed elixir is BELOW the card's cost (impossible in
the real game) is printed and stored -- 1.7% on the icebow corpus, 2.8% on hogeq (2026-09-02).

WHAT THE TABLE IS. For every `dt`-second decision window of every crawled-side timeline (dt =
`sim.agent_dt`, the trainer's own cadence, so the prior is P(play) PER DECISION, the same event
the gate head models): the elixir bucket at the window's start (floor, 0..10), the phase (single /
double / triple, the ENGINE's boundaries, not a guess) and whether a card was played inside it.
Both corpora show the same shape (2026-09-02): in single elixir pros play in ~4-8% of windows at
3-7 elixir and ~20-25% at 9 -- they BANK. The 18k agent spent 0.02% of its steps at >= 6.

THE THIRD KEY (schema 2, `--pressure-s W`, HANDOFF 5bw/5bx). The ruling's v0 also named
threat-on-our-half, and the docstring above used to say that needed an engine pass -- it does not:
the OPPONENT's plays are in the same CSV. "Pressure" = the opponent played a TROOP (CardDB kind,
not a spell or building) within the last W seconds of the window's start. The measured split
(2026-09-03, W=6, single elixir, 5/6/7 elixir): pros play in 2.4/3.0/2.9% of QUIET windows vs
8.6/6.8/6.6% under PRESSURE, so the blended table pulled "wait" twice as hard on pressured rows
(where PPO is right to play) and half as hard on quiet ones (where banking happens). Schema 2
keeps `p_play` (the blend, byte-identical to schema 1) and adds `p_play_by_pressure[phase]
["quiet"|"pressure"][bucket]`; the trainer reads the split only when `sim.ppo_gate_prior_pressure_s`
matches the table's W, and the sim-side key is "a living enemy TROOP younger than W s"
(`SimMatchEnv.enemy_troop_min_age`), the same event.

WHAT IT IS NOT. Not an imitation target for WHICH card or WHERE -- the card/cell heads are
untouched. Not a threat-on-OUR-half test (a troop played anywhere counts): the CSV has tiles, but
the sim key must be computable in the worker from the engine alone, and the two must agree.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clashrl.config import Config                                    # noqa: E402
from clashrl import cards as _cards                                  # noqa: E402

PHASES = ("single", "double", "triple")
N_BUCKETS = 11          # floor(elixir) 0..10
PRESSURE_KEYS = ("quiet", "pressure")
MIN_CELL_N = 30         # a conditioned cell thinner than this falls back to the blended p_play


def _rate(t: float, reg: float, ot: float) -> float:
    """engine.elixir_rate, byte for byte in meaning: double from reg-60 THROUGH overtime, triple
    only in overtime's last minute."""
    if t >= reg + max(0.0, ot - 60.0):
        return 1.0 / 0.93
    if t >= reg - 60.0:
        return 1.0 / 1.4
    return 1.0 / 2.8


def _phase(t: float, reg: float, ot: float) -> str:
    if t >= reg + max(0.0, ot - 60.0):
        return "triple"
    return "double" if t >= reg - 60.0 else "single"


def _base(slug: str) -> str:
    return re.sub(r"-ev\d+$|-hero$", "", slug)


def _is_troop(db, slug: str, unknown: Counter) -> bool:
    """The opponent-side classifier of the pressure key. CardDB kind; a card the DB does not know
    is COUNTED (reported) and treated as a troop, the majority class."""
    k = db.kind(_base(slug).replace("-", "_"))
    if k is None:
        unknown[slug] += 1
        return True
    return k == "troop"


def fit(src: Path, cfg, db, side: str = "blue", pressure_s: float = 0.0):
    dt = float(cfg.get("sim", "agent_dt", default=0.6))
    reg = float(cfg.get("sim", "regulation_s", default=180.0))
    ot = float(cfg.get("sim", "overtime_s", default=120.0))
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    by = defaultdict(list)
    for r in rows:
        by[r["replay_tag"]].append(r)
    windows = {ph: [0] * N_BUCKETS for ph in PHASES}      # count of decision windows
    plays = {ph: [0] * N_BUCKETS for ph in PHASES}        # ...in which the pro played
    # ...split by the PRESSURE key (schema 2 only; [quiet, pressure] per phase)
    windows_p = {ph: [[0] * N_BUCKETS for _ in PRESSURE_KEYS] for ph in PHASES}
    plays_p = {ph: [[0] * N_BUCKETS for _ in PRESSURE_KEYS] for ph in PHASES}
    elx_at_play = Counter()
    unpriced: Counter = Counter()
    unknown_kind: Counter = Counter()
    n_plays = n_under = n_rep = 0
    other = "red" if side == "blue" else "blue"
    for tag, rs in by.items():
        mine = sorted((r for r in rs if r.get("attr_s") == side), key=lambda r: float(r["seconds"]))
        if not mine:
            continue
        # the OPPONENT's troop plays (abilities and non-troops are not pressure)
        theirs = sorted(float(r["seconds"]) for r in rs
                        if r.get("attr_s") == other and r.get("attr_ability") != "1"
                        and r.get("attr_card") != "_invalid" and _is_troop(db, r["attr_card"], unknown_kind))
        seq = []
        for r in mine:
            if r.get("attr_ability") == "1" or r.get("attr_card") == "_invalid":
                # a champion ABILITY costs its own elixir; the only champion in either deck is the
                # Mighty Miner, so price the `_invalid` rows as its ability
                seq.append((float(r["seconds"]), "mighty_miner_ability"))
            else:
                seq.append((float(r["seconds"]), _base(r["attr_card"])))
        end = max(float(r["seconds"]) for r in rs) + dt
        n_rep += 1
        e, t, j, k = 5.0, 0.0, 0, 0
        while t < end:
            eb = min(N_BUCKETS - 1, int(math.floor(e + 1e-9)))
            ph = _phase(t, reg, ot)
            while k < len(theirs) and theirs[k] <= t:
                k += 1
            pres = int(pressure_s > 0.0 and k > 0 and t - theirs[k - 1] < pressure_s)
            played = 0
            t2, tt = t + dt, t
            while j < len(seq) and seq[j][0] < t2:
                pt, name = seq[j]
                e = min(10.0, e + _rate(tt, reg, ot) * (pt - tt))
                tt = pt
                cost = db.elixir(name)
                if cost is None:
                    unpriced[name] += 1
                    cost = 0
                n_plays += 1
                elx_at_play[min(10, int(e))] += 1
                if e + 1e-6 < cost:
                    n_under += 1
                e = max(0.0, e - cost)
                played = 1
                j += 1
            e = min(10.0, e + _rate(tt, reg, ot) * (t2 - tt))
            t = t2
            windows[ph][eb] += 1
            plays[ph][eb] += played
            windows_p[ph][pres][eb] += 1
            plays_p[ph][pres][eb] += played
    table = {ph: [plays[ph][b] / max(1, windows[ph][b]) for b in range(N_BUCKETS)] for ph in PHASES}
    out = {
        "schema": 1, "side": side, "dt": dt, "regulation_s": reg, "overtime_s": ot,
        "source": str(src), "replays": n_rep, "plays": n_plays,
        "reconstruction_under_cost_frac": n_under / max(1, n_plays),
        "unpriced": dict(unpriced),
        "elixir_at_play": {str(k): v for k, v in sorted(elx_at_play.items())},
        "windows": windows, "play_windows": plays, "p_play": table,
    }
    if pressure_s > 0.0:
        out["schema"] = 2
        out["pressure_s"] = float(pressure_s)
        out["unknown_kind"] = dict(unknown_kind)
        out["windows_by_pressure"] = {ph: dict(zip(PRESSURE_KEYS, windows_p[ph])) for ph in PHASES}
        out["play_windows_by_pressure"] = {ph: dict(zip(PRESSURE_KEYS, plays_p[ph])) for ph in PHASES}
        out["p_play_by_pressure"] = {
            ph: {key: [plays_p[ph][q][b] / windows_p[ph][q][b] if windows_p[ph][q][b] >= MIN_CELL_N
                       else table[ph][b] for b in range(N_BUCKETS)]
                 for q, key in enumerate(PRESSURE_KEYS)} for ph in PHASES}
    return out


def report(pr: dict) -> None:
    print(f"[gate-prior] {pr['replays']} replays, {pr['plays']} plays by the crawled side, dt {pr['dt']} s; "
          f"reconstructed elixir below cost on {100.0 * pr['reconstruction_under_cost_frac']:.1f}% of plays"
          f"{'  UNPRICED: ' + str(pr['unpriced']) if pr['unpriced'] else ''}")
    tot = sum(pr["elixir_at_play"].values())
    hi = sum(v for k, v in pr["elixir_at_play"].items() if int(k) >= 6)
    print(f"[gate-prior] share of plays made at >= 6 elixir: {100.0 * hi / max(1, tot):.0f}%")
    print(f"{'phase':<8}" + "".join(f"{b:>10d}" for b in range(N_BUCKETS)))
    for ph in PHASES:
        print(f"{ph:<8}" + "".join(f"{pr['p_play'][ph][b]:>10.3f}" for b in range(N_BUCKETS)))
        print(f"{'  n':<8}" + "".join(f"{pr['windows'][ph][b]:>10d}" for b in range(N_BUCKETS)))
    if pr.get("schema", 1) >= 2:
        print(f"[gate-prior] split by PRESSURE (opponent troop within {pr['pressure_s']:.0f} s)"
              f"{'  UNKNOWN KIND: ' + str(pr['unknown_kind']) if pr.get('unknown_kind') else ''}")
        for ph in PHASES:
            for key in PRESSURE_KEYS:
                n = sum(pr["windows_by_pressure"][ph][key])
                tot = max(1, sum(pr["windows"][ph]))
                print(f"{ph[:3] + '/' + key[:4]:<8}"
                      + "".join(f"{pr['p_play_by_pressure'][ph][key][b]:>10.3f}" for b in range(N_BUCKETS))
                      + f"   ({100.0 * n / tot:.0f}% of windows)")
                print(f"{'  n':<8}" + "".join(f"{pr['windows_by_pressure'][ph][key][b]:>10d}" for b in range(N_BUCKETS)))


def load_table(path: Path) -> dict:
    """The trainer's reader: {phase: [p_play per bucket]} plus dt / phase boundaries; schema 2
    adds p_play_by_pressure[phase][quiet|pressure] and pressure_s."""
    pr = json.loads(Path(path).read_text(encoding="utf-8"))
    assert pr.get("schema") in (1, 2), "unknown gate_prior schema"
    return pr


def prior_array(pr: dict, pressure_s: float = 0.0):
    """What the trainer indexes. pressure_s == 0: [phase, bucket] from p_play (schema 1 or 2,
    identical numbers). pressure_s > 0: [phase, pressure(0/1), bucket], and the table's own W
    must match -- a table fit at 6 s indexed by a 10 s sim key is a different prior."""
    import numpy as np
    if pressure_s <= 0.0:
        return np.asarray([pr["p_play"][p] for p in PHASES], np.float32)
    assert pr.get("schema") == 2, "gate prior: ppo_gate_prior_pressure_s > 0 needs a schema-2 table"
    assert abs(float(pr["pressure_s"]) - float(pressure_s)) < 1e-6, (
        f"gate prior: table fit at W={pr['pressure_s']} s, config asks {pressure_s} s")
    return np.asarray([[pr["p_play_by_pressure"][p][k] for k in PRESSURE_KEYS] for p in PHASES], np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/royaleapi/crawl2/plays_ext.csv")
    ap.add_argument("--side", default="blue", help="crawled player's side in the payload (blue)")
    ap.add_argument("--out", default=None, help="write the prior here (JSON), e.g. config/gate_prior.json")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--pressure-s", type=float, default=0.0,
                    help="schema 2: also split by 'opponent troop played within W s' (0 = schema 1)")
    a = ap.parse_args()
    cfg = Config.load(None)
    db = _cards.load(cfg)
    src = Path(a.src) if Path(a.src).is_absolute() else Path(cfg.path(a.src))
    pr = fit(src, cfg, db, side=a.side, pressure_s=a.pressure_s)
    if a.report or not a.out:
        report(pr)
    if a.out:
        out = Path(a.out) if Path(a.out).is_absolute() else Path(cfg.path(a.out))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(pr, indent=1), encoding="utf-8")
        print(f"[gate-prior] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

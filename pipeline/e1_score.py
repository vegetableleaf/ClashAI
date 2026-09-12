"""E1 option B scorer: read ``e1_eval`` output dirs, write a markdown + json report.

    icebow/.venv/Scripts/python.exe -m pipeline.e1_score scratchpad/gauntlet/L67/e1/baseline_k0/slot0 ^
        scratchpad/gauntlet/L67/e1/baseline_k0/slot1 --control none=scratchpad/gauntlet/L67/e1/ctrl_none/slot0,scratchpad/gauntlet/L67/e1/ctrl_none/slot1 ^
        --out scratchpad/gauntlet/L67/e1/score_baseline_k0

Reads every ``matches.jsonl`` line (a repeated (tag, k) keeps the LAST line and is counted). Reports:
  * W / D / L, winrate (a draw is not a win), and an ENTRY-CLUSTERED bootstrap 95% CI: resample entries (tags) with
    replacement, statistic = mean over sampled entries of the entry's mean win over its seeds (10,000 draws, fixed
    seed). The unclustered normal-approximation interval is printed beside it for contrast only.
  * winrate per seed k and per slot; winrate over matches decided BEFORE the ghost script ended
    (``after_script`` False = end tick <= last ghost tick + 200) and the share of wins that came after it;
  * wins bucketed by ghost plays DELIVERED (<=10 / 11-30 / >30) and by distinct ghost cards delivered (<=3 / 4-6 / >6);
  * wins where the real pro LOST that replay; plays/min, accepted/min, accepted fraction, anti-stall fires;
  * with ``--control LABEL=DIR[,DIR]``: the paired comparison by (tag, k) -- 2x2 table, exact McNemar, paired winrate
    delta with an entry-clustered bootstrap CI, survival (seconds) delta +- SE, plays/min on both sides.
  * parity lines (``--mode parity``) are summarised separately: hash matches / n and the mismatching tags.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

DRAWS = 10_000
BOOT_SEED = 20260912


def read_dirs(dirs: Iterable[Path]) -> tuple[list[dict], list[dict], int]:
    """-> (eval lines, parity lines, duplicates dropped). Last line wins for a repeated (tag, k[, mode])."""
    ev: dict[tuple, dict] = {}
    par: dict[tuple, dict] = {}
    dup = 0
    for d in dirs:
        p = Path(d) / "matches.jsonl"
        if not p.exists():
            raise SystemExit(f"no matches.jsonl in {d}")
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("mode") == "liveness":
                continue
            key = (str(r["tag"]), int(r.get("k", 0)))
            tgt = par if r.get("mode") == "parity" else ev
            dup += int(key in tgt)
            tgt[key] = r
    return list(ev.values()), list(par.values()), dup


def win(r: dict) -> float:
    return 1.0 if r["outcome"] == "win" else 0.0


def cluster_bootstrap(by_entry: dict[str, list[float]], draws: int = DRAWS, seed: int = BOOT_SEED) -> dict:
    """Entry-clustered percentile bootstrap of the mean of per-entry means."""
    tags = sorted(by_entry)
    if not tags:
        return {"point": None, "lo": None, "hi": None, "n_entries": 0}
    means = np.array([float(np.mean(by_entry[t])) for t in tags], dtype=np.float64)
    rng = np.random.default_rng(seed)
    n = len(means)
    stats = np.empty(draws, dtype=np.float64)
    step = max(1, 2_000_000 // max(n, 1))          # bound the index matrix to ~16 MB
    for a in range(0, draws, step):
        b = min(draws, a + step)
        idx = rng.integers(0, n, size=(b - a, n))
        stats[a:b] = means[idx].mean(axis=1)
    return {"point": float(means.mean()), "lo": float(np.percentile(stats, 2.5)), "hi": float(np.percentile(stats, 97.5)),
            "n_entries": n, "draws": draws, "seed": seed}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p on the discordant pairs (b = run-only wins, c = control-only wins)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * p)


def bucket_delivered(n: int) -> str:
    return "<=10" if n <= 10 else ("11-30" if n <= 30 else ">30")


def bucket_distinct(n: int) -> str:
    return "<=3" if n <= 3 else ("4-6" if n <= 6 else ">6")


def _rate(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(win(r) for r in rows)
    return {"n": n, "wins": int(w), "winrate": (w / n) if n else None}


def summarise(lines: list[dict], draws: int = DRAWS, seed: int = BOOT_SEED) -> dict:
    n = len(lines)
    oc = Counter(r["outcome"] for r in lines)
    by_entry: dict[str, list[float]] = defaultdict(list)
    for r in lines:
        by_entry[r["tag"]].append(win(r))
    wr = (oc.get("win", 0) / n) if n else None
    se = math.sqrt(wr * (1 - wr) / n) if n else None
    wins = [r for r in lines if r["outcome"] == "win"]
    before = [r for r in lines if not r.get("after_script")]
    minutes = sum(float(r["seconds"]) for r in lines) / 60.0
    att = sum(int(r.get("plays_attempted", 0)) for r in lines)
    acc = sum(int(r.get("plays_accepted", 0)) for r in lines)
    buckets = {}
    for name, fn, field in (("ghost_delivered", bucket_delivered, "ghost_delivered"),
                            ("ghost_distinct_delivered", bucket_distinct, "ghost_distinct_delivered")):
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in lines:
            groups[fn(int(r.get(field, 0)))].append(r)
        order = ("<=10", "11-30", ">30") if name == "ghost_delivered" else ("<=3", "4-6", ">6")
        buckets[name] = {b: {**_rate(groups.get(b, [])),
                             "share_of_wins": (sum(win(r) for r in groups.get(b, [])) / len(wins)) if wins else None}
                         for b in order}
    real_loss = [r for r in lines if r.get("real_outcome") == "loss"]
    deg_bad = sum(1 for r in lines if r.get("degraded_equals_decisions") is False)
    return {
        "matches": n, "entries": len(by_entry), "W": oc.get("win", 0), "D": oc.get("draw", 0), "L": oc.get("loss", 0),
        "winrate": wr, "winrate_entry_weighted": cluster_bootstrap(by_entry, draws, seed),
        "unclustered_normal_95": ([wr - 1.96 * se, wr + 1.96 * se] if n else None),
        "per_seed": {str(k): _rate([r for r in lines if int(r["k"]) == k]) for k in sorted({int(r["k"]) for r in lines})},
        "per_slot": {str(s): _rate([r for r in lines if r.get("slot") == s]) for s in sorted({r.get("slot") for r in lines}, key=str)},
        "decided_before_script_end": _rate(before),
        "wins_after_script": sum(1 for r in wins if r.get("after_script")),
        "share_of_wins_after_script": (sum(1 for r in wins if r.get("after_script")) / len(wins)) if wins else None,
        "buckets": buckets,
        "wins_where_real_pro_lost": sum(1 for r in real_loss if r["outcome"] == "win"),
        "matches_where_real_pro_lost": len(real_loss),
        "plays_per_min": (att / minutes) if minutes else None, "accepted_per_min": (acc / minutes) if minutes else None,
        "accepted_fraction": (acc / att) if att else None,
        # rate-matched random control: attempted plays per decision that HAD an allowed (affordable, in-hand) slot --
        # the per-decision probability that makes `--policy random` (affordability-masked) attempt as often
        "suggested_p_random": (att / max(1, sum(int(r.get("decisions", 0)) - int(r.get("no_affordable", 0)) for r in lines)))
        if any("decisions" in r for r in lines) else None,
        "plays_attempted_per_match": att / n if n else None, "plays_accepted_per_match": acc / n if n else None,
        "stall_fired_per_match": (sum(int(r.get("stall_fired", 0)) for r in lines) / n) if n else None,
        "no_affordable_per_match": (sum(int(r.get("no_affordable", 0)) for r in lines) / n) if n else None,
        "mean_seconds": (sum(float(r["seconds"]) for r in lines) / n) if n else None,
        "mean_seconds_won": (sum(float(r["seconds"]) for r in wins) / len(wins)) if wins else None,
        "ghost_refused_per_match": (sum(int(r.get("ghost_refused", 0)) for r in lines) / n) if n else None,
        "ghost_undelivered_per_match": (sum(int(r.get("ghost_undelivered", 0)) for r in lines) / n) if n else None,
        "crowns_for_per_match": (sum(int(r["crowns_for"]) for r in lines) / n) if n else None,
        "crowns_against_per_match": (sum(int(r["crowns_against"]) for r in lines) / n) if n else None,
        "matches_degraded_count_ne_decisions": deg_bad,
        "wall_s_per_match": (sum(float(r.get("wall_s", 0)) for r in lines) / n) if n else None,
        "policies": dict(Counter(str(r.get("policy")) for r in lines)),
    }


def paired(run: list[dict], ctrl: list[dict], draws: int = DRAWS, seed: int = BOOT_SEED) -> dict:
    R = {(r["tag"], int(r["k"])): r for r in run}
    C = {(r["tag"], int(r["k"])): r for r in ctrl}
    keys = sorted(set(R) & set(C))
    both = run_only = ctrl_only = neither = 0
    diff_by_entry: dict[str, list[float]] = defaultdict(list)
    dsec = []
    for key in keys:
        a, b = win(R[key]), win(C[key])
        both += int(a and b)
        run_only += int(a and not b)
        ctrl_only += int(b and not a)
        neither += int(not a and not b)
        diff_by_entry[key[0]].append(a - b)
        dsec.append(float(R[key]["seconds"]) - float(C[key]["seconds"]))
    n = len(keys)
    mins_r = sum(float(R[k]["seconds"]) for k in keys) / 60.0
    mins_c = sum(float(C[k]["seconds"]) for k in keys) / 60.0
    return {
        "pairs": n, "entries": len(diff_by_entry), "run_only_in_run": len(set(R) - set(C)), "only_in_control": len(set(C) - set(R)),
        "both_win": both, "run_win_only": run_only, "control_win_only": ctrl_only, "neither": neither,
        "run_winrate": ((both + run_only) / n) if n else None, "control_winrate": ((both + ctrl_only) / n) if n else None,
        "delta_winrate": ((run_only - ctrl_only) / n) if n else None,
        "delta_entry_clustered": cluster_bootstrap(diff_by_entry, draws, seed),
        "mcnemar_exact_p": mcnemar_exact(run_only, ctrl_only),
        "survival_delta_s_mean": (float(np.mean(dsec)) if dsec else None),
        "survival_delta_s_se": (float(np.std(dsec, ddof=1) / math.sqrt(len(dsec))) if len(dsec) > 1 else None),
        "run_plays_per_min": (sum(int(R[k].get("plays_attempted", 0)) for k in keys) / mins_r) if mins_r else None,
        "control_plays_per_min": (sum(int(C[k].get("plays_attempted", 0)) for k in keys) / mins_c) if mins_c else None,
        "run_accepted_per_min": (sum(int(R[k].get("plays_accepted", 0)) for k in keys) / mins_r) if mins_r else None,
        "control_accepted_per_min": (sum(int(C[k].get("plays_accepted", 0)) for k in keys) / mins_c) if mins_c else None,
    }


def parity_summary(lines: list[dict]) -> dict:
    ok = [r for r in lines if r.get("hash_match")]
    return {"n": len(lines), "hash_match": len(ok), "opening_hash_match": sum(1 for r in lines if r.get("opening_hash_match")),
            "gate_19_of_20": (len(ok) >= math.ceil(0.95 * len(lines))) if lines else None,
            "per_slot": {str(s): sum(1 for r in ok if r.get("slot") == s) for s in sorted({r.get("slot") for r in lines}, key=str)},
            "mismatches": [{k: r.get(k) for k in ("tag", "slot", "end_tick", "corpus_tick", "terminated", "corpus_terminated",
                                                  "winner", "corpus_winner", "our_cmd_ok", "our_corpus_accepted", "ghost_ok",
                                                  "ghost_corpus_accepted", "corpus_rejected_by_reason")}
                           for r in lines if not r.get("hash_match")]}


def score(run_dirs: list[Path], controls: Optional[dict[str, list[Path]]] = None, draws: int = DRAWS,
          seed: int = BOOT_SEED) -> dict:
    ev, par, dup = read_dirs(run_dirs)
    rep = {"run_dirs": [str(d) for d in run_dirs], "duplicates_dropped": dup, "draws": draws, "boot_seed": seed}
    if ev:
        rep["run"] = summarise(ev, draws, seed)
    if par:
        rep["parity"] = parity_summary(par)
    rep["controls"] = {}
    for label, dirs in (controls or {}).items():
        cev, _, cdup = read_dirs(dirs)
        rep["controls"][label] = {"dirs": [str(d) for d in dirs], "duplicates_dropped": cdup,
                                  "summary": summarise(cev, draws, seed), "paired": paired(ev, cev, draws, seed)}
    return rep


def _pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{100.0 * v:.1f}%"


def _num(v, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


def to_markdown(rep: dict, title: str) -> str:
    L = [f"# {title}", "", f"Run dirs: {', '.join('`%s`' % d for d in rep['run_dirs'])}. Duplicates dropped: {rep['duplicates_dropped']}.",
         f"Bootstrap: entry-clustered, {rep['draws']} draws, seed {rep['boot_seed']}.", ""]
    s = rep.get("run")
    if s:
        ci = s["winrate_entry_weighted"]
        L += ["## Run", "",
              f"| matches | entries | W | D | L | winrate | entry-clustered 95% CI | unclustered normal 95% (contrast only) |",
              "|---|---|---|---|---|---|---|---|",
              f"| {s['matches']} | {s['entries']} | {s['W']} | {s['D']} | {s['L']} | {_pct(s['winrate'])} | "
              f"{_pct(ci['lo'])} .. {_pct(ci['hi'])} (entry-weighted {_pct(ci['point'])}) | "
              f"{_pct(s['unclustered_normal_95'][0])} .. {_pct(s['unclustered_normal_95'][1])} |", "",
              "| per seed k | n | winrate |", "|---|---|---|"]
        L += [f"| {k} | {v['n']} | {_pct(v['winrate'])} |" for k, v in s["per_seed"].items()]
        L += ["", "| per slot | n | winrate |", "|---|---|---|"]
        L += [f"| {k} | {v['n']} | {_pct(v['winrate'])} |" for k, v in s["per_slot"].items()]
        d = s["decided_before_script_end"]
        L += ["", f"Decided BEFORE the ghost script ended (end <= last ghost tick + 200): {d['wins']}/{d['n']} = {_pct(d['winrate'])}. "
                  f"Wins after the script ended: {s['wins_after_script']} ({_pct(s['share_of_wins_after_script'])} of wins).",
              f"Wins where the real pro lost: {s['wins_where_real_pro_lost']} of {s['matches_where_real_pro_lost']} such matches.", ""]
        for name, title2 in (("ghost_delivered", "ghost plays delivered"), ("ghost_distinct_delivered", "distinct ghost cards delivered")):
            L += [f"| {title2} | n | wins | winrate | share of wins |", "|---|---|---|---|---|"]
            L += [f"| {b} | {v['n']} | {v['wins']} | {_pct(v['winrate'])} | {_pct(v['share_of_wins'])} |" for b, v in s["buckets"][name].items()]
            L.append("")
        L += ["| plays/min | accepted/min | accepted frac | attempted/match | stall fires/match | no-affordable/match | mean s | mean s won | ghost refused/match | wall s/match |",
              "|---|---|---|---|---|---|---|---|---|---|",
              f"| {_num(s['plays_per_min'])} | {_num(s['accepted_per_min'])} | {_pct(s['accepted_fraction'])} | "
              f"{_num(s['plays_attempted_per_match'], 1)} | {_num(s['stall_fired_per_match'])} | {_num(s['no_affordable_per_match'], 1)} | "
              f"{_num(s['mean_seconds'], 1)} | {_num(s['mean_seconds_won'], 1)} | {_num(s['ghost_refused_per_match'])} | {_num(s['wall_s_per_match'], 1)} |",
              "", f"Matches whose degraded-observation count != decisions: {s['matches_degraded_count_ne_decisions']}. Policies: {s['policies']}.", ""]
    for label, c in rep.get("controls", {}).items():
        p = c["paired"]
        dc = p["delta_entry_clustered"]
        L += [f"## Paired vs control `{label}`", "",
              f"| pairs | entries | both win | run only | control only | neither | run WR | control WR | delta | clustered 95% CI | McNemar p | survival delta s |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|",
              f"| {p['pairs']} | {p['entries']} | {p['both_win']} | {p['run_win_only']} | {p['control_win_only']} | {p['neither']} | "
              f"{_pct(p['run_winrate'])} | {_pct(p['control_winrate'])} | {_pct(p['delta_winrate'])} | {_pct(dc['lo'])} .. {_pct(dc['hi'])} | "
              f"{p['mcnemar_exact_p']:.3g} | {_num(p['survival_delta_s_mean'], 1)} +- {_num(p['survival_delta_s_se'], 1)} |",
              "", f"Plays/min run {_num(p['run_plays_per_min'])} vs control {_num(p['control_plays_per_min'])}; "
                  f"accepted/min {_num(p['run_accepted_per_min'])} vs {_num(p['control_accepted_per_min'])}. "
                  f"Unpaired keys: run {p['run_only_in_run']}, control {p['only_in_control']}.", ""]
    if rep.get("parity"):
        q = rep["parity"]
        L += ["## Parity (design 6.2: need >= 19/20)", "",
              f"state_hash matches: **{q['hash_match']}/{q['n']}** (opening hash {q['opening_hash_match']}/{q['n']}); per slot {q['per_slot']}; "
              f"gate passed: {q['gate_19_of_20']}.", ""]
        if q["mismatches"]:
            L += ["Mismatches:", "", "```", *[json.dumps(m) for m in q["mismatches"]], "```", ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--control", action="append", default=[], help="LABEL=DIR[,DIR...]; repeatable")
    ap.add_argument("--out", type=Path, required=True, help="report path WITHOUT extension (.md and .json written)")
    ap.add_argument("--title", default="E1 option B -- S1 vs held-out ghosts (live rule)")
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--seed", type=int, default=BOOT_SEED)
    ap.add_argument("--force", action="store_true", help="overwrite an existing report")
    a = ap.parse_args(argv)
    md, js = a.out.with_suffix(".md"), a.out.with_suffix(".json")
    if (md.exists() or js.exists()) and not a.force:
        raise SystemExit(f"REFUSING to overwrite {md} / {js} (use --force)")
    controls = {}
    for spec in a.control:
        label, _, dirs = spec.partition("=")
        if not label or not dirs:
            raise SystemExit(f"bad --control {spec!r}; want LABEL=DIR[,DIR]")
        controls[label] = [Path(d) for d in dirs.split(",") if d]
    rep = score(a.run_dirs, controls, a.draws, a.seed)
    md.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    md.write_text(to_markdown(rep, a.title), encoding="utf-8")
    s = rep.get("run")
    print(json.dumps({"report": str(md), "matches": s and s["matches"], "winrate": s and s["winrate"],
                      "ci": s and [s["winrate_entry_weighted"]["lo"], s["winrate_entry_weighted"]["hi"]],
                      "parity": rep.get("parity", {}).get("hash_match")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

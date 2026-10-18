"""L74 combo eval report: win rates (paired vs Mark CXXXVIII and vs the control, same eval variant) + the spell numbers the
reward is about + the three reward-hacking detectors, from combo/chain.sh's evals (--spell-log --record-plays rows).
    python spell_report.py [ROOT]      ROOT default C:/Users/benpe/pod_backup_weekend/pod1018_combo (ROOT/<run>/eval_<v>/...)
Per (run, variant): wins / 960 and paired delta [95% CI] (heroiw/validate.paired_drift: pairs by census + seed, bootstrap
within census x side); per match: Rockets that landed, combos (a setup Tornado), troop elixir value hit, net reward at the
default weights (w 0.02), princess-in-blast Rockets, combos on my half / near my king. Hacking detectors:
  swarm      Rockets whose every hit body is worth < 1 elixir (>= 3 hit) -- Rocketing cheap swarms
  spend      Rockets / Tornados per match (own_plays) next to the win delta -- over-spending spells at the cost of wins
  wait       plays / match, crowns against, own tower hp at the end -- waiting for clumps instead of defending
Gap = Tornado landing tick - Rocket landing tick for every Rocket with a Tornado landing within 60 ticks (own_plays)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "heroiw"), str(HERE.parents[3])]
from validate import paired_drift  # noqa: E402
from pipeline.spell_value import match_summary  # noqa: E402

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "C:/Users/benpe/pod_backup_weekend/pod1018_combo")
RUNS = ("ref_cxxxviii", "combo_ctl", "combo_rew", "combo_ctl_pipe", "combo_rew_pipe")
VARIANTS = ("off", "offc", "on")
SEEDS = (741200, 742000)


def load(run, v):
    rows = []
    for s in SEEDS:
        p = ROOT / run / f"eval_{v}" / f"{run}_{s}" / "D3" / "matches.jsonl"
        if not p.is_file():
            return None
        rows += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return rows if len(rows) == 960 else None


def vs(base, rows):
    if base is None:
        return "-"
    try:
        d = paired_drift(base, rows, expected=960)
    except ValueError as exc:
        return f"unpaired ({exc})"
    return f"{d['delta_pp']:+.2f} [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]"


def per_match(rows):
    n = len(rows)
    s = [match_summary((r.get("spell") or {}).get("events")) for r in rows]
    tot = {k: sum(x[k] for x in s) for k in s[0]}
    own = [r.get("own_plays") or [] for r in rows]
    cnt = (lambda c: sum(sum(1 for q in o if q[2] == c and q[3]) for o in own) / n)
    gaps = []
    for o in own:
        rk = [q[1] for q in o if q[2] == "rocket" and q[3]]
        tn = [q[1] for q in o if q[2] == "tornado" and q[3]]
        for a in rk:
            near = [b - a for b in tn if abs(b - a) <= 60]
            if near:
                gaps.append(min(near, key=abs))
    return {"rockets": tot["rockets"] / n, "combos": tot["combos"] / n, "value": tot["value"] / n,
            "value_per_rocket": tot["value"] / max(tot["rockets"], 1), "reward": tot["reward"] / n,
            "misses": tot["misses"] / max(tot["rockets"], 1), "swarm": tot["swarm"] / max(tot["rockets"], 1),
            "princess": tot["princess"] / n, "combo_my_half": tot["combo_my_half"] / n,
            "near_my_king": tot["near_my_king"] / n, "rocket_plays": cnt("rocket"), "tornado_plays": cnt("tornado"),
            "plays": sum(r["plays_accepted"] for r in rows) / n,
            "crowns_against": sum(r["crowns_against"] for r in rows) / n,
            "own_tower_hp": sum(r["tower_hp_for"] for r in rows) / n, "logged": sum("spell" in r for r in rows),
            "gaps": gaps}


data = {(r, v): load(r, v) for r in RUNS for v in VARIANTS}
print(f"ROOT {ROOT}")
for v in VARIANTS:
    print(f"\n== eval {v}  (paired deltas in pp, 960 games)")
    print(f"{'run':16} {'wins':>5} {'vs CXXXVIII':>22} {'vs ctl':>22} | rk/m comb/m val/rk  rew/m miss% swarm% prin/m "
          f"myhalf/m nearK/m | Rplays Tplays plays crA  ownHP | combo gaps")
    for r in RUNS:
        rows = data[(r, v)]
        if rows is None:
            continue
        m = per_match(rows)
        ctl = data[("combo_ctl_pipe" if r == "combo_rew_pipe" else "combo_ctl", v)] if r.startswith("combo_") else None
        g = sorted(m["gaps"])
        warn = "" if m["logged"] == 960 else f"  (only {m['logged']} rows carry 'spell': run the eval with --spell-log)"
        print(f"{r:16} {sum(x['outcome'] == 'win' for x in rows):5d} {vs(data[('ref_cxxxviii', v)], rows):>22} "
              f"{vs(ctl, rows) if r not in ('combo_ctl', 'combo_ctl_pipe') else '-':>22} | "
              f"{m['rockets']:.3f} {m['combos']:.3f} {m['value_per_rocket']:6.2f} {m['reward']:+.3f} {100 * m['misses']:5.1f} "
              f"{100 * m['swarm']:5.1f} {m['princess']:.3f} {m['combo_my_half']:.3f} {m['near_my_king']:.3f} | "
              f"{m['rocket_plays']:.3f} {m['tornado_plays']:.3f} {m['plays']:5.1f} {m['crowns_against']:.2f} "
              f"{m['own_tower_hp']:6.0f} | n {len(g)}: {g[:12]}{' ...' if len(g) > 12 else ''}{warn}")

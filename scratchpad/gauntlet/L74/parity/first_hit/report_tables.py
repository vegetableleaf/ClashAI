"""Part A report: priority-card table + full unit table (markdown) from the three decoded cards.json files.

    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/first_hit/report_tables.py
writes TABLE_FULL.md next to it and prints the priority table. Reads decoded JSON only.
"""
from __future__ import annotations

import json
from pathlib import Path

import measure as m
import table_compare as tc

HERE = Path(__file__).resolve().parent
PRIORITY = ["Xbow", "Tesla", "Tesla_EV1", "IceWizard", "Knight", "Knight_EV1", "Skeleton", "Skeleton_EV1",
            "MegaKnight", "SkeletonBalloon", "Balloon", "MiniPekka", "Barbarian", "AngryBarbarian", "RageBarbarian",
            "IceWizardHero", "ElixirGolem1", "Firecracker", "Golem", "Golemite", "ElixirGolem", "ElixirGolemite", "Witch", "Prince", "Recruit",
            "Giant", "BattleRam", "RamRider", "NightWitch", "DarkWitch", "Valkyrie", "HogRider", "RoyalHog", "Musketeer",
            "Wizard", "LavaHound", "MinionGiant", "Ronin", "MiniZapMachine", "GoblinDummy", "ZapMachine", "Berserker",
            "SkeletonKing", "Minion", "MinionHorde", "LittlePrince", "ThreeMusketeers", "Bowler", "ElectroWizard"]


def fmt(u):
    if u is None:
        return "-"
    lt, hs, dp = u.get("load_time_ms"), u.get("hit_speed_ms"), u.get("deploy_time_ms")
    return f"{lt}/{hs}/{dp}" + ("/LFH" if u.get("load_first_hit") else "")


def main():
    old = json.load(open(m.SIM_OLD, encoding="utf-8"))
    new = json.load(open(m.SIM_NEW, encoding="utf-8"))
    live = json.load(open(m.LIVE, encoding="utf-8"))
    uo, un, ul = tc.all_units(old), tc.all_units(new), tc.all_units(live)
    names = sorted(set(uo) | set(un) | set(ul))
    lines = ["| unit | 15.535 (wheel default) LT/HS/Deploy | 16.402.19 (runtime table) | live 160402012+device | 15.535 vs live | runtime vs live |",
             "|---|---|---|---|---|---|"]
    for n in names:
        a, b, c = uo.get(n), un.get(n), ul.get(n)
        keys = ("load_time_ms", "hit_speed_ms", "deploy_time_ms", "load_first_hit")
        fa = "MISMATCH" if a and c and any(a.get(k) != c.get(k) for k in keys) else ("" if a and c else "n/a")
        fb = "MISMATCH" if b and c and any(b.get(k) != c.get(k) for k in keys) else ("" if b and c else "n/a")
        lines.append(f"| {n} | {fmt(a)} | {fmt(b)} | {fmt(c)} | {fa} | {fb} |")
    (HERE / "TABLE_FULL.md").write_text("Columns are LoadTime/HitSpeed/DeployTime in ms (LFH = LoadFirstHit). n/a = unit absent from that table.\n\n"
                                        + "\n".join(lines) + "\n", encoding="utf-8")
    print("units", len(names), "mismatch 15.535 vs live", sum("MISMATCH" in x.split("|")[5] for x in lines[2:]),
          "runtime vs live", sum("MISMATCH" in x.split("|")[6] for x in lines[2:]))
    print("\n| unit | 15.535 | 16.402.19 | live | flag |\n|---|---|---|---|---|")
    for n in PRIORITY:
        a, b, c = uo.get(n), un.get(n), ul.get(n)
        if not (a or b or c):
            continue
        flag = "15.535 differs" if a and c and fmt(a) != fmt(c) else ""
        print(f"| {n} | {fmt(a)} | {fmt(b)} | {fmt(c)} | {flag} |")


if __name__ == "__main__":
    main()

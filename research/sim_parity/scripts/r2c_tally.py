# -*- coding: utf-8 -*-
"""Write r2_troops_c_tally.json: per-key auditable-field counts for the troops_c group.
'fields_checked' counts only fields the WIKI PUBLISHES (so collision/mass/sight/load_time_s,
which come from the separate mechanics import and appear nowhere on the wiki, are excluded)."""
import json, io, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# key -> (matching auditable fields, note)
M = {
 "night_witch": (20, "full match incl. Bat sub-unit (1.3s / 1.2t / Very Fast 120 = 2.0 t-s) and "
                     "spawn cadence 5s / first wave 1s / 1 Bat on death"),
 "pekka":       (12, "damage 842 confirmed post-6/7/2026 +3%; range 1.2 post-4/2/2025"),
 "phoenix":     (14, "3 flagged: egg lifetime x2, reborn_frac"),
 "phoenix_egg": (0,  "only hitpoints is wiki-auditable, and it is flagged (239 vs 240 vs ~317)"),
 "prince":      (15, "charge_range 2.5 (post-6/10/2025) and charge_damage 783 both confirmed"),
 "princess":    (14, "deploy_time 1.2 already reflects 4/3/2025; splash 2.0, projectile 600"),
 "ram_rider":   (14, "4 flagged: hitpoints lag, hit_speed history conflict, rider attack, snare "
                     "duration. Ram body/charge numbers all match"),
 "rascals":     (18, "1 flagged: Rascal Boy hitpoints lag. Boy+Girl component stats all match"),
 "ronin":       (15, "full match. Page has NO vardefines (P1 structurally absent); level-11 row "
                     "is literal 1,779 / 371 / Dps(371,1.4)=265"),
 "royal_ghost": (13, "1 flagged: invisibility_time_s 1.8 -> 2.0"),
 "royal_giant": (14, "full match; the 2/3/2026 History entry is garbled and was resolved AGAINST "
                     "the history via rev 434690 (pre-change table read 1.7)"),
 "royal_hogs":  (12, "full match incl. Very Fast (120) = 2.0 t-s and Melee: Short (0.7)"),
 "royal_recruit": (9, "2 flagged (missing range_tiles, dps). Sourced from the PARENT page Royal "
                      "Delivery, section 'Royal Recruit Attributes'"),
 "royal_recruits": (13, "full match incl. shield 240 and Melee: Long (1.6)"),
 "rune_giant":  (10, "3 flagged: hitpoints lag, damage lag, entire enchant mechanic missing"),
 "skarmy_general": (10, "1 flagged: range_tiles 0.5 -> 1.6. Resolves the cards.yaml [verify] "
                        "marker; sourced from PARENT page Skeleton Army/Evolution, section "
                        "'General Gerry Attributes'"),
 "skeleton_army": (12, "full match"),
 "skeleton_barrel": (16, "1 low-priority ambiguity logged (0.5 vs 0.6 deploy cell); everything "
                         "else matches incl. death_damage 145 / radius 2.0 / 7 skeletons"),
 "skeleton_dragons": (12, "1 flagged: damage lag. The 6/4/2026 splash 1.5 + hit speed 2.0 changes "
                          "ARE correctly reflected"),
 "skeletons":   (12, "full match; 6/10/2025 hit speed 1.1 correctly reflected"),
 "sparky":      (14, "full match"),
 "spear_goblins": (12, "2 flagged: hit_speed 1.7 -> 1.6 and dependent dps 48 -> 51"),
 "spirit_empress": (8, "2 flagged: hitpoints (PIN) and damage 307 vs 309"),
 "spirit_empress_air": (7, "3 flagged: hitpoints (PIN), damage, hit_speed (PIN)"),
 "suspicious_bush": (12, "1 flagged: range_tiles. Bush Goblin sub-unit cadence/reach/speed match"),
 "three_musketeers": (7, "5 flagged -- the 3/11/2025 Elite Musketeer rework is unmodelled and the "
                         "row has no damage/dps/range_tiles/attacks at all"),
 "valkyrie":    (13, "full match"),
 "wall_breakers": (10, "1 flagged: damage lag 391 -> 313"),
 "witch":       (20, "full match incl. Skeleton sub-unit and 7s / 4-skeleton spawn cadence"),
 "wizard":      (14, "full match"),
 "zappies":     (13, "full match; 4/8/2026 hit speed 2.2 already correct in the KB"),
}

lines = [json.loads(l) for l in open(
    "C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_c.jsonl", encoding="utf-8")]
per_key_lines = Counter(d["key"] for d in lines)
verd = Counter(d["verdict"] for d in lines)
non_match_lines = sum(1 for d in lines if d["verdict"] != "match")

out = {}
for k, (m, note) in M.items():
    out[k] = {"fields_checked": m + sum(1 for d in lines
                                        if d["key"] == k and d["verdict"] != "match"),
              "matches": m, "flagged": per_key_lines.get(k, 0), "notes": note}

matches = sum(v["matches"] for v in out.values())
checked = sum(v["fields_checked"] for v in out.values())
out["_totals"] = {"keys_done": len(M), "fields_checked": checked, "matches": matches,
                  "flagged_lines": len(lines), "updates": verd["update"], "pins": verd["pin"],
                  "escalations": verd["escalate"], "resolved_match_lines": verd["match"],
                  "edit_war": "pass on all 29 pages (live revid == archived revid, "
                              "content byte-identical, refetched 2026-08-26)"}
json.dump(out, open("C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_c_tally.json",
                    "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(out["_totals"], indent=1))
assert checked == matches + non_match_lines, (checked, matches, non_match_lines)
print("consistency OK: checked == matches + non-match lines")

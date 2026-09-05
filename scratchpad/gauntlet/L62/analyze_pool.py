#!/usr/bin/env python
"""L62 -- measurements on the ghost pool + the corpus it was cut from.  Pure stdlib."""
from __future__ import annotations
import csv, json, statistics, collections, sys
from pathlib import Path

L62 = Path(__file__).resolve().parent
REPO = L62.parents[2]
sys.path.insert(0, str(L62))
from ghost_pool import load_pool, ghost_deck_key  # noqa: E402

pool = load_pool()
refused = json.loads((L62 / "refused.json").read_text())
battles = list(csv.DictReader((L62 / "snap" / "battles.csv").open(encoding="utf-8", newline="")))

R = {}
R["n_pool"] = len(pool)
R["result"] = dict(collections.Counter(r["result"] for r in pool))
R["mirror"] = sum(1 for r in pool if r["mirror"])
R["engine_verified"] = sum(1 for r in pool if r["engine_verified"])
ev = [r for r in pool if r["engine_verified"]]
R["engine_verified_position_based"] = sum(1 for r in ev if r["engine_verified"]["position_based"])
R["engine_verified_crowns_match"] = sum(1 for r in ev if r["engine_verified"]["crowns_match"])

# ---- refusals
R["refused_total"] = len(refused)
R["refused_by_reason"] = dict(collections.Counter(r["reason"].split(":")[0] for r in refused).most_common())
evo = collections.Counter(r["reason"].split(":")[1] for r in refused if r["reason"].startswith("no_native_evolution_form"))
R["refused_evo_slugs"] = dict(evo.most_common())
R["refused_hero"] = dict(collections.Counter(r["reason"].split(":")[1] for r in refused
                                             if r["reason"].startswith("no_native_hero_form")).most_common())

# ---- ghost deck diversity (pool)
keys = [ghost_deck_key(r) for r in pool]
freq = collections.Counter(keys)
R["distinct_ghost_decks"] = len(freq)
R["ghost_decks_seen_once"] = sum(1 for v in freq.values() if v == 1)
R["ghost_deck_freq_hist"] = dict(sorted(collections.Counter(freq.values()).items()))
R["top10_ghost_decks"] = [{"n": n, "deck": ",".join(s if f == "base" else s + "-" + f[:3] for s, f in k)}
                          for k, n in freq.most_common(10)]
cards = collections.Counter()
for r in pool:
    for c in r["ghost_deck"]:
        cards[(c["slug"], c["form"])] += 1
R["distinct_ghost_card_variants"] = len(cards)
R["distinct_ghost_card_base_slugs"] = len({s for s, f in cards})
R["top15_ghost_cards"] = [{"card": s if f == "base" else s + "-" + f[:3], "n_decks": n}
                          for (s, f), n in cards.most_common(15)]
R["ghost_cards_in_1_deck_only"] = sum(1 for v in cards.values() if v == 1)
R["distinct_opponent_players"] = len({r["opponent_tag"] for r in pool if r["opponent_tag"]})
R["distinct_icebow_players"] = len({r["player_tag"] for r in pool})

# ---- saturation: new distinct decks per battle, on the pool in timestamp order
ordered = sorted(pool, key=lambda r: (r["battle_timestamp"] if r["battle_timestamp"] != "" else 0))
seen = set(); curve = []
for i, r in enumerate(ordered, 1):
    seen.add(ghost_deck_key(r))
    if i in (50, 100, 200, 300, 444):
        curve.append({"battles": i, "distinct_decks": len(seen)})
R["saturation_pool"] = curve
R["new_deck_rate_last_100"] = round((curve[-1]["distinct_decks"] - curve[-2]["distinct_decks"]) /
                                    (curve[-1]["battles"] - curve[-2]["battles"]), 3)

# ---- diversity over the WHOLE corpus (what conversion would reach if positions were recovered)
allkeys = collections.Counter()
for b in battles:
    toks = tuple(sorted(t.strip() for t in b["opponent_deck"].split(",") if t.strip()))
    if len(toks) == 8:
        allkeys[toks] += 1
R["corpus_battles"] = len(battles)
R["corpus_distinct_ghost_decks"] = len(allkeys)
R["corpus_ghost_decks_seen_once"] = sum(1 for v in allkeys.values() if v == 1)
seen = set(); curve2 = []
ob = sorted(battles, key=lambda b: int(b["battle_timestamp"] or 0))
for i, b in enumerate(ob, 1):
    toks = tuple(sorted(t.strip() for t in b["opponent_deck"].split(",") if t.strip()))
    seen.add(toks)
    if i in (100, 250, 500, 750, 1000, len(ob)):
        curve2.append({"battles": i, "distinct_decks": len(seen)})
R["saturation_corpus"] = curve2

# ---- ratings
rated = [r["rating"] for r in pool if r["rating"] != ""]
R["rating_present"] = len(rated); R["rating_missing"] = len(pool) - len(rated)
if rated:
    s = sorted(rated)
    R["rating_stats"] = {"min": s[0], "p10": s[len(s)//10], "median": statistics.median(s),
                         "p90": s[int(len(s)*0.9)], "max": s[-1], "mean": round(statistics.mean(s), 1)}
    buckets = collections.Counter()
    for v in rated:
        buckets[(v // 500) * 500] += 1
    R["rating_buckets_500"] = {str(k): buckets[k] for k in sorted(buckets)}
ranks = [r["rank"] for r in pool if r["rank"] != ""]
R["rank_present"] = len(ranks)
if ranks:
    sr = sorted(ranks)
    R["rank_stats"] = {"min": sr[0], "median": statistics.median(sr), "max": sr[-1]}
R["opponent_rating_column_exists"] = any(k for k in battles[0] if "oppo" in k and "rating" in k)
R["battles_csv_columns"] = list(battles[0].keys())

# ---- command density
gp = [len(r["ghost_commands"]) for r in pool]
ip = [len(r["icebow_commands"]) for r in pool]
R["ghost_plays_per_match"] = {"mean": round(statistics.mean(gp), 2), "median": statistics.median(gp),
                              "min": min(gp), "max": max(gp), "total": sum(gp)}
R["icebow_plays_per_match"] = {"mean": round(statistics.mean(ip), 2), "median": statistics.median(ip),
                               "min": min(ip), "max": max(ip), "total": sum(ip)}
gaps = []
per_match_gap = []
for r in pool:
    ts = [c["tick"] for c in r["ghost_commands"]]
    if len(ts) >= 2:
        d = [(b - a) / 20.0 for a, b in zip(ts, ts[1:])]
        gaps.extend(d)
        per_match_gap.append(statistics.mean(d))
sg = sorted(gaps)
R["ghost_gap_seconds"] = {"n": len(gaps), "mean": round(statistics.mean(gaps), 2),
                          "median": round(statistics.median(gaps), 2),
                          "p10": round(sg[len(sg)//10], 2), "p90": round(sg[int(len(sg)*0.9)], 2),
                          "max": round(sg[-1], 2), "zero_gap_same_tick": sum(1 for g in gaps if g == 0)}
R["ghost_gap_mean_of_match_means"] = round(statistics.mean(per_match_gap), 2)
dur = [r["duration_ticks"] / 20.0 for r in pool]
R["match_seconds_last_play"] = {"mean": round(statistics.mean(dur), 1), "median": round(statistics.median(dur), 1),
                                "min": round(min(dur), 1), "max": round(max(dur), 1)}
R["ghost_ability_presses"] = sum(1 for r in pool for c in r["ghost_commands"] if c["ability"])
R["icebow_ability_presses"] = sum(1 for r in pool for c in r["icebow_commands"] if c["ability"])
R["matches_with_ghost_ability"] = sum(1 for r in pool if any(c["ability"] for c in r["ghost_commands"]))
R["ghost_cmds_unmapped_sim_key"] = sum(1 for r in pool for c in r["ghost_commands"] if c["sim_key"] is None and not c["ability"])
R["deck_cards_unmapped_sim_key"] = sorted({c["slug"] for r in pool for c in (r["ghost_deck"] + r["icebow_deck"])
                                           if c["sim_key"] is None})
# deal ambiguity
dc = [r["deal_candidates"]["0"] for r in pool]
R["ghost_deal_candidates"] = {"mean": round(statistics.mean(dc), 2), "median": statistics.median(dc),
                              "unique_1": sum(1 for v in dc if v == 1), "max": max(dc)}
# crowns
R["final_crowns_ghost"] = dict(sorted(collections.Counter(r["final_crowns"][0] for r in pool).items()))
R["final_crowns_icebow"] = dict(sorted(collections.Counter(r["final_crowns"][1] for r in pool).items()))
R["battle_types"] = dict(collections.Counter(r["battle_type"] for r in pool).most_common())

(L62 / "analysis.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
print(json.dumps(R, indent=1))

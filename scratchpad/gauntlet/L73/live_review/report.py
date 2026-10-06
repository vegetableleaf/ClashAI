"""Aggregate per_match.pkl -> results.json (+ facts printed). Run after run_all.py."""
import pickle, json, collections, statistics as st, sys
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review/"
allrows = pickle.load(open(HERE + "per_match.pkl", "rb"))
EXCL = [r["file"] for r in allrows if r["n_plays"] < 5 or r["result"] not in ("WIN", "LOSS")]
rows = [r for r in allrows if r["n_plays"] >= 5 and r["result"] in ("WIN", "LOSS")]
for r in rows:
    r["day"] = r["file"][10:18]; r["has_state"] = r["state_src"] in ("decision", "frame"); r["has_hand"] = r["state_src"] == "decision"
CHEAP = ("Skeletons", "Log", "Knight")
def mean(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 3) if v else None
def pct(a, b): return round(100.0 * a / b, 1) if b else None
def tag(r): return r["file"][10:25]

def phase_exposure(r):
    d = r["dur_s"]; return {"P1": min(d, 120), "P2": max(0, min(d, 180) - 120), "P3": max(0, d - 180), "T3": max(0, d - 240)}

def summarize(Q):
    n = len(Q); w = sum(r["result"] == "WIN" for r in Q)
    o = {"n": n, "W": w, "L": n - w, "winrate": pct(w, n), "dur_s": mean(r["dur_s"] for r in Q)}
    S = [r for r in Q if r["has_state"]]
    o["crowns_for"] = mean(r["crowns_me"] for r in S); o["crowns_against"] = mean(r["crowns_opp"] for r in S); o["n_state"] = len(S)
    for ph in ("P1", "P2", "P3", "T3"):
        pl = sum(r["an"]["phase_n"][ph] for r in Q); ex = sum(phase_exposure(r)[ph] for r in Q)
        ch = sum(r["an"]["phase_cheap"][ph] for r in Q)
        el = [e for r in Q for e in [r["an"]["phase_elixir"][ph]] if e is not None]
        o[ph] = {"plays": pl, "plays_per_min": round(60 * pl / ex, 2) if ex else None, "cheap_share_pct": pct(ch, pl),
                 "mean_elixir_at_play": round(sum(r["an"]["phase_elixir"][ph] * r["an"]["phase_n"][ph] for r in Q if r["an"]["phase_elixir"][ph] is not None) / max(pl, 1), 2)}
    for c in ("Rocket", "Xbow", "Tesla", "Log", "Knight", "Skeletons", "IceWizard", "Tornado"):
        o["per_match_" + c] = round(sum(sum(r["an"]["phase_plays"][p].get(c, 0) for p in ("P1", "P2", "P3")) for r in Q) / n, 2)
    o["abilities_per_match"] = round(sum(len(r["an"]["abil"]) for r in Q) / n, 2)
    H = [r for r in Q if r["has_hand"]]
    o["rocket_in_hand_pct_of_match"] = pct(sum(r["an"]["rocket_inhand_s"] for r in H), sum(r["dur_s"] for r in H))
    o["rocket_castable_pct_of_match"] = pct(sum(r["an"]["rocket_avail_s"] for r in H), sum(r["dur_s"] for r in H))
    o["rocket_matches_with_cast"] = sum(1 for r in Q if r["an"]["rockets"])
    o["no_crown_scored_pct"] = pct(sum(1 for r in S if r["crowns_me"] == 0), len(S))
    o["conceded_first_crown_pct"] = pct(sum(1 for r in S if r["an"]["first_crown"] and r["an"]["first_crown"][1] == "opp"), len(S))
    o["scored_first_crown_pct"] = pct(sum(1 for r in S if r["an"]["first_crown"] and r["an"]["first_crown"][1] == "me"), len(S))
    return o

R = {"scope": {"first_log": "live_play_20261004_205129", "n_logs_in_scope": len(allrows), "n_analysed": len(rows), "excluded": EXCL,
               "state_source_counts": dict(collections.Counter(r["state_src"] for r in rows))}}
# ----- per-model table
models = collections.defaultdict(list)
for r in rows: models[r["model"]].append(r)
R["per_model"] = {k: summarize(v) for k, v in models.items()}
r1 = [r for r in rows if r["model"] == "rseries_r1e31"]
R["r1e31_by_day"] = {d: summarize([r for r in r1 if r["day"] == d]) for d in sorted({r["day"] for r in r1})}
# R1e31 from the supervisor run vs the manual v7 etc.
R["by_result"] = {}
for model in ("rseries_r1e31", "tower_spatial_v7"):
    Q = [r for r in rows if r["model"] == model]
    R["by_result"][model] = {res: summarize([r for r in Q if r["result"] == res]) for res in ("WIN", "LOSS")}
R["by_result"]["ALL"] = {res: summarize([r for r in rows if r["result"] == res]) for res in ("WIN", "LOSS")}

# ----- pattern flags per match
def flags(r):
    a = r["an"]; f = {}
    xb = a["xbows"]; rk = a["rockets"]; br = a["barrels"]; wc = a["wincons"]
    f["rocket_never_cast"] = len(rk) == 0
    f["rocket_pinned_in_hand_ge80pct_and_never_cast"] = (len(rk) == 0 and r["has_hand"] and a["rocket_inhand_s"] >= 0.8 * r["dur_s"]) if r["has_hand"] else None
    f["no_rocket_on_tower"] = (not any((x["target"] or "").startswith("e") for x in rk)) if r["has_state"] else None
    if r["has_state"]:
        reach = [x for x in xb if x["reach"]]; non = [x for x in xb if not x["reach"]]
        f["xbow_ge2_reaching_none_defensive"] = len(reach) >= 2 and len(non) == 0
        f["xbow_any_nonreaching"] = len(non) > 0
        f["xbow_deadlane_any"] = any(x["lane_dead"] for x in xb)
        f["xbow_deadlane_at_1_1"] = any(x["lane_dead"] and x["crowns"] == (1, 1) for x in xb)
        f["xbow_deadlane_with_tesla"] = any(x["lane_dead"] and x["tesla_adj"] for x in xb)
        f["xbow_deadlane_tesla_at_1_1"] = any(x["lane_dead"] and x["tesla_adj"] and x["crowns"] == (1, 1) for x in xb)
        f["xbow_at_1_1_any"] = any(x["crowns"] == (1, 1) for x in xb)
        f["xbow_ge2_reaching_that_died_early_ge2"] = sum(1 for x in reach if x.get("killed_early")) >= 2
        fc = a["first_crown"]
        f["conceded_first_crown"] = bool(fc and fc[1] == "opp")
        f["scored_first_crown"] = bool(fc and fc[1] == "me")
        f["never_scored_a_crown"] = r["crowns_me"] == 0
        f["match_under_150s"] = r["dur_s"] < 150
        f["three_crowned"] = r["crowns_opp"] >= 3
    if r["has_hand"]:
        f["has_barrel"] = len(br) > 0
        f["barrel_logless_tower_hit"] = any((b["tower_dmg_frac_10s"] or 0) >= 0.05 and not b["log_responded"] for b in br)
        f["barrel_log_in_hand_not_cast_el_ge2"] = any(b["log_in_hand"] and b["elixir"] >= 2 and not b["log_responded"] for b in br)
        f["barrel_log_not_in_hand"] = any(not b["log_in_hand"] for b in br)
        f["wincon_with_no_tesla_board_or_hand"] = any(w["tesla_on_board"] == 0 and not w["tesla_in_hand"] for w in wc)
        f["wincon_tesla_absent_and_tower_hit"] = any(w["tesla_on_board"] == 0 and (w["tower_dmg_frac_15s"] or 0) >= 0.10 for w in wc)
    ab = a["abil"]
    f["ability_ge1_with_le1_enemy_near"] = any((x["enemies_near"] is not None and x["enemies_near"] <= 1) for x in ab) if r["has_state"] else None
    return f
for r in rows: r["flags"] = flags(r)
keys = sorted({k for r in rows for k in r["flags"]})
R["flags"] = {}
for k in keys:
    den_l = [r for r in rows if r["result"] == "LOSS" and r["flags"].get(k) is not None]
    den_w = [r for r in rows if r["result"] == "WIN" and r["flags"].get(k) is not None]
    nl = sum(1 for r in den_l if r["flags"][k]); nw = sum(1 for r in den_w if r["flags"][k])
    R["flags"][k] = {"losses": nl, "of_losses": len(den_l), "wins": nw, "of_wins": len(den_w),
                     "loss_rate_when_flag_pct": pct(nl, nl + nw), "examples_loss": [tag(r) for r in den_l if r["flags"][k]][:6]}

# ----- X-Bow / Rocket / barrel / Tesla / ability event tables
def evtab(res):
    Q = [r for r in rows if r["result"] == res and r["has_state"]]
    xs = [x for r in Q for x in r["an"]["xbows"]]
    o = {"matches": len(Q), "xbow_placements": len(xs), "reach": sum(x["reach"] for x in xs), "nonreach": sum(not x["reach"] for x in xs),
         "deadlane": sum(x["lane_dead"] for x in xs), "deadlane_tesla": sum(x["lane_dead"] and x["tesla_adj"] for x in xs),
         "deadlane_at_1_1": sum(x["lane_dead"] and x["crowns"] == (1, 1) for x in xs), "at_1_1": sum(x["crowns"] == (1, 1) for x in xs),
         "at_1_1_reach": sum(x["crowns"] == (1, 1) and x["reach"] for x in xs),
         "tesla_adjacent": sum(x["tesla_adj"] for x in xs),
         "reach_life_s": mean(x["life_s"] for x in xs if x["reach"]), "reach_died_early_pct": pct(sum(1 for x in xs if x["reach"] and x.get("killed_early")), sum(1 for x in xs if x["reach"])),
         "reach_tower_dmg_mean_pct": round(100 * mean(x["tower_dmg_frac"] for x in xs if x["reach"]), 1) if mean(x["tower_dmg_frac"] for x in xs if x["reach"]) is not None else None,
         "per_match": round(len(xs) / max(len(Q), 1), 2)}
    rk = [x for r in Q for x in r["an"]["rockets"]]
    o["rockets"] = len(rk); o["rocket_targets"] = dict(collections.Counter(x["target"] for x in rk))
    o["rocket_finishing_blows"] = sum(bool(x.get("killed_within_5s")) for x in rk)
    o["rocket_mean_elixir"] = mean(x["elixir"] for x in rk)
    o["rocket_tower_drop_mean_pct"] = round(100 * mean(x.get("tower_drop_frac") for x in rk if (x["target"] or "").startswith("e")), 1)
    o["rocket_phase"] = dict(collections.Counter(("P1" if x["sec"] < 120 else "P2" if x["sec"] < 180 else "P3") for x in rk))
    # >=2 rockets on same tower within a match
    o["matches_2plus_rockets_same_tower"] = sum(1 for r in Q if any(v >= 2 for v in collections.Counter(x["target"] for x in r["an"]["rockets"] if (x["target"] or "").startswith("e")).values()))
    H = [r for r in Q if r["has_hand"]]
    br = [b for r in H for b in r["an"]["barrels"]]
    o["barrels"] = len(br); o["matches_with_barrel"] = sum(1 for r in H if r["an"]["barrels"])
    o["barrel_log_in_hand"] = sum(bool(b["log_in_hand"]) for b in br); o["barrel_log_responded"] = sum(b["log_responded"] for b in br)
    o["barrel_log_in_hand_and_el_ge2_not_cast"] = sum(1 for b in br if b["log_in_hand"] and b["elixir"] >= 2 and not b["log_responded"])
    o["barrel_since_log_le10s"] = sum(1 for b in br if b["since_last_log_s"] is not None and b["since_last_log_s"] <= 10)
    o["barrel_tower_dmg_ge5pct"] = sum(1 for b in br if (b["tower_dmg_frac_10s"] or 0) >= 0.05)
    o["barrel_tower_dmg_mean_pct"] = round(100 * mean(b["tower_dmg_frac_10s"] for b in br), 1) if br else None
    o["barrel_dmg_when_log_responded_pct"] = round(100 * (mean(b["tower_dmg_frac_10s"] for b in br if b["log_responded"]) or 0), 1)
    o["barrel_dmg_when_no_log_pct"] = round(100 * (mean(b["tower_dmg_frac_10s"] for b in br if not b["log_responded"]) or 0), 1)
    o["barrel_mean_elixir"] = mean(b["elixir"] for b in br)
    wc = [w for r in H for w in r["an"]["wincons"]]
    o["wincons"] = len(wc); o["wincon_tesla_on_board"] = sum(w["tesla_on_board"] > 0 for w in wc)
    o["wincon_tesla_in_hand_only"] = sum(w["tesla_on_board"] == 0 and bool(w["tesla_in_hand"]) for w in wc)
    o["wincon_tesla_neither"] = sum(w["tesla_on_board"] == 0 and not w["tesla_in_hand"] for w in wc)
    o["wincon_tower_dmg_mean_pct"] = round(100 * mean(w["tower_dmg_frac_15s"] for w in wc), 1)
    ab = [a for r in Q for a in r["an"]["abil"]]
    o["abilities"] = len(ab); o["ability_enemies_near_mean"] = mean(a["enemies_near"] for a in ab)
    o["ability_le1_enemy_near"] = sum((a["enemies_near"] is not None and a["enemies_near"] <= 1) for a in ab)
    o["ability_elixir_mean"] = mean(a["elixir"] for a in ab)
    o["ability_kind"] = dict(collections.Counter(a["why"].split()[0] for a in ab))
    return o
R["events"] = {res: evtab(res) for res in ("WIN", "LOSS")}

# base rates for the Log claim (time share Log in hand / within 10 s of a Log play) over barrel matches handled in barrel_base.py
# ----- opponent cards: loss rate
cnt = collections.Counter(); lc = collections.Counter()
S = [r for r in rows if r["has_state"]]
for r in S:
    for c in set(r["an"]["enemy_cards"]): cnt[c] += 1; lc[c] += r["result"] == "LOSS"
R["opp_card_loss_rate"] = {c: {"n": n, "losses": lc[c], "loss_pct": pct(lc[c], n)} for c, n in cnt.items() if n >= 10}
R["base_loss_pct_state_matches"] = pct(sum(r["result"] == "LOSS" for r in S), len(S))
# time of first concession / first crown
tt = [r["an"]["first_crown"][0] / 20 for r in S if r["result"] == "LOSS" and r["an"]["first_crown"] and r["an"]["first_crown"][1] == "opp"]
R["first_conceded_tower_s"] = {"n": len(tt), "median": st.median(tt), "q": [round(x, 1) for x in st.quantiles(tt, n=4)]}
tw = [r["an"]["first_crown"][0] / 20 for r in S if r["result"] == "WIN" and r["an"]["first_crown"] and r["an"]["first_crown"][1] == "me"]
R["first_scored_tower_s_in_wins"] = {"n": len(tw), "median": st.median(tw), "q": [round(x, 1) for x in st.quantiles(tw, n=4)]}
R["final_crowns"] = {res: dict(collections.Counter("%d-%d" % (r["crowns_me"], r["crowns_opp"]) for r in S if r["result"] == res)) for res in ("WIN", "LOSS")}
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
INCOME = {"P1": 21.43, "P2": 42.86, "P3": 42.86, "T3": 64.29}  # elixir per minute at 1x / 2x / (2x until 240 s) / 3x
def spend_tab(Q):
    o = {}
    for ph in ("P1", "P2", "P3", "T3"):
        e = sum(phase_exposure(r)[ph] for r in Q); cnt = collections.Counter()
        for r in Q: cnt.update(r["an"]["phase_plays"][ph])
        n = sum(cnt.values()); sp = sum(COST[c] * v for c, v in cnt.items())
        o[ph] = {"mean_card_cost": round(sp / n, 2) if n else None, "elixir_spent_per_min": round(60 * sp / e, 1) if e else None, "income_per_min": INCOME[ph],
                 "le3_share_pct": pct(n - sum(cnt[c] for c in ("Tesla", "Xbow", "Rocket")), n),
                 "xbow_per_min": round(60 * cnt["Xbow"] / e, 2) if e else None, "tornado_per_min": round(60 * cnt["Tornado"] / e, 2) if e else None,
                 "tesla_per_min": round(60 * cnt["Tesla"] / e, 2) if e else None, "rocket_per_min": round(60 * cnt["Rocket"] / e, 3) if e else None}
    return o
R["spend"] = {res: spend_tab([r for r in rows if r["result"] == res]) for res in ("WIN", "LOSS")}
# tower race at 60/120/180 s (matches that lasted >= 180 s)
race = {}
for res in ("WIN", "LOSS"):
    Q = [r for r in rows if r["result"] == res and r["has_state"] and r["dur_s"] >= 180]
    o = {"n": len(Q)}
    for sec in (60, 120, 180):
        dd = []; dt_ = []
        for r in Q:
            tl = r["an"]["tower_tl"][sec]
            dd.append(sum(1 - (tl[k] if tl[k] is not None else 0) for k in ("eL", "eR")) / 2); dt_.append(sum(1 - (tl[k] if tl[k] is not None else 0) for k in ("mL", "mR")) / 2)
        o[str(sec)] = {"princess_hp_dealt_pct": round(100 * st.mean(dd), 1), "princess_hp_taken_pct": round(100 * st.mean(dt_), 1)}
    o["first_xbow_s"] = mean(min((x["sec"] for x in r["an"]["xbows"]), default=None) for r in Q)
    o["xbows_before_120s"] = mean(sum(1 for x in r["an"]["xbows"] if x["sec"] < 120) for r in Q)
    race[res] = o
R["tower_race"] = race
# base-rate checks for the Log / Tesla claims (state-time shares in the same matches that contain the event)
bm = [r for r in rows if r["has_hand"] and r["an"]["barrels"]]
tt = sum(r["an"]["base"]["t"] for r in bm)
brs = [b for r in bm for b in r["an"]["barrels"]]
R["barrel_base"] = {"matches": len(bm), "barrels": len(brs), "base_log_in_hand_pct": pct(sum(r["an"]["base"]["log_in_hand"] for r in bm), tt),
                    "at_barrel_log_in_hand_pct": pct(sum(bool(b["log_in_hand"]) for b in brs), len(brs)),
                    "base_within10s_after_own_log_pct": pct(sum(r["an"]["base"]["within10s_after_log"] for r in bm), tt),
                    "at_barrel_within10s_after_own_log_pct": pct(sum(1 for b in brs if b["since_last_log_s"] is not None and b["since_last_log_s"] <= 10), len(brs)),
                    "barrel_responded_pct_when_log_in_hand": pct(sum(1 for b in brs if b["log_in_hand"] and b["log_responded"]), sum(1 for b in brs if b["log_in_hand"])),
                    "barrel_responded_pct_when_log_in_hand_and_el_ge2": pct(sum(1 for b in brs if b["log_in_hand"] and b["elixir"] >= 2 and b["log_responded"]), sum(1 for b in brs if b["log_in_hand"] and b["elixir"] >= 2)),
                    "barrel_elixir_le2_pct": pct(sum(1 for b in brs if b["elixir"] < 2), len(brs))}
hm = [r for r in rows if r["has_hand"]]
tt2 = sum(r["an"]["base"]["t"] for r in hm); wcs = [w for r in hm for w in r["an"]["wincons"]]
R["wincon_base"] = {"base_tesla_on_board_pct_of_time": pct(sum(r["an"]["base"]["tesla_on_board"] for r in hm), tt2),
                    "at_wincon_tesla_on_board_pct": pct(sum(w["tesla_on_board"] > 0 for w in wcs), len(wcs)), "n_wincon_arrivals": len(wcs)}
on = [w for w in wcs if w["tesla_on_board"] > 0]; off = [w for w in wcs if w["tesla_on_board"] == 0]
R["wincon_base"]["tower_dmg_15s_mean_pct_tesla_on_board"] = round(100 * mean(w["tower_dmg_frac_15s"] for w in on), 1)
R["wincon_base"]["tower_dmg_15s_mean_pct_no_tesla_on_board"] = round(100 * mean(w["tower_dmg_frac_15s"] for w in off), 1)
R["wincon_base"]["n_on"] = len(on); R["wincon_base"]["n_off"] = len(off)
R["wincon_base"]["tower_hit_ge10pct_share_on"] = pct(sum(1 for w in on if (w["tower_dmg_frac_15s"] or 0) >= 0.10), len(on))
R["wincon_base"]["tower_hit_ge10pct_share_off"] = pct(sum(1 for w in off if (w["tower_dmg_frac_15s"] or 0) >= 0.10), len(off))
R["adjusted_final_blow_matches"] = sum(1 for r in rows if r.get("crowns_adjusted"))
R["derived_result_matches"] = sum(1 for r in rows if r["result_src"] == "derived")
# X-Bow failed offence -> what next
sw = {"W": collections.Counter(), "L": collections.Counter()}; sw_m = {"W": 0, "L": 0}; sw_examples = []
for r in rows:
    if not r["has_state"]: continue
    xs_ = sorted(r["an"]["xbows"], key=lambda x: x["tick"]); k = "W" if r["result"] == "WIN" else "L"
    fail_then_reach = False; consecutive = 0
    for i, x in enumerate(xs_):
        failed = x["reach"] and x.get("killed_early") and (x["tower_dmg_frac"] is None or x["tower_dmg_frac"] < 0.10)
        if failed:
            nxt = xs_[i + 1] if i + 1 < len(xs_) else None
            sw[k]["failed_reaching_xbow"] += 1
            sw[k]["next_none"] += nxt is None; sw[k]["next_reaching"] += bool(nxt and nxt["reach"]); sw[k]["next_nonreaching"] += bool(nxt and not nxt["reach"])
    nfail = sum(1 for x in xs_ if x["reach"] and x.get("killed_early") and (x["tower_dmg_frac"] is None or x["tower_dmg_frac"] < 0.10))
    if nfail >= 2 and not any(not x["reach"] for x in xs_):
        sw_m[k] += 1
        if k == "L" and len(sw_examples) < 6: sw_examples.append({"log": tag(r), "failed_reaching_xbows": nfail, "placements": [(round(x["sec"]), x["lane"]) for x in xs_]})
R["xbow_failed_offence"] = {"counts": {k: dict(v) for k, v in sw.items()}, "matches_ge2_failed_no_defensive": sw_m, "examples_loss": sw_examples}
# early collapse
def first_my_tower(r):
    ds = [r["dead"].get(k) for k in ("mL", "mR")]; ds = [d_ for d_ in ds if d_ is not None]
    return min(ds) / 20 if ds else None
R["early_collapse"] = {
    "losses_my_princess_down_before_90s": sum(1 for r in rows if r["result"] == "LOSS" and r["has_state"] and (first_my_tower(r) or 999) < 90),
    "wins_my_princess_down_before_90s": sum(1 for r in rows if r["result"] == "WIN" and r["has_state"] and (first_my_tower(r) or 999) < 90),
    "losses_ended_by_king_3crowns": sum(1 for r in rows if r["result"] == "LOSS" and r["has_state"] and r["crowns_opp"] >= 3),
    "king_after_princess_gap_s_median": None, "examples_3crown_under_150s": [(tag(r), round(r["dur_s"]), r["crowns_me"], r["crowns_opp"]) for r in rows if r["result"] == "LOSS" and r["dur_s"] < 150][:8]}
gaps = []
for r in rows:
    if r["result"] == "LOSS" and r["has_state"] and r["dead"].get("mK") is not None:
        ds = [r["dead"].get(k) for k in ("mL", "mR") if r["dead"].get(k) is not None]
        if ds: gaps.append((r["dead"]["mK"] - min(ds)) / 20)
if gaps: R["early_collapse"]["king_after_first_princess_gap_s_median"] = round(st.median(gaps), 1); R["early_collapse"]["n_king_losses"] = len(gaps)
# examples
ex = {}
ex["xbow_deadlane_at_1_1_loss"] = [{"log": tag(r), "sec": round(x["sec"]), "tick": x["tick"], "lane": x["lane"], "tesla_adjacent": x["tesla_adj"], "crowns": x["crowns"]}
                                    for r in rows if r["result"] == "LOSS" and r["has_state"] for x in r["an"]["xbows"] if x["lane_dead"] and x["crowns"] == (1, 1)][:8]
ex["barrel_log_in_hand_not_cast_loss"] = [{"log": tag(r), "sec": round(b["sec"]), "tick": b["tick"], "elixir": round(b["elixir"], 1), "lane": b["lane"], "tower_dmg_pct": round(100 * (b["tower_dmg_frac_10s"] or 0))}
                                           for r in rows if r["result"] == "LOSS" and r["has_hand"] for b in r["an"]["barrels"] if b["log_in_hand"] and b["elixir"] >= 2 and not b["log_responded"]][:6]
ex["barrel_no_log_big_hit_loss"] = [{"log": tag(r), "sec": round(b["sec"]), "tick": b["tick"], "log_in_hand": b["log_in_hand"], "elixir": round(b["elixir"], 1), "tower_dmg_pct": round(100 * (b["tower_dmg_frac_10s"] or 0))}
                                     for r in rows if r["result"] == "LOSS" and r["has_hand"] for b in r["an"]["barrels"] if (b["tower_dmg_frac_10s"] or 0) >= 0.25 and not b["log_responded"]][:6]
ex["rocket_loss"] = [{"log": tag(r), "sec": round(x["sec"]), "tick": x["tick"], "target": x["target"], "elixir": round(x["elixir"], 1)} for r in rows if r["result"] == "LOSS" and r["has_state"] for x in r["an"]["rockets"]][:8]
ex["wincon_no_tesla_big_hit_loss"] = [{"log": tag(r), "sec": round(w["sec"]), "tick": w["tick"], "card": w["name"], "lane": w["lane"], "tower_dmg_pct": round(100 * (w["tower_dmg_frac_15s"] or 0))}
                                       for r in rows if r["result"] == "LOSS" and r["has_hand"] for w in r["an"]["wincons"] if w["tesla_on_board"] == 0 and not w["tesla_in_hand"] and (w["tower_dmg_frac_15s"] or 0) >= 0.25][:6]
R["examples"] = ex
# ability confirmation
R["ability_total"] = {"presses": sum(len(r["an"]["abil"]) for r in rows), "confirmed": sum(r["abil_conf"] for r in rows)}
# per match compact table
def line(r):
    a = r["an"]; xb = a["xbows"]
    return {"log": r["file"], "model": r["model"], "res": r["result"], "src": r["result_src"], "dur_s": round(r["dur_s"]), "crowns": [r["crowns_me"], r["crowns_opp"]],
            "plays": r["n_plays"], "rockets": len(a["rockets"]), "xb": len(xb), "xb_reach": sum(1 for x in xb if x["reach"]), "xb_deadlane": sum(1 for x in xb if x["lane_dead"]),
            "barrels": len(a["barrels"]), "abil": len(a["abil"]), "first_crown": a["first_crown"], "flags": {k: v for k, v in r["flags"].items() if v}}
R["matches"] = [line(r) for r in rows]
json.dump(R, open(HERE + "results.json", "w"), indent=1, default=str)
print("ok", len(rows), "excluded", EXCL)

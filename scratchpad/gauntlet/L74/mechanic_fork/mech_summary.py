"""Summarise mech_fork runs: paired B - A per opportunity, 95% CIs clustered by match.

    python mech_summary.py RUN_DIR[,RUN_DIR...] [--json OUT]

Each run dir holds search_s0's matches.jsonl with a ``mech`` block per match (mech_fork.py).  An opportunity whose
mechanic decision equals the model's own (``same``) has B == A by construction: it enters the "all" rows as 0 and is
left out of the "forked" rows.  CI: cluster-robust (CR1) standard error of a mean, clusters = matches, +-1.96 SE."""
import json
import math
import sys
from pathlib import Path

METRICS = (("tower_diff", lambda s: s["hp_us"] - s["hp_them"]), ("hp_us", lambda s: s["hp_us"]),
           ("hp_them", lambda s: s["hp_them"]), ("el_us", lambda s: s["el_us"]), ("el_them", lambda s: s["el_them"]),
           ("u_us", lambda s: s["u_us"]), ("u_them", lambda s: s["u_them"]),
           ("crowns_diff", lambda s: s["cr_us"] - s["cr_them"]))
SCORE = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def cr_mean(vals, clusters):
    """-> (mean, half-width of the 95% CI, n, n_clusters); CR1 SE over ``clusters``."""
    n = len(vals)
    if n == 0:
        return None, None, 0, 0
    mu = sum(vals) / n
    g = {}
    for v, c in zip(vals, clusters):
        g[c] = g.get(c, 0.0) + (v - mu)
    C = len(g)
    if C < 2:
        return mu, None, n, C
    se = math.sqrt(sum(x * x for x in g.values()) * C / (C - 1)) / n
    return mu, 1.96 * se, n, C


def fmt(r, nd=3):
    mu, hw, n, C = r
    if mu is None:
        return "n/a"
    return f"{mu:+.{nd}f} [{mu - hw:+.{nd}f}, {mu + hw:+.{nd}f}] (n {n}, matches {C})" if hw is not None else f"{mu:+.{nd}f} (n {n})"


def main(argv):
    dirs = argv[0].split(",")
    rows = []
    for d in dirs:
        for ln in (Path(d) / "matches.jsonl").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                if not r.get("skipped"):
                    r["_cl"] = f"{d}|{r['tag']}"
                    rows.append(r)
    opps = [(r["_cl"], o) for r in rows for o in r["mech"]["opps"]]
    name = rows[0]["mech"]["name"] if rows else "?"
    out = {"mechanic": name, "matches": len(rows), "opportunities": len(opps),
           "trigger_decisions": sum(r["mech"]["trigger_decisions"] for r in rows),
           "matches_with_opportunity": sum(1 for r in rows if r["mech"]["opps"])}
    out["opps_per_match"] = out["opportunities"] / max(1, len(rows))
    forked = [(c, o) for c, o in opps if "Bres" in o]
    out["forked"] = len(forked)
    out["same_as_model"] = sum(1 for _, o in opps if o["same"])
    # faithfulness: A replayed from the snapshot vs the original continuation
    chk = [(c, o) for c, o in opps if "Acheck" in o]
    fa = {"n": len(chk), "n_matches": len({c for c, _ in chk})}
    for k in ("10", "20", "end"):
        fa[f"hash_equal_{k}"] = sum(o["Acheck"][k]["h"] == o["Ares"][k]["h"] for _, o in chk)
        fa[f"tower_hp_equal_{k}"] = sum((o["Acheck"][k]["hp_us"], o["Acheck"][k]["hp_them"]) ==
                                         (o["Ares"][k]["hp_us"], o["Ares"][k]["hp_them"]) for _, o in chk)
    fa["outcome_equal"] = sum(o["Acheck"]["outcome"] == o["Ares"]["outcome"] for _, o in chk)
    out["faithfulness"] = fa
    res = {}
    for scope, sel in (("forked", forked), ("all", opps)):
        cl = [c for c, _ in sel]
        block = {}
        for k in ("10", "20", "end"):
            for mname, f in METRICS:
                v = [(f(o["Bres"][k]) - f(o["Ares"][k])) if "Bres" in o else 0.0 for _, o in sel]
                block[f"{mname}@{k}"] = cr_mean(v, cl)
        v = [(SCORE[o["Bres"]["outcome"]] - SCORE[o["Ares"]["outcome"]]) if "Bres" in o else 0.0 for _, o in sel]
        block["result@end"] = cr_mean(v, cl)
        v = [((o["Bres"]["outcome"] == "win") - (o["Ares"]["outcome"] == "win")) if "Bres" in o else 0.0 for _, o in sel]
        block["win@end"] = cr_mean(v, cl)
        res[scope] = block
    out["B_minus_A"] = res
    # per-match expected effect: episodes per match x local win effect (first decision of each episode, same -> 0).
    # ponytail: additive model -- only meaningful while episodes per match stay ~1; re-armed forks are excluded.
    fe = [(c, o) for c, o in opps if o.get("first", True)]
    w = cr_mean([((o["Bres"]["outcome"] == "win") - (o["Ares"]["outcome"] == "win")) if "Bres" in o else 0.0
                 for _, o in fe], [c for c, _ in fe])
    out["episodes_per_match"] = len(fe) / max(1, len(rows))
    if w[0] is not None:
        k = out["episodes_per_match"]
        out["per_match_win_pp"] = (100 * k * w[0], None if w[1] is None else 100 * k * w[1])
    if name == "sneaky":
        sk = {}
        sk["B_lock"] = sum(bool(o["Bres"].get("lock")) for _, o in forked)
        sk["A_lock_forked"] = sum(bool(o["Ares"].get("lock")) for _, o in forked)
        sk["A_lock_all"] = sum(bool(o["Ares"].get("lock")) for _, o in opps)
        sk["B_lock_live"] = sum(bool(o["Bres"].get("lock_live")) for _, o in forked)
        sk["A_lock_live"] = sum(bool(o["Ares"].get("lock_live")) for _, o in forked)
        fo = lambda b: sorted(o[b]["first_on"] for _, o in forked if o[b].get("first_on") is not None)
        sk["first_on_median_ticks"] = {b: (v[len(v) // 2] if v else None, len(v)) for b, v in (("B", fo("Bres")), ("A", fo("Ares")))}
        sk["lock_live_diff"] = cr_mean([float(bool(o["Bres"].get("lock_live"))) - float(bool(o["Ares"].get("lock_live")))
                                        for _, o in forked], [c for c, _ in forked])
        sk["A_root_tornado"] = sum(o["A_card"] == "tornado" for _, o in opps)
        sk["A_tornado_2s"] = sum(bool(o.get("A_tornado_2s")) for _, o in opps)
        sk["king_touch"] = sum(bool((o.get("plan") or {}).get("king_touch")) for _, o in opps if isinstance(o.get("plan"), dict))
        sk["A_why"] = {}
        for _, o in opps:
            key = o["A"]["why"] + ":" + str(o["A_card"])
            sk["A_why"][key] = sk["A_why"].get(key, 0) + 1
        out["sneaky"] = sk
    if name == "patience":
        pt = {"near8": sum(bool(o.get("near8")) for _, o in opps), "A_card": {}, "held_decisions": {}}
        for _, o in opps:
            pt["A_card"][o["A_card"]] = pt["A_card"].get(o["A_card"], 0) + 1
        for _, o in forked:
            h = o["Bres"].get("held_decisions", 0)
            pt["held_decisions"][h] = pt["held_decisions"].get(h, 0) + 1
        pt["elixir_mean"] = sum(o["elixir"] for _, o in opps) / max(1, len(opps))
        # the --patience-exempt 8 variant would hold only the opportunities with no enemy within 8 tiles of my towers
        sub = [(c, o) for c, o in opps if not o.get("near8")]
        pt["exempt8_subset"] = {
            "n": len(sub), "win@end": cr_mean([((o["Bres"]["outcome"] == "win") - (o["Ares"]["outcome"] == "win"))
                                               if "Bres" in o else 0.0 for _, o in sub], [c for c, _ in sub]),
            "tower_diff@20": cr_mean([((o["Bres"]["20"]["hp_us"] - o["Bres"]["20"]["hp_them"]) -
                                       (o["Ares"]["20"]["hp_us"] - o["Ares"]["20"]["hp_them"])) if "Bres" in o else 0.0
                                      for _, o in sub], [c for c, _ in sub])}
        out["patience"] = pt
    if name == "rocket_tower":
        def cells(sel):
            cl = [c for c, _ in sel]
            r = {"n": len(sel), "forked": sum("Bres" in o for _, o in sel)}
            for k in ("10", "20", "end"):
                r[f"tower_diff@{k}"] = cr_mean([((o["Bres"][k]["hp_us"] - o["Bres"][k]["hp_them"]) -
                                                 (o["Ares"][k]["hp_us"] - o["Ares"][k]["hp_them"])) if "Bres" in o else 0.0
                                                for _, o in sel], cl)
            r["win@end"] = cr_mean([((o["Bres"]["outcome"] == "win") - (o["Ares"]["outcome"] == "win"))
                                    if "Bres" in o else 0.0 for _, o in sel], cl)
            r["loss@end"] = cr_mean([((o["Bres"]["outcome"] == "loss") - (o["Ares"]["outcome"] == "loss"))
                                     if "Bres" in o else 0.0 for _, o in sel], cl)
            return r
        crown = lambda o: "ahead" if o["cr_us"] > o["cr_them"] else "behind" if o["cr_us"] < o["cr_them"] else "level"
        sp = {}
        for scope, sel0 in (("all", opps), ("first_of_episode", [(c, o) for c, o in opps if o.get("first", True)])):
            sp[scope] = {"ALL": cells(sel0)}
            for lab, f in (("push7", lambda o: o["push_val"] >= 7), ("no_push7", lambda o: o["push_val"] < 7),
                           ("tau_threat", lambda o: o["tau_threat"]), ("no_tau_threat", lambda o: not o["tau_threat"])):
                sp[scope][lab] = cells([(c, o) for c, o in sel0 if f(o)])
            for cs in ("ahead", "level", "behind"):
                for push in (True, False):
                    sp[scope][f"{cs}|{'push7' if push else 'no_push7'}"] = cells(
                        [(c, o) for c, o in sel0 if crown(o) == cs and (o["push_val"] >= 7) == push])
        sp["A_card"] = {}
        for _, o in opps:
            sp["A_card"][str(o["A_card"])] = sp["A_card"].get(str(o["A_card"]), 0) + 1
        sp["A_rocket"] = sum(o["A_card"] == "rocket" for _, o in opps)
        out["rocket_tower"] = sp
        for scope in ("all", "first_of_episode"):
            print(f"-- rocket_tower cells ({scope}): B - A tower diff (ours - theirs) and win")
            for lab, r in sp[scope].items():
                print(f"   {lab:22s} n {r['n']:4d} forked {r['forked']:4d} | +10 {fmt(r['tower_diff@10'], 0)} | +20 "
                      f"{fmt(r['tower_diff@20'], 0)} | end {fmt(r['tower_diff@end'], 0)} | win {fmt(r['win@end'], 3)}")
    print(f"== {name}: {out['matches']} matches, {out['opportunities']} opportunities "
          f"({out['opps_per_match']:.2f}/match; {out['matches_with_opportunity']} matches with >= 1), "
          f"{out['forked']} forked, {out['same_as_model']} same as the model, {out['trigger_decisions']} trigger decisions")
    print("faithfulness:", json.dumps(fa))
    for scope in ("forked", "all"):
        print(f"-- B - A, {scope} opportunities")
        for k, v in res[scope].items():
            print(f"   {k:16s} {fmt(v, 4 if k.startswith(('win', 'result')) else 1)}")
    if "per_match_win_pp" in out:
        print("per-match win effect (pp):", out["per_match_win_pp"])
    for k in ("sneaky", "patience"):
        if k in out:
            print(k, json.dumps(out[k]))
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

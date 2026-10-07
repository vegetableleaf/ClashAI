"""opt3 T2 scorer gate: do horizon-H branch scores track the FULL-MATCH outcome delta of PLAY vs HOLD?

    env ROYALE_RUNTIME=20261006 PYTHONPATH="<Royale-20261006>/runtime;<worktree>" <Royale venv python> \
        scratchpad/gauntlet/L73/opt3/validate.py --out scratchpad/gauntlet/L73/opt3/val/run1 --seeds 0:8 --k 4 \
        [--per-stratum 1,1,1] [--band 0.2,0.65] [--holds 2,4,8] [--horizons 10,20,40] [--workers 2] [--threads 2]
    ... validate.py --smoke --out DIR        (seed 0, one 1x point, k 2, + the CRN determinism check)
    ... validate.py --summarise DIR [DIR ...] (re-aggregate points.jsonl of one or more runs)
    ... validate.py --selftest               (the statistics on synthetic input)

CPU only, below-normal priority. Reads checkpoints and the census from the main checkout (read-only).

MATCHES. search_s0's reactive setup: ours gen_v32_s0 (icebow, live rule tau 0.35 greedy, forms deck, hero abilities
v2) vs the frozen gen_v1_s0 (live rule tau 0.27 greedy) on a seeded census deck (L70/pool_forms/loadable_decks.json).
POINTS. Pass 1 plays the match and traces every eligible decision of ours (>= 1 affordable card). Candidates = those
with p_play in --band. Stratified by elixir phase (index into
royale_env.REGEN_SCHEDULE: 1x, 2x, 3x+): up to --per-stratum points per stratum per match, uniform without replacement
(rng [seed, 73]). Pass 2 replays the (deterministic) match, refusing if a chosen decision's tick or engine hash differs,
and evaluates there; the main match always continues with the live decision.
BRANCHES (contract T1, aligned with pipeline/branching.py). PLAY = play NOW with the gate forced open (the live
action when p > 0.35, else the argmax card at its argmax cell: a forced play). HOLD(h) = our gate tau --hold-tau (0.55) for h s from the root
(anti-stall unchanged; the model still plays if p > 0.55), then the live rule (tau 0.35). At the root HOLD plays the same
action iff p > 0.55 or the stall rule fires, else waits. Both sides then run to the END of the match: ours greedy at
the live rule, the opponent its own model SAMPLED at --opp-T 0.3 / --opp-tau 0.35 (R2's actor_cfg, which R3's
league opponents use; with both sides greedy the engine is deterministic and the k continuations would be identical).
k continuations per branch; continuation j of every branch gets the same seeds for every python RNG
(branching.reseed: common random numbers), so PLAY_j - HOLD_j differences are not seed noise.
HORIZON SCORES from the SAME continuations: at the first decision of ours at or after root + H s, "phi" (frozen
gen_v32_s0 value head, P(win) - P(loss), branch_score.phi_values on our gen row) and "towers" (branch_score.
tower_frac_diff). A continuation whose match ended before H scores its outcome (branch_score.score).
ANALYSIS (``summarise``): items = (point, h); full delta D = mean_j(outcome PLAY_j - outcome HOLD_j) in [-2, 2]; horizon
delta = the same mean of horizon scores. Spearman(horizon, D) and sign agreement (horizon delta 0 counts as a miss) on
|D| >= 0.25 and on D != 0; HOLD-better share by stratum; noise = the paired SE of D at k, its k-projection, and
split-half sign agreement. 95% CIs by a CLUSTER bootstrap over matches (a match brings all its items).
GATE (pre-set, ticket T2): a horizon score passes iff its sign agreement on |D| >= 0.25 is >= 65% with CI low > 50%.
SIGN AGREEMENT counts only pairs where the score's delta is nonzero (a zero delta gives no label: T3 drops it);
n_big_labelled says how many; the crossfit table also gives the ties-as-miss rate.
CROSS-FIT (added after run1): the horizon score and D above come from the SAME continuations, so a continuation's luck
before H moves both (shared noise) and can pass the gate while D itself is unreproducible. crossfit_table compares the
score on the even continuations with D on the odd ones (and vice versa), next to the same check for the outcome itself.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np

WT = Path(__file__).resolve().parents[4]
MAIN = Path("C:/Users/benpe/ClashBot")
# CODE PATH. Many pipeline modules read engine data at REPO/research/ext (untracked, absent from a worktree), so the
# package `pipeline` is imported from the MAIN checkout (content-identical to this worktree's apart from the opt3 files,
# checked and recorded by code_provenance) and the worktree's pipeline dir is appended to its __path__ so the NEW
# modules (branch_score, branching) come from the worktree.
for _p in (MAIN / "icebow" / "src", MAIN):
    if str(_p) in sys.path:
        sys.path.remove(str(_p))
    sys.path.insert(0, str(_p))
import pipeline                               # noqa: E402
if Path(pipeline.__file__).resolve().parent != (MAIN / "pipeline").resolve():
    raise RuntimeError(f"pipeline imported from {pipeline.__file__}, expected the main checkout")
pipeline.__path__.append(str(WT / "pipeline"))

V32 = str(MAIN / "icebow/data/pipeline/gen_v32_s0/gen_s0.pt")
GEN1 = str(MAIN / "icebow/data/pipeline/gen_v1_s0/gen_s0.pt")
EVO = str(MAIN / "scratchpad/gauntlet/L70/pool_forms/loadable_decks.json")
STRATA = ("1x", "2x", "3x+")
GATE_MIN_ABS, GATE_AGREE = 0.25, 0.65


def below_normal() -> None:
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)          # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:                                               # noqa: BLE001 -- not Windows: leave it
        pass


# ------------------------------------------------------------------------------------------------------
# statistics
# ------------------------------------------------------------------------------------------------------
def spearman(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    if len(a) < 3:
        return None

    def rk(x):
        r = np.empty(len(x))
        r[np.argsort(x, kind="mergesort")] = np.arange(len(x), dtype=np.float64)
        for v in np.unique(x):
            r[x == v] = r[x == v].mean()
        return r
    ra, rb = rk(a), rk(b)
    return None if ra.std() == 0 or rb.std() == 0 else float(np.corrcoef(ra, rb)[0, 1])


def cboot(fn, clusters, n: int = 2000, seed: int = 0):
    """95% percentile CI of fn(index array) under a cluster bootstrap over ``clusters`` (one label per item)."""
    cl = np.asarray([str(c) for c in clusters])
    ids = np.unique(cl)
    if len(ids) < 2:
        return [None, None]
    by = [np.where(cl == c)[0] for c in ids]
    rng, vals = np.random.default_rng(seed), []
    for _ in range(n):
        v = fn(np.concatenate([by[i] for i in rng.integers(0, len(ids), len(ids))]))
        if v is not None:
            vals.append(v)
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)] if vals else [None, None]


def r4(v):
    return None if v is None else round(float(v), 4)


def items_of(recs: list[dict]) -> list[dict]:
    """(point, hold) items with full and horizon deltas."""
    out = []
    for r in recs:
        play = r["branches"][0]
        assert play["kind"] == "play"
        op = np.asarray(play["outcome"], np.float64)
        for b in r["branches"][1:]:
            if b["kind"] != "hold":
                continue
            oh = np.asarray(b["outcome"], np.float64)
            d = op - oh
            it = {"cluster": f"{r['seed']}", "stratum": r["stratum"], "hold_s": b["hold_s"], "p": r["p"],
                  "D": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None,
                  "half": (float(d[0::2].mean()), float(d[1::2].mean())) if len(d) > 1 else None, "hz": {},
                  "dj": d, "hj": {}}
            for H, hp in play["H"].items():
                hh = b["H"][H]
                for kind in ("phi", "towers"):
                    sp = np.where(hp["ended"], op, np.asarray(hp[kind], np.float64))
                    sh = np.where(hh["ended"], oh, np.asarray(hh[kind], np.float64))
                    dd = sp - sh
                    it["hj"][f"{kind}@{H}"] = dd
                    it["hz"][f"{kind}@{H}"] = (float(dd.mean()), float(dd.std(ddof=1) / np.sqrt(len(dd))) if len(dd) > 1 else None)
            out.append(it)
    return out


def score_table(items: list[dict]) -> dict:
    """Per horizon score: Spearman with D, sign agreement on |D| >= GATE_MIN_ABS and on D != 0, the gate verdict."""
    out = {}
    if not items:
        return out
    D = np.array([i["D"] for i in items])
    cl = [i["cluster"] for i in items]
    for key in items[0]["hz"]:
        h = np.array([i["hz"][key][0] for i in items])
        se_h = [i["hz"][key][1] for i in items if i["hz"][key][1] is not None]

        def agree(idx, thr):
            m = idx[(np.abs(D[idx]) >= thr) & (h[idx] != 0)] if thr > 0 else idx[(D[idx] != 0) & (h[idx] != 0)]
            return None if len(m) == 0 else float(np.mean(np.sign(h[m]) == np.sign(D[m])))
        big = np.abs(D) >= GATE_MIN_ABS
        a_big = agree(np.arange(len(D)), GATE_MIN_ABS)
        ci_big = cboot(lambda idx: agree(idx, GATE_MIN_ABS), cl)
        out[key] = {"n": len(items), "spearman": r4(spearman(h, D)), "spearman_ci95": cboot(lambda idx: spearman(h[idx], D[idx]), cl),
                    "n_big": int(big.sum()), "n_big_labelled": int((big & (h != 0)).sum()), "sign_agree_big": r4(a_big), "sign_agree_big_ci95": ci_big,
                    "n_nonzero": int((D != 0).sum()), "sign_agree_nonzero": r4(agree(np.arange(len(D)), 0)),
                    "sign_agree_nonzero_ci95": cboot(lambda idx: agree(idx, 0), cl),
                    "horizon_delta_se_mean": r4(np.mean(se_h)) if se_h else None,
                    "GATE": "PASS" if (a_big is not None and a_big >= GATE_AGREE and ci_big[0] is not None
                                       and ci_big[0] > 0.5) else "FAIL"}
    return out


def crossfit_table(items: list[dict]) -> dict:
    """CROSS-FIT check (shared-noise free): the score's delta on the EVEN continuations vs the full-outcome delta on the
    ODD ones, and vice versa (2 pairs per item; the halves share no continuation, so a lucky continuation cannot make
    both agree). Reference row "outcome" = the full-outcome delta on one half vs the other: the most any k/2 label can
    agree with an independent k/2 outcome estimate. Agreement on pairs with |outcome half-delta| >= GATE_MIN_ABS."""
    its = [i for i in items if len(i["dj"]) >= 2]
    out = {}
    if not its:
        return out
    for key in ["outcome"] + list(its[0]["hj"]):
        x, y, cl = [], [], []
        for i in its:
            src = i["dj"] if key == "outcome" else i["hj"][key]
            for a, b in ((0, 1), (1, 0)):
                x.append(float(src[a::2].mean()))
                y.append(float(i["dj"][b::2].mean()))
                cl.append(i["cluster"])
        x, y = np.array(x), np.array(y)

        def agree(idx, ties_miss=False):
            m = idx[(np.abs(y[idx]) >= GATE_MIN_ABS) & ((x[idx] != 0) | ties_miss)]
            return None if len(m) == 0 else float(np.mean(np.sign(x[m]) == np.sign(y[m])))
        a = agree(np.arange(len(x)))
        ci = cboot(agree, cl)
        big = np.abs(y) >= GATE_MIN_ABS
        out[key] = {"n_pairs": len(x), "n_big": int(big.sum()), "n_big_labelled": int((big & (x != 0)).sum()),
                    "sign_agree_big": r4(a), "sign_agree_big_ci95": ci,
                    "sign_agree_big_ties_as_miss": r4(agree(np.arange(len(x)), True)), "spearman": r4(spearman(x, y)),
                    "spearman_ci95": cboot(lambda idx: spearman(x[idx], y[idx]), cl),
                    "GATE": "PASS" if (a is not None and a >= GATE_AGREE and ci[0] is not None and ci[0] > 0.5) else "FAIL"}
    return out


def summarise(recs: list[dict]) -> dict:
    recs = [r for r in recs if "branches" in r]
    items = items_of(recs)
    if not items:
        return {"n_points": len(recs), "n_items": 0}
    ks = sorted({len(r["branches"][0]["outcome"]) for r in recs})
    k = ks[0] if len(ks) == 1 else ks
    out = {"n_points": len(recs), "n_matches": len({r["seed"] for r in recs}), "k": k, "n_items": len(items),
           "points_per_stratum": {s: sum(r["stratum"] == s for r in recs) for s in STRATA},
           "wall_per_point_s": r4(np.mean([r["wall_s"] for r in recs])),
           "scores_pooled_over_holds": score_table(items),
           "crossfit_pooled_over_holds": crossfit_table(items)}
    for h in sorted({i["hold_s"] for i in items}):
        out[f"scores_hold{h:g}"] = score_table([i for i in items if i["hold_s"] == h])
    # HOLD truly better (D < 0) by stratum x hold
    hb = {}
    for s in STRATA + ("all",):
        for h in sorted({i["hold_s"] for i in items}) + ["all"]:
            its = [i for i in items if (s == "all" or i["stratum"] == s) and (h == "all" or i["hold_s"] == h)]
            if not its:
                continue
            D = np.array([i["D"] for i in its])
            cl = [i["cluster"] for i in its]
            hb[f"{s}|hold{h}"] = {"n": len(its), "hold_better": r4(np.mean(D < 0)),
                                  "hold_better_ci95": cboot(lambda idx: float(np.mean(D[idx] < 0)), cl),
                                  "play_better": r4(np.mean(D > 0)), "tie": r4(np.mean(D == 0)),
                                  "mean_D": r4(D.mean()), "mean_D_ci95": cboot(lambda idx: float(D[idx].mean()), cl),
                                  "big_hold_better": r4(np.mean(D <= -GATE_MIN_ABS)),
                                  "big_play_better": r4(np.mean(D >= GATE_MIN_ABS))}
    out["hold_better_by_stratum"] = hb
    # horizon cost / degeneracy: share of horizon scores that ARE the outcome (match ended before H), and the
    # simulated ticks of an H-horizon fork relative to a run to the end (same forks)
    hz = {}
    for H in recs[0]["branches"][0]["H"]:
        Ht = round(float(H) / E.TICK_S)
        ended = [e for r in recs for b in r["branches"] for e in b["H"][H]["ended"]]
        full = [t - r["tick"] for r in recs for b in r["branches"] for t in b["end_tick"]]
        hz[H] = {"ended_share": r4(np.mean(ended)), "cost_vs_full": r4(sum(min(Ht, x) for x in full) / sum(full)),
                 "ended_share_by_stratum": {s: r4(np.mean([e for r in recs if r["stratum"] == s for b in r["branches"]
                                                           for e in b["H"][H]["ended"]] or [np.nan])) for s in STRATA}}
    out["horizons"] = hz
    for s in STRATA:                     # late points: many horizon scores ARE outcomes (ended_share_by_stratum)
        out[f"crossfit_{s}"] = crossfit_table([i for i in items if i["stratum"] == s])
    se = np.array([i["se"] for i in items if i["se"] is not None])
    halves = [i["half"] for i in items if i["half"] is not None and i["half"][0] != 0 and i["half"][1] != 0]
    out["noise"] = {"k": k, "D_se_mean": r4(se.mean()) if len(se) else None,
                    "D_se_median": r4(np.median(se)) if len(se) else None,
                    "D_se_projected": {f"k{kk}": r4(se.mean() * np.sqrt(k / kk)) for kk in (4, 8, 16, 32)}
                    if len(se) and isinstance(k, int) else None,
                    "share_abs_D_ge_0.25": r4(np.mean(np.abs([i["D"] for i in items]) >= GATE_MIN_ABS)),
                    "share_D_zero": r4(np.mean([i["D"] == 0 for i in items])),
                    "split_half_sign_agree": r4(np.mean([np.sign(a) == np.sign(b) for a, b in halves])) if halves else None,
                    "split_half_n": len(halves),
                    "note": "split halves are k/2 means each; sign agreement between two k/2 means"}
    return out


def selftest() -> None:
    rng = np.random.default_rng(0)
    recs = []
    for s in range(12):
        for q in range(3):
            o = rng.choice([-1, 0, 1], size=(2, 4))
            hz = lambda oo: {"ended": [False] * 4, "phi": (oo * 0.5).tolist(), "towers": (-oo * 0.5).tolist()}  # noqa: E731
            recs.append({"seed": s, "stratum": STRATA[q], "p": 0.4, "wall_s": 1.0, "tick": 0, "branches": [
                {"kind": "play", "hold_s": 0, "outcome": o[0].tolist(), "end_tick": [400] * 4, "H": {"10": hz(o[0])}},
                {"kind": "hold", "hold_s": 2, "outcome": o[1].tolist(), "end_tick": [400] * 4, "H": {"10": hz(o[1])}}]})
    sm = summarise(recs)
    t = sm["scores_pooled_over_holds"]
    assert t["phi@10"]["spearman"] == 1.0 and t["phi@10"]["sign_agree_big"] == 1.0 and t["phi@10"]["GATE"] == "PASS"
    assert t["towers@10"]["spearman"] == -1.0 and t["towers@10"]["sign_agree_big"] == 0.0 and t["towers@10"]["GATE"] == "FAIL"
    assert sm["crossfit_pooled_over_holds"]["phi@10"]["n_pairs"] == 72
    assert sm["horizons"]["10"] == {"ended_share": 0.0, "cost_vs_full": 0.5, "ended_share_by_stratum": {s: 0.0 for s in STRATA}}
    hb = sm["hold_better_by_stratum"]["all|holdall"]
    assert abs(hb["hold_better"] + hb["play_better"] + hb["tie"] - 1) < 1e-9
    print("selftest OK")


# ------------------------------------------------------------------------------------------------------
# the evaluation
# ------------------------------------------------------------------------------------------------------
from pipeline import search_s0 as S          # noqa: E402
from pipeline import e1_eval as E            # noqa: E402
from pipeline import branch_score as BS      # noqa: E402
from pipeline.branching import reseed        # noqa: E402  (T1's common-random-numbers seeding)


def code_provenance() -> dict:
    """Which pipeline modules differ (CRLF-normalised) between the worktree and the main checkout; the new modules'
    actual import paths."""
    norm = lambda q: q.read_bytes().replace(b"\r\n", b"\n")      # noqa: E731
    diff = sorted(q.name for q in (WT / "pipeline").glob("*.py")
                  if (MAIN / "pipeline" / q.name).is_file() and norm(q) != norm(MAIN / "pipeline" / q.name))
    import pipeline.branching as BR
    return {"pipeline_from": str(Path(pipeline.__file__).parent), "differs_from_worktree": diff,
            "branch_score_from": BS.__file__, "branching_from": BR.__file__}


def stratum_of(sched, tick: int) -> str:
    return STRATA[min(2, max(j for j, (t0, _) in enumerate(sched) if t0 <= tick))]


class ValRunner(S.Runner):
    """search_s0.Runner whose search arm traces (pass 1) or evaluates (pass 2) and always plays the live decision."""
    trace = expect = None
    eval_idx: frozenset = frozenset()

    def arm_decide(self, m, ds, arm, p, enc, heads, allowed, plain, st, rng, stalled=False):
        i = st["eligible"] - 1
        here = [int(m.env.tick), str(m.env.core.state_hash())]
        if self.trace is not None:
            self.trace.append({"here": here, "p": float(p), "play": bool(plain["play"]), "stalled": bool(stalled),
                               "stratum": stratum_of(m.env.elixir_regen_schedule, here[0])})
        elif i in self.eval_idx:
            if self.expect is None or i >= len(self.expect) or self.expect[i]["here"] != here:
                raise RuntimeError(f"{m.spec['tag']}: eligible decision {i} at {here} differs from pass 1")
            t = time.perf_counter()
            force = plain if plain["play"] else E.live_decide_batch(
                self.learner, enc, heads, [p], allowed[None], np.array([bool(stalled)]), tau=float("-inf"),
                device=self.dev)[0]                    # PLAY = the gate forced open (T1): argmax card, argmax cell
            rec = self.evaluate(m, ds, p, plain, force, bool(stalled))
            rec.update({"eligible_idx": i, "wall_s": round(time.perf_counter() - t, 1)})
            self.records.append(rec)
            print(f"[val] {m.spec['tag']} dec {i} tick {rec['tick']} {rec['stratum']} p {p:.3f} "
                  f"wall {rec['wall_s']}s", flush=True)
        return plain

    def evaluate(self, m, ds, p, plain, force, stalled) -> dict:
        from pipeline.decision_options import match_kwargs
        a, K, L, root = self.a, self.a["k"], m.learner.side, int(m.env.tick)
        branches = [("play", 0.0)] + [("hold", h) for h in a["holds"]] + ([("play", 0.0)] if a["crn_check"] else [])
        base = m.learner.cfg
        hold_cfg = {**base, "tau": a["hold_tau"]}
        ocfg = {**m.opp.cfg, "policy": "sample", "T": a["opp_T"], "tau": a["opp_tau"]} if a["opp_T"] > 0 else m.opp.cfg
        seed = zlib.crc32(f"{m.spec['tag']}:{root}".encode())
        blob = m.env.core.save_state()
        forks = [S.fork_into(m, e2, blob) for e2 in self._pool(len(branches) * K)]
        Ht = {str(int(h) if float(h).is_integer() else h): root + int(round(h / E.TICK_S)) for h in a["horizons"]}
        meta = {}
        for n, f in enumerate(forks):
            kind, h = branches[n // K]
            j = n % K
            f.opp.cfg = ocfg
            reseed(f, seed, j)                          # common random numbers across branches (T1's seeding)
            act = force
            if kind == "hold":
                f.learner.cfg = hold_cfg
                if not (p > a["hold_tau"] or stalled):
                    act = {"play": False, "slot": force["slot"], "cell": -1, "why": "wait"}
            meta[id(f.learner)] = {"f": f, "release": root + int(round(h / E.TICK_S)) if kind == "hold" else None,
                                   "H": {}, "end": None}
            f.learner.apply(p, act)
        first = [f.opp for f in forks] if m.opp in ds else []
        active = list(forks)
        while True:
            due, first = first, []
            if not due:
                for f in list(active):
                    got = f.due()
                    if got:
                        due += got
                    else:
                        active.remove(f)
                        mt = meta[id(f.learner)]
                        mt["end"] = (BS.outcome_value(f.env.outcome(L)[0]), int(f.env.tick))
                if not due:
                    break
                for s in due:
                    s.prepare()
            hits = []
            for s in due:
                mt = meta.get(id(s))
                if mt is None:
                    continue
                t = int(s.env.tick)
                if mt["release"] is not None and t >= mt["release"]:
                    s.cfg, mt["release"] = base, None
                for H, tH in Ht.items():
                    if H not in mt["H"] and t >= tH:
                        mt["H"][H] = {"tick": t, "towers": BS.tower_frac_diff(s.env.core.state(), L)}
                        hits.append((mt["H"][H], s))
            if hits:
                vals = BS.phi_values(self.phi, [s.gen_row(self.phi) for _, s in hits])
                for (snap, _), v in zip(hits, vals):
                    snap["phi"] = float(v)
            groups: dict = {}
            for s in due:
                groups.setdefault((id(s.model), s.side, id(s.cfg)), []).append(s)
            todo = {}
            for sides in groups.values():
                model, c = sides[0].model, sides[0].cfg
                enc, heads, pp, hand = model.forward_batch([s.gen_row(model) for s in sides], c["device"])
                pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
                allowed, stl = np.stack([x[1] for x in pre]), np.array([x[2] for x in pre], dtype=bool)
                if c["policy"] == "sample":
                    dec = E.sample_decide_batch(model, enc, heads, pp, allowed, stl, sides, c)
                else:
                    dec = E.live_decide_batch(model, enc, heads, pp, allowed, stl, tau=c["tau"], device=c["device"],
                                              **match_kwargs(sides))
                todo.update({id(s): (pp[r], dec[r]) for r, s in enumerate(sides)})
            for s in due:
                s.apply(*todo[id(s)])
        out = []
        for b, (kind, h) in enumerate(branches):
            ms = [meta[id(f.learner)] for f in forks[b * K:(b + 1) * K]]
            out.append({"kind": kind, "hold_s": h, "outcome": [mt["end"][0] for mt in ms],
                        "end_tick": [mt["end"][1] for mt in ms],
                        "H": {H: {"ended": [H not in mt["H"] for mt in ms],
                                  "tick": [mt["H"].get(H, {}).get("tick") for mt in ms],
                                  "phi": [mt["H"].get(H, {}).get("phi") for mt in ms],
                                  "towers": [mt["H"].get(H, {}).get("towers") for mt in ms]} for H in Ht}})
        rec = {"tag": m.spec["tag"], "seed": int(m.spec["seed"]), "tick": root, "p": float(p), "stalled": stalled,
               "stratum": stratum_of(m.env.elixir_regen_schedule, root),
               "elixir": float(int(m.learner._cur[2].my_elixir)),
               "plain": {x: plain[x] for x in ("play", "slot", "cell", "why")},
               "force": {x: force[x] for x in ("play", "slot", "cell", "why")},
               "k": K, "opp_T": a["opp_T"], "opp_tau": a["opp_tau"], "hold_tau": a["hold_tau"], "branches": out}
        if a["crn_check"]:
            p0, p1 = out[0], out[-1]
            rec["crn_ok"] = p0["outcome"] == p1["outcome"] and p0["end_tick"] == p1["end_tick"] and p0["H"] == p1["H"]
            rec["branches"] = out[:-1]
        return rec


_W: dict = {}


def _init(args: dict) -> None:
    below_normal()
    S._init_worker(args)
    run = S._W["runner"]
    run.__class__ = ValRunner
    run.a, run.records = args, []
    run.phi = run.learner if args["phi"] == args["gen"] else BS.load_phi(args["phi"], "cpu")
    _W["args"] = args


def pick(trace: list[dict], seed: int, band, per: list[int]) -> frozenset:
    rng = np.random.default_rng([int(seed), 73])
    out = []
    for s, n in zip(STRATA, per):
        cand = [i for i, t in enumerate(trace) if band[0] <= t["p"] <= band[1] and t["stratum"] == s]
        out += [int(i) for i in rng.choice(cand, size=min(n, len(cand)), replace=False)] if cand else []
    return frozenset(out)


def _play(run, m, until=None) -> None:
    st = {"eligible": 0, "unsearched": 0}
    while until is None or len(run.records) < until:
        ds = m.due()
        if not ds:
            return
        run.round(m, ds, "search", st, None)


def _job(seed: int) -> list[dict]:
    a, run = _W["args"], S._W["runner"]
    t0 = time.perf_counter()
    got = S.setup_job(run, S._W["census"], "gen", seed)
    if got is None:
        return [{"seed": seed, "skipped": "no loadable deck"}]
    m, name = got
    run.eval_idx, run.records, run.trace, run.expect = frozenset(), [], [], None
    _play(run, m)
    trace, outcome = run.trace, m.result()["outcome"]
    idx = pick(trace, seed, a["band"], a["per_stratum"])
    pass1_s = round(time.perf_counter() - t0, 1)
    if not idx:
        return [{"seed": seed, "skipped": "no point in band", "n_eligible": len(trace), "pass1_s": pass1_s}]
    m, name = S.setup_job(run, S._W["census"], "gen", seed)
    run.eval_idx, run.trace, run.expect = idx, None, trace
    _play(run, m, until=len(idx))
    if len(run.records) != len(idx):
        raise RuntimeError(f"seed {seed}: evaluated {len(run.records)} of {len(idx)} points")
    return [{**r, "opp_deck_name": name, "main_outcome": outcome, "n_eligible": len(trace),
             "n_band": sum(a["band"][0] <= t["p"] <= a["band"][1] for t in trace), "pass1_s": pass1_s}
            for r in run.records]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--summarise", type=Path, nargs="+", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seeds", default="0:8")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--per-stratum", default="1,1,1", help="points per match in 1x,2x,3x+")
    ap.add_argument("--band", default="0.2,0.65")
    ap.add_argument("--holds", default="2,4,8")
    ap.add_argument("--hold-tau", type=float, default=0.55)
    ap.add_argument("--horizons", default="10,20,40")
    ap.add_argument("--opp-T", type=float, default=0.3, help="0 = the opponent's own cfg (greedy: k continuations equal)")
    ap.add_argument("--opp-tau", type=float, default=0.35, help="opponent gate tau when sampled (R2 actor_cfg: 0.35)")
    ap.add_argument("--gen", default=V32)
    ap.add_argument("--opp-gen", default=GEN1)
    ap.add_argument("--phi", default=V32)
    ap.add_argument("--census", default=EVO)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--crn-check", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    if a.summarise:
        recs = [json.loads(x) for d in a.summarise for x in (d / "points.jsonl").read_text(encoding="utf-8").splitlines() if x]
        sm = summarise(recs)
        (a.summarise[0] / "summary.json").write_text(json.dumps(sm, indent=1), encoding="utf-8")
        print(json.dumps(sm, indent=1))
        return 0
    if a.smoke:
        a.seeds, a.k, a.per_stratum, a.workers, a.crn_check = "0", 2, "1,0,0", 1, True
    if a.out is None:
        ap.error("--out is required")
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"REFUSING: {a.out} exists and is not empty")
    a.out.mkdir(parents=True, exist_ok=True)
    fl = lambda s: [float(x) for x in s.split(",") if x]    # noqa: E731
    args = {"gen": a.gen, "opp_gen": a.opp_gen, "opp_gen_sha256": None, "s1": S.S1_CKPT, "opps": ["gen"],
            "threads": a.threads, "tail_cap": 7200, "horizon": 12.0, "interval": 1, "topk": 4, "cells": 3,
            "device": "cpu", "search_min_p": 0.0, "rollout_self": "idle", "forms_mode": "deck", "hero_abilities": True,
            "ability_policy": "v2", "census": a.census, "tau_plain": 0.35, "phi": a.phi, "k": a.k,
            "band": fl(a.band), "holds": fl(a.holds), "hold_tau": a.hold_tau, "horizons": fl(a.horizons),
            "opp_T": a.opp_T, "opp_tau": a.opp_tau, "per_stratum": [int(x) for x in a.per_stratum.split(",")], "crn_check": a.crn_check}
    (a.out / "run.json").write_text(json.dumps({**args, "gen_sha256": S.sha256(a.gen), "opp_gen_sha256": S.sha256(a.opp_gen),
                                                "phi_sha256": S.sha256(a.phi), "seeds": a.seeds,
                                                "code": code_provenance(),
                                                "started": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
    seeds, recs, t0 = S._range(a.seeds), [], time.perf_counter()
    fh = (a.out / "points.jsonl").open("a", encoding="utf-8")

    def emit(rs):
        for r in rs:
            recs.append(r)
            fh.write(json.dumps(r) + "\n")
            if r.get("skipped"):
                print(f"[val] seed {r['seed']} skipped: {r['skipped']}", flush=True)
        fh.flush()
        print(f"[val] {len([r for r in recs if 'branches' in r])} points, {time.perf_counter() - t0:.0f}s", flush=True)

    if a.workers <= 1:
        _init(args)
        for s in seeds:
            emit(_job(s))
    else:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.workers, initializer=_init, initargs=(args,)) as pool:
            for rs in pool.imap_unordered(_job, seeds):
                emit(rs)
    fh.close()
    sm = summarise(recs)
    sm["wall_total_s"] = round(time.perf_counter() - t0, 1)
    if a.crn_check:
        sm["crn_ok"] = [r.get("crn_ok") for r in recs if "branches" in r]
    (a.out / "summary.json").write_text(json.dumps(sm, indent=1), encoding="utf-8")
    print(json.dumps(sm, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

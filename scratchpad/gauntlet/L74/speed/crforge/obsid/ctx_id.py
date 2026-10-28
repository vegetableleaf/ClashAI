"""LOOP-CTX identity harness: CfCtx (Java) + cf_ctx.kwargs vs production decision_options.match_kwargs, and the
UNCHANGED decision_options.decide on both, at the live decision config (L70/live/LIVE_OPTIONS decision flags).

obs_id.py's setup (ROYALE_ENGINE=crforge facade, e1_eval.run_selfplay_batch, CLXIII on both seats, search_s0.live_cfg +
delay 26 + fv6) plus the LIVE_OPTIONS decision options in cfg. Hooks:
  Match.gen_row      production row, then JavaMain (the FacadeMatch obs: look-ahead snapshot + names) and JavaPub
                     (the obs block's projectiles) on the same facade battle and tick
  Match._land        an accepted play -> the side's CfCtx.Seat.played (done_plays' landing tick, slot, cell)
  match_kwargs       production's dict, then CfCtx.build per side + cf_ctx.kwargs; every field compared (canon below)
  decide_batch       decide on the Java context with the side's OWN decision RNG (cf_ctx.decision_rng, kept beside
                     production's), then production's; decision dicts (repr) and RNG states compared; a STRESS pair
                     (rules that read the board more often) runs on copies of both RNGs
usage (pod 32657): obsid/run_ctx.sh OUT.json [--n 56] [--hero-abilities]
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import shlex
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import obs_id as O  # noqa: E402  (sets ROYALE_ENGINE / sys.path like the obs harness)
import cf_ctx  # noqa: E402
import jpype  # noqa: E402
import numpy as np  # noqa: E402

LIVE_OPTIONS = O.RL / "scratchpad/gauntlet/L70/live/LIVE_OPTIONS"
FIELDS = ("decision_options", "card_names", "tau_threat", "t_sec", "grid", "enemy_alive", "rocket_boards", "lethal",
          "log_air_boards", "barrel_goblins", "rocket_value", "projectiles")


def live_decision_options(path=LIVE_OPTIONS) -> dict:
    """livecal.live_decision_options: the file's decision-option flags -> {dest: value} (EXTRA_LIVE_FLAGS left out)."""
    from pipeline.decision_options import add_arguments
    from pipeline.live_options import EXTRA_LIVE_FLAGS
    dec, full = argparse.ArgumentParser(add_help=False, allow_abbrev=False), argparse.ArgumentParser(add_help=False,
                                                                                                    allow_abbrev=False)
    add_arguments(dec)
    add_arguments(full)
    for flag, kw in EXTRA_LIVE_FLAGS:
        full.add_argument(flag, **kw)
    tokens = shlex.split(Path(path).read_text(encoding="utf-8-sig"), comments=True)
    parsed = full.parse_args(tokens)
    dests = [dec._option_string_actions[t.split("=", 1)[0]].dest for t in tokens
             if t.startswith("--") and t.split("=", 1)[0] in dec._option_string_actions]
    return {d: getattr(parsed, d) for d in dests}


# ---------------------------------------------------------------------------------------------------- canon
def board_proj(b):
    """The BoardState fields CtxBoard stands for (decide's Rocket rules read only these)."""
    return ("board", b.t_sec, b.double_elixir, b.overtime, b.my_elixir, b.my_hand, tuple(b.towers), tuple(b.units))


def canon(x) -> str:
    """Type-tagged, order-exact text (floats as hex: -0.0 / NaN / the last bit count); sets sorted."""
    from pipeline.obs_contract import BoardState
    if isinstance(x, (BoardState, cf_ctx.CtxBoard)):
        return canon(board_proj(x))
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return type(x).__name__ + canon(tuple(getattr(x, f.name) for f in dataclasses.fields(x)))
    if isinstance(x, cf_ctx.Lazy):
        x = [x[i] for i in range(len(x))]
    if isinstance(x, (set, frozenset)):
        return "set{" + ",".join(sorted(canon(v) for v in x)) + "}"
    if isinstance(x, dict):
        return "{" + ",".join(f"{canon(k)}:{canon(v)}" for k, v in x.items()) + "}"
    if isinstance(x, (list, tuple)):
        return ("[" if isinstance(x, list) else "(") + ",".join(canon(v) for v in x) + ("]" if isinstance(x, list) else ")")
    if isinstance(x, np.ndarray):
        return f"nd<{x.dtype},{x.shape},{x.tobytes().hex()}>"
    if isinstance(x, float):
        return type(x).__name__ + ":" + x.hex()
    return type(x).__name__ + ":" + repr(x)


def rng_state(g) -> str:
    return canon(g.bit_generator.state) if g is not None else "None"


class Rep:
    def __init__(self, first):
        self.first, self.rows, self.f, self.diffs = first, 0, Counter(), {}
        self.c = Counter()                  # coverage / decision counters
        self.ns = Counter()                 # timing sums (ns)

    def field(self, key, a, b, s):
        ok = a == b
        self.f[key + (".equal" if ok else ".diff")] += 1
        if not ok and len(self.diffs.setdefault(key, [])) < self.first:
            self.diffs[key].append(dict(tag=s.tag, side=int(s.side), tick=int(s._cur[0]), prod=a[:1500], java=b[:1500]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=56)
    ap.add_argument("--inflight", type=int, default=8)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--set", action="append", default=[], help="cfg override k=v (JSON value), both seats")
    ap.add_argument("--min-rows", type=int, default=38400)
    ap.add_argument("--first-diffs", type=int, default=5)
    ap.add_argument("--pairs", default="")
    ap.add_argument("--hero-abilities", action="store_true")
    ap.add_argument("--stress", type=int, default=1, help="0 = no stress decide pair")
    ap.add_argument("--build", default=str(HERE / "build_ctx"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    shas = O.src_shas()
    import hashlib
    for p in (HERE / "CfCtx.java", HERE / "cf_ctx.py", HERE / "ctx_id.py", LIVE_OPTIONS, O.RL / "pipeline/decision_options.py"):
        shas[f"ctx/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    O.start_jvm(Path(a.build))
    import torch
    torch.set_num_threads(a.threads)
    from pipeline import decision_options as D
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline.royale_runtime import ENGINE
    assert ENGINE == "crforge", ENGINE

    model, info = E.load_policy(O.CLXIII)
    main_b = O.JavaMain()
    main_b.opp_spells, main_b.gid = True, model.gid
    pub = O.JavaPub(main_b, model)
    Ctx = jpype.JClass("CfCtx")
    cfg = S.live_cfg(0.5, info["grid"])
    cfg.update(action_delay_ticks=26, feature_version=6)
    live = live_decision_options()
    cfg.update(live)
    over = {k: json.loads(v) for k, v in (x.split("=", 1) for x in a.set)}
    cfg.update(over)
    options = cf_ctx.options_for(cfg)
    stress = replace_stress(options) if a.stress else None
    rep = Rep(a.first_diffs)
    state = dict(T=None)
    BB = jpype.JClass("java.nio.ByteBuffer")
    raw_buf = BB.allocateDirect(8 * 65536).order(jpype.JClass("java.nio.ByteOrder").nativeOrder())
    jbuf, vbuf = raw_buf.asDoubleBuffer(), np.frombuffer(memoryview(raw_buf), np.float64)
    stash = {}

    orig_gen, orig_land, orig_mk, orig_db = E.Match.gen_row, E.Match._land, D.match_kwargs, D.decide_batch

    def seat(s):
        st = s.__dict__.get("_ctx_seat")
        if st is None:
            st = s._ctx_seat = Ctx.Seat()
            SEATS.append(st)
            s._ctx_rng = cf_ctx.decision_rng(s.tag, s.k, int(s.cfg.get("decision_seed", 0)))
        return st

    def gen_row(self, policy):
        row = orig_gen(self, policy)
        main_b(self)                                     # the FacadeMatch obs of this seat (look-ahead + names)
        j = pub(self)
        self._ctx_proj = j["projectiles"]
        return row

    def _land(self, p, d, land, landed, cur=None):
        acc = orig_land(self, p, d, land, landed, cur)
        if acc:
            if state["T"] is None:
                state["T"] = cf_ctx.tables(self.env.names, cfg["grid"], options)
            seat(self).played(state["T"], int(land), int(d["slot"]), int(d["cell"]))
        return acc

    def java_kwargs(matches):
        if state["T"] is None:
            state["T"] = cf_ctx.tables(matches[0].env.names, cfg["grid"], options)
        T, rows, tj = state["T"], [], 0
        for s in matches:
            st = seat(s)
            fm = s.env.core.__dict__["_obsid_match"]
            assert int(fm.tick()) == int(s._cur[0]) == int(s.env.core._cf.tick())   # bound to this battle (JavaMain)
            assert not s.pend, "pipeline_decisions is not ported"
            while True:
                t = time.perf_counter_ns()
                n = int(Ctx.build(T, main_b.names, fm, int(s.side), st, jbuf, 0))
                tj += time.perf_counter_ns() - t
                if n != -1:
                    break
                rep.c["table_fills"] += cf_ctx.fill_missing(T)
            assert n > 0, n
            t = time.perf_counter_ns()
            rows.append(cf_ctx.decode(vbuf[:n].tolist()))
            rep.ns["adapter_decode"] += time.perf_counter_ns() - t
        t = time.perf_counter_ns()
        kw = cf_ctx.kwargs(rows, options=options, grid=cfg["grid"], card_names=[list(s.deck.cards) for s in matches],
                           card_ids=[list(s.deck.card_ids) for s in matches], sides=[int(s.side) for s in matches],
                           pending=[getattr(s, "pending", None) is not None for s in matches],
                           rngs=[s._ctx_rng for s in matches], projectiles=[s._ctx_proj for s in matches])
        rep.ns["adapter_kwargs"] += time.perf_counter_ns() - t
        rep.ns["jpype_build"] += tj
        return kw, rows

    def match_kwargs(matches):
        t = time.perf_counter_ns()
        prod = orig_mk(matches)
        rep.ns["prod_match_kwargs"] += time.perf_counter_ns() - t
        if not prod:
            return prod
        java, rows = java_kwargs(matches)
        rep.rows += len(matches)
        assert set(prod) == set(java), (sorted(prod), sorted(java))
        for i, s in enumerate(matches):
            for k in FIELDS:
                if k not in prod:
                    continue
                if k == "decision_options":
                    rep.field(k, canon(prod[k]), canon(java[k]), s)
                elif k == "grid":
                    rep.field(k, canon(prod[k]), canon(java[k]), s)
                elif k == "rocket_value":               # (board, pending, holder): the holder is unread at this cfg
                    rep.field(k, canon(prod[k][i][:2]), canon(java[k][i][:2]), s)
                else:
                    rep.field(k, canon(prod[k][i]), canon(java[k][i]), s)
            rep.field("rng_before", rng_state(prod["rngs"][i]), rng_state(java["rngs"][i]), s)
            cover(rows[i], prod, i, s)
        stash[id(prod["rngs"])] = java
        return prod

    def cover(r, prod, i, s):
        c = rep.c
        c["units"] += len(r.units) // 6
        c["rows_tau_threat"] += int(r.tau_threat)
        c["rows_kills_king"] += int(r.kills_king)
        c["rows_glitch_filter"] += int(r.rocket_alive != r.enemy_alive)
        c["rows_enemy_tower_down"] += int(not all(r.enemy_alive))
        c["rows_skip"] += int(bool(r.skip))
        c["rows_own"] += int(bool(r.own))
        c["own_with_before"] += sum(1 for j in range(0, len(r.own), 10) if r.own[j + 4])
        c["rows_goblins"] += int(bool(r.goblins))
        c["rows_air"] += int(bool(r.air))
        c["rows_lookahead"] += int(s._view_tick != s._cur[0])
        c["rows_pending"] += int(getattr(s, "pending", None) is not None)
        c["rows_ot"] += int(r.t_sec >= 180.0)
        c["rows_hp_unknown"] += int(any(np.isnan(r.units[j + 4]) for j in range(0, len(r.units), 6)))

    def decide_batch(model_, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names, **context):
        java = stash.pop(id(rngs), None)
        if java is None:
            rep.c["decide_unpaired"] += 1
            return orig_db(model_, enc, heads, p, allowed, stalled, tau=tau, device=device, options=options, rngs=rngs,
                           card_names=card_names, **context)
        jctx = {k: v for k, v in java.items() if k not in ("decision_options", "rngs", "card_names")}
        if stress is not None:                           # copies of both streams: the real decisions never see it
            sp = orig_db(model_, enc, heads, p, allowed, stalled, tau=tau, device=device, options=stress,
                         rngs=copy.deepcopy(rngs), card_names=card_names, **context)
            sj = orig_db(model_, enc, heads, p, allowed, stalled, tau=tau, device=device, options=stress,
                         rngs=copy.deepcopy(java["rngs"]), card_names=java["card_names"], **jctx)
            for d1, d2 in zip(sp, sj):
                rep.c["stress_" + ("equal" if repr(d1) == repr(d2) else "diff")] += 1
                rep.c["stress_why_" + str(d1.get("why"))] += 1
        t = time.perf_counter_ns()
        rj = orig_db(model_, enc, heads, p, allowed, stalled, tau=tau, device=device, options=java["decision_options"],
                     rngs=java["rngs"], card_names=java["card_names"], **jctx)
        rep.ns["decide_java"] += time.perf_counter_ns() - t
        t = time.perf_counter_ns()
        res = orig_db(model_, enc, heads, p, allowed, stalled, tau=tau, device=device, options=options, rngs=rngs,
                      card_names=card_names, **context)
        rep.ns["decide_prod"] += time.perf_counter_ns() - t
        for i, (d1, d2) in enumerate(zip(res, rj)):
            ok = repr(d1) == repr(d2)
            rep.c["decision_" + ("equal" if ok else "diff")] += 1
            rep.c["rng_after_" + ("equal" if rng_state(rngs[i]) == rng_state(java["rngs"][i]) else "diff")] += 1
            rep.c["why_" + str(d1.get("why"))] += 1
            if d1.get("follow_ups"):
                rep.c["follow_ups"] += 1
            if not ok and len(rep.diffs.setdefault("decision", [])) < rep.first:
                rep.diffs["decision"].append(dict(prod=repr(d1), java=repr(d2)))
        return res

    E.Match.gen_row, E.Match._land, D.match_kwargs, D.decide_batch = gen_row, _land, match_kwargs, decide_batch

    jobs, cen = [], O.census()
    pairs = [int(v) for v in a.pairs.split(",")] if a.pairs else list(range(a.n))
    for i, (d1, f1) in enumerate(cen[p] for p in pairs):
        jobs.append((i, {"tag": f"ctxid{i}", "seed": 5000 + i, "learner_side": i % 2,
                         "learner_deck": list(E.ICEBOW_ENGINE_DECK), "opp_deck": [n + O.SFX[f] for n, f in zip(d1, f1)],
                         "opp": {"id": "clxiii"}}, 0))
    envs, done, skips, t0 = [], [], [], time.time()

    def make():
        envs.append(RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=a.hero_abilities))
        return envs[-1]

    def on_result(r):
        done.append(r["tag"])
        print(json.dumps(dict(tag=r["tag"], seat_rows=rep.rows, decisions=dict(eq=rep.c["decision_equal"],
                                                                              diff=rep.c["decision_diff"]),
                              wall_s=round(time.time() - t0))), flush=True)

    E.run_selfplay_batch(make, model, {"clxiii": (model, dict(cfg))}, jobs, cfg, min(len(jobs), a.inflight), on_result,
                         on_skip=lambda spec, exc: skips.append((spec["tag"], repr(exc))))
    T = state["T"]
    fields = {k: dict(equal=rep.f[k + ".equal"], diff=rep.f[k + ".diff"]) for k in FIELDS + ("rng_before",)
              if rep.f[k + ".equal"] + rep.f[k + ".diff"]}
    n = max(rep.rows, 1)
    out = dict(
        ticket="LOOP-CTX", seat_rows=rep.rows, matches=len(done), skipped=skips, wall_s=round(time.time() - t0, 1),
        hero_abilities=a.hero_abilities, cfg_overrides=over, live_decision_options=live, options=repr(options),
        stress_options=repr(stress),
        acceptance=dict(min_rows=a.min_rows, rows_ok=rep.rows >= a.min_rows,
                        fields_identical=all(v["diff"] == 0 for v in fields.values()),
                        decisions_identical=rep.c["decision_diff"] == 0 and rep.c["decision_equal"] == rep.rows,
                        rng_identical=rep.c["rng_after_diff"] == 0 and fields.get("rng_before", {}).get("diff", 1) == 0,
                        stress_identical=rep.c["stress_diff"] == 0),
        fields=fields, counters=dict(rep.c), first_diffs=rep.diffs,
        cost_us_per_seat_row={k: round(v / n / 1000.0, 2) for k, v in rep.ns.items()},
        tables=dict(dmg_keys=int(T.dmg.size()) if T is not None else 0, child_cards=int(T.childHp.size()) if T else 0),
        src_sha256=shas,
        note=("prod = decision_options.match_kwargs on the SelfPlaySide; java = CfCtx.build + cf_ctx.kwargs on the same "
              "facade battle and tick. Fields compared by canon() (type-tagged, floats as hex, sets sorted, BoardState / "
              "CtxBoard as board_proj: t_sec, phase flags, my_elixir, my_hand, the 6 Towers, every Unit). rocket_value's "
              "holder (prod: the match; java: None) is not compared: unread unless rocket_value_lead / _threat are on "
              "(cf_ctx refuses those). Decisions: repr of decide's dicts; RNG: bit_generator.state of each side's own "
              "decision stream. jpype_build includes the JPype call; the JVM-side time alone is in java_build."))
    out["cost_us_per_seat_row"]["java_build"] = round(sum(int(st.nanos) for st in SEATS) / n / 1000.0, 2)
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("seat_rows", "matches", "acceptance", "fields", "cost_us_per_seat_row")},
                     default=str))


SEATS: list = []         # every CfCtx.Seat (its JVM-side build nanos)


def replace_stress(options):
    """Rules that read the board / hand / towers far more often than the live cfg (lone Rocket at 2 elixir of value,
    the combo on, princess tower bonus, log_air retarget), run on RNG copies only."""
    return dataclasses.replace(options, rocket_value=2.0, rocket_tornado="on", rocket_tornado_lone="best",
                               rocket_value_towers="on", log_air="retarget")


if __name__ == "__main__":
    main()

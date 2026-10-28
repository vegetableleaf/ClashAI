"""LOOP-OPP test: inside rl_royale's actor processes (production config, crforge), every league OPPONENT decision is
re-made by the fast-loop path (pipeline.loop_opp) and compared with production's, on the same match state:

  cfg      loop_opp.opp_match_cfg (from the run's config + the match spec) vs the SelfPlaySide's cfg, DECISION_KEYS;
  rng      loop_opp.behave_rng at match start vs the side's rng_behave (bit-generator state);
  decide   the side's production row -> policy_server.Forward (cpu, eager) -> loop_opp.decide with the CANDIDATE cfg,
           its OWN rng (carried through the match) and the bank inputs read off the row (loop_opp.bank_inputs);
           play / slot / cell / why / _style_delay / gate_sampled / allowed / stalled identical, lp_* and p_gate within
           TOL; the candidate rng's state after the call vs production's (a divergence re-syncs it and is counted);
  schedule loop_opp.after_decision vs SelfPlaySide.apply's pending landing tick and next_tick.
Production state is only read (the candidate has its own cfg / rng objects). Loaded by sitecustomize.py under
LOOPOPP_CHECK=outdir (+ LOOPOPP_CFG = the run's --config, LOOPOPP_OVR = its overrides as a JSON list). Writes
outdir/<pid>.json after every run_selfplay_batch call."""
from __future__ import annotations

import copy
import json
import os
import time
import traceback
from pathlib import Path

import numpy as np

OUT = Path(os.environ["LOOPOPP_CHECK"])
TOL = 1e-5
EXACT = ("play", "slot", "cell", "why", "_style_delay", "gate_sampled", "stalled")
CLOSE = ("lp_gate", "lp_card", "lp_cell", "p_gate", "T")


def install(E) -> None:
    from pipeline import adaptive_opponents as AO
    from pipeline import loop_opp as LO
    from pipeline import rl_royale as R
    from pipeline.decision_options import model_cell_logits
    from pipeline.policy_server import Forward
    cfg = R.load_config(Path(os.environ["LOOPOPP_CFG"]), json.loads(os.environ.get("LOOPOPP_OVR", "[]")), False)
    S: dict = {}                                            # opponent id -> counters
    G = dict(t0=time.time(), batches=0, errors={}, learner_decisions=0, learner_matches=0, first=[])
    grids, fwds = {}, {}
    run0, init0, apply0, sd0 = E.run_selfplay_batch, E.SelfPlayMatch.__init__, E.SelfPlaySide.apply, AO.styled_decisions

    def st(i):
        return S.setdefault(i, dict(matches=0, cfg_equal=0, cfg_diff_keys={}, rng_init_equal=0, decisions=0,
                                    compared=0, actions_equal=0, keys_diff={}, lp_max_abs_diff=0.0, rng_after_equal=0,
                                    rng_resync=0, sched=0, sched_equal=0, bank_rows=0, bank_flip=0, bank_true=0,
                                    elixir_max_abs_diff=0.0, enemy_half_diff=0, styled_rows=0, plays=0,
                                    style_delay_plays=0, intervals={}, per_match_decisions=[], first_diffs=[]))

    def err(where, e=None):
        k = where + " " + (traceback.format_exc(limit=4)[-600:] if e is not None else "")
        G["errors"][k] = G["errors"].get(k, 0) + 1

    def grid_of(path):
        if path not in grids:
            grids[path] = str(E.load_policy(Path(R.REPO) / path, "cpu")[1].get("grid", "floor"))
        return grids[path]

    def init(self, env, spec, k, cfg_l, opp_cfg, learner=None, opponent=None):
        init0(self, env, spec, k, cfg_l, opp_cfg, learner, opponent)
        try:
            o, i = self.opp, spec["opp"]["id"]
            s = st(i)
            upd = int(cfg_l.get("update", 0))
            c = LO.opp_match_cfg(cfg, spec["opp"], grid_of(spec["opp"]["path"]), int(spec["seed"]), int(k), upd,
                                 E.policy_feature_version(opponent))
            keys = set(LO.DECISION_KEYS) | {x for x in list(c) + list(o.cfg) if x.startswith("opp_style")}
            diff = sorted(x for x in keys if (x in c) != (x in o.cfg) or (x in c and c[x] != o.cfg[x]))
            s["matches"] += 1
            s["cfg_equal"] += int(not diff)
            for x in diff:
                s["cfg_diff_keys"][x] = s["cfg_diff_keys"].get(x, 0) + 1
                if len(s["first_diffs"]) < 5:
                    s["first_diffs"].append(dict(what="cfg", key=x, prod=str(o.cfg.get(x)), cand=str(c.get(x))))
            rng = LO.behave_rng(str(spec["tag"]), int(k), upd)
            s["rng_init_equal"] += int(rng.bit_generator.state == o.rng_behave.bit_generator.state)
            o._lo = dict(id=i, cfg=c, rng=rng, ids=LO.deck_ids(spec["opp_deck"]), n=0)
            self.learner._lo_learner = True
        except Exception as e:                              # noqa: BLE001 -- a check never stops the actor
            err("init", e)

    def check(model, sides, allowed, stalled, out):
        n = len(sides)
        keys = E.gen_row_keys(model.model)
        rows = [s._gen_row for s in sides]
        arrs = {x: np.ascontiguousarray(np.stack([r[x] for r in rows])) for x in keys}
        F = fwds.get(id(model))
        if F is None:
            F = fwds[id(model)] = Forward(model, "cpu", "eager")
        enc, heads, p, _ = F(arrs, n)
        p = p.cpu().numpy()
        bank = [LO.bank_inputs(r) for r in rows]
        cand = LO.decide([s._lo["cfg"] for s in sides], [s._lo["rng"] for s in sides], [s._lo["ids"] for s in sides],
                         [b[0] for b in bank], [b[1] for b in bank], heads, p, allowed, stalled,
                         model_cell_logits(model, enc, "cpu"))
        for r, s in enumerate(sides):
            t = st(s._lo["id"])
            t["compared"] += 1
            view = s._cur[2]
            el, eh = float(view.my_elixir), any(u.side == 1 and u.y >= .5 for u in view.units)
            t["elixir_max_abs_diff"] = max(t["elixir_max_abs_diff"], abs(el - bank[r][0]))
            t["enemy_half_diff"] += int(eh != bank[r][1])
            sty = s._lo["cfg"].get("_opp_style")
            if sty is not None:
                t["styled_rows"] += 1
                t["bank_rows"] += 1
                tr, cb = el < sty["bank"] and not eh, bank[r][0] < sty["bank"] and not bank[r][1]
                t["bank_true"] += int(tr)
                t["bank_flip"] += int(tr != cb)
            a, b = out[r], cand[r]
            bad = [x for x in EXACT if a.get(x) != b.get(x)]
            if not np.array_equal(np.asarray(a.get("allowed")), np.asarray(b.get("allowed"))):
                bad.append("allowed")
            for x in CLOSE:
                if (x in a) != (x in b):
                    bad.append(x)
                elif x in a:
                    dv = abs(float(a[x]) - float(b[x]))
                    if x.startswith("lp_"):
                        t["lp_max_abs_diff"] = max(t["lp_max_abs_diff"], dv)
                    if dv > TOL:
                        bad.append(x)
            t["actions_equal"] += int(not bad)
            for x in bad:
                t["keys_diff"][x] = t["keys_diff"].get(x, 0) + 1
            if bad and len(t["first_diffs"]) < 8:
                t["first_diffs"].append(dict(what="decide", tag=s.tag, tick=int(s._cur[0]), keys=bad,
                                             prod={x: str(a.get(x)) for x in EXACT + CLOSE},
                                             cand={x: str(b.get(x)) for x in EXACT + CLOSE}))
            same = s._lo["rng"].bit_generator.state == s.rng_behave.bit_generator.state
            t["rng_after_equal"] += int(same)
            if not same:                                    # one divergence must not spoil the rest of the match
                t["rng_resync"] += 1
                s._lo["rng"] = copy.deepcopy(s.rng_behave)

    def styled(model, enc, heads, p, allowed, stalled, sides):
        out = sd0(model, enc, heads, p, allowed, stalled, sides)
        if all(getattr(s, "_lo", None) is not None for s in sides):
            try:
                check(model, sides, allowed, stalled, out)
            except Exception as e:                          # noqa: BLE001
                err("check", e)
        return out

    def apply(self, p, d):
        lo = getattr(self, "_lo", None)
        if lo is None:
            if getattr(self, "_lo_learner", False):
                G["learner_decisions"] += 1
            return apply0(self, p, d)
        tick = int(self._cur[0])
        try:
            pred = LO.after_decision(tick, d, lo["cfg"], int(getattr(self.env, "engine_delay_ticks", 0)))
        except Exception as e:                              # noqa: BLE001
            err("sched", e)
            pred = None
        r = apply0(self, p, d)
        t = st(lo["id"])
        t["decisions"] += 1
        lo["n"] += 1
        t["plays"] += int(bool(d.get("play")))
        t["style_delay_plays"] += int(bool(d.get("play")) and int(d.get("_style_delay", 0)) > 0)
        if pred is not None:
            land = self.pending[0] if self.pending else (tick if d.get("play") else None)
            got = (land, int(self.next_tick))
            t["sched"] += 1
            t["sched_equal"] += int(got == tuple(pred))
            iv = str(int(self.next_tick) - tick)
            t["intervals"][iv] = t["intervals"].get(iv, 0) + 1
            if got != tuple(pred) and len(t["first_diffs"]) < 8:
                t["first_diffs"].append(dict(what="sched", tag=self.tag, tick=tick, play=bool(d.get("play")),
                                             prod=list(got), cand=list(pred)))
        return r

    def result_hook(m):
        lo = getattr(m.opp, "_lo", None)
        if lo is not None:
            st(lo["id"])["per_match_decisions"].append(lo["n"])
        G["learner_matches"] += 1

    def run_selfplay_batch(make_env, learner, opponents, jobs, cfg_, n, on_result, *a, **kw):
        try:
            return run0(make_env, learner, opponents, jobs, cfg_, n, on_result, *a, **kw)
        finally:
            G["batches"] += 1
            dump()

    res0 = E.SelfPlayMatch.result

    def result(self):
        try:
            result_hook(self)
        except Exception as e:                              # noqa: BLE001
            err("result", e)
        return res0(self)

    def dump():
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{os.getpid()}.json").write_text(json.dumps(dict(
            pid=os.getpid(), wall_s=round(time.time() - G["t0"]), **{k: v for k, v in G.items() if k != "t0"},
            opponents=S), default=str))

    E.run_selfplay_batch, E.SelfPlayMatch.__init__, E.SelfPlaySide.apply = run_selfplay_batch, init, apply
    E.SelfPlayMatch.result, AO.styled_decisions = result, styled

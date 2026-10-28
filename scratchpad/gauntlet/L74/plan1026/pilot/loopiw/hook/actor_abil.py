"""LOOP-IW actor-path identity check: inside rl_royale's actor processes (the production config's rollouts, warm start
and screens), every RoyalePoolEnv.ability_commands / ability_options and every _fire_abilities recheck (_scan with
_any_gate / _v2_recheck) is compared with CfAbil (obsid/ability_id.JavaAbil) on the same facade battle at the same tick.
CfAbil's own env state comes from the env's events (reset, accepted plays, queue / pops, accepted presses), never from
production's Python state; production's pending queue is compared with CfAbil's after every fire (aux).
Production results are returned unchanged. Writes $LIW_OUT/<pid>.json every 30 s and at the end of each selfplay batch."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

OUT = Path(os.environ["LIW_OUT"])
sys.path.insert(0, os.environ["OBSID_DIR"])


def install(R) -> None:
    import ability_id
    J = {"j": None}
    st = dict(rows=0, last={}, t0=time.time(), dump=time.time(), err={}, skip={}, pend_diff=0, pend_checks=0,
              selftest=None, exact=None, py_ns=0, java_ns=0)
    keys: dict = {}

    def rec(kind):
        return keys.setdefault(kind, dict(calls=0, equal=0, nonempty=0, first_diffs=[]))

    def count(d, k):
        d[k] = d.get(k, 0) + 1

    def jab():
        if J["j"] is None:
            import jpype
            J["j"] = ability_id.JavaAbil(freeze=True)
            st["exact"] = bool(jpype.JClass("CfAbil").EXACT)
            st["selftest"] = dict(draw_mismatch=ability_id.selftest_draw(), libm_mismatch=ability_id.selftest_libm())
        return J["j"]

    def on(env):
        return (env.__dict__.get("_liw_on") and env.ability_policy == "v2" and env.hero_abilities
                and env.forms_mode == "deck")

    def seat(env, side):
        k = (id(env), side)
        if st["last"].get(k) != env.tick:
            st["last"][k] = env.tick
            st["rows"] += 1

    def diff(kind, env, side, prod, java, eq, extra=None):
        r = rec(kind)
        r["calls"] += 1
        r["nonempty"] += int(bool(prod) or bool(java))
        if eq:
            r["equal"] += 1
        elif len(r["first_diffs"]) < 5:
            r["first_diffs"].append(dict(tick=int(env.tick), side=int(side), tag=getattr(env, "entry", {}).get("tag", ""),
                                         prod=str(prod)[:600], java=str(java)[:600], **(extra or {})))

    def guard(name, f):
        try:
            f()
        except Exception:                                   # noqa: BLE001 -- a check never stops the actor
            count(st["err"], name + " " + traceback.format_exc(limit=4)[-500:])

    o_reset, o_act, o_queue, o_fire = R.RoyalePoolEnv._reset_abilities, R._Core.act, R.RoyalePoolEnv.queue_abilities, \
        R.RoyalePoolEnv._fire_abilities
    o_cmd, o_opt, o_scan = R.RoyalePoolEnv.ability_commands, R.RoyalePoolEnv.ability_options, R.RoyalePoolEnv._scan
    recheck_fn = R.RoyalePoolEnv._v2_recheck

    def _reset_abilities(self):
        o_reset(self)
        self._liw_on = getattr(self.core, "_cf", None) is not None
        if on(self):
            guard("reset", lambda: jab().reset(self))

    def act(core_, *, side, deck_index=-1, x=0, y=0, ability_button=None):
        env = core_.env
        t = int(env.core._cf.tick()) if on(env) else 0
        r = o_act(core_, side=side, deck_index=deck_index, x=x, y=y, ability_button=ability_button)
        if r["accepted"] and on(env):
            if ability_button is None:
                guard("played", lambda: J["j"].of(env).played(int(side), int(env.deck_ids[side][deck_index]), t,
                                                              int(env.engine_delay_ticks)))
            else:
                cid, uid = env.__dict__.get("_liw_fire", {}).get((int(side), int(ability_button)), (None, None))
                if cid is None:
                    count(st["err"], "press with no CfAbil pop")
                else:
                    guard("pressed", lambda: J["j"].of(env).pressed(int(side), cid, uid, int(env.tick)))
        return r

    def queue_abilities(self, side, commands, delay):
        if on(self):
            for b, cid, uid in commands:
                guard("queue", lambda: J["j"].of(self).queue(int(side), int(b), int(cid), int(uid), int(self.tick + delay)))
        return o_queue(self, side, commands, delay)

    def _fire_abilities(self):
        if not on(self):
            return o_fire(self)
        fire = {}

        def pop():
            d = list(J["j"].of(self).due(int(self.tick)))
            for i in range(0, len(d), 5):
                fire[(d[i + 1], d[i + 2])] = (d[i + 3], d[i + 4])
        guard("due", pop)
        self._liw_fire = fire
        r = o_fire(self)

        def cmp():
            jp = list(J["j"].of(self).pendingFlat())
            st["pend_checks"] += 1
            st["pend_diff"] += int([tuple(jp[i:i + 5]) for i in range(0, len(jp), 5)]
                                   != [tuple(int(v) for v in p) for p in self._ability_pending])
        guard("pending", cmp)
        return r

    def ability_commands(self, side):
        t = time.perf_counter_ns()
        res = o_cmd(self, side)
        st["py_ns"] += time.perf_counter_ns() - t
        if on(self):
            def chk():
                seat(self, side)
                t = time.perf_counter_ns()
                j = J["j"].commands(self, side)
                st["java_ns"] += time.perf_counter_ns() - t
                p = [tuple(int(v) for v in c) for c in res]
                diff("commands", self, side, p, j, p == j)
            guard("commands", chk)
        return res

    def ability_options(self, side, rule=None):
        t = time.perf_counter_ns()
        res = o_opt(self, side, rule)
        st["py_ns"] += time.perf_counter_ns() - t
        if on(self):
            def chk():
                seat(self, side)
                t = time.perf_counter_ns()
                j = J["j"].options(self, side, rule)
                st["java_ns"] += time.perf_counter_ns() - t
                eq = len(j) == len(res)
                f32 = eq
                for o, r in zip(res, j):
                    eq &= tuple(int(v) for v in o["cmd"]) == tuple(int(v) for v in r[:3])
                    eq &= o["card"] == J["j"].names[int(r[1])]
                    a = np.asarray(o["feat"], np.float64)
                    eq &= a.shape == r[4:].shape and a.tobytes() == r[4:].tobytes()
                    f32 &= a.shape == r[4:].shape and a.astype(np.float32).tobytes() == r[4:].astype(np.float32).tobytes()
                    if rule is not None:
                        eq &= np.float64(o["q"]).tobytes() == np.float64(r[3]).tobytes()
                diff("options" + ("_label" if rule is not None else ""), self, side,
                     [(o["cmd"], o.get("q"), [round(float(v), 6) for v in o["feat"]]) for o in res],
                     [(tuple(int(v) for v in r[:3]), float(r[3]), [round(float(v), 6) for v in r[4:]]) for r in j], eq)
                rec("options_f32")["calls"] += 1
                rec("options_f32")["equal"] += int(f32)
                st["opt_rows"] = st.get("opt_rows", 0) + len(res)
            guard("options", chk)
        return res

    def _scan(self, side, gate):
        res = o_scan(self, side, gate)
        learned = gate is R._any_gate
        if (learned or getattr(gate, "__func__", None) is recheck_fn) and on(self):
            def chk():
                j = J["j"].recheck(self, side, learned)
                p = [tuple(int(v) for v in c) for c in res]
                diff("recheck", self, side, p, j, p == j)
            guard("recheck", chk)
        return res

    R.RoyalePoolEnv._reset_abilities, R._Core.act = _reset_abilities, act
    R.RoyalePoolEnv.queue_abilities, R.RoyalePoolEnv._fire_abilities = queue_abilities, _fire_abilities
    R.RoyalePoolEnv.ability_commands, R.RoyalePoolEnv.ability_options, R.RoyalePoolEnv._scan = \
        ability_commands, ability_options, _scan

    def dump():
        j = J["j"]
        cnt = {}
        if j is not None:                                   # CfAbil's own counters, summed over this process's cores
            for k in ("nIw", "nV2", "nNear", "nHazard", "nanos", "calls"):
                cnt["java_" + k] = int(sum(getattr(c, k) for c in j.all))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{os.getpid()}.json").write_text(json.dumps(dict(
            pid=os.getpid(), wall_s=round(time.time() - st["t0"]), seat_rows=st["rows"], opt_rows=st.get("opt_rows", 0),
            exact=st["exact"], selftest=st["selftest"], py_ns=st["py_ns"], java_ns=st["java_ns"],
            pending_checks=st["pend_checks"], pending_diff=st["pend_diff"], errors=st["err"], keys=keys, **cnt),
            default=str))

    import atexit
    atexit.register(dump)
    import threading

    def loop():
        while True:
            time.sleep(30)
            try:
                dump()
            except Exception:                               # noqa: BLE001
                pass
    threading.Thread(target=loop, daemon=True).start()

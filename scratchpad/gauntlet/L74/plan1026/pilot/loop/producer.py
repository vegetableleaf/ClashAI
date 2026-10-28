"""LOOP-INT (plan1026 pilot fast loop): one producer = one in-process JVM running CfTrain (N crforge matches on T
threads, e1_eval.SelfPlayMatch's schedule + the obsid builders in Java) and this Python side, which does what
rl_royale.actor_main's self-play branch does per decision with PRODUCTION code: the per-side state is a real
``e1_eval.SelfPlaySide`` (built for each job on a capture-only env: deck slots, costs, RNG streams, cfg), the decide is
``e1_eval.sample_decide_batch`` (learner) / the opponent's own cfg, the record is ``SelfPlaySide._record`` +
``_traj_arrays``. What Java replaces: ``SelfPlayMatch.due`` / ``SelfPlaySide.apply`` / ``Match._land`` (CfTrain) and
``Match.prepare`` + ``gen_row`` (the obsid builders). The forward runs on this process's device (``GenPolicy.heads_t``
on a batch gathered straight from the JVM's buffers), one forward per policy per round.

Not supported yet (each raises): hero ability presses (LOOP-IW), opp_style, follow-ups, pipelined decisions, tap
loss / slow, tower troops, mid-match starts, posture / ability heads, memory models (LOOP-MEM), decision rules in the
sampled decide (LOOP-CTX), record_phi / crown / habit / spell tracking (record fields that need production state).
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
OBSID = REPO / "scratchpad/gauntlet/L74/speed/crforge/obsid"
SPEED = REPO / "scratchpad/gauntlet/L74/speed/crforge"
CFCORE = REPO / "scratchpad/gauntlet/L74/crforge/facade/CfCore.java"
JAVA_SRC = [CFCORE, SPEED / "CfSpeed.java"] + [OBSID / f for f in ("CfObsBind.java", "CfOppElixir.java", "CfIdent.java",
                                                                  "CfCue.java", "CfPubObj.java")] + [HERE / "CfTrain.java"]
UNSUPPORTED_CFG = ("posture", "ability", "spell_track", "crown_track", "habit_track", "record_phi", "record_ctx",
                   "record_elixir", "pipeline_decisions", "tap_loss", "tap_slow", "follow_ups", "_opp_style",
                   "own_effects", "predict_drops", "afford_ticks")
UNSUPPORTED_SPEC = ("opp_tower", "start")


def compile_java(build: Path, lib: Path) -> None:
    """javac the facade + the obsid builders + CfTrain into ``build`` (skipped when every class is newer than its source)."""
    import subprocess
    build.mkdir(parents=True, exist_ok=True)
    stamp = build / ".src_mtime"
    newest = max(p.stat().st_mtime for p in JAVA_SRC)
    if stamp.exists() and float(stamp.read_text()) >= newest:
        return
    cp = os.pathsep.join(str(p) for p in sorted(lib.glob("*.jar")))
    subprocess.run(["javac", "-nowarn", "-d", str(build), "-cp", cp] + [str(p) for p in JAVA_SRC], check=True)
    stamp.write_text(str(newest))


class Rows:
    """numpy views of CfTrain's direct buffers (no copy; Java writes them during step())."""
    KEYS = (("tok", "tokB", np.float32, (64, 14)), ("mask", "maskB", np.uint8, (64,)), ("sc", "scB", np.float32, (70,)),
            ("unit_form", "formB", np.int8, (64,)), ("opp_past", "oppPastB", np.float32, (3, 5)),
            ("ids", "idsB", np.int64, (48,)), ("past", "pastB", np.float32, (3, 5)),
            ("projectiles", "projB", np.float32, (64, 8)), ("effects", "effB", np.float32, (32, 6)),
            ("own_ability", "abilB", np.float32, (8, 7)), ("opp_cycle", "cycB", np.float32, (8, 4)),
            ("cue", "cueB", np.float32, (64, 22)), ("meta", "metaB", np.int32, (8,)), ("act", "actB", np.int32, (5,)),
            ("el", "elB", np.float64, ()), ("tal", "talB", np.int32, (6,)))

    def __init__(self, L, n: int):
        for k, attr, dt, shape in self.KEYS:
            setattr(self, k, np.frombuffer(memoryview(getattr(L, attr)), dt).reshape((2 * n,) + shape))
        self.res = np.frombuffer(memoryview(L.resB), np.int32).reshape(n, 8)


# ids [48] = hand_slot 4, hand_card 4, hand_form 4, next_card, next_form, deck_card 8, deck_form 8, slot_card 9, slot_form 9
ID_SPLIT = (("hand_slot", 0, 4), ("hand_card", 4, 8), ("hand_form", 8, 12), ("next_card", 12, None),
            ("next_form", 13, None), ("deck_card", 14, 22), ("deck_form", 22, 30), ("slot_card", 30, 39),
            ("slot_form", 39, 48))


class Producer:
    def __init__(self, base: dict, n: int, threads: int, device: str, build: Path, aid: int = 0):
        import jpype
        import torch
        self.base, self.n, self.dev, self.aid = base, int(n), device, int(aid)
        torch.set_num_threads(int(base.get("actor_threads", 1)))
        # lead ruling 10-28 (LOOP-LRN): no TF32 in any forward that produces / recomputes log-probs
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
        from pipeline import crforge_core as cc
        compile_java(build, cc.LIB)
        if not jpype.isJVMStarted():
            cp = sorted(str(p) for p in cc.LIB.glob("*.jar")) + [str(build)]
            jpype.startJVM(f"-Xmx{os.environ.get('CRFORGE_XMX', '16g')}", classpath=cp, convertStrings=True)
        sys.path.insert(0, str(OBSID))
        import obs_id                                        # noqa: F401  (table fillers; sets ROYALE_ENGINE=crforge)
        import cf_loop_obs
        from pipeline import e1_eval as E
        from pipeline import rl_royale as R
        from pipeline.royale_env import RoyaleSelfPlayEnv
        from pipeline.royale_runtime import require_same
        require_same(base.get("runtime"))
        self.E, self.R, self.jpype, self.torch, self.obs_id, self.fill_fn = E, R, jpype, torch, obs_id, cf_loop_obs.Cohort.fill
        g = base["gen"]
        from pipeline.model_gen import GenModel
        net = GenModel(d=int(base["d"]), layers=int(base["layers"]), d_c=int(g["d_c"]), n_cards=len(g["card_vocab"]),
                       feature_version=int(g.get("feature_version", 1))).to(device).eval()
        self.net, self.model = net, E.GenPolicy(net, g["card_vocab"])
        self.opp_cache: dict = {}
        # the capture-only env: SelfPlaySide's deck slots / costs / forms come from a real RoyaleSelfPlayEnv.reset whose
        # engine calls are stubbed (CfTrain runs the match)
        env = self.env = RoyaleSelfPlayEnv(decision_ticks=int(base["decide_every"]), forms_mode=base.get("forms_mode", "base"),
                                           hero_abilities=base.get("hero_abilities", False),
                                           ability_policy=base.get("ability_policy", "generic"),
                                           ability_features=base.get("ability_features") or "base")
        if env.hero_abilities:
            raise NotImplementedError("hero ability presses are not in CfTrain yet (LOOP-IW)")
        self._got = []
        tmpl = env.core
        self.names = {c.card_id: c.name for c in tmpl.cards()}
        self.card_names = dict(env.names)
        tmpl_cf = tmpl._cf
        real_reset = tmpl.reset                              # kept: _form_loads probes need its ValueError

        def capture(seed, setup):
            self._got.append((seed, setup))
            real_reset(seed, setup)
        tmpl.reset = capture
        env._advance_to = lambda target: None
        env.raw = lambda: None
        J = jpype.JClass
        self.JStr, self.JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
        L = self.L = J("CfTrain")(cc._jvm()["tables"], tmpl_cf, self.n, int(threads))
        L.extrap = int(base.get("extrapolate_ticks") or 0)
        L.tailCap, L.warmup = int(env.tail_cap), int(env.warmup_ticks)
        L.cellOff = 0.5 if base["grid"] == "floor" else 0.0
        if int(env.engine_delay_ticks) != int(L.ENG):
            raise RuntimeError(f"engine delay {env.engine_delay_ticks} != CfTrain.ENG {L.ENG}")
        # table fillers (obsid's, pointed at CfTrain's tables), as cf_loop_obs.Cohort
        main = obs_id.JavaMain()
        main.names, main.keys, main.gid, main.card_names = L.names, L.keys, self.model.gid, self.card_names
        shim = SimpleNamespace(env=SimpleNamespace(names=self.card_names, feature_version=6), state={"projectiles": []})
        main.spell_table(shim)
        pub = obs_id.JavaPub(main, self.model)
        pub.T = L.pub
        pub.tables(shim)
        self.main, self.pub = main, pub
        # cue rows for every seat (a policy without a cue layer never reads them; the weights, hence cue_in, arrive later)
        self.jc = obs_id.JavaCue(main, E)
        L.cue = self.jc.T
        L.start()
        self.v = Rows(L, self.n)
        self.serial = 0
        self.stats = Counter()
        self.tm = Counter()                                  # seconds per stage (java / fill / start / decide / forward ...)
        self.progress = None                                 # bench.py: called after every round with the totals

    # ------------------------------------------------------------------------------------------------ tables
    def _fill(self) -> int:
        """cf_loop_obs.Cohort.fill with ONE fix (a, compare.py lint_d1 u0000 job 0: an evolved body's opp_past form 0
        vs production 1): a detector key "card|body row|form" carries CfOppElixir's form, which leaves out
        STATUS_EVOLVED; production resolves the REAL raw() entity, whose status_flags carry CfCore.evolvedBit (an _EV
        body row). So the entity built for the key gets bit 8 from the body row name, as state() sets it."""
        from pipeline import royale_heroiw as heroiw, vocab
        from pipeline.obs_contract import catalog_card_form
        from pipeline.opp_elixir_count import _catalog_names
        from pipeline.public_observation import public_frame
        L, k = self.L, 0
        for miss in L.keys.takeMissing():
            key, _ = str(miss).rsplit("#", 1)
            card, body, form = key.split("|")
            flags = {2: 16, 1: 8}.get(int(form), 0) | (8 if "_EV" in body.upper() else 0)
            ent = dict(side=1, x=0.0, y=0.0, hp=1, max_hp=1, entity_id=0, name=self.card_names.get(int(card), card),
                       card_id=int(card), status_flags=flags)
            if heroiw.ENABLED and heroiw.public_identity(body) is not None:
                ent.update(name="IceWizard", public_card_id=heroiw.public_identity(body), public_form=2)
            f = public_frame({"tick": 0, "entities": [ent]}, source="sim")["entities"]
            name = _catalog_names().get(f[0]["card_id"]) if f else None
            L.keys.putBody(key, self.main.key_index(vocab.engine_key(name) if name else None),
                           int(catalog_card_form(f[0]["card_id"])[1]) if f else 0)
            k += 1
        shim = SimpleNamespace(L=L, main=self.main, pub=self.pub, jc=self.jc, names=self.card_names)
        return k + self.fill_fn(shim)                      # the rest (names, pub, cue, cyc) as Cohort.fill does

    def _resolve_rows(self) -> None:
        """Rows that met a table key Python had not filled: fill, resume them; until none is left."""
        for _ in range(20):
            if not (self.v.meta[:, 0].astype(bool) & (self.v.meta[:, 5] != 6)).any():
                return
            self.stats["fills"] += self._fill()
            if int(self.L.rebuild()) == 0:
                return
        raise RuntimeError("rows still missing table keys after 20 fills")

    # ------------------------------------------------------------------------------------------------ jobs
    def _policy(self, path: str):
        if path not in self.opp_cache:
            pol, mi = self.E.load_policy(self.R.REPO / path, self.dev)
            if not isinstance(pol, self.E.GenPolicy) or pol.gid != self.model.gid:
                raise NotImplementedError(f"opponent {path}: CfTrain shares one card-id table per match (same vocab only)")
            if getattr(pol.model, "mem", None) is not None:
                raise NotImplementedError(f"opponent {path}: inputs the learner's builders do not make")
            self.opp_cache[path] = (pol, str(mi.get("grid", "floor")))
        return self.opp_cache[path]

    def _start(self, i: int, job, cfg: dict, opps: dict) -> dict:
        """SelfPlayMatch.__init__ for job (i, spec, k, over) on match slot ``i``: the two SelfPlaySides on the capture
        env, then CfTrain.setJob with CfCore.reset's arguments (CrforgeCore.reset's conversion of the setup)."""
        E, env = self.E, self.env
        ei, spec, k, over = job
        for key in UNSUPPORTED_SPEC:
            if key in spec:
                raise NotImplementedError(f"spec key {key!r} is not in CfTrain yet")
        L_ = int(spec["learner_side"])
        decks = {L_: spec["learner_deck"], 1 - L_: spec["opp_deck"]}
        opp, ocfg = opps[spec["opp"]["id"]]
        lcfg = {**cfg, **over, "entry_index": ei}
        ocfg = {**ocfg, **{x: v for x, v in over.items() if x not in ("obs_seed", "pipeline_decisions", "pipeline_tau_delta")},
                "entry_index": ei}
        E.enable_sim_features(env, self.model, opp)
        kw = {}
        if "levels" in spec:
            lv = {L_: spec["levels"]["learner"], 1 - L_: spec["levels"]["opp"]}
            kw["levels"] = {"cards": [lv[0]["cards"], lv[1]["cards"]], "towers": [lv[0]["tower"], lv[1]["tower"]]}
        self._got.clear()
        env.reset(decks[0], decks[1], int(spec["seed"]), **kw)
        seed, setup = self._got[-1]
        from pipeline.adaptive_opponents import style_config
        ocfg = style_config(ocfg, int(spec["seed"]), int(k))
        tag = str(spec["tag"])
        ls = E.SelfPlaySide(env, spec["learner_deck"], L_, tag, k, lcfg, self.model)
        os_ = E.SelfPlaySide(env, spec["opp_deck"], 1 - L_, f"{tag}:opp", k, ocfg, opp)
        ls.other, os_.other = os_, ls
        sides = sorted((ls, os_), key=lambda s: s.side)
        for s in sides:
            bad = [x for x in UNSUPPORTED_CFG if s.cfg.get(x)]
            if bad:
                raise NotImplementedError(f"cfg {bad} is not in CfTrain yet")
            if s.pipe or s.drops is not None or s.own_fx is not None or s.delay <= 0:
                raise NotImplementedError("CfTrain ports the delayed-play rollout schedule only")
        # CrforgeCore.reset's conversion
        names = self.names
        d = [[names[int(c)] for c in dk] for dk in setup.decks]
        forms = setup.forms or [[0] * 8, [0] * 8]
        lv = getattr(setup, "levels", None) or [[16] * 8, [16] * 8]
        tl = getattr(setup, "tower_levels", None) or [16, 16]
        a = []
        for s in sides:
            slot_of = {ix: slot for slot, ix in s.deck_index_of_slot.items()}
            dk, deal = env.decks[s.side], env.deal[s.side]
            inv = [slot_of.get(list(dk).index(nm), 8) for nm in deal]
            a.append((self.JStr(d[s.side]), self.JInt([int(x) for x in forms[s.side]]),
                      self.JInt([int(x) for x in setup.decks[s.side]]), self.JInt([int(x) for x in lv[s.side]]),
                      self.JInt(inv), int(tl[s.side]), int(s.cfg["decide_every"]), int(s.delay)))
            from pipeline.dataset_gen import card_key
            for cid, nm in zip(env.deck_ids[s.side], s.engine_deck):   # JavaIdent.of: the policy's gid of each deck card
                if card_key(nm) in self.model.gid:
                    self.L.putGidMatch(i, int(cid), int(self.model.gid[card_key(nm)]))
        self.serial += 1
        self.L.setJob(i, self.serial, int(seed) & 0x7FFFFFFF, *a[0], *a[1])
        for s in sides:                                       # Match.prepare's first-decision clock
            s.last_play_tick = None
            s.fl = Counter()                                  # fast-loop tallies (result())
            s.fl_el = []
        return {"serial": self.serial, "sides": sides, "learner": ls, "opp": os_, "spec": spec, "k": k,
                "t0": time.perf_counter(), "form_fallbacks": [list(x) for x in getattr(env, "form_fallbacks", [])]}

    # ------------------------------------------------------------------------------------------------ results
    def _result(self, i: int, m: dict) -> dict:
        """SelfPlayMatch.result's record from CfTrain's end state + tallies and the sides' own (production) tallies."""
        E = self.E
        res, tal = self.v.res[i], self.v.tal
        end, over, winner, cr = int(res[1]), bool(res[2]), int(res[3]), (int(res[4]), int(res[5]))
        for s in m["sides"]:
            t = tal[2 * i + s.side]
            s.n_att, s.n_acc, s.n_unlanded = int(t[0]), int(t[1]), int(t[2])
            s.refuse = Counter({k: v for k, v in (("not_in_hand", int(t[3])), ("refused_engine", int(t[4])),
                                                  ("match_over_before_landing", int(t[2]))) if v})
        ls, os_ = m["learner"], m["opp"]
        side = ls.side
        crowns = (cr[side], cr[1 - side])
        w = {0: 0, 1: 1}.get(winner, -1) if over else -1
        outcome = ("draw" if crowns[0] == crowns[1] else "win" if crowns[0] > crowns[1] else "loss") if w < 0 else \
            ("win" if w == side else "loss")
        cfg = ls.cfg
        minutes = end * E.TICK_S / 60.0
        pg = np.asarray(ls.p_gates, dtype=np.float64)
        r = {"tag": ls.tag, "k": int(ls.k), "slot": cfg["slot"], "port": cfg["port"], "split": None,
             "entry_index": cfg["entry_index"], "policy": cfg["policy"], "obs": cfg["obs"], "tau": cfg["tau"],
             "afford_mask": cfg["afford_mask"], "stall_elixir": cfg["stall_elixir"], "p_random": cfg["p_random"],
             "obs_seed": ls.obs_seed_used, "side": side, "outcome": outcome, "crowns_for": crowns[0],
             "crowns_against": crowns[1], "end_tick": end, "seconds": round(end * E.TICK_S, 1), "terminated": over,
             "termination_reason": "game_over" if over else None,
             "last_ghost_tick": 0, "after_script": False, "won_after_script": False, "ghost_plays": os_.n_att,
             "ghost_delivered": os_.n_acc, "ghost_refused": os_.n_att - os_.n_acc - os_.n_unlanded,
             "ghost_undelivered": os_.n_unlanded, "ghost_distinct_delivered": None,
             "ghost_refuse_reasons": dict(os_.refuse),
             "plays_attempted": ls.n_att, "plays_accepted": ls.n_acc, "plays_refused": ls.n_att - ls.n_acc,
             "refuse_reasons": dict(ls.refuse), "plays_per_min": round(ls.n_att / minutes, 3) if minutes else None,
             "accepted_per_min": round(ls.n_acc / minutes, 3) if minutes else None,
             "card_mix_attempted": dict(ls.fl), "card_mix_accepted": None, "play_elixir": list(ls.fl_el), "plays": None,
             "stall_fired": ls.n_stall, "no_affordable": ls.n_noaff, "decisions": ls.n_dec, "degraded_obs": ls.n_dec,
             "degraded_equals_decisions": True if cfg["obs"] == "live" else None,
             "p_gate_mean": round(float(pg.mean()), 4) if len(pg) else None,
             "p_gate_p90": round(float(np.percentile(pg, 90)), 4) if len(pg) else None,
             "frac_gt_tau": round(float((pg > cfg["tau"]).mean()), 4) if len(pg) else None,
             "real_outcome": None, "s1_split": None, "group": None, "unmapped": [],
             "wall_s": round(time.perf_counter() - m["t0"], 1),
             **({"traj": self.fast_traj(ls, E)} if cfg.get("record") else {}),
             "action_delay_ticks": ls.delay, "plays_unlanded": ls.n_unlanded,
             "plays_refused_at_landing": ls.n_att - ls.n_acc - ls.n_unlanded,
             **({"extrapolate_ticks": ls.extrap} if ls.extrap else {}),
             **({"forms_mode": "deck", "form_fallbacks": m["form_fallbacks"]}
                if getattr(self.env, "forms_mode", "base") == "deck" else {}),
             "fastloop": {"crashed": bool(res[7]), "approx": ["card_mix_accepted", "plays", "opp_counter",
                                                              "refuse_reasons names", "ghost_distinct_delivered"]}}
        r["league"] = dict(m["spec"])
        r["opp_side"] = {"side": os_.side, "policy": os_.cfg["policy"], "plays_attempted": os_.n_att,
                         "plays_accepted": os_.n_acc, "plays_per_min": round(os_.n_att / minutes, 3) if minutes else None,
                         "stall_fired": os_.n_stall, "decisions": os_.n_dec}
        if cfg.get("record"):
            r["rollout_index"], r["update"] = int(r["k"]), int(cfg.get("update", 0))
        return r

    # ------------------------------------------------------------------------------------------------ one update
    def run(self, update: int, sd: bytes, jobs: list) -> tuple[list[dict], list[dict], dict]:
        """actor_main's ('selfplay', update, sd, jobs) -> (results, skipped, stats)."""
        R, base = self.R, self.base
        t0 = time.perf_counter()
        msd, psd = R.split_actor_sd(sd, self.dev)
        if R.pop_prefix(msd, R.ABILITY_SD) or psd:
            raise NotImplementedError("posture / ability heads are not in the fast loop yet")
        self.net.load_state_dict(msd)
        self.net.eval()
        if getattr(self.net, "mem", None) is not None:
            raise NotImplementedError("memory models: LOOP-MEM's Java tables are not in CfTrain yet")
        cfg = R.actor_cfg(base, "rollout", self.aid, self.dev)
        need = {j[1]["opp"]["path"] for j in jobs}
        for pth in [x for x in self.opp_cache if x not in need]:
            del self.opp_cache[pth]
        ocfg0 = {k: v for k, v in cfg.items() if k not in ("posture", "ability", "tau_phase")}
        specs = {j[1]["opp"]["id"]: j[1]["opp"] for j in jobs}
        opps = {}
        for j in jobs:
            o = j[1]["opp"]
            pol, grid = self._policy(o["path"])
            oc = {**ocfg0, "policy": base["league_opp_policy"], "record": False, "T_gate": None, "T": R.opp_T(base),
                  **{k: base[k] for k in R.AO.STYLE_KEYS if k in base}, "grid": grid}
            opps[o["id"]] = (pol, R.live_opp_cfg(R.own_opp_cfg(oc, specs[o["id"]], base), specs[o["id"]], base))
        todo = list(R.rollout_jobs(jobs, update, base.get("learner_pipeline_frac", 0), base["seed"]))[::-1]
        live: dict = {}                                       # match slot -> its record
        results, skipped, st = [], [], Counter()
        L, v = self.L, self.v
        for i in range(self.n):
            if todo:
                live[i] = self._start(i, todo.pop(), cfg, opps)
        tm = self.tm
        while live:
            a = time.perf_counter()
            L.step()
            b = time.perf_counter()
            self._resolve_rows()
            tm["java"] += b - a
            tm["fill"] += time.perf_counter() - b
            for i in np.flatnonzero(v.res[:, 0]):
                v.res[i, 0] = 0
                m = live.pop(int(i))
                if int(v.res[i, 6]) != m["serial"]:
                    raise RuntimeError(f"match slot {i}: result serial {v.res[i, 6]} != job {m['serial']}")
                if v.res[i, 7]:                               # crforge refused a case: production's actor would crash
                    skipped.append({"tag": m["spec"]["tag"], "why": f"crforge: {L.firstCrash}"})
                else:
                    results.append(self._result(int(i), m))
                if todo:
                    s0 = time.perf_counter()
                    live[int(i)] = self._start(int(i), todo.pop(), cfg, opps)
                    tm["start"] += time.perf_counter() - s0
            c = time.perf_counter()
            self._decide(live)
            tm["decide"] += time.perf_counter() - c
            st["rounds"] += 1
            if self.progress is not None:
                self.progress(len(results), int(L.rowsBuilt.get()))
        results.sort(key=R.row_key)
        stats = {"wall_s": time.perf_counter() - t0, "matches": len(results), "rounds": st["rounds"],
                 "crashed": len(skipped), "fills": self.stats["fills"], "time": dict(tm),
                 "java_engine_core_s": int(L.engineNs.get()) / 1e9, "java_obs_core_s": int(L.obsNs.get()) / 1e9,
                 "rows": int(L.rowsBuilt.get()), "first_crash": None if L.firstCrash is None else str(L.firstCrash)}
        return results, skipped, stats

    def _decide(self, live: dict) -> None:
        """The round's forward (one per policy) + decide + record + actions, as run_selfplay_batch's round."""
        E, torch, v = self.E, self.torch, self.v
        from pipeline import engine_play as ep
        from pipeline.dataset_gen import SC_SLOT_COLS
        from pipeline.royale_env import SCALE
        rows = np.flatnonzero(v.meta[:, 0])
        if not len(rows):
            return
        groups: dict = {}
        for r in rows:
            i, seat = divmod(int(r), 2)
            m = live[i]
            if int(v.meta[r, 6]) != m["serial"]:
                raise RuntimeError(f"row {r}: job serial {v.meta[r, 6]} != {m['serial']}")
            s = m["sides"][seat]
            groups.setdefault(id(s.model), []).append((int(r), s))
        K = 18                                               # crforge_core.K
        for members in groups.values():
            idx = np.array([r for r, _ in members])
            sides = [s for _, s in members]
            model, c = sides[0].model, sides[0].cfg
            batch = {"tok": v.tok[idx], "mask": v.mask[idx].astype(bool), "sc": v.sc[idx], "past": v.past[idx],
                     "unit_form": v.unit_form[idx], "opp_past": v.opp_past[idx], "projectiles": v.projectiles[idx],
                     "effects": v.effects[idx], "own_ability": v.own_ability[idx], "opp_cycle": v.opp_cycle[idx]}
            if self.jc is not None:
                batch["cue"] = v.cue[idx]
            ids = v.ids[idx]
            for k, a, b in ID_SPLIT:
                batch[k] = ids[:, a:b] if b is not None else ids[:, a]
            batch["sc"][:, SC_SLOT_COLS] = 0.0                # GenPolicy.row's zeroing (batch["sc"] is a copy)
            keys = E.gen_row_keys(model.model)
            f0 = time.perf_counter()
            with torch.no_grad():
                tb = {k: torch.from_numpy(np.ascontiguousarray(batch[k])).to(c["device"]) for k in keys}
                enc, heads = model.heads_t(tb)
                B = heads["card"].shape[0]
                hand = torch.zeros(B, 9, dtype=torch.bool, device=heads["card"].device)
                hand = hand.scatter(1, tb["hand_slot"], True)[:, :8].cpu().numpy()
                p = torch.sigmoid(heads["gate"]).cpu().tolist()
            self.tm["forward"] += time.perf_counter() - f0      # incl. H2D / D2H (the .cpu() syncs)
            self.tm["fwd_rows"] += len(idx)
            self.tm["fwd_calls"] += 1
            if c["policy"] != "sample":
                raise NotImplementedError(f"policy {c['policy']!r}: the fast loop samples (learner and league)")
            d0 = time.perf_counter()
            if FAST_DECIDE and fast_ok(c):
                self._fast_group(model, c, sides, idx, batch, keys, enc, heads, p, hand)
                self.tm["decide_py"] += time.perf_counter() - d0
                continue
            for j, s in enumerate(sides):                    # Match.prepare's state the decide / record read
                r = idx[j]
                tick, vt = int(v.meta[r, 3]), int(v.meta[r, 4])
                if s.last_play_tick is None:
                    s.last_play_tick = tick
                s._cur = (tick, SimpleNamespace(t_sec=vt * 0.05), SimpleNamespace(my_elixir=float(v.el[r])))
                s._view_tick = vt
                s._gen_row = {k: batch[k][j] for k in keys}
                s._obs = (s._gen_row["tok"], s._gen_row["mask"], s._gen_row["sc"], s._gen_row["past"])
            pre = [s.pre(hand[j]) for j, s in enumerate(sides)]
            allowed = np.stack([x[1] for x in pre])
            stalled = np.array([x[2] for x in pre], dtype=bool)
            decisions = E.sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, c)
            for j, (s, d) in enumerate(zip(sides, decisions)):
                r = idx[j]
                s._record(p[j], d)
                a = v.act[r]
                if d["play"]:
                    X, Y = ep.cell_to_engine(d["cell"], s.mirror, s.cfg["grid"])
                    a[:] = (1, int(d["slot"]), int(d["cell"]), int(X) * SCALE // K, int(Y) * SCALE // K)
                    s.fl[s.deck.cards[d["slot"]]] += 1        # card_mix_attempted / play_elixir / stall (Match._land)
                    s.fl_el.append(float(int(s._cur[2].my_elixir)))
                    s.n_stall += int(d["why"] == "stall")
                else:
                    a[:] = (0, -1, -1, 0, 0)
            self.tm["decide_py"] += time.perf_counter() - d0

    # ------------------------------------------------------------------------------------------------ fast decide
    def _fast_group(self, model, c, sides, idx, batch, keys, enc, heads, p, hand) -> None:
        """Match.pre + e1_eval.sample_decide_batch + decision_options.decide (decode 'sample', no rules) + _record for one
        policy group, vectorised where the arithmetic allows it and EXACT: the same torch ops on the same batch, every
        draw from the row's own rng in production's order (gate, card, cell), numpy Generator.choice reproduced as its
        own cdf / searchsorted('right') on one uniform. compare.py asserts it against production (actor_main)."""
        import math
        import torch
        from pipeline import engine_play as ep
        from pipeline.decision_options import model_cell_logits, phase_index
        from pipeline.royale_env import SCALE
        v, n = self.v, len(sides)
        tick = v.meta[idx, 3].astype(np.int64)
        vt = v.meta[idx, 4].astype(np.int64)
        el_int = np.floor(v.el[idx])                         # float(int(view.my_elixir)), elixir >= 0
        costs = np.array([s.costs for s in sides], dtype=np.float64)
        allowed = hand & (costs <= el_int[:, None] + 1e-6)   # allowed_slots (afford_mask)
        stalled = np.zeros(n, dtype=bool)                    # anti_stall with stall_elixir None
        T, tau = float(c.get("T", 0.5)), float(c["tau"])
        T_gate = float(c.get("T_gate") or T)
        tau_r = None
        if c.get("tau_phase") is not None:
            tau_r = np.asarray(c["tau_phase"], dtype=np.float64)[phase_index([float(t) * 0.05 for t in vt])]
        any_allowed = allowed.any(axis=1)
        gate_sampled = any_allowed & ~stalled
        logit_tau = math.log(tau / (1.0 - tau)) if tau_r is None else np.log(tau_r / (1.0 - tau_r))
        z_gate = heads["gate"].detach().cpu().numpy().astype(np.float64)
        with np.errstate(over="ignore"):
            p_b = 1.0 / (1.0 + np.exp(-(z_gate - logit_tau) / T_gate))
        rngs = [s.rng_behave for s in sides]
        g = np.zeros(n, dtype=bool)
        lp_gate, lp_card, lp_cell = np.zeros(n), np.zeros(n), np.zeros(n)
        for r in np.flatnonzero(gate_sampled):
            g[r] = rngs[r].random() < p_b[r]
            lp_gate[r] = math.log(p_b[r] if g[r] else 1.0 - p_b[r])
        playing = any_allowed & (stalled | g)
        slots = np.full(n, -1, dtype=np.int64)
        cells = np.full(n, -1, dtype=np.int64)
        play_idx = np.flatnonzero(playing)
        if len(play_idx):
            with torch.no_grad():
                cl = heads["card"].clone().masked_fill(~torch.from_numpy(allowed).to(heads["card"].device), float("-inf"))
                card_probs = torch.softmax(cl.double() / T, dim=-1).cpu().numpy()
            slots[play_idx] = self._choice(card_probs[play_idx], [rngs[r] for r in play_idx])
            for r in play_idx:
                lp_card[r] = math.log(card_probs[r, slots[r]])
            with torch.no_grad():
                cel = model_cell_logits(model, enc, heads["card"].device)(list(map(int, play_idx)),
                                                                         [int(slots[r]) for r in play_idx])
                cell_probs = torch.softmax(cel.double() / T, dim=-1).cpu().numpy()
            cells[play_idx] = self._choice(cell_probs, [rngs[r] for r in play_idx])
            for j, r in enumerate(play_idx):
                lp_cell[r] = math.log(cell_probs[j, cells[r]])
        K = 18
        for j, s in enumerate(sides):
            r = idx[j]
            if s.last_play_tick is None:                     # Match.prepare's first-decision clock
                s.last_play_tick = int(tick[j])
            pj = p[j]
            s.n_dec += 1                                     # SelfPlaySide._record's tallies
            s.p_gates.append(pj)
            if not any_allowed[j]:
                s.n_noaff += 1
            if s.cfg.get("record"):
                rows = s.__dict__.setdefault("fl_rows", {})
                for k in keys:
                    rows.setdefault(k, []).append(batch[k][j])
                for k, x in (("tick", int(tick[j])), ("allowed", allowed[j]), ("stalled", bool(stalled[j])),
                             ("gate_sampled", bool(gate_sampled[j])), ("played", bool(playing[j])),
                             ("slot", int(slots[j])), ("cell", int(cells[j])), ("lp_gate", float(lp_gate[j])),
                             ("lp_card", float(lp_card[j])), ("lp_cell", float(lp_cell[j])), ("p_gate", float(pj)),
                             ("T", T)) + ((("gate_tau", float(tau_r[j])),) if tau_r is not None else ()):
                    rows.setdefault(k, []).append(x)
            a = v.act[r]
            if playing[j]:
                X, Y = ep.cell_to_engine(int(cells[j]), s.mirror, s.cfg["grid"])
                a[:] = (1, int(slots[j]), int(cells[j]), int(X) * SCALE // K, int(Y) * SCALE // K)
                s.fl[s.deck.cards[int(slots[j])]] += 1
                s.fl_el.append(float(el_int[j]))
            else:
                a[:] = (0, -1, -1, 0, 0)

    @staticmethod
    def _choice(P, rngs):
        """numpy Generator.choice(len(p), p=p) per row: cdf = p.cumsum(); cdf /= cdf[-1]; one uniform;
        cdf.searchsorted(u, 'right') (numpy/random/_generator.pyx). Row-wise cumsum adds in the same order."""
        cdf = np.cumsum(P, axis=1)
        cdf /= cdf[:, -1:]
        u = np.array([rg.random() for rg in rngs])
        return (cdf <= u[:, None]).sum(axis=1)

    @staticmethod
    def fast_traj(s, E) -> dict:
        """SelfPlaySide._traj_arrays from the fast record (same keys, dtypes and order of rows)."""
        rows = s.__dict__.get("fl_rows")
        if not rows:
            return s._traj_arrays()
        st = lambda k: np.stack(rows[k])                       # noqa: E731
        sc = lambda k, dt: np.array(rows[k], dtype=dt)         # noqa: E731
        out = {"tok": st("tok").astype(np.float32), "mask": st("mask").astype(bool), "sc": st("sc").astype(np.float32),
               "past": st("past").astype(np.float32), "allowed": st("allowed").astype(bool),
               "stalled": sc("stalled", bool), "gate_sampled": sc("gate_sampled", bool), "played": sc("played", bool),
               "slot": sc("slot", np.int64), "cell": sc("cell", np.int64), "lp_gate": sc("lp_gate", np.float64),
               "lp_card": sc("lp_card", np.float64), "lp_cell": sc("lp_cell", np.float64),
               "p_gate": sc("p_gate", np.float64), "T": sc("T", np.float64)}
        out.update({k: st(k).astype(np.int64) for k in E.GEN_IDENT_KEYS})
        if "unit_form" in rows:
            out["unit_form"] = st("unit_form").astype(np.int64)
            out["opp_past"] = st("opp_past").astype(np.float32)
        if "opp_cycle" in rows:
            for k in E.GEN_V31_KEYS:
                out[k] = st(k).astype(np.float32)
        if "cue" in rows:
            out["cue"] = st("cue").astype(np.float32)
        if s.cfg.get("record_tick"):
            out["tick"] = sc("tick", np.int64)
        if "gate_tau" in rows:
            out["gate_tau"] = sc("gate_tau", np.float64)
        return out


FAST_DECIDE = os.environ.get("FASTLOOP_DECIDE", "fast") == "fast"


def fast_ok(c: dict) -> bool:
    """The cfg the fast decide reproduces: sample decode, all three heads, no decide rules / posture / ability, the
    afford mask on, no anti-stall clock. Anything else takes production's path."""
    from pipeline.decision_options import DecisionOptions, options_from_config, sample_rules
    return (c["policy"] == "sample" and "sample_heads" not in c and not c.get("posture") and not c.get("ability")
            and bool(c["afford_mask"]) and c.get("stall_elixir") is None and c.get("afford_ticks") is None
            and "_opp_style" not in c and sample_rules(options_from_config(c)) == DecisionOptions())

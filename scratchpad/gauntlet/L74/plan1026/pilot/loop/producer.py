"""LOOP-INT (plan1026 pilot fast loop): one producer = one in-process JVM running CfTrain (N crforge matches on T
threads, e1_eval.SelfPlayMatch's schedule + the obsid builders in Java) and this Python side, which does what
rl_royale.actor_main's self-play branch does per decision with PRODUCTION code: the per-side state is a real
``e1_eval.SelfPlaySide`` (built for each job on a capture-only env: deck slots, costs, RNG streams, cfg), the decide is
``e1_eval.sample_decide_batch`` (learner) / the opponent's own cfg, the record is ``SelfPlaySide._record`` +
``_traj_arrays``. What Java replaces: ``SelfPlayMatch.due`` / ``SelfPlaySide.apply`` / ``Match._land`` (CfTrain) and
``Match.prepare`` + ``gen_row`` (the obsid builders). The forward runs on this process's device (``GenPolicy.heads_t``
on a batch gathered straight from the JVM's buffers), one forward per policy per round.

Memory v2 (LOOP-MEM's CfMem, both seats, learner and frozen opponents) is wired: MEM_KEYS per row, mem_t per recorded
row, the learner's end-of-match event table in result["memory"]. MEM-FULL: each memory policy's own layout (its model's
match_memory.opts: memory_e_max / memory_board_snap; CfMem's instance layout, rows at CfTrain.memStride).
Hero abilities (ability_policy v2, forms deck) are wired: LOOP-IW's CfAbil per match in CfTrain (commands / options at
prepare, the pending queue + recheck + press in _advance_to), the rule for opponents, rl_royale's B6 head for the learner
(production's ability_decide; label mode = the B6 warm start), own_ability_events -> CfPubObj / CfMem.Log.
P2 timing-head opponents (OPP-LEARN-A; gate_decode 'timing_head') are wired for FROZEN opponent seats: CfTrain's timing
schedule (10-tick slots, th_tick re-decide, plays issued at the drawn tick, per-seat extrapolate 0), production's
timing_decide_batch on a per-seat env view (ThEnv: CfTrain's game-over flag = th_decided, its ready list = th_ability's
_scan, the press queued back through CfTrain), done_plays from CfTrain's accepted tally (held plays, Mirror's th_costs). An
opponent whose card_vocab differs from the learner's gets its own card-id universe (CfTrain.addUniverse: keys / pub /
memory tables + builders filled with ITS gid). A timing-head LEARNER seat (OPP-LEARN-C, opponent-as-learner: rl_royale's
base["opp_init"]) is the same seat with cfg th_learner: production's timing_decide_batch -> th_record rows + _record /
_traj_arrays, its own universe 0 (its card_vocab), ability mode 3 when it has the learned ability head.
'live'-policy seats (FAST-LIVEOPP: CfCtx context + production's live decide) incl. a decision's follow_ups (the
rocket_tornado combo's 2nd card: CfTrain ports SelfPlaySide's _follow_start / _follow_check schedule, setFollowUps).
Not supported yet (each raises): cfg follow_ups / pipelined decisions, tap loss / slow, tower troops, mid-match starts,
the posture head, decision rules in the sampled decide (LOOP-CTX), crown / habit / spell tracking.
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
                                                                  "CfCue.java", "CfTgt.java", "CfPubObj.java", "CfMem.java",
                                                                  "CfAbil.java", "CfCtx.java")] + [HERE / "CfTrain.java"]
# LOOP-IW CfAbil: glibc exp / pow through JDK 17's incubator FFI (byte-exact with production's numpy / math)
JVM_FLAGS = ("--add-modules=jdk.incubator.foreign", "--enable-native-access=ALL-UNNAMED")
UNSUPPORTED_CFG = ("posture", "spell_track", "crown_track", "habit_track", "record_ctx",
                   "record_elixir", "pipeline_decisions", "tap_loss", "tap_slow", "follow_ups",
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
            ("cue", "cueB", np.float32, (64, 22)), ("meta", "metaB", np.int32, (8,)), ("act", "actB", np.int32, (8,)),
            ("el", "elB", np.float64, ()), ("tal", "talB", np.int32, (6,)), ("twr", "twrB", np.int32, (25,)))

    def __init__(self, L, n: int):
        for k, attr, dt, shape in self.KEYS:
            setattr(self, k, np.frombuffer(memoryview(getattr(L, attr)), dt).reshape((2 * n,) + shape))
        self.res = np.frombuffer(memoryview(L.resB), np.int32).reshape(n, 8)
        self.th = np.frombuffer(memoryview(L.thB), np.int32).reshape(2 * n, int(L.TH))
        self.memv = {}

    def memory(self, L, n: int, e_max: int, snap: bool) -> dict:
        """MEM_KEYS views of CfTrain.memB for one memory layout (row r at r * L.memStride; CfMem's instance layout at
        e_max / snap = obs_id.JavaMem's offsets, CfMem.OFF_* at the defaults; no copy), cached per layout."""
        if (e_max, snap) not in self.memv:
            import jpype
            C = jpype.JClass("CfMem")
            mv, B, n2 = memoryview(L.memB), int(L.memStride), 2 * n
            nf, sv = int(C.F_SNAP if snap else C.F), int(C.S_V2)
            om = e_max * nf * 4
            off = (om, om + e_max, om + 9 * e_max, om + 17 * e_max, om + 17 * e_max + 4 * sv)   # mask card form sum ans
            assert int(C.bytes(e_max, snap)) == off[4] + 8 <= B, (e_max, snap, B)
            if (e_max, snap) == (int(C.E_MAX), False):
                assert (0,) + off == (C.OFF_EV, C.OFF_MASK, C.OFF_CARD, C.OFF_FORM, C.OFF_SUM, C.OFF_ANS), "CfMem layout"
            mk = (lambda shape, dt, o, inner: np.ndarray((n2,) + shape, dt, buffer=mv, offset=int(o), strides=(B,) + inner))
            self.memv[(e_max, snap)] = {
                "mem_ev": mk((e_max, nf), np.float32, 0, (4 * nf, 4)), "mem_mask": mk((e_max,), np.bool_, off[0], (1,)),
                "mem_card": mk((e_max,), np.int64, off[1], (8,)), "mem_form": mk((e_max,), np.int64, off[2], (8,)),
                "mem_summary": mk((sv,), np.float32, off[3], (4,)), "mem_answer": mk((), np.int64, off[4], ())}
        return self.memv[(e_max, snap)]

    def targets(self, L, n: int) -> None:
        """TARGET-OBS: CfTrain.tgtB / tgtIdxB views (CfTrain.enableTargets: "tgt" [64, 8] float32, "tgt_idx" [64] int64)."""
        self.tgt = np.frombuffer(memoryview(L.tgtB), np.float32).reshape(2 * n, 64, 8)
        self.tgt_idx = np.frombuffer(memoryview(L.tgtIdxB), np.int64).reshape(2 * n, 64)

    def abilities(self, L, n: int) -> None:
        """CfTrain.abCmdB / abOptB views (CfTrain.enableAbilities: per row {n commands, n options, (button, cid, uid)
        x AB_MAX}; options {button, cid, uid, q, features} x AB_MAX)."""
        self.ab_cmd = np.frombuffer(memoryview(L.abCmdB), np.int32).reshape(2 * n, int(L.AB_CMD))
        self.ab_opt = np.frombuffer(memoryview(L.abOptB), np.float64).reshape(2 * n, int(L.AB_MAX), int(L.abW))


def has_mem(policy) -> bool:
    return getattr(policy.model, "mem", None) is not None


def mem_opts(policy) -> tuple:
    """MEM-FULL: the policy's memory layout (e_max, snap) = match_memory.opts (no memory / absent keys = 128, False)."""
    from pipeline import match_memory as MM
    o = MM.opts(getattr(policy.model, "mem", None))
    return o["e_max"], o["snap"]


def loop_mem(obs_id, main, gid):
    """obs_id.JavaMem's tables (production's own functions: v2_lut, lock_head, _regen_table, slugs, units, detector
    slugs, java_table) WITHOUT its harness hooks (those wrap production's act / _memory / result for the identity run)."""
    import jpype
    from pipeline import match_memory as MM
    J = object.__new__(obs_id.JavaMem)
    J.MM, J.main, J.ident, J.gid = MM, main, None, gid
    J.C = C = jpype.JClass("CfMem")
    J.T = T = C.Tables()
    J.check_constants()
    D = jpype.JArray(jpype.JDouble)
    lut, head, (bp, rate, cum) = MM.v2_lut(gid), MM.lock_head(), MM._regen_table()
    T.lutDeck, T.lutAns = D(lut["deck"].tolist()), D(lut["answer"].tolist())
    T.lockMean, T.lockStd, T.lockW = (D(head[k].tolist()) for k in ("mean", "std", "w"))
    T.lockB = float(np.asarray(head["b"]).reshape(-1)[0])
    T.regenBp, T.regenRate, T.regenCum = D(bp.tolist()), D(rate.tolist()), D(cum.tolist())
    J.slug_of, J.unit_of, J.cid_ready = {}, {}, False
    J.Int = jpype.JArray(jpype.JInt)
    return J


# ids [48] = hand_slot 4, hand_card 4, hand_form 4, next_card, next_form, deck_card 8, deck_form 8, slot_card 9, slot_form 9
ID_SPLIT = (("hand_slot", 0, 4), ("hand_card", 4, 8), ("hand_form", 8, 12), ("next_card", 12, None),
            ("next_form", 13, None), ("deck_card", 14, 22), ("deck_form", 22, 30), ("slot_card", 30, 39),
            ("slot_form", 39, 48))


class ThEnv:
    """The env a timing-head seat's PRODUCTION decode reads beyond its row (e1_eval.th_decided / th_ability), answered from
    CfTrain at this decision: core.check_deploy -> GAME_OVER iff the row's TH flag (CfCore.check of hand slot 0, as
    CrforgeCore.check_deploy maps it); _scan -> the row's ready list (CfAbil.recheck(side, learned) = _scan(_any_gate));
    queue_abilities -> kept (``queued``) for CfTrain, which queues + fires it before the round's applies. Every other
    attribute is the capture env's."""

    def __init__(self, env):
        self.__dict__.update(_env=env, over=False, ready=[], queued=None)
        self.__dict__["core"] = self

    def __getattr__(self, k):
        return getattr(self._env, k)

    def check_deploy(self, cmd):
        from royalegym.protocol import DeployStatus
        return DeployStatus.GAME_OVER if self.over else DeployStatus.OK

    def _scan(self, side, gate):
        return list(self.ready)

    def queue_abilities(self, side, commands, delay) -> None:
        if self.queued is not None:
            raise RuntimeError("two th_ability presses in one decision")
        self.queued = (list(commands), int(delay))


def gid_key(gid: dict) -> tuple:
    return tuple(sorted(gid.items()))


class Producer:
    def __init__(self, base: dict, n: int, threads: int, device: str, build: Path, aid: int = 0, server=None):
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
            jpype.startJVM(f"-Xmx{os.environ.get('CRFORGE_XMX', '16g')}", *JVM_FLAGS, classpath=cp, convertStrings=True)
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
        if base.get("opp_init"):                              # OPP-LEARN-C: the timing-head learner (actor_main's branch)
            from pipeline.model_gen import load_model as load_gen
            net, st = load_gen(base["opp_init"], torch.device(device))
            net = net.eval()
            self.net, self.model = net, E.GenPolicy(net, st["card_vocab"], st.get("opp_sim"))
        else:
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
        if env.hero_abilities and (env.ability_policy != "v2" or env.forms_mode != "deck"):
            raise NotImplementedError("hero abilities: CfAbil ports ability_policy v2 with forms_mode deck only")
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
        self.tgt = False                                    # TARGET-OBS: CfTgt rows once the learner has target layers (run)
        self.ja = self.ahead = None
        self.ab_mode = 0                                     # the learner seat's CfTrain ability mode this run()
        if env.hero_abilities:                               # LOOP-IW CfAbil: tables from production code (ability_id)
            import ability_id
            if not bool(J("CfAbil").EXACT):
                raise RuntimeError(f"CfAbil.EXACT false: start the JVM with {JVM_FLAGS} on JDK 17")
            ja = self.ja = ability_id.JavaAbil(freeze=env.ability_features == "freeze")
            ja.setup(env)
            ja.main.spell_table(shim)                        # the IW observers' spell table (JavaAbil.reset's first fill)
            ja.main.resolve_opp = lambda s: self._resolve_keys(ja.main.keys, ja.main)   # raw()-free (see _resolve_keys)
            L.enableAbilities(ja.T, ja.freeze, int(env.decision_ticks), getattr(env, "_iw_policy", None) is not None,
                              bool(env._iw_never))
        L.start()
        self.v = Rows(L, self.n)
        if self.ja is not None:
            self.v.abilities(L, self.n)
        self.serial = 0
        self.stats = Counter()
        self.tm = Counter()                                  # seconds per stage (java / fill / start / decide / forward ...)
        self.progress = None                                 # bench.py: called after every round with the totals
        self.cl, self.opp_name, self.want_ver = None, {}, None
        self.lmem = None                                     # loop_mem(): CfMem tables once a memory model plays
        self.ctx = None                                      # FAST-LIVEOPP: (CfCtx.Tables, options) once a 'live' seat plays
        # card-id universes (CfTrain.addUniverse): 0 = the learner's gid tables above; one more per other opponent gid
        self.univs = [SimpleNamespace(gid=self.model.gid, main=main, pub=pub, keys=L.keys, T=L.pub, lmem=None)]
        self.univ_of = {gid_key(self.model.gid): 0}
        self._raw = RoyaleSelfPlayEnv.raw                    # production's raw() (the capture env's is stubbed)
        if server:                                           # LOOP-SRV PolicyServer (serve.py) at this address
            from pipeline.policy_server import connect
            sh = int(os.environ.get("FASTLOOP_SHARDS", "1"))   # SPEED2 F2' (opt-in): bench.start_servers' shards
            if sh > 1:
                from pipeline.policy_server import MultiClient
                self.cl = MultiClient([connect(server)] + [connect(server.replace(".sock", f".s{j}.sock"))
                                                           for j in range(1, sh)])
            else:
                self.cl = connect(server)

    # ------------------------------------------------------------------------------------------------ tables
    def _fill(self) -> int:
        """cf_loop_obs.Cohort.fill with ONE fix (a, compare.py lint_d1 u0000 job 0: an evolved body's opp_past form 0
        vs production 1): a detector key "card|body row|form" carries CfOppElixir's form, which leaves out
        STATUS_EVOLVED; production resolves the REAL raw() entity, whose status_flags carry CfCore.evolvedBit (an _EV
        body row). So the entity built for the key gets bit 8 from the body row name, as state() sets it.
        Hero abilities: CfAbil's tables (ability_id.JavaAbil.fill; its IW observers' detector keys the same way)."""
        L = self.L
        k = self._resolve_keys(L.keys, self.main)
        shim = SimpleNamespace(L=L, main=self.main, pub=self.pub, jc=self.jc, names=self.card_names)
        k += self.fill_fn(shim)                            # the rest (names, pub, cue, cyc) as Cohort.fill does
        if self.lmem is not None:                          # CfMem: detector slugs, then the bodies observe() missed
            self.lmem.fill_det()
            k += self._mem_bodies()
        if self.ja is not None:
            k += len(self.ja.T.missing)
            self.ja.fill(self.env)                         # P: / N: keys, the IW observers' keys, their make_play rows
        if self.ctx is not None:                           # FAST-LIVEOPP: CfCtx's (king, my tower max_hp) -> Rocket damage
            import cf_ctx
            k += cf_ctx.fill_missing(self.ctx[0])
        for U in self.univs[1:]:                           # an opponent's own card-id tables, filled the same way
            k += self._resolve_keys(U.keys, U.main)
            CP = self.jpype.JClass("CfPubObj")
            Lu = SimpleNamespace(names=L.names, keys=U.keys, pub=U.T, detKeys=lambda U=U, CP=CP: CP.detKeys(U.keys))
            k += self.fill_fn(SimpleNamespace(L=Lu, main=U.main, pub=U.pub, jc=None, names=self.card_names))
            if U.lmem is not None:
                U.lmem.fill_det()
                k += self._mem_bodies(U.lmem)
        return k

    def _univ(self, pol) -> int:
        """The card-id universe of a policy: 0 for the learner's gid, else (created on first sight) a JavaMain / JavaPub /
        CfMem table set with ITS gid (obs_id's fillers without their harness hooks) registered in CfTrain."""
        gk = gid_key(pol.gid)
        if gk in self.univ_of:
            return self.univ_of[gk]
        obs_id, L = self.obs_id, self.L
        main = obs_id.JavaMain()
        main.names, main.gid, main.card_names = L.names, pol.gid, self.card_names
        shim = SimpleNamespace(env=SimpleNamespace(names=self.card_names, feature_version=6), state={"projectiles": []})
        main.spell_table(shim)
        pub = object.__new__(obs_id.JavaPub)                # JavaPub.__init__ hooks royale_env._Core.act: not wanted twice
        pub.main, pub.gid, pub.C = main, pol.gid, self.jpype.JClass("CfPubObj")
        pub.T, pub.pub, pub.ready, pub.press_tick_mismatch, pub.presses = pub.C.Tables(), {}, False, 0, 0
        pub.tables(shim)
        u = int(L.addUniverse(main.keys, pub.T))
        if u != len(self.univs):
            raise RuntimeError(f"CfTrain universe {u} != {len(self.univs)}")
        self.univs.append(SimpleNamespace(gid=pol.gid, main=main, pub=pub, keys=main.keys, T=pub.T, lmem=None))
        self.univ_of[gk] = u
        return u

    def _resolve_keys(self, keys, main) -> int:
        """Each missing detector key "card|body row|form#entity id" of ``keys`` -> main.key_index of the name public_frame
        gives an entity built from the key (see _fill: the evolved bit from the body row)."""
        from pipeline import royale_heroiw as heroiw, vocab
        from pipeline.obs_contract import catalog_card_form
        from pipeline.opp_elixir_count import _catalog_names
        from pipeline.public_observation import public_frame
        k = 0
        for miss in keys.takeMissing():
            key, _ = str(miss).rsplit("#", 1)
            card, body, form = key.split("|")
            flags = {2: 16, 1: 8}.get(int(form), 0) | (8 if "_EV" in body.upper() else 0)
            ent = dict(side=1, x=0.0, y=0.0, hp=1, max_hp=1, entity_id=0, name=self.card_names.get(int(card), card),
                       card_id=int(card), status_flags=flags)
            if heroiw.ENABLED and heroiw.public_identity(body) is not None:
                ent.update(name="IceWizard", public_card_id=heroiw.public_identity(body), public_form=2)
            f = public_frame({"tick": 0, "entities": [ent]}, source="sim")["entities"]
            name = _catalog_names().get(f[0]["card_id"]) if f else None
            keys.putBody(key, main.key_index(vocab.engine_key(name) if name else None),
                         int(catalog_card_form(f[0]["card_id"])[1]) if f else 0)
            k += 1
        return k

    def _mem_bodies(self, lmem=None) -> int:
        """obs_id.JavaMem.resolve for the fast loop: each missing "card|body|form#entity id" -> the unit of the key
        MatchMemory gives that body (public_frame source 'sim' on production's raw() entity of the SAME battle, read
        off the facade of a match whose row stopped at the memory stage)."""
        from pipeline import vocab
        from pipeline.obs_contract import catalog_card_form
        from pipeline.public_observation import public_frame
        lmem = self.lmem if lmem is None else lmem          # an opponent universe's CfMem tables (its own slugs / units)
        miss = [str(m) for m in lmem.T.takeMissing()]
        if not miss:
            return 0
        rows = np.flatnonzero(self.v.meta[:, 0].astype(bool) & (self.v.meta[:, 5] == 6))
        env, cf0 = self.env, self.env.core._cf
        ents = []
        try:
            for i in sorted({int(r) // 2 for r in rows}):
                env.core._cf = self.L.core(i)
                st = self._raw(env)
                ents.append((i, st["tick"], {int(e["entity_id"]): e for e in st["entities"]}))
        finally:
            env.core._cf = cf0
        for m in miss:
            k, eid = m.rsplit("#", 1)
            # entity ids restart in every battle: several stopped matches can hold this id (thread timing decides which
            # stop together; LOOP-INT2 measured 3 / 16 wrong outcome values once with the first hit taken). The body is
            # in a match whose entity gives the SAME CfMem key (CfTrain.memBodyKey); every such candidate must resolve
            # to one unit, else refuse.
            hit = [(t, e[int(eid)]) for i, t, e in ents if int(eid) in e and str(self.L.memBodyKey(i, int(eid))) == k]
            self.stats["mem_eid_in_other_matches"] += sum(int(eid) in e for _, _, e in ents) - len(hit)
            if not hit:
                raise RuntimeError(f"CfMem missing body {m}: entity in no stopped match")
            self.stats["mem_eid_shared"] += int(len(hit) > 1)
            units = set()
            for t, e in hit:
                f = public_frame({"tick": t, "entities": [e]}, source="sim")["entities"]
                name = catalog_card_form(int(f[0]["card_id"]))[0] if f else None
                key = vocab.engine_key(name) if name else None
                units.add(lmem.unit(key) if key else -1)
            if len(units) != 1:
                raise RuntimeError(f"CfMem body {m}: candidates in several matches resolve to units {sorted(units)}")
            lmem.T.putBody(k, units.pop())
        return len(miss)

    def _resolve_rows(self) -> None:
        """Rows that met a table key Python had not filled: fill, resume them; until none is left."""
        for _ in range(20):
            if not (self.v.meta[:, 0].astype(bool) & (self.v.meta[:, 5] != int(self.L.DONE))).any():
                return
            self.stats["fills"] += self._fill()
            if int(self.L.rebuild()) == 0:
                return
        raise RuntimeError("rows still missing table keys after 20 fills")

    # ------------------------------------------------------------------------------------------------ jobs
    def _policy(self, path: str):
        if path not in self.opp_cache:
            pol, mi = self.E.load_policy(self.R.REPO / path, self.dev)
            if not isinstance(pol, self.E.GenPolicy):
                raise NotImplementedError(f"opponent {path}: not a GenPolicy")
            self._univ(pol)                                  # another card_vocab: its own CfTrain card-id universe
            if has_mem(pol) and getattr(pol.model.mem, "version", "v1") != "v2":
                raise NotImplementedError(f"opponent {path}: memory {pol.model.mem.version} (CfMem ports v2)")
            self.opp_cache[path] = (pol, str(mi.get("grid", "floor")))
            self.opp_name[id(pol)] = path                    # the server's model name for it (serve.py --opp PATH)
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
        if not E.is_timing(opp):                             # = SelfPlayMatch: P2 timing-head opponents play unstyled
            ocfg = style_config(ocfg, int(spec["seed"]), int(k))
        tag = str(spec["tag"])
        ls = E.SelfPlaySide(env, spec["learner_deck"], L_, tag, k, lcfg, self.model)
        os_ = E.SelfPlaySide(env, spec["opp_deck"], 1 - L_, f"{tag}:opp", k, ocfg, opp)
        ls.other, os_.other = os_, ls
        sides = sorted((ls, os_), key=lambda s: s.side)
        for s in sides:
            if s.cfg.get("record_phi") not in (None, False, "tower_phat"):
                raise NotImplementedError(f"record_phi {s.cfg['record_phi']!r}: the fast loop records tower_phat only")
            if s.cfg.get("record_phi"):
                self.L.towers = True                          # CfTrain fills the crown-tower rows from now on
            bad = [x for x in UNSUPPORTED_CFG if s.cfg.get(x)]
            if bad:
                raise NotImplementedError(f"cfg {bad} is not in CfTrain yet")
            if s.pipe or s.drops is not None or s.own_fx is not None or (s.delay <= 0 and not s.timing):
                raise NotImplementedError("CfTrain ports the delayed-play rollout schedule only")
            if s.timing and (s.delay or s.extrap or (s is ls and not s.cfg.get("th_learner"))):
                raise NotImplementedError("timing-head seats: delay 0, no look-ahead; a learner seat needs th_learner")
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
            u = self._univ(s.model)
            if u:                                             # the seat's own universe: ITS gid (slot_ident raises on a miss)
                for o in sides:
                    for cid, nm in zip(env.deck_ids[o.side], o.engine_deck):
                        if card_key(nm) in s.model.gid:
                            self.L.putGidMatchU(u, i, int(cid), int(s.model.gid[card_key(nm)]))
                        elif o is s:
                            raise KeyError(f"card {nm!r} ({card_key(nm)}) not in the generalist's card_vocab")
            self.L.setSeat(i, int(s.side), bool(s.timing), int(s.extrap), u)
            if s.timing:                                      # timing_decide_batch's env reads (ThEnv) + done_plays sync
                s.env, s._th_issue, s._th_nacc = ThEnv(env), None, 0
        self.serial += 1
        self.L.setJob(i, self.serial, int(seed) & 0x7FFFFFFF, *a[0], *a[1])
        if self.lmem is not None:
            self.L.setMem(i, has_mem(sides[0].model), has_mem(sides[1].model), *mem_opts(sides[0].model),
                          *mem_opts(sides[1].model))
        if self.ctx is not None:                              # FAST-LIVEOPP: the 'live' seats build CfCtx rows
            self.L.setCtx(i, *[s.cfg["policy"] == "live" for s in sides])
        if self.ja is not None:                               # _reset_abilities (CfTrain.reset): the env seed, seat modes
            if not self.ja.ranges and hasattr(env, "_hero_ranges"):
                self.ja.fill_ranges(env)                      # JavaAbil.reset: the first env reset that had heroes
            th_ab = getattr(self.E, "th_has_ability", None)   # P2-OPP2: a timing seat's learned ability head (mode 3)
            self.L.setAbil(i, int(env.seed), *[3 if s.timing and th_ab and th_ab(s.model) else self.ab_mode if s is ls
                                               else 0 for s in sides])   # OPP-LEARN-C: a timing learner = mode 3 too
            for s in sides:
                s._ability_commands, s._ability_opts = {s.side: []}, None
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
             **({"memory": self.lmem.java_table(self.L.memOf(i, side))} if cfg.get("record") and has_mem(ls.model)
                else {}),
             "fastloop": {"crashed": bool(res[7]), "approx": ["card_mix_accepted", "plays", "opp_counter",
                                                              "refuse_reasons names", "ghost_distinct_delivered"]}}
        if self.ja is not None:                               # Match.result's hero-ability fields (CfTrain.abLog)
            from pipeline.royale_env import V2_KEYS
            pr, dep, fb = {0: Counter(), 1: Counter()}, {0: Counter(), 1: Counter()}, Counter()
            lg = list(self.L.abLogFlat(i))
            for kind, sd_, cid in zip(lg[0::3], lg[1::3], lg[2::3]):
                nm = self.card_names[int(cid)]
                if kind == 0:
                    pr[int(sd_)][nm] += 1
                    if V2_KEYS.get(nm) is None:
                        fb[nm] += 1
                else:
                    dep[int(sd_)][nm] += 1
            r.update({"hero_abilities": True, "ability_presses": {s: dict(c) for s, c in pr.items()},
                      "ability_policy": "v2", "ability_fallback_generic": dict(fb),
                      "ability_deployments": {s: dict(c) for s, c in dep.items()}})
            if getattr(ls, "ab_stats", None):
                st_ = ls.ab_stats
                r["ability_head"] = {"decisions": st_["decisions"], "presses": st_["presses"],
                                     "p_mean": round(st_["p_sum"] / st_["decisions"], 4)}
        if "_opp_style" in os_.cfg:                          # SelfPlayMatch.result
            r["opp_style"] = dict(os_.cfg["_opp_style"])
        r["league"] = dict(m["spec"])
        r["opp_side"] = {"side": os_.side, "policy": os_.cfg["policy"], "plays_attempted": os_.n_att,
                         "plays_accepted": os_.n_acc, "plays_per_min": round(os_.n_att / minutes, 3) if minutes else None,
                         "stall_fired": os_.n_stall, "decisions": os_.n_dec}
        if cfg.get("record"):
            r["rollout_index"], r["update"] = int(r["k"]), int(cfg.get("update", 0))
        return r

    # ------------------------------------------------------------------------------------------------ one update
    def run(self, update: int, sd: bytes, jobs: list, ver=None) -> tuple[list[dict], list[dict], dict]:
        """actor_main's ('selfplay', update, sd, jobs) -> (results, skipped, stats). ``ver`` (fastloop --overlap): the
        weight version of ``sd`` when it is not ``update`` (a wave one update stale); the jobs' seeds stay update's."""
        R, base = self.R, self.base
        t0 = time.perf_counter()
        c0 = (int(self.L.engineNs.get()), int(self.L.obsNs.get()), int(self.L.rowsBuilt.get()))   # JVM counters: per run
        msd, psd = R.split_actor_sd(sd, self.dev)
        asd = R.pop_prefix(msd, R.ABILITY_SD)
        if psd:
            raise NotImplementedError("the posture head is not in the fast loop yet")
        # the server's learner = this update's weights (server_version: a message with the ability head is its own version)
        self.want_ver = server_version(update if ver is None else ver, bool(asd)) if self.cl is not None else None
        self.net.load_state_dict(msd)
        self.net.eval()
        if not self.tgt and "tgt_in.weight" in msd:           # TARGET-OBS (rl_royale target_obs on: the init got the layers;
            self.tgt = True                                   # actor_base carries no target_obs key): CfTgt rows from now on
            self.L.enableTargets()
            self.v.targets(self.L, self.n)
        cfg = R.actor_cfg(base, "rollout", self.aid, self.dev)
        self.ab_mode = 0                                      # actor_main.mk_cfg's B6 branch, then the CfTrain seat mode
        if "ability" in cfg:
            if self.ja is None:
                raise NotImplementedError("an ability head without hero_abilities")
            if asd:                                           # this update's head: the learner's presses (sample)
                if self.ahead is None:
                    ab = base["ability"]
                    self.ahead = R.AbilityHead(int(ab["d_g"]), int(ab.get("hidden", R.ABILITY_HIDDEN)),
                                               int(ab.get("n_feat", self.E.ABILITY_FEAT_N))).to(self.dev).eval()
                self.ahead.load_state_dict(asd)
                cfg["ability"] = {**cfg["ability"], "head": self.ahead}
                self.ab_mode = 2
            else:                                             # no head: the rule presses, its labels (B6 warm start)
                cfg["ability"] = {"mode": "label", "n_feat": cfg["ability"]["n_feat"]}
                cfg.pop("cf", None)
                self.ab_mode = 1
            if cfg["ability"]["mode"] not in ("sample", "label"):
                raise NotImplementedError(f"ability mode {cfg['ability']['mode']!r} in a rollout")
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
        mem_pols = [m for m in [self.model] + [x[0] for x in opps.values()] if has_mem(m)]
        if mem_pols and self.lmem is None:                    # CfMem: one table set per JVM (v2 LUT of ONE gid)
            if has_mem(self.model) and getattr(self.net.mem, "version", "v1") != "v2":
                raise NotImplementedError(f"learner memory {self.net.mem.version}: CfMem ports v2")
            self.lmem = loop_mem(self.obs_id, self.main, self.model.gid)
            # MEM-FULL: rows wide enough for every memory policy of this first run (ponytail: a later, wider opponent
            # fails in setMem; allocate for the widest layout up front if that ever happens)
            C = self.jpype.JClass("CfMem")
            self.L.enableMemory(self.lmem.T, max(int(C.bytes(*mem_opts(m))) for m in mem_pols))
            self.lmem.slugs(self.env)
        for m in mem_pols:                                    # a memory opponent of another universe: its own CfMem tables
            U = self.univs[self._univ(m)]
            if U.lmem is None and U is not self.univs[0]:
                U.lmem = loop_mem(self.obs_id, U.main, U.gid)
                self.L.enableMemoryU(self.univ_of[gid_key(U.gid)], U.lmem.T)
                U.lmem.slugs(self.env)
        self._ctx_on([c for _, c in opps.values()] + [cfg])
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
                 "crashed": len(skipped), "fills": self.stats["fills"], "time": dict(tm), "counts": dict(self.stats),
                 "java_engine_core_s": (int(L.engineNs.get()) - c0[0]) / 1e9, "java_obs_core_s": (int(L.obsNs.get()) - c0[1]) / 1e9,
                 "rows": int(L.rowsBuilt.get()) - c0[2], "first_crash": None if L.firstCrash is None else str(L.firstCrash),
                 "follow_ups": [int(L.fuPlans.get()), int(L.fuFired.get()), int(L.fuCancelled.get())]}   # JVM totals
        return results, skipped, stats

    def _decide(self, live: dict) -> None:
        """The round's forward (one per policy) + decide + record + actions, as run_selfplay_batch's round."""
        E, torch, v = self.E, self.torch, self.v
        from pipeline.dataset_gen import SC_SLOT_COLS
        from pipeline.decision_options import model_cell_logits
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
            key = (id(s.model), "opponent_style") if "_opp_style" in s.cfg else id(s.model)   # run_selfplay_batch's
            groups.setdefault(key, []).append((int(r), s))
        g0 = time.perf_counter()
        work = []
        for members in groups.values():
            idx = np.array([r for r, _ in members])
            sides = [s for _, s in members]
            model, c = sides[0].model, sides[0].cfg
            if c["policy"] not in ("sample", "live") or (c["policy"] == "live" and self.ctx is None):
                raise NotImplementedError(f"policy {c['policy']!r}: the fast loop samples or plays 'live' (CfCtx)")
            batch = {"tok": v.tok[idx], "mask": v.mask[idx].astype(bool), "sc": v.sc[idx], "past": v.past[idx],
                     "unit_form": v.unit_form[idx], "opp_past": v.opp_past[idx], "projectiles": v.projectiles[idx],
                     "effects": v.effects[idx], "own_ability": v.own_ability[idx], "opp_cycle": v.opp_cycle[idx]}
            if self.jc is not None:
                batch["cue"] = v.cue[idx]
            if getattr(model.model, "tgt_in", None) is not None:   # TARGET-OBS: Match.gen_row's sim_target_rows
                if not self.tgt:
                    raise RuntimeError("a model with target layers in a run without target_obs (CfTgt off)")
                batch["tgt"], batch["tgt_idx"] = v.tgt[idx], v.tgt_idx[idx]
            if has_mem(model):                                # Match._memory's MEM_KEYS (CfMem)
                from pipeline.match_memory import MEM_KEYS
                mv = v.memory(self.L, self.n, *mem_opts(model))    # MEM-FULL: this model's layout
                for k in MEM_KEYS:
                    batch[k] = mv[k][idx]
            ids = v.ids[idx]
            for k, a, b in ID_SPLIT:
                batch[k] = np.ascontiguousarray(ids[:, a:b] if b is not None else ids[:, a])
            batch["sc"][:, SC_SLOT_COLS] = 0.0                # GenPolicy.row's zeroing (batch["sc"] is a copy)
            if getattr(model, "opp_sim", None) is not None:   # P2 opponents: deck id + context tokens (Match.gen_row)
                oi = [model.opp_inputs({"deck_card": batch["deck_card"][j], "deck_form": batch["deck_form"][j]})
                      for j in range(len(idx))]
                for k in oi[0]:
                    batch[k] = np.array([o[k] for o in oi], dtype=np.int64)
            name = "learner" if model is self.model else self.opp_name.get(id(model))
            # timing / live: in-process (live_decide_batch reads enc). ponytail: a live partner's forward runs on the producer's
            # device, not the server; route it to serve.py (enc + cells there) if that forward shows up in the profile
            srv = self.cl is not None and name in self.cl.models and not E.is_timing(model) and c["policy"] != "live"
            work.append((idx, sides, model, c, batch, E.gen_row_keys(model.model), name, srv))
        self.tm["gather"] += time.perf_counter() - g0
        fs = {}
        if any(w[7] for w in work):                          # LOOP-SRV: every server model's block in ONE call
            f0 = time.perf_counter()
            blocks = [(w[6], w[4], len(w[0])) for w in work if w[7]]
            while True:                                      # the learner's weights of THIS update (watch dir push)
                fs = dict(zip([b[0] for b in blocks], self.cl.forward(blocks)))
                if "learner" not in fs or self.want_ver is None or fs["learner"].ver >= self.want_ver:
                    break
                self.cl.done(list(fs.values()))
                time.sleep(0.05)
            self.tm["forward_wait"] += time.perf_counter() - f0
            self.tm["fwd_rows"] += sum(b[2] for b in blocks)
            self.tm["fwd_calls"] += 1
        pend = []                                            # CELLS1: fast server groups waiting for their cells
        for idx, sides, model, c, batch, keys, name, srv in work:
            self._abil_in(idx, sides)
            if srv:
                f = fs[name]
                if name == "learner" and self.want_ver is not None and f.ver != self.want_ver:
                    raise RuntimeError(f"server learner weights v{f.ver}, this update needs v{self.want_ver}")
                heads = {k: torch.from_numpy(x) for k, x in f.heads.items()}
                p = torch.sigmoid(heads["gate"]).tolist()
                hand = np.zeros((len(idx), 9), dtype=bool)
                hand[np.arange(len(idx))[:, None], batch["hand_slot"]] = True
                hand = hand[:, :8]
                cl = self.cl
                cell_fn = (lambda f_: lambda ids_, slots_: torch.from_numpy(cl.cells(f_, ids_, slots_)))(f)
                vold = None
                if "value" in heads and name == "learner":
                    vold = self.R.value_scalar(heads["value"]).numpy()
                if not (FAST_DECIDE and fast_ok(c)):
                    if "_opp_style" not in c:
                        raise NotImplementedError("a server-forwarded group needs the fast decide's cfg (fast_ok)")
                    d0 = time.perf_counter()
                    self._prod_group(model, c, sides, idx, batch, keys, None, heads, p, hand, cell_fn)
                    self.tm["decide_py"] += time.perf_counter() - d0
                    continue
                d0 = time.perf_counter()
                abx = None
                if c.get("ability"):                         # ability_decide's head on the server (the block's g)
                    head = (lambda f_: lambda gi, ft: torch.from_numpy(cl.ability(f_, gi.numpy(), ft.numpy())))(f)
                    abx = ({"g": torch.arange(len(idx))}, {**c, "ability": {**c["ability"], "head": head}})
                if CELLS1:                                   # SPEED2 F3: draw gate + card now, cells after ONE request
                    g = self._fast_gen(model, c, sides, idx, batch, keys, heads, p, hand, vold, f.ver // 2, abx)
                    pend.append((g, f, next(g, None)))
                else:
                    self._fast_group(model, c, sides, idx, batch, keys, heads, p, hand, cell_fn, vold, f.ver // 2, abx)
                self.tm["decide_py"] += time.perf_counter() - d0
                continue
            f0 = time.perf_counter()
            with torch.no_grad():
                tb = {k: torch.from_numpy(np.ascontiguousarray(batch[k])).to(c["device"]) for k in keys}
                enc, heads = model.heads_t(tb)
                B = heads["card"].shape[0]
                hand = torch.zeros(B, 9, dtype=torch.bool, device=heads["card"].device)
                hand = hand.scatter(1, tb["hand_slot"], True)[:, :8].cpu().numpy()
                p = torch.sigmoid(heads["gate"] if "gate" in heads else heads["hazard"]).cpu().tolist()   # timing: h_s
            self.tm["forward"] += time.perf_counter() - f0      # incl. H2D / D2H (the .cpu() syncs)
            self.tm["fwd_rows"] += len(idx)
            self.tm["fwd_calls"] += 1
            d0 = time.perf_counter()
            if FAST_DECIDE and fast_ok(c) and not E.is_timing(model):
                self._fast_group(model, c, sides, idx, batch, keys, heads, p, hand,
                                 model_cell_logits(model, enc, heads["card"].device), abx=(enc, c))
                self.tm["decide_py"] += time.perf_counter() - d0
                continue
            self._prod_group(model, c, sides, idx, batch, keys, enc, heads, p, hand,
                             model_cell_logits(model, enc, heads["card"].device))
            self.tm["decide_py"] += time.perf_counter() - d0
        if pend:                                             # every group's rows are its own sides: their rng order holds
            c0 = time.perf_counter()
            ask = [(f, *req) for g, f, req in pend if req is not None]
            got = iter(self.cl.cells_multi(ask) if ask else [])
            self.tm["cells_wait"] += time.perf_counter() - c0
            d0 = time.perf_counter()
            for g, f, req in pend:
                if req is not None:
                    try:
                        g.send(torch.from_numpy(next(got)))
                    except StopIteration:
                        pass
                    else:
                        raise RuntimeError("_fast_gen asked for cells twice")
            self.tm["decide_py"] += time.perf_counter() - d0
        if fs:
            self.cl.done(list(fs.values()))
        if self.ja is not None:                              # SelfPlaySide.apply's queue_abilities input (CfTrain.apply)
            for idx, sides, *_ in work:
                self._abil_out(idx, sides)

    def _abil_in(self, idx, sides) -> None:
        """Match.prepare's hero-ability results from CfTrain (abilities()): _ability_commands = the rule's presses ([] for a
        HEAD seat), _ability_opts = ability_options' records (cfg ability: label q, or NaN) for ability_decide."""
        if self.ja is None:
            return
        cmd, opt = self.v.ab_cmd, self.v.ab_opt
        for j, s in enumerate(sides):
            r = int(idx[j])
            a = cmd[r]
            s._ability_commands = {s.side: [tuple(int(x) for x in a[2 + 3 * k:5 + 3 * k]) for k in range(int(a[0]))]}
            if isinstance(s.env, ThEnv):                       # the timing seat's ready list; its head presses, never the rule
                s.env.ready, s.env.queued = (s._ability_commands[s.side] if self._th_head(s) else []), None
                if self._th_head(s):
                    s._ability_commands = {s.side: []}
            if s.cfg.get("ability"):
                s._ability_opts = [{"cmd": (int(o[0]), int(o[1]), int(o[2])), "card": self.card_names[int(o[1])],
                                    "q": float(o[3]), "feat": o[4:].copy()} for o in opt[r, :int(a[1])]]

    def _abil_out(self, idx, sides) -> None:
        """The commands apply queues (ability_decide put a HEAD seat's press in _ability_commands) -> CfTrain's row."""
        cmd = self.v.ab_cmd
        for j, s in enumerate(sides):
            if isinstance(s.env, ThEnv) and self._th_head(s):   # CfTrain mode 3: {1, j, button, cid, uid} or nothing
                r, q = int(idx[j]), s.env.queued
                cmd[r, :] = 0
                if q is not None and q[0]:
                    cmd[r, 0], cmd[r, 1] = 1, q[1]
                    cmd[r, 2:5] = [int(x) for x in q[0][0]]
                continue
            if not s.cfg.get("ability"):
                continue                                     # a RULE seat: CfTrain's own commands stand
            cs = s._ability_commands[s.side]
            if len(cs) > int(self.L.AB_MAX):
                raise RuntimeError(f"{len(cs)} ability commands")
            r = int(idx[j])
            cmd[r, 0] = len(cs)
            for k, x in enumerate(cs):
                cmd[r, 2 + 3 * k:5 + 3 * k] = [int(v) for v in x]

    def _th_head(self, s) -> bool:
        f = getattr(self.E, "th_has_ability", None)
        return bool(self.ja is not None and f is not None and f(s.model))

    def _prod_group(self, model, c, sides, idx, batch, keys, enc, heads, p, hand, cell_fn) -> None:
        """PRODUCTION's decide for one policy group (run_selfplay_batch's round): Match.prepare's state, SelfPlaySide.pre,
        then adaptive_opponents.styled_decisions for a styled opponent (through pipeline.loop_opp.decide: production's
        own function on stand-in sides, cell logits from ``cell_fn``; bank inputs = the Java view's float64 elixir and
        the enemy-on-my-half flag from the unit tokens) else e1_eval.sample_decide_batch (in-process forward only);
        SelfPlaySide._record; the actions (incl. the style's spell delay) back to Java."""
        E, v = self.E, self.v
        from pipeline import engine_play as ep
        from pipeline import loop_opp
        from pipeline.royale_env import SCALE
        K = 18
        if True:
            for j, s in enumerate(sides):                    # Match.prepare's state the decide / record read
                r = idx[j]
                tick, vt = int(v.meta[r, 3]), int(v.meta[r, 4])
                if s.last_play_tick is None:
                    s.last_play_tick = tick
                s._cur = (tick, SimpleNamespace(t_sec=vt * 0.05), SimpleNamespace(my_elixir=float(v.el[r])))
                s._view_tick = vt
                if s.cfg.get("record") and s.cfg.get("record_phi"):   # (opponents carry the key, record False)
                    raise NotImplementedError("record_phi in production's decide path: the fast decide only")
                if has_mem(model) and getattr(s, "mem", None) is None:
                    s.mem = "cfmem"                           # _record's mem_t switch (the table is CfMem's)
                s._gen_row = {k: batch[k][j] for k in keys}
                s._obs = (s._gen_row["tok"], s._gen_row["mask"], s._gen_row["sc"], s._gen_row["past"])
                if isinstance(s.env, ThEnv):                   # timing: done_plays from CfTrain's accepted tally, game over
                    nacc = int(v.tal[r, 1])
                    if s._th_issue is not None and nacc > s._th_nacc:
                        s.done_plays.append(s._th_issue)      # Match._land: (land tick = issue tick, slot, x, y)
                        s.last_play_tick = s._th_issue[0]
                    s._th_issue, s._th_nacc = None, nacc
                    s.env.over = bool(v.th[r, 0])
            pre = [s.pre(hand[j]) for j, s in enumerate(sides)]
            allowed = np.stack([x[1] for x in pre])
            stalled = np.array([x[2] for x in pre], dtype=bool)
            if "_opp_style" in c:
                half = [loop_opp.bank_inputs(s._gen_row)[1] for s in sides]
                decisions = loop_opp.decide([s.cfg for s in sides], [s.rng_behave for s in sides],
                                            [s.deck.card_ids for s in sides], [float(v.el[r]) for r in idx], half,
                                            {k: x.cpu() for k, x in heads.items()}, p, allowed, stalled,   # loop_opp: CPU rows
                                            lambda rows, slots: cell_fn(list(map(int, rows)), list(map(int, slots))))
                self.stats["styled_rows"] += len(sides)
            elif c["policy"] == "live" and enc is not None:   # selfplay_decide's live branch, match_kwargs from CfCtx
                kw = self._ctx_kwargs(sides, idx, c)
                E.ability_decide(sides, enc, c)
                tau, kw = E.posture_live(sides, enc, c, c["tau"], kw)
                decisions = E.live_decide_batch(model, enc, heads, p, allowed, stalled, tau=tau, device=c["device"], **kw)
                self.stats["live_rows"] += len(sides)
            elif enc is not None:
                decisions = E.sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, c)
            else:
                raise NotImplementedError("production's sample decide needs the in-process forward")
            for j, (s, d) in enumerate(zip(sides, decisions)):
                r = idx[j]
                s._record(p[j], d)
                if isinstance(s.env, ThEnv):                  # SelfPlaySide.apply's _th_slot (CfTrain keeps the schedule)
                    s._th_slot = int(v.meta[r, 3]) if d.get("th_tick") else None
                a = v.act[r]
                if d["play"]:
                    X, Y = ep.cell_to_engine(d["cell"], s.mirror, s.cfg["grid"])
                    a[:] = (1, int(d["slot"]), int(d["cell"]), int(X) * SCALE // K, int(Y) * SCALE // K, int(X), int(Y),
                            int(d.get("_style_delay", 0)) if "_opp_style" in s.cfg else 0)
                    s.fl[s.deck.cards[d["slot"]]] += 1        # card_mix_attempted / play_elixir / stall (Match._land)
                    s.fl_el.append(float(int(s._cur[2].my_elixir)))
                    s.n_stall += int(d["why"] == "stall")
                    if isinstance(s.env, ThEnv):              # issued now: done_plays once CfTrain accepts it
                        s._th_issue = (int(v.meta[r, 3]), int(d["slot"]), *s.ep.cell_center(d["cell"], s.cfg["grid"]))
                    if d.get("follow_ups"):                   # SelfPlaySide.apply -> _follow_start (CfTrain.followStart)
                        self._follow_ups(int(r), s, d["follow_ups"])
                else:
                    a[:] = (0, -1, -1, 0, 0, 0, 0, int(d.get("th_tick", 0)) if isinstance(s.env, ThEnv) else 0)

    def _follow_ups(self, r: int, s, fus) -> None:
        """Row r's follow_up_spec list -> CfTrain.setFollowUps (each play's action ints as _prod_group writes them, after /
        within / afford (-1 = None) / require_first), the seat's arrival ticks and deck-slot costs."""
        from pipeline import engine_play as ep
        from pipeline.e1_eval import FOLLOW_ARRIVAL_TICKS
        from pipeline.royale_env import SCALE
        a = []
        for fu in fus:
            X, Y = ep.cell_to_engine(fu["cell"], s.mirror, s.cfg["grid"])
            aff = fu.get("afford_ticks")
            a += [int(fu["slot"]), int(fu["cell"]), int(X) * SCALE // 18, int(Y) * SCALE // 18, int(X), int(Y),
                  int(fu["after_ticks"]), int(fu["within_ticks"]), -1 if aff is None else int(aff),
                  int(bool(fu.get("require_first", True)))]
        JD = self.jpype.JArray(self.jpype.JDouble)
        self.L.setFollowUps(r, int(s.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS)), JD([float(c) for c in s.costs]),
                            self.JInt(a))
        self.stats["follow_up_plans"] += 1

    def _ctx_on(self, cfgs) -> None:
        """FAST-LIVEOPP: CfCtx on (once per JVM) when a seat plays policy 'live'; one options / grid set per JVM (CfCtx's
        Tables carry lethal_quiet's window and the grid's cell offset)."""
        live = [c for c in cfgs if c["policy"] == "live"]
        if not live:
            return
        sys.path.insert(0, str(OBSID))
        import cf_ctx
        for c in live:
            if c.get("pipeline_decisions") or c.get("follow_ups"):
                raise NotImplementedError("a 'live' seat with pipeline_decisions / follow_ups")
            key = (cf_ctx.options_for(c), c["grid"])         # options_for refuses what CfCtx does not build
            if self.ctx is None:
                self.ctx = (cf_ctx.tables(self.env.names, c["grid"], key[0]), *key)
                self.L.enableCtx(self.ctx[0])
                self.v.ctx = np.frombuffer(memoryview(self.L.ctxB), np.float64).reshape(2 * self.n, int(self.L.CTX))
            elif key != self.ctx[1:]:
                raise NotImplementedError("two 'live' option sets in one producer (CfCtx.Tables are per JVM)")

    def _ctx_kwargs(self, sides, idx, c) -> dict:
        """decision_options.match_kwargs(sides) from the rows' CfCtx context (LOOP-CTX cf_ctx.kwargs: identical on 45,211
        facade seat-rows at the live config); the per-match decision stream is match_kwargs' own (rng_decision_options)."""
        import cf_ctx
        from pipeline.e1_eval import obs_seed
        rows = []
        for j, s in enumerate(sides):
            r = int(idx[j])
            rows.append(cf_ctx.decode(self.v.ctx[r, 1:1 + int(self.v.ctx[r, 0])].tolist()))
            if not hasattr(s, "rng_decision_options"):       # match_kwargs' seeding, verbatim
                s.rng_decision_options = np.random.default_rng(np.random.SeedSequence(
                    [obs_seed("decision_options:" + s.tag, s.k), int(c.get("decision_seed", 0))]))
            if getattr(s, "pending", None) is not None or getattr(s, "pend", None):
                raise RuntimeError("a 'live' seat with a pending play (pipeline_decisions is refused)")
        return cf_ctx.kwargs(rows, options=self.ctx[1], grid=c["grid"], card_names=[list(s.deck.cards) for s in sides],
                             card_ids=[list(s.deck.card_ids) for s in sides], sides=[int(s.side) for s in sides],
                             pending=[False] * len(sides), rngs=[s.rng_decision_options for s in sides],
                             projectiles=[s._gen_row.get("projectiles") for s in sides])

    # ------------------------------------------------------------------------------------------------ fast decide
    def _fast_group(self, model, c, sides, idx, batch, keys, heads, p, hand, cell_fn, v_old=None, wver=None,
                    abx=None) -> None:
        """_fast_gen with its one cell request answered by ``cell_fn`` at once (the sequential form)."""
        g = self._fast_gen(model, c, sides, idx, batch, keys, heads, p, hand, v_old, wver, abx)
        req = next(g, None)
        if req is not None:
            try:
                g.send(cell_fn(*req))
            except StopIteration:
                pass

    def _fast_gen(self, model, c, sides, idx, batch, keys, heads, p, hand, v_old=None, wver=None, abx=None):
        """A generator: yields once (ids, slots) when rows play, and takes their cell logits by send(). Match.pre + e1_eval.sample_decide_batch + decision_options.decide (decode 'sample', no rules) + _record for one
        policy group, vectorised where the arithmetic allows it and EXACT: the same torch ops on the same batch, every
        draw from the row's own rng in production's order (gate, card, cell), numpy Generator.choice reproduced as its
        own cdf / searchsorted('right') on one uniform. compare.py asserts it against production (actor_main)."""
        import math
        import torch
        from pipeline import engine_play as ep
        from pipeline.decision_options import phase_index
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
                cel = yield (list(map(int, play_idx)), [int(slots[r]) for r in play_idx])
                cell_probs = torch.softmax(cel.double() / T, dim=-1).cpu().numpy()
            cells[play_idx] = self._choice(cell_probs, [rngs[r] for r in play_idx])
            for j, r in enumerate(play_idx):
                lp_cell[r] = math.log(cell_probs[j, cells[r]])
        # sample_decide_batch's last step: PRODUCTION's ability_decide (before _record's n_dec + 1; its own rng_ability)
        ab = self.E.ability_decide(sides, *abx) if abx is not None and c.get("ability") else None
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
                    if not k.startswith("mem_"):              # MEM_KEYS ride in result["memory"] (production)
                        rows.setdefault(k, []).append(batch[k][j])
                if s.cfg.get("record_phi"):                   # reward_shaping.state_record on Match.state's towers
                    rows.setdefault("phi_state", []).append(self._phi(s, int(r), int(tick[j])))
                if has_mem(model):
                    rows.setdefault("mem_t", []).append(int(tick[j]))
                    if MEMHASH:                               # compare.py: the forward's MEM row vs the learner rebuild
                        import hashlib
                        from pipeline.match_memory import MEM_KEYS
                        rows.setdefault("mem_h", []).append(hashlib.sha1(b"".join(
                            np.ascontiguousarray(batch[k][j]).tobytes() for k in MEM_KEYS)).hexdigest())
                for k, x in (("tick", int(tick[j])), ("allowed", allowed[j]), ("stalled", bool(stalled[j])),
                             ("gate_sampled", bool(gate_sampled[j])), ("played", bool(playing[j])),
                             ("slot", int(slots[j])), ("cell", int(cells[j])), ("lp_gate", float(lp_gate[j])),
                             ("lp_card", float(lp_card[j])), ("lp_cell", float(lp_cell[j])), ("p_gate", float(pj)),
                             ("T", T)) + ((("gate_tau", float(tau_r[j])),) if tau_r is not None else ()) + (
                                 (("v_old", float(v_old[j])), ("wver", int(wver))) if v_old is not None else ()):
                    rows.setdefault(k, []).append(x)
                if ab is not None:                            # _record: the ability_defaults keys of the decision
                    for k in self.E.ability_defaults():
                        rows.setdefault(k, []).append(ab[j][k])
            a = v.act[r]
            if playing[j]:
                X, Y = ep.cell_to_engine(int(cells[j]), s.mirror, s.cfg["grid"])
                a[:] = (1, int(slots[j]), int(cells[j]), int(X) * SCALE // K, int(Y) * SCALE // K, int(X), int(Y), 0)
                s.fl[s.deck.cards[int(slots[j])]] += 1
                s.fl_el.append(float(el_int[j]))
            else:
                a[:] = (0, -1, -1, 0, 0, 0, 0, 0)

    def _phi(self, s, r: int, tick: int) -> list:
        """SelfPlaySide._record's phi_state for record_phi tower_phat: production's state_record on a state holding what
        it reads (raw()'s episode crown_towers from CfTrain.towerRow, the tick; no crowns key: derived from the towers)."""
        from pipeline import reward_shaping as RS
        t = self.v.twr[r]
        tw = [{"side": int(t[1 + 4 * k]), "type": "king" if t[2 + 4 * k] else "princess", "hp": int(t[3 + 4 * k]),
               "max_hp": int(t[4 + 4 * k]), "destroyed": int(t[3 + 4 * k]) <= 0} for k in range(int(t[0]))]
        return RS.state_record(s.cfg["record_phi"], {"tick": tick, "episode": {"crown_towers": tw}}, s.side, None,
                               s.__dict__.setdefault("_phi_mem", {}))

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
        if "tgt" in rows:                                    # TARGET-OBS: _traj_arrays' tgt / tgt_idx
            out["tgt"] = st("tgt").astype(np.float32)
            out["tgt_idx"] = st("tgt_idx").astype(np.int64)
        if s.cfg.get("record_tick"):
            out["tick"] = sc("tick", np.int64)
        if "gate_tau" in rows:
            out["gate_tau"] = sc("gate_tau", np.float64)
        if "phi_state" in rows:                              # cfg["record_phi"]: reward_shaping state rows
            out["phi_state"] = np.stack([np.asarray(x) for x in rows["phi_state"]]).astype(np.float64)
        if "mem_t" in rows:                                  # Plan A memory model: each row's memory tick
            out["mem_t"] = sc("mem_t", np.int64)
        if "mem_h" in rows:
            out["mem_h"] = list(rows["mem_h"])
        if "v_old" in rows:                                  # LOOP-SRV: the critic of the same batch / version
            out["v_old"] = sc("v_old", np.float64)
            out["wver"] = sc("wver", np.int64)
        if "ab_sampled" in rows:                             # cfg["ability"] (rl_royale ability_head): per row
            out.update(ab_sampled=sc("ab_sampled", bool), ab_press=sc("ab_press", bool), ab_lp=sc("ab_lp", np.float64),
                       ab_feat=st("ab_feat").astype(np.float32), ab_cand=sc("ab_cand", bool), ab_q=sc("ab_q", np.float64))
        return out


FAST_DECIDE = os.environ.get("FASTLOOP_DECIDE", "fast") == "fast"


def server_version(update: int, ability: bool) -> int:
    """LOOP-SRV weight version of an update's learner message: 2 u (+ 1 when it carries the ability head). rl_royale's B6
    warm start (no head) and u0000's rollout (head) are both update 0 with different heads; the server only loads a newer
    version. Traj wver = version // 2 = the update."""
    return 2 * int(update) + int(bool(ability))
# SPEED2 F3 (ROLLOUT-SPEED, opt-in): with --server, the fast groups' cell requests of a round go to serve.py as ONE
# message (policy_server Client.cells_multi) instead of one round trip per model group; absent = per group, as before
CELLS1 = bool(os.environ.get("FASTLOOP_CELLS1"))
MEMHASH = bool(os.environ.get("FASTLOOP_MEMHASH"))           # compare.py only: per-row MEM_KEYS hashes in the traj


def fast_ok(c: dict) -> bool:
    """The cfg the fast decide reproduces: sample decode, all three heads, no decide rules / posture, the afford mask
    on, no anti-stall clock (the ability head: production's ability_decide, called by _fast_group). Anything else takes
    production's path."""
    from pipeline.decision_options import DecisionOptions, options_from_config, sample_rules
    return (c["policy"] == "sample" and "sample_heads" not in c and not c.get("posture")
            and bool(c["afford_mask"]) and c.get("stall_elixir") is None and c.get("afford_ticks") is None
            and "_opp_style" not in c and sample_rules(options_from_config(c)) == DecisionOptions())

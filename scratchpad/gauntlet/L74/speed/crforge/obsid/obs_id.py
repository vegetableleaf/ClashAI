"""S3b-3a (plan1026 Pillar 4): byte identity of the Java observation builders against the production GenModel row.

At EVERY decision of facade-driven self-play (ROYALE_ENGINE=crforge, e1_eval.run_selfplay_batch, CLXIII on both seats,
search_s0.live_cfg + action delay 26 + feature_version 6, as F1's accept_f1 obs), the hook on ``e1_eval.Match.gen_row``
takes (1) the production row (``prepare`` + ``gen_row``, unchanged) and (2) every builder in ``BUILDERS`` run on the
SAME facade battle at the same tick, and compares each GenModel key byte for byte (dtype, shape, bytes). A key no
builder produces is NOT_PORTED. Per key: rows, rows equal, rows that differ at each last-axis index, first diffs.

Adding a port = one function in BUILDERS returning {key: array in the production dtype}; nothing else changes.

usage (pod 32657): obsid/run.sh [--n 56] [--set extrapolate_ticks=0 ...]   (compiles, then runs this file)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RL = Path(os.environ.get("OBSID_RL", "/workspace/f1/rl"))       # the facade work tree (pipeline/ at HEAD)
os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
os.environ["ROYALE_ENGINE"] = "crforge"
sys.path[:0] = ["/workspace/cfspeed/pylib", str(RL)]

import jpype  # noqa: E402
import numpy as np  # noqa: E402

DECKS = Path("/workspace/cfspeed/decks.tsv")
CLXIII = os.environ.get("OBSID_CLXIII", "/workspace/f1/models/succ48_o_s91_u0075_grafted.pt")   # S3b-3d: pod 30408 keeps it elsewhere
SFX = {0: "", 1: "@evolution", 2: "@hero"}
OPP_EL = 5            # sc index of the opponent's elixir: S3b-3c, both sides the PUBLIC estimate (no truth anywhere)
NO_VALUES: set = set()  # keys whose first diffs record indices only


def start_jvm(build: Path) -> None:
    """The facade's JVM (crforge_core._jvm skips startJVM when one runs) with the builders' classes beside CfCore.
    OBSID_FACADE_BUILD (optional): a facade class dir put first, so ITS CfCore runs (a build another ticket made)."""
    from pipeline import crforge_core as cc
    first = [os.environ["OBSID_FACADE_BUILD"]] if os.environ.get("OBSID_FACADE_BUILD") else []
    cp = sorted(str(p) for p in cc.LIB.glob("*.jar")) + first + [str(build)]
    jpype.startJVM(f"-Xmx{os.environ.get('CRFORGE_XMX', '4g')}", classpath=cp, convertStrings=True)


def src_shas() -> dict:
    """sha256 of the facade / production sources this run uses (taken at start: the work tree is shared)."""
    import hashlib
    files = {"CfCore.java": os.environ.get("OBSID_CFCORE", str(RL / "scratchpad/gauntlet/L74/crforge/facade/CfCore.java"))}
    files.update({f"pipeline/{m}": str(RL / "pipeline" / m) for m in ("crforge_core.py", "royale_env.py", "e1_eval.py",
                                                                      "obs_contract.py", "body_identity.py",
                                                                      "public_observation.py", "opp_elixir_count.py",
                                                                      "vocab.py")})
    files.update({f"builder/{p.name}": str(p) for p in (HERE.parent / "CfSpeed.java", HERE / "CfObsBind.java",
                                                        HERE / "CfOppElixir.java", HERE / "CfPubObj.java", HERE / "obs_id.py")})
    files.update({f"pipeline/{m}": str(RL / "pipeline" / m) for m in ("sim_unit_state.py", "fast_obs.py", "model_gen.py")}
                 | {"builder/CfCue.java": str(HERE / "CfCue.java")})      # S3b-3f: the cue path
    out = {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in files.items()}
    fb = os.environ.get("OBSID_FACADE_BUILD")
    if fb:
        out.update({f"{fb}/{c.name}": hashlib.sha256(c.read_bytes()).hexdigest() for c in sorted(Path(fb).glob("*.class"))})
    return out


def census():
    out = []
    for line in DECKS.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[3].split(","), [int(v) for v in f[4].split(",")]))
    return out


# ---------------------------------------------------------------------------------------------------- builders
class JavaMain:
    """CfSpeed.Match.obs at feature version 6 (CfObsBind.FacadeMatch) on the facade battle: tok / mask / sc /
    unit_form. Body identity: the facade's own tables (body_map, root play) give each body its card; the Names table
    maps "card|body row|max_hp|form|tower kind|tower max_hp" -> production's class / form (``resolve``)."""

    def __init__(self):
        from pipeline import crforge_core as cc
        J = cc._jvm()
        self.tables = J["tables"]
        self.CfSpeed, self.Bind = jpype.JClass("CfSpeed"), jpype.JClass("CfObsBind")
        self.Match = jpype.JClass("CfObsBind$FacadeMatch")
        self.facade_hero_rule = str(self.Bind.facadeHeroRule())
        self.names = self.CfSpeed.Names()
        self.card_names = None
        self.match = {}                                   # unused since D2-T2 (core._obsid_match per core object)
        BB = jpype.JClass("java.nio.ByteBuffer")
        order = jpype.JClass("java.nio.ByteOrder").nativeOrder()
        self.b = {k: BB.allocateDirect(n).order(order) for k, n in
                  (("tok", 64 * 14 * 4), ("mask", 64), ("sc", 70 * 4), ("form", 64))}
        self.tokF, self.scF = self.b["tok"].asFloatBuffer(), self.b["sc"].asFloatBuffer()
        self.v = {k: np.frombuffer(memoryview(b), dt) for (k, b), dt in
                  zip(self.b.items(), (np.float32, np.uint8, np.float32, np.int8))}
        self.Int = jpype.JArray(jpype.JInt)
        self.keys = jpype.JClass("CfOppElixir$Keys")()     # S3b-3c: the public counter's detector keys
        self.key_of, self.spell_cards, self.opp_spells, self.gid = {}, None, True, None   # gid: the policy's (main)
        self.b["opp_past"] = BB.allocateDirect(15 * 4).order(order)
        self.pastF, self.v["opp_past"] = self.b["opp_past"].asFloatBuffer(), np.frombuffer(memoryview(self.b["opp_past"]), np.float32)

    def key_index(self, key) -> int:
        """A detector key -> its index in the Java table (cost, swarm window), registered on first sight."""
        from pipeline.dataset_gen import card_key
        from pipeline.opp_elixir_count import PlayDetector, card_cost
        if key is None:
            return -1
        if key not in self.key_of:
            d, c = PlayDetector(), card_cost(key)
            self.key_of[key] = int(self.keys.addKey(key, float("nan") if c is None else float(c),
                                                    int(d.swarm_ticks_by_key.get(key, d.swarm_ticks)),
                                                    int(self.gid.get(card_key(key), 0))))
        return self.key_of[key]

    def spell_table(self, s) -> None:
        """card id -> detector key when public_frame (source 'sim') counts that card's board objects as a spell
        (cards.yaml kind 'spell'), on the names raw() gives them: env.names, else str(id) (-1 tower, -2 none)."""
        from pipeline.public_observation import public_frame
        names = s.env.names
        tab = [-1] * (max(names) + 3)
        self.spell_cards = set()
        for cid in range(-2, max(names) + 1):
            row = dict(side=0, x=0.0, y=0.0, name=names.get(cid, str(cid)))
            sp = public_frame({"tick": 0, "effects": [row], "projectiles": [row]}, source="sim")["spells"]
            if sp:
                assert len(sp) == 2 and sp[0]["card"] == sp[1]["card"], sp
                self.spell_cards.add(cid)
                tab[cid + 2] = self.key_index(sp[0]["card"]) if self.opp_spells else -1
        self.keys.spell = self.Int(tab)
        self.keys.shots = "projectiles" in s.state           # raw() has shots only at env feature_version >= 4

    def resolve_opp(self, s) -> None:
        """Each new "card|body row|form#entity id" -> the detector key production gives that body: public_frame
        (source 'sim') on its raw() entity, then PlayDetector's catalog name -> vocab.engine_key (None -> -1)."""
        from pipeline import vocab
        from pipeline.obs_contract import catalog_card_form
        from pipeline.opp_elixir_count import _catalog_names
        from pipeline.public_observation import public_frame
        ents = {int(e["entity_id"]): e for e in s.state["entities"]}
        for miss in self.keys.takeMissing():
            k, eid = str(miss).rsplit("#", 1)
            f = public_frame({"tick": s.state["tick"], "entities": [ents[int(eid)]]}, source="sim")["entities"]
            name = _catalog_names().get(f[0]["card_id"]) if f else None
            self.keys.putBody(k, self.key_index(vocab.engine_key(name) if name else None),
                              int(catalog_card_form(f[0]["card_id"])[1]) if f else 0)

    def resolve(self) -> None:
        """Each new key -> what RoyaleSelfPlayEnv.raw() + from_engine fv6 give that body: raw's name (the Hero Ice
        Wizard's body rows read 'IceWizard', royale_heroiw.public_identity), the tower level factor from_engine takes
        from the side's first tower, then body_identity.resolve_board. None -> -1 (dropped, as from_engine drops it)."""
        from pipeline import royale_heroiw as heroiw
        from pipeline.body_identity import resolve_board
        for s in self.names.takeMissing():
            assert s.startswith("U:"), s                  # fv6 builds no spell tokens
            key = s[2:]
            card, body, mhp, form, king, tmhp = key.split("|")
            name = "IceWizard" if heroiw.public_identity(body) is not None else self.card_names.get(int(card), card)
            f = {0: float(tmhp) / (4824.0 if king == "1" else 3052.0)} if int(tmhp) else {}
            ident = resolve_board([(0, name, int(mhp), int(form), False)], f)[0]
            self.names.putUnit(key, -1 if ident.cls is None else int(ident.cls), int(ident.form))

    def _obs(self, m, seat):
        m.obs(seat, self.names, self.tokF, 0, self.b["mask"], 0, self.scF, 0, self.b["form"], 0)

    def _past(self, opp):
        opp.past(self.pastF, 0)
        return self.v["opp_past"].reshape(3, 5).copy()

    def __call__(self, s) -> dict:
        from pipeline.dataset_gen import SC_SLOT_COLS
        core = s.env.core
        m = core.__dict__.get("_obsid_match")             # D2-T2: per core OBJECT (an id(core) key is reused by a
        if m is None:                                     # later env's core once the old one is freed)
            m = core._obsid_match = self.Match(self.tables)
        if self.card_names is None:
            self.card_names = dict(s.env.names)              # raw()'s card id -> name
        # crforge deck index = the env's deal order (RoyaleSelfPlayEnv.deal, ShuffleMode.NONE); our slots index env.decks
        slot_of = {i: slot for slot, i in s.deck_index_of_slot.items()}
        decks, deal = s.env.decks[s.side], s.env.deal[s.side]
        inv = [slot_of.get(list(decks).index(n), 8) for n in deal]
        self.Bind.bind(m, core._cf, int(s.side), self.Int(inv))
        m.extrap = int(s.cfg.get("extrapolate_ticks") or 0)
        if self.spell_cards is None:
            from pipeline.opp_elixir_count import REGEN_SCHEDULE
            assert tuple(s.env.elixir_regen_schedule) == REGEN_SCHEDULE   # CfObsBind's regen constants
            assert s.opp_mode == "counter" and s.feature_version >= 4    # prepare: opp_elixir = public.estimate_at
            self.spell_table(s)
        opp = m.opp(int(s.side), self.keys)
        while not opp.update():                           # S3b-3c: the public counter sees this decision's board
            self.resolve_opp(s)
        self._obs(m, int(s.side))
        if self.names.missing.size():                     # new names: fill the tables, build again
            self.resolve()
            m.rewind(int(s.side))                         # the rebuild sees this decision's previous state again
            self._obs(m, int(s.side))
        sc = self.v["sc"].copy()
        sc_pre = sc.copy()
        sc[SC_SLOT_COLS] = 0.0                            # GenPolicy.row's zeroing (the key the model reads)
        mask = self.v["mask"].copy()
        assert mask.max() <= 1
        return {"tok": self.v["tok"].reshape(64, 14).copy(), "mask": mask.astype(bool), "sc": sc,
                "unit_form": self.v["form"].copy(), "_sc_prepare": sc_pre, "_tick": int(core._cf.tick()),
                "_n_bodies_moved": int(m.movedLast), "_n_rows_moved": int(m.movedLast > 0),
                "opp_past": self._past(opp), "_opp_plays": np.int64(opp.plays), "_opp_spawns": np.int64(opp.spawns),
                "_nospell_opp": not any(int(c) in self.spell_cards for c in s.env.deck_ids[1 - s.side])}


class JavaIdent:
    """S3b-3b: CfIdent on the facade battle: past + the hand / next / deck / slot identity arrays. Its inputs: the facade
    (deck card ids and forms by deal index, hand, queue, tick), the deal -> slot map, a card id -> checkpoint id table
    (filled here from the policy's gid, as slot_ident looks it up) and the plays the facade GAVE, logged by the
    ``Match._land`` hook (main) with the facade's tick at the act, the decided slot and cell."""
    ID_KEYS = (("hand_slot", 4), ("hand_card", 4), ("hand_form", 4), ("next_card", 0), ("next_form", 0),
               ("deck_card", 8), ("deck_form", 8), ("slot_card", 9), ("slot_form", 9))

    def __init__(self, policy):
        self.Ident, self.gid, self.ident = jpype.JClass("CfIdent"), policy.gid, {}   # unused since D2-T2 (core._obsid_ident)
        BB = jpype.JClass("java.nio.ByteBuffer")
        order = jpype.JClass("java.nio.ByteOrder").nativeOrder()
        self.bi, self.bp = BB.allocateDirect(8 * 48).order(order), BB.allocateDirect(4 * 15).order(order)
        self.ids, self.past = self.bi.asLongBuffer(), self.bp.asFloatBuffer()
        self.vi, self.vp = np.frombuffer(memoryview(self.bi), np.int64), np.frombuffer(memoryview(self.bp), np.float32)
        self.Int = jpype.JArray(jpype.JInt)

    def of(self, s):
        """The CfIdent of ``s``'s core (cfg and the gid table set on first sight)."""
        from pipeline.dataset_gen import card_key
        core = s.env.core
        j = core.__dict__.get("_obsid_ident")
        if j is None:
            j = core._obsid_ident = self.Ident()
            j.extrap = int(s.cfg.get("extrapolate_ticks") or 0)
            j.cellOff = 0.5 if s.cfg["grid"] == "floor" else 0.0
        for cid, nm in zip(s.env.deck_ids[s.side], s.engine_deck):     # env deck order, slot_ident's names
            if card_key(nm) in self.gid:
                j.putGid(int(cid), int(self.gid[card_key(nm)]))
        return j

    def played(self, s, d) -> None:
        self.of(s).played(s.env.core._cf, int(s.side), int(s.env.core._cf.tick()), int(d["slot"]), int(d["cell"]))

    def __call__(self, s) -> dict:
        slot_of = {i: slot for slot, i in s.deck_index_of_slot.items()}
        decks, deal = s.env.decks[s.side], s.env.deal[s.side]
        inv = [slot_of.get(list(decks).index(n), 8) for n in deal]
        self.of(s).build(s.env.core._cf, int(s.side), self.Int(inv), self.ids, 0, self.past, 0)
        out, o = {"past": self.vp.reshape(3, 5).copy()}, 0
        for k, n in self.ID_KEYS:
            out[k] = self.vi[o:o + n].copy() if n else np.int64(self.vi[o])
            o += max(n, 1)
        return out


class JavaPub:
    """S3b-3d: CfPubObj on the facade battle -> projectiles / effects / own_ability (PublicObserver.update + features at
    the view tick, advance_public_objects under the look-ahead) and opp_cycle (on S3b-3c's CfOppElixir detected plays).
    Its tables come from production's own functions (projectile_observation.objects / constant_projectile_speeds /
    unavailable_area_timers, own_ability.observe / catalog, dataset_gen.card_key, the policy's gid); its action log from
    a hook on royale_env._Core.act (accepted plays: the facade tick at the act + the deck card id; accepted presses: the
    tick + the button), as the loop that gives the commands will log them."""
    KEYS = (("projectiles", (64, 8)), ("effects", (32, 6)), ("own_ability", (8, 7)), ("opp_cycle", (8, 4)))

    def __init__(self, main, policy):
        from pipeline import royale_env as R
        self.main, self.gid = main, policy.gid
        self.C = jpype.JClass("CfPubObj")
        self.T, self.pub, self.ready = self.C.Tables(), {}, False
        BB = jpype.JClass("java.nio.ByteBuffer")
        order = jpype.JClass("java.nio.ByteOrder").nativeOrder()
        self.b = {k: BB.allocateDirect(4 * s[0] * s[1]).order(order) for k, s in self.KEYS}
        self.f = {k: b.asFloatBuffer() for k, b in self.b.items()}
        self.v = {k: np.frombuffer(memoryview(self.b[k]), np.float32).reshape(s) for k, s in self.KEYS}
        self.press_tick_mismatch = self.presses = 0
        orig, pub = R._Core.act, self

        def act(core_, *, side, deck_index=-1, x=0, y=0, ability_button=None):
            env = core_.env
            t = int(env.core._cf.tick())
            r = orig(core_, side=side, deck_index=deck_index, x=x, y=y, ability_button=ability_button)
            if r["accepted"]:
                j = pub.of(env)
                if ability_button is None:
                    j.act(int(side), t, int(env.deck_ids[side][deck_index]))
                else:
                    pub.press_tick_mismatch += int(t != int(env.tick))   # own_ability_events' tick is env.tick
                    j.press(int(side), t, int(ability_button))
                    pub.presses += 1
            return r

        R._Core.act = act

    def key(self, k) -> int:
        return int(self.T.addKey("\0None" if k is None else k, int(self.gid.get(k, 0)) if k is not None else 0))

    def tables(self, s) -> None:
        """Per RoyaleSim card id (-2 .. max): objects()'s key of the name raw() gives that card's shots / spell rows (sim
        source; dropped -> -1), its catalog speed, its area-timer mask; card_key of the name (the action log's key)."""
        from pipeline.dataset_gen import card_key
        from pipeline.projectile_observation import constant_projectile_speeds, objects
        assert s.env.feature_version >= 4 and "projectiles" in s.state      # raw() carries sim_objects
        names = s.env.names
        n = max(names) + 3
        ok, nt, ev = [-1] * n, [False] * n, [-1] * n
        for cid in range(-2, n - 2):
            nm = names.get(cid, str(cid))
            row = dict(side=0, x=0.0, y=0.0, name=nm)
            o = objects({"projectiles": [dict(row, target_x=0.0, target_y=0.0, time_to_impact_ms=None)],
                         "effects": [dict(row, remaining_ms=50)]}, source="sim")
            if o["projectiles"]:
                k = o["projectiles"][0][0]
                ok[cid + 2], nt[cid + 2] = self.key(k), o["effects"][0][4] is None
                sp = constant_projectile_speeds().get(k)
                self.T.putSpeed(ok[cid + 2], float(sp) if sp else float("nan"))
            if cid in names:
                ev[cid + 2] = self.key(card_key(nm))
        self.T.objKey, self.T.objNoTimer, self.T.evKey = (jpype.JArray(jpype.JInt)(ok), jpype.JArray(jpype.JBoolean)(nt),
                                                         jpype.JArray(jpype.JInt)(ev))
        self.names, self.ready = dict(names), True

    def resolve(self) -> None:
        """Each new own body "card|body row|form bits" -> own_ability.observe on the entity raw() makes of it (name, or
        'IceWizard' + public identity for a hero Ice Wizard body row, status bits) -> (key, form), or -1; the key's
        own_ability.catalog specs (hero_spec 'off')."""
        from pipeline import royale_heroiw as heroiw
        from pipeline.own_ability import catalog, observe
        for k in self.T.takeMissing():
            card, body, bits = str(k).split("|")
            ent = dict(side=0, hp=1, max_hp=1, x=0.0, y=0.0, name=self.names.get(int(card), card), card_id=int(card),
                       status_flags=int(bits))
            if heroiw.ENABLED and heroiw.public_identity(body) is not None:     # RoyalePoolEnv.raw's unit_types rule
                ent.update(name="IceWizard", public_card_id=heroiw.public_identity(body), public_form=2)
            rows = observe({"entities": [ent]}, 0, "sim")
            if not rows:
                self.T.putBody(k, -1, 0)
                continue
            key, form = rows[0][0], int(rows[0][1])
            i = self.key(key)
            self.T.putBody(k, i, form)
            for f in (0, 1, 2):
                sp = catalog("off").get((key, f))
                if sp:
                    self.T.putSpec(i, f, float(sp["max_charges"]), float(sp["deploy_ms"]), float(sp.get("cooldown_ms") or 0))

    def of(self, env):
        core = env.core
        j = core.__dict__.get("_obsid_pub")
        if j is None:
            j = core._obsid_pub = self.pub[len(self.pub)] = self.C(core._cf, self.T)
        return j

    def __call__(self, s) -> dict:
        from pipeline.dataset_gen import card_key
        if not self.ready:
            self.tables(s)
        j, seat = self.of(s.env), int(s.side)
        j.extrap = int(s.cfg.get("extrapolate_ticks") or 0)
        while not j.update(seat):
            self.resolve()
        m = s.env.core.__dict__.get("_obsid_match")
        opp = m.opp(seat, self.main.keys) if m is not None and hasattr(m, "opp") else None
        if opp is not None:                                   # CfOppElixir key -> card_key's key (opp_cycle dedup)
            cyc = list(self.T.cyc)
            for i in range(len(cyc), int(self.C.detKeys(self.main.keys))):
                cyc.append(self.key(card_key(str(self.C.detKey(self.main.keys, i)))))
            self.T.cyc = jpype.JArray(jpype.JInt)(cyc)
        f = self.f
        j.build(seat, f["projectiles"], f["effects"], f["own_ability"], opp, f["opp_cycle"])
        out = {k: self.v[k].copy() for k, _ in self.KEYS if k != "opp_cycle" or opp is not None}
        prod_events = len(s.public.own_events)
        out.update(_n_view_tick_mismatch=int(j.viewTick(seat) != s._view_tick),
                   _n_own_events_mismatch=int(j.events(seat) != prod_events), _n_own_events=prod_events,
                   _n_rows_proj=int(out["projectiles"][:, 0].any()), _n_rows_eff=int(out["effects"][:, 0].any()),
                   _n_rows_abil=int(out["own_ability"][:, 0].any()), _n_rows_abil_known=int(out["own_ability"][:, 4].any()),
                   _n_rows_cycle=int(out.get("opp_cycle", np.zeros((1, 1)))[:, 0].any()))
        # the press branch, on PRODUCTION's row (cols: card, form, n, ready, ready_known, charges, cooldown_s): a known
        # controller not ready / with no charge left (a press after its deploy) / a cooldown still running
        pa = s._gen_row["own_ability"]
        kn = (pa[:, 0] > 0) & (pa[:, 4] == 1)
        out.update(_n_rows_abil_not_ready=int((kn & (pa[:, 3] == 0)).any()),
                   _n_rows_abil_spent=int((kn & (pa[:, 5] == 0)).any()),
                   _n_rows_abil_cooldown=int((kn & (pa[:, 6] > 0)).any()),
                   _n_rows_abil_spent_identical=int((kn & (pa[:, 5] == 0)).any()
                                                    and pa.tobytes() == out["own_ability"].tobytes()))
        return out


class JavaCue:
    """S3b-3f: CfCue on the facade battle -> "cue" ([64, 22] float32, e1_eval.sim_cue_rows), from the tok / mask the
    builder before it (JavaMain) left in its buffers for this row. The card-table facts (sim_unit_state._tbl: hit speed,
    hides_when_not_attacking, the idle buff, each buff's _statuses and table totals) go to CfCue.Tables on first sight;
    the buff memo lives on the production Match as production's does (``_s3b3f_cue`` beside ``_cue_memo``).
    Cost diagnostics (ns, summed): production's sim_cue_rows (timed in place), fast_obs.sim_cue_rows (S1b, on a copy of
    the memo), the Java build inside the JVM and the Python call around it."""
    TAG = {"frozen": 1, "slowed": 2, "raged": 4, "invisible": 8, "shielded": 16}   # CfCue's status bits

    def __init__(self, main, E):
        from pipeline import sim_unit_state as SU
        self.main, self.Cue, self.SU = main, jpype.JClass("CfCue"), SU
        self.T = self.Cue.Tables()
        sim = sys.modules["royalesim"]
        bit = {n: 1 << b for b, n in enumerate(sim.STATUS_BITS)}
        self.T.underground, self.T.invisible, self.T.windup = bit["underground"], bit["invisible"], bit["ability_windup"]
        assert (self.T.underground, self.T.invisible, self.T.windup) == (1, 2, 64)   # the bits CfCue.vector computes
        self.tbl = SU._tbl(sim)
        BB = jpype.JClass("java.nio.ByteBuffer")
        self.bo = BB.allocateDirect(64 * 22 * 4).order(jpype.JClass("java.nio.ByteOrder").nativeOrder())
        self.outF, self.v = self.bo.asFloatBuffer(), np.frombuffer(memoryview(self.bo), np.float32)
        from pipeline import fast_obs
        self.fast, self.py_ns = fast_obs.sim_cue_rows, 0
        orig = E.sim_cue_rows

        def timed(match):                                 # production's call, unchanged, timed
            t = time.perf_counter_ns()
            r = orig(match)
            self.py_ns = time.perf_counter_ns() - t
            return r
        E.sim_cue_rows = timed

    def _bits(self, alias) -> int:
        return sum(self.TAG[t] for t in self.SU._statuses(alias, self.tbl["buffs"]) if t in self.TAG)

    def fill(self) -> None:
        for m in self.T.takeMissing():
            kind, name = str(m)[0], str(m)[2:]
            if kind == "B":
                ct = self.tbl["char"].get(name, {})
                hs, ib = ct.get("hit_speed_ms"), ct.get("idle_buff")
                assert hs is None or type(hs) is int, (name, hs)
                self.T.putBody(name, int(hs or 0), bool(ct.get("hides_when_not_attacking")),
                               self._bits(ib["buff_name"]) if ib else -1)
            else:
                self.T.putBuff(name, self._bits(name), max(self.tbl["totals"].get(a, 0) for a in name.split("|")))

    def __call__(self, s) -> dict:
        seat = s.__dict__.get("_s3b3f_cue")
        if seat is None:
            seat = s._s3b3f_cue = self.Cue.Seat()
        jn0 = int(seat.nanos)
        while True:
            t = time.perf_counter_ns()
            ok = self.Cue.build(s.env.core._cf, int(s.side), self.T, seat, self.main.tokF, 0, self.main.b["mask"], 0,
                                self.outF, 0)
            t = time.perf_counter_ns() - t
            if ok:
                break
            self.fill()
        memo = s._cue_memo                                # S1b's path on a copy (the production memo stays as it is)
        s._cue_memo = dict(memo)
        tf = time.perf_counter_ns()
        self.fast(s)
        tf = time.perf_counter_ns() - tf
        s._cue_memo = memo
        prod = s._gen_row["cue"]
        return {"cue": self.v.reshape(64, 22).copy(), "_n_cue_py_ns": self.py_ns, "_n_cue_fast_ns": tf,
                "_n_cue_java_ns": int(seat.nanos) - jn0, "_n_cue_jcall_ns": t,
                "_n_rows_cue_active": int(bool(prod[:, 0].any())), "_n_cue_tokens": int((prod[:, 0] > 0).sum()),
                **{f"_n_cue_col{k:02d}": int((prod[:, k] != 0).sum()) for k in range(22)}}   # tokens with column k set


BUILDERS: list = []   # filled in main (they need the JVM); a later ticket appends one builder per ported key


# ---------------------------------------------------------------------------------------------------- comparison
class Report:
    def __init__(self, first: int):
        self.first, self.keys, self.rows, self.tick_mismatch = first, {}, 0, 0
        self.diag = {}                                    # '_n_*' counters the builders / the hook report

    def _k(self, key):
        return self.keys.setdefault(key, dict(rows=0, equal=0, not_ported=0, dtype_shape_diff=0, per_index=None,
                                              first_diffs=[]))

    def add(self, s, prod: dict, java: dict, prod_sc_prepare) -> None:
        self.rows += 1
        tick = int(s._cur[0])
        for k in [k for k in java if k.startswith("_n_")]:
            self.diag[k[3:]] = self.diag.get(k[3:], 0) + int(java.pop(k))
        if java.pop("_tick", tick) != tick:
            self.tick_mismatch += 1
        aux = {"_sc_prepare": np.array(prod_sc_prepare, copy=True)}
        for key in sorted(set(prod) | {k for k in java if not k.startswith("_")}) + ["_sc_prepare"]:
            a = aux[key] if key in aux else prod.get(key)
            r = self._k(key)
            r["rows"] += 1
            if key not in java:
                r["not_ported"] += 1
                continue
            b = java[key]
            a, b = np.asarray(a), np.asarray(b)
            if a.dtype != b.dtype or a.shape != b.shape:
                r["dtype_shape_diff"] += 1
                if len(r["first_diffs"]) < self.first:
                    r["first_diffs"].append(dict(tag=s.tag, tick=tick, prod=[str(a.dtype), a.shape],
                                                 java=[str(b.dtype), b.shape]))
                continue
            if a.tobytes() == b.tobytes():
                r["equal"] += 1
                continue
            a, b = np.atleast_1d(a), np.atleast_1d(b)
            u = f"u{a.itemsize}"                       # element bits, so -0.0 vs 0.0 and NaNs count as bytes do
            ne = np.ascontiguousarray(a).view(u) != np.ascontiguousarray(b).view(u)
            per = ne.reshape(-1, ne.shape[-1]).any(0).astype(np.int64)
            r["per_index"] = per if r["per_index"] is None else r["per_index"] + per
            if len(r["first_diffs"]) < self.first:
                d = dict(tag=s.tag, side=int(s.side), tick=tick, index=np.argwhere(ne)[:6].tolist())
                if key not in NO_VALUES and not key.startswith("_sc"):
                    rows = sorted({int(i[0]) for i in np.argwhere(ne)[:3]}) if a.ndim > 1 else []
                    d.update(prod=[a[i].tolist() for i in rows] if rows else a.tolist()[:16],
                             java=[b[i].tolist() for i in rows] if rows else b.tolist()[:16])
                r["first_diffs"].append(d)

    def result(self) -> dict:
        out = {}
        for k, r in self.keys.items():
            st = ("NOT_PORTED" if r["not_ported"] == r["rows"] else
                  "IDENTICAL" if r["equal"] == r["rows"] else "DIFF")
            per = r["per_index"]
            out[k] = dict(status=st, **{x: r[x] for x in ("rows", "equal", "not_ported", "dtype_shape_diff")},
                          rows_diff_at_last_axis_index=({int(i): int(per[i]) for i in np.flatnonzero(per)}
                                                        if per is not None else {}),
                          first_diffs=r["first_diffs"])
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=56, help="matches (both seats CLXIII): about 900 seat-rows each")
    ap.add_argument("--inflight", type=int, default=8)
    ap.add_argument("--threads", type=int, default=4, help="torch threads")
    ap.add_argument("--set", action="append", default=[], help="cfg override k=v (JSON value), both seats")
    ap.add_argument("--min-rows", type=int, default=38400)
    ap.add_argument("--first-diffs", type=int, default=5)
    ap.add_argument("--opp-spells", type=int, default=1, help="0 = S3b-3c step 1: the counter sees bodies only")
    ap.add_argument("--pairs", default="", help="census pair indices (comma list, repeats allowed); default the first --n")
    ap.add_argument("--hero-abilities", action="store_true", help="S3b-3d: env presses ability buttons by its rule "
                    "(RoyaleSelfPlayEnv hero_abilities, ability_policy generic): exercises own_ability after a press")
    ap.add_argument("--build", default=str(HERE / "build"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    shas = src_shas()
    start_jvm(Path(a.build))
    import torch
    torch.set_num_threads(a.threads)
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline.royale_runtime import ENGINE

    assert ENGINE == "crforge", ENGINE
    model, info = E.load_policy(CLXIII)
    BUILDERS.append(JavaMain())
    BUILDERS[0].opp_spells, BUILDERS[0].gid = bool(a.opp_spells), model.gid
    ident = JavaIdent(model)
    BUILDERS.append(ident)
    BUILDERS.append(JavaCue(BUILDERS[0], E))           # S3b-3f: "cue" from JavaMain's tok / mask
    pub = JavaPub(BUILDERS[0], model)                   # S3b-3d: projectiles / effects / own_ability / opp_cycle
    BUILDERS.append(pub)
    cfg = S.live_cfg(0.5, info["grid"])
    cfg.update(action_delay_ticks=26, feature_version=6)
    over = {k: json.loads(v) for k, v in (x.split("=", 1) for x in a.set)}
    cfg.update(over)
    rep = Report(a.first_diffs)
    orig = E.Match.gen_row
    orig_land = E.Match._land
    from pipeline.dataset_gen import opponent_past
    # S3b-3b: opp_past vs the delivered-play log; rows whose past / opp_past hold a play AND a look-ahead view tick
    # (dt = view tick - play tick: those keys move with extrapolate_ticks)
    odiag = dict(rows=0, equal=0, cards_equal=0, prod_nonempty=0, past_view_ahead=0, opp_past_view_ahead=0)

    def _land(self, p, d, land, landed, cur=None):
        acc = orig_land(self, p, d, land, landed, cur)
        if acc:                                           # the facade gave it: CfIdent's play log (past)
            ident.played(self, d)
        return acc

    E.Match._land = _land

    def gen_row(self, policy):
        row = orig(self, policy)
        # rows whose production view took a look-ahead / showed pending plays (e1_eval.Match.prepare's h, pend;
        # SelfPlaySide.pending = my decided play not yet run, other.pending = the opponent's)
        java = {"_n_rows_lookahead": int(self._view_tick != self._cur[0]), "_n_rows_pend": int(bool(self.pend)),
                "_n_rows_own_pending": int(getattr(self, "pending", None) is not None),
                "_n_rows_opp_pending": int(getattr(getattr(self, "other", None), "pending", None) is not None),
                "_n_rows_own_fx": int(self.own_fx is not None), "_n_rows_drops": int(self.drops is not None)}
        for b in BUILDERS:
            java.update(b(self))
        # S3b-3c aux checks (public information only): production's PublicObserver play / spawn tallies, and sc on the
        # rows whose opponent deck has no spell card (bodies alone decide sc[5] there)
        prod = dict(row, _opp_plays=np.int64(len(self.public.plays)), _opp_spawns=np.int64(self.public.body.spawns))
        if java.pop("_nospell_opp"):
            prod["sc@nospell_opp"], java["sc@nospell_opp"] = row["sc"], java["sc"]
        rep.add(self, prod, java, self._obs[2])
        # diagnostic only, no builder: opp_past from the env's DELIVERED opponent plays (public_plays) vs production fv6
        # (PublicObserver.plays, detected from the public board)
        dl = opponent_past(self.env.public_plays, self._view_tick, self.side, policy.gid)
        odiag["rows"] += 1
        odiag["equal"] += int(dl.tobytes() == row["opp_past"].tobytes())
        odiag["cards_equal"] += int(dl[:, :2].tobytes() == row["opp_past"][:, :2].tobytes())
        odiag["prod_nonempty"] += int(bool((row["opp_past"][:, 0] > 0).any()))
        ahead = self._view_tick != self._cur[0]
        odiag["past_view_ahead"] += int(ahead and bool((row["past"][:, 0] > 0).any()))
        odiag["opp_past_view_ahead"] += int(ahead and bool((row["opp_past"][:, 0] > 0).any()))
        return row

    E.Match.gen_row = gen_row
    jobs = []
    cen = census()
    pairs = [int(v) for v in a.pairs.split(",")] if a.pairs else list(range(a.n))
    for i, (d1, f1) in enumerate(cen[p] for p in pairs):
        jobs.append((i, {"tag": f"obsid{i}", "seed": 5000 + i, "learner_side": i % 2,
                         "learner_deck": list(E.ICEBOW_ENGINE_DECK), "opp_deck": [n + SFX[f] for n, f in zip(d1, f1)],
                         "opp": {"id": "clxiii"}}, 0))
    envs, done, skips, t0 = [], [], [], time.time()

    def make():
        envs.append(RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=a.hero_abilities))
        return envs[-1]

    def on_result(r):
        done.append(r["tag"])
        print(json.dumps(dict(tag=r["tag"], decisions=r.get("decisions"), seat_rows=rep.rows,
                              wall_s=round(time.time() - t0))), flush=True)

    E.run_selfplay_batch(make, model, {"clxiii": (model, dict(cfg))}, jobs, cfg, min(len(jobs), a.inflight), on_result,
                         on_skip=lambda spec, exc: skips.append((spec["tag"], repr(exc))))
    keys = rep.result()
    core4 = ("tok", "mask", "sc", "unit_form")
    ident_keys = ("past",) + tuple(k for k, _ in JavaIdent.ID_KEYS)
    out = dict(
        hero_abilities=a.hero_abilities,
        ticket="S3b-3c", opp_spells=bool(a.opp_spells), census_pairs=pairs, matches=len(done), skipped=skips, seat_rows=rep.rows, tick_mismatch=rep.tick_mismatch,
        diag=rep.diag,
        wall_s=round(time.time() - t0, 1), cfg_overrides=over, feature_version=cfg["feature_version"],
        gen_row_keys=list(E.gen_row_keys(model.model)),
        acceptance=dict(min_rows=a.min_rows, rows_ok=rep.rows >= a.min_rows,
                        core_keys_identical={k: keys.get(k, {}).get("status") == "IDENTICAL" for k in core4},
                        ident_keys_identical={k: keys.get(k, {}).get("status") == "IDENTICAL" for k in ident_keys},
                        # sc[5] = the public counter on both sides (S3b-3c): core_keys_identical["sc"] covers it
                        sc_identical_except_opp_elixir=bool(keys.get("sc")) and keys["sc"]["dtype_shape_diff"] == 0
                        and set(keys["sc"]["rows_diff_at_last_axis_index"]) <= {OPP_EL},
                        opp_past_identical=keys.get("opp_past", {}).get("status") == "IDENTICAL",
                        pub_keys_identical={k: keys.get(k, {}).get("status") == "IDENTICAL" for k, _ in JavaPub.KEYS},
                        sc_nospell_opp=keys.get("sc@nospell_opp", {}).get("status"),
                        opp_counter_tallies={k: keys.get(k, {}).get("status") for k in ("_opp_plays", "_opp_spawns")}),
        status_by_key={k: v["status"] for k, v in sorted(keys.items())}, keys=keys, opp_past_delivered=odiag,
        pub_counters=dict(motion_estimated=int(sum(j.motionEstimated for j in pub.pub.values())),
                          landed=int(sum(j.landed for j in pub.pub.values())),
                          expired=int(sum(j.expired for j in pub.pub.values())), press_tick_mismatch=pub.press_tick_mismatch,
                          presses=pub.presses),
        opp_counter_edges=dict(zip(map(str, jpype.JClass("CfOppElixir").EDGE_NAMES),
                                   map(int, jpype.JClass("CfOppElixir").EDGE))),
        stamp=envs[0].core.card_table_stamp() if envs else None, facade_hero_rule=BUILDERS[0].facade_hero_rule,
        facade_src_sha256=shas,
        note=("prod = e1_eval prepare + gen_row; java = BUILDERS on the same facade battle and tick. Keys starting '_' "
              "are aux checks, not GenModel keys: _sc_prepare = prepare()'s sc before GenPolicy.row zeroes the hand "
              f"one-hots. sc[{OPP_EL}] (opponent elixir) is production's PUBLIC estimate on both sides (S3b-3c: CfOppElixir), "
              "compared like every index; no engine truth is read or logged. sc@nospell_opp = sc on the rows whose "
              "opponent deck has no spell card; _opp_plays / _opp_spawns = PublicObserver's play / spawn tallies."))
    out["acceptance"]["cue_identical"] = keys.get("cue", {}).get("status") == "IDENTICAL"     # S3b-3f
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("seat_rows", "tick_mismatch", "diag", "opp_counter_edges", "acceptance",
                                          "status_by_key")}, default=str))


if __name__ == "__main__":
    main()

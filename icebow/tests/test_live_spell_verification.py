"""Live spell-impact verification + the threat-gate memory fix (2026-08-19, user reports).

THE BUG SET, as reported and confirmed:
1. "the live training results never displays spell_waste even when the model misses every single
   spell" -- true by construction: env.py's own note says the spell-impact frame sampler was
   RETIRED, so live spells were scored at cast by aim geometry (_wincon_exec_live) and a rocket
   into empty grass paid like a hit. `spell_waste` existed only in the sim.
2. No pricing for a tornado that pulls enemies into a BETTER position for them.
3. "the advisor suggests HOLD despite the enemy making several plays" -- the _needs_answer gate
   read only d.team == "enemy" from the LATEST detector pass, so (a) a threat that blinked out on
   the decision tick (the detector misses units in ~31% of passes) made the board read quiet: the
   model FORGOT an enemy it had seen; the tracker's bridged tracks now feed the gate too.

The evaluators are pure functions in reward.py (testable without a live window); the queue and
gate wiring are exercised through minimal stand-ins shaped like the live objects.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.reward import nado_regressed, spell_whiffed          # noqa: E402
from clashrl.replay_mine import Detection, TeamTracker            # noqa: E402


class SpellWhiffTests(unittest.TestCase):
    def test_empty_blast_is_a_whiff(self):
        self.assertTrue(spell_whiffed(0.5, 0.3, 3.0, []))

    def test_an_enemy_inside_the_blast_is_not(self):
        self.assertFalse(spell_whiffed(0.5, 0.3, 3.0, [(0.55, 0.33, 0, 0)]))

    def test_a_live_tower_aim_is_exempt(self):
        """Rocket/EQ chip on a standing tower is a legitimate cast, never a whiff."""
        self.assertFalse(spell_whiffed(0.25, 0.21, 3.0, [],
                                       tower_anchors=[(0.25, 0.21)], tower_alive=[True]))

    def test_a_dead_tower_is_no_exemption(self):
        """Rocketing rubble is exactly the waste this term exists to price."""
        self.assertTrue(spell_whiffed(0.25, 0.21, 3.0, [],
                                      tower_anchors=[(0.25, 0.21)], tower_alive=[False]))

    def test_the_tracker_bridges_a_detector_blink(self):
        """The whole reason tracks (not raw detections) feed the verdict: a unit the detector
        missed THIS pass is still in the tracker's memory, so the landed spell is not billed."""
        tr = TeamTracker(own_cards=["x_bow"])
        d0 = Detection("knight", 0.50, 0.60, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], 0.0)
        d1 = Detection("knight", 0.50, 0.66, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], 0.5)                                  # marching down -> enemy
        tr.tag([], 1.0)                                    # the detector BLINKS: empty pass
        tracks = tr.enemy_tracks(1.2)
        self.assertTrue(tracks, "the tracker forgot the enemy after one missed pass")
        self.assertFalse(spell_whiffed(0.50, 0.66, 3.0, tracks),
                         "a spell landing on a remembered enemy was billed as a whiff")


class NadoRegressionTests(unittest.TestCase):
    MY = [(0.25, 0.80), (0.72, 0.80)]

    def test_pulled_closer_and_alive_is_bad(self):
        self.assertTrue(nado_regressed([(0.5, 0.55)], [(0.5, 0.62, 0, 0)], self.MY))

    def test_pulled_units_that_died_are_not_billed(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [], self.MY))

    def test_pulled_away_from_us_is_fine(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [(0.5, 0.50, 0, 0)], self.MY))

    def test_sub_tile_drift_is_free(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [(0.5, 0.559, 0, 0)], self.MY))


class SimNadoBadTests(unittest.TestCase):
    """The engine-truth twin, through the real _nado_watch machinery."""

    @classmethod
    def setUpClass(cls):
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        cls.env = SimMatchEnv(Config.load(), seed=5)

    def _run_watch(self, survivor_moves_to):
        from clashrl.sim.engine import Unit, build_spec
        env = self.env
        env.reset()
        e = env.eng
        e.units.clear()
        sp = build_spec(e.db, "knight", 11)
        u = Unit(spec=sp, team=1, x=0.50, y=0.55, hp=sp.hp * 50)
        u.deploy_left = 0.0
        e.units.append(u)
        env._nado_watch = [{"t0": e.t, "cx": 0.50, "cy": 0.55, "pulled": [u],
                            "pulled_at": [(u.x, u.y)], "targeters": [],
                            "king_was_asleep": False, "early_done": True}]
        e.t += 4.0                                      # expire the watch
        u.x, u.y = survivor_moves_to
        before = dict(getattr(env.rw_stats, "run", {}) or {})
        credit = env._nado_shaping()
        return credit

    def test_a_survivor_dragged_toward_our_tower_is_billed(self):
        credit = self._run_watch((0.50, 0.66))          # ~3.5 tiles closer to our towers
        self.assertLess(credit, 0.0, "the bad pull was not billed")

    def test_a_survivor_left_farther_away_is_not(self):
        credit = self._run_watch((0.50, 0.47))
        self.assertGreaterEqual(credit, 0.0)


class ThreatGateMemoryTests(unittest.TestCase):
    """The HOLD bug: the gate must triage the tracker's remembered enemies, not just the pass."""

    def _gate(self, dets, tracker):
        """Replicates train_rl._needs_answer's structure against stand-ins (it is a closure)."""
        import time as _t
        from clashrl import threat_value
        from clashrl.cards import CardDB
        from clashrl.config import Config
        db = CardDB(Config.load())
        seen, bases = [], []
        for d in dets:
            if d.team == "enemy" and float(getattr(d, "gy", 0.0)) >= 0.42:
                bases.append(str(d.base))
                seen.append((float(d.cx), float(getattr(d, "gy", 0.0)), str(d.base)))
        for tr in tracker.enemy_tracks(_t.time(), with_base=True):
            x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
            if y < 0.42 or not b:
                continue
            if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen):
                continue
            bases.append(b)
            seen.append((x, y, b))
        if not bases:
            return False
        return threat_value.group_ignore_frac(db, bases, tower_level=15) >= threat_value.IGNORE_FRAC

    def _tracker_with_marching_enemy(self, base="pekka"):
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["x_bow", "tesla", "knight"])
        d0 = Detection(base, 0.50, 0.55, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection(base, 0.50, 0.62, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)                         # marching down -> enemy
        return tr

    def test_a_blinked_out_threat_still_needs_an_answer(self):
        """The reported failure: enemy seen, detector blinks on the decision tick, gate said
        quiet, advisor said HOLD. The tracker's memory now keeps the gate honest."""
        import time as _t
        tr = self._tracker_with_marching_enemy()
        tr.tag([], _t.time())                            # the decision-tick blink: empty pass
        self.assertTrue(self._gate([], tr),
                        "an empty detector pass made a remembered P.E.K.K.A read as a quiet board")

    def test_a_genuinely_quiet_board_still_reads_quiet(self):
        tr = TeamTracker(own_cards=["x_bow"])
        self.assertFalse(self._gate([], tr))

    def test_no_double_count_when_both_see_the_same_unit(self):
        """A unit present in BOTH the pass and the memory is one threat, not two: a lone
        skeletons group must stay ignorable even counted through both paths."""
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["x_bow"])
        d0 = Detection("skeletons", 0.50, 0.55, 0.04, 0.04, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection("skeletons", 0.50, 0.60, 0.04, 0.04, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)
        live = Detection("skeletons", 0.50, 0.60, 0.04, 0.04, 0.9, "enemy", None, None, None)
        self.assertFalse(self._gate([live], tr),
                         "one skeletons group was double-counted into a real threat")


class AdvisorSituationMemoryTests(unittest.TestCase):
    """The other half of the HOLD report: the gate remembering is not enough if the ADVISOR's
    situation string still describes one detector pass -- the LLM was literally told "nothing on
    the board" while a remembered enemy marched. Replicates _situation's memory-append block
    (it is a closure in train_rl, like _needs_answer above)."""

    class _Warp:
        def frame_to_board(self, x, y):
            return x, y                                  # identity: frame coords ARE board coords

    def _remembered_groups(self, dets, tracker):
        import time as _t
        seen_xy = [(float(d.cx), float(d.gy), str(d.base)) for d in dets if d.team == "enemy"]
        groups = {}
        w = self._Warp()
        for tr in tracker.enemy_tracks(_t.time(), with_base=True):
            x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
            if not b:
                continue
            if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen_xy):
                continue
            seen_xy.append((x, y, b))
            bx, by = w.frame_to_board(x, y)
            where = ("deep in your half" if by > 0.66 else
                     "in your half" if by > 0.52 else
                     "at the bridge" if by > 0.44 else "on their side")
            lane = "left" if bx < 0.42 else "right" if bx > 0.58 else "centre"
            groups[(b.replace("_", " "), where + ", briefly out of sight", lane)] = 1
        return groups

    def _marching(self, base="knight"):
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["x_bow", "tesla"])
        d0 = Detection(base, 0.50, 0.55, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection(base, 0.50, 0.62, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)
        return tr

    def test_a_blinked_enemy_is_still_described_to_the_advisor(self):
        import time as _t
        tr = self._marching()
        tr.tag([], _t.time())                            # the advisor-tick blink
        groups = self._remembered_groups([], tr)
        self.assertTrue(any(n == "knight" and "briefly out of sight" in wh
                            for (n, wh, _l) in groups),
                        "the advisor was told nothing about a remembered marching knight")

    def test_a_unit_the_pass_already_reports_is_not_repeated_from_memory(self):
        tr = self._marching()
        live = Detection("knight", 0.50, 0.62, 0.05, 0.05, 0.9, "enemy", None, None, None)
        self.assertEqual({}, self._remembered_groups([live], tr),
                         "the same knight was described twice (once live, once from memory)")

class LiveEnvInitLintTests(unittest.TestCase):
    """STATIC guard on live env.py, added after it cost a match mid-training (2026-08-19).

    `self.w_spell_waste_live = ("spell_waste", -0.3)` shipped: the config-reader call had lost its
    function name in patching, so the weight was a TUPLE and the first genuine whiff crashed
    train-rl at `float(value)` -- after the detection had worked perfectly. hogeq had the same line
    reading `r(...)`, a name that does not exist in live env.py at all (its reader is `rw`), which
    would have raised NameError the moment a live env was built.

    Neither was caught because NO test constructs the live MatchEnv -- it needs a window and a
    detector, so every existing test uses SimMatchEnv. This lints the source instead: reward
    weights must be scalars, and no function may call a bare name that is not bound anywhere in
    its own scope, the module, or builtins.
    """

    @classmethod
    def setUpClass(cls):
        import ast
        cls.ast = ast
        cls.path = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "env.py")
        with io.open(cls.path, encoding="utf-8") as fh:
            cls.tree = ast.parse(fh.read())

    def _bound_in(self, fn):
        """Every name bound inside a function: args, assignments, loops, with/except, imports."""
        ast = self.ast
        names = {}

        def note(name, lineno):
            if name and (name not in names or lineno < names[name]):
                names[name] = lineno

        a = fn.args
        for arg in list(a.args) + list(a.posonlyargs) + list(a.kwonlyargs):
            note(arg.arg, fn.lineno)
        for extra in (a.vararg, a.kwarg):
            if extra:
                note(extra.arg, fn.lineno)
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                note(node.id, node.lineno)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for al in node.names:
                    note(al.asname or al.name.split(".")[0], node.lineno)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                note(node.name, node.lineno)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node is not fn:
                    note(node.name, node.lineno)
        return names

    def _module_names(self):
        """MODULE scope only -- deliberately NOT ast.walk. Walking descends into function bodies,
        so a local variable in one method (env.py binds a bare `r` inside _wheels_spell_aim) would
        count as globally visible and mask exactly the NameError this checks for; verified by
        re-injecting the shipped bug. Module-level if/try/with ARE descended (the tolerant
        `try: from .reward import nado_king_cell` block lives in one)."""
        ast = self.ast
        out = set()

        def scan(body):
            for node in body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for al in node.names:
                        out.add(al.asname or al.name.split(".")[0])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.add(node.name)                     # the name, never the body
                elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for t in tgts:
                        for n in ast.walk(t):
                            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                                out.add(n.id)
                elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                    for attr in ("body", "orelse", "finalbody", "handlers"):
                        for sub in getattr(node, attr, []) or []:
                            scan(sub.body if isinstance(sub, ast.ExceptHandler) else [sub])
        scan(self.tree.body)
        return out

    def _functions(self):
        ast = self.ast
        return [n for n in ast.walk(self.tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def test_every_reward_weight_is_a_scalar_not_a_container(self):
        ast = self.ast
        bad = []
        for fn in self._functions():
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign):
                    continue
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self" and tgt.attr.startswith("w_")
                            and isinstance(node.value, (ast.Tuple, ast.List, ast.Dict, ast.Set))):
                        bad.append("line %d: self.%s = %s"
                                   % (node.lineno, tgt.attr, type(node.value).__name__))
        self.assertEqual([], bad,
                         "reward weight(s) assigned a container -- rw_stats.add() does float(value) "
                         "and dies on the first fire: " + "; ".join(bad))

    def test_no_function_calls_a_name_that_is_never_bound(self):
        """The hogeq half: `r(...)` where the reader is named `rw`. Only bare-name calls are
        checked (self.x() / mod.x() resolve at runtime), against local + module + builtin scope."""
        import builtins
        ast = self.ast
        mod = self._module_names() | set(dir(builtins))
        bad = []
        for fn in self._functions():
            local = self._bound_in(fn)
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    n = node.func.id
                    if n in mod:
                        continue
                    if n in local and local[n] <= node.lineno:
                        continue
                    if n in local:
                        where = "bound at line %d but USED at line %d" % (local[n], node.lineno)
                    else:
                        where = "never bound"
                    bad.append("%s() in %s(): %s" % (n, fn.name, where))
        self.assertEqual([], bad,
                         "call(s) to unbound or late-bound name(s) -- NameError the moment the "
                         "live env runs: " + "; ".join(bad))

    def test_reset_clears_the_pending_spell_queue(self):
        """Cross-match leak: a spell cast in the closing seconds comes due during the NEXT match,
        whose opening board is empty by definition -- a phantom whiff billed to a match that never
        cast it. reset() must drop the queue."""
        ast = self.ast
        resets = [fn for fn in self._functions() if fn.name == "reset"]
        self.assertTrue(resets, "live env.py has no reset()")
        cleared = False
        for fn in resets:
            for node in ast.walk(fn):
                if (isinstance(node, ast.Attribute) and node.attr in ("clear", "_pending_spells")
                        and "_pending_spells" in ast.dump(fn)):
                    cleared = True
        self.assertTrue(cleared,
                        "reset() never touches _pending_spells -- last match's casts bill the next")

    def test_the_spell_verification_weights_read_through_the_config(self):
        """Both weights must come from a reader call, so config/config.yaml actually controls them."""
        ast = self.ast
        found = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                            and tgt.attr in ("w_spell_waste_live", "w_nado_bad")):
                        found[tgt.attr] = node.value
        self.assertEqual({"w_spell_waste_live", "w_nado_bad"}, set(found),
                         "the live spell-verification weights vanished from env.py")
        for attr, val in found.items():
            self.assertIsInstance(val, ast.Call,
                                  "self.%s is not read through a config reader" % attr)


if __name__ == "__main__":
    unittest.main(verbosity=1)

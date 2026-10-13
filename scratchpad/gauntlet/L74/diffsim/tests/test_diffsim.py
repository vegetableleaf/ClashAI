from copy import deepcopy
import json
from pathlib import Path
import random
import sys
from contextlib import contextmanager
import uuid
from types import SimpleNamespace
import unittest

from scratchpad.gauntlet.L74.diffsim.adapters import FakeEngine, ForkEngine, NativeEngine
from scratchpad.gauntlet.L74.diffsim.analysis import attribute, metrics, minimize, proportion, save_history, signature
from scratchpad.gauntlet.L74.diffsim.core import Aligner, Unsupported, compare_traces, differences, validate
from scratchpad.gauntlet.L74.diffsim.generators import (catalog, chosen_cards, deck, LegalPolicy, play,
                                                      random_scenario, scenario, unit_suites)
from scratchpad.gauntlet.L74.diffsim.runner import execute, paired, projection, Worker

HERE = Path(__file__).resolve().parents[1]
TEMP = HERE / "test-output"
TEMP.mkdir(exist_ok=True)


@contextmanager
def artifacts():
    # Default ACL inheritance avoids Python 3.13 mode-0700 on managed Windows.
    path = TEMP / uuid.uuid4().hex
    path.mkdir()
    yield path


def case():
    s = scenario(41, "skirmish", "planted", [deck(["Knight", "Noise"]), deck(["Archers", "Noise"])], 40)
    s["plays"] = [play(1, 0, "Noise"), play(3, 0, "Knight"), play(5, 1, "Archers"), play(20, 1, "Noise")]
    return s


def capture(s, bug=False):
    frames = []
    result = execute(FakeEngine(bug=bug), s, frames.append)
    return frames, result


class ComparatorTests(unittest.TestCase):
    def test_exact_and_first_field(self):
        left, _ = capture(case())
        self.assertIsNone(compare_traces(left, deepcopy(left)))
        right = deepcopy(left)
        right[6]["units"][1]["hp"] -= 1
        right[7]["units"][1]["x"] += 1
        d = compare_traces(left, right)
        self.assertEqual((d.tick, d.seconds if hasattr(d, "seconds") else d.json()["seconds"]), (6, .3))
        self.assertTrue(d.field.endswith(".hp"))
        self.assertEqual(d.cards, ("Archers", "Knight"))

    def test_id_and_list_permutation_and_targets(self):
        left, _ = capture(case())
        right = deepcopy(left)
        for frame in right:
            for e in frame["units"]:
                e["id"] += 5000000
                e["spawn_order"] += 900
                if e["target"] is not None:
                    e["target"] += 5000000
            frame["units"].reverse()
        self.assertIsNone(compare_traces(left, right))

    def test_death_does_not_renumber(self):
        align = Aligner()
        frames, _ = capture(case())
        initial = align.state(frames[21])
        later = deepcopy(frames[22])
        later["units"] = [u for u in later["units"] if u["id"] != 0]
        for u in later["units"]:
            u["target"] = None
        after = align.state(later)
        self.assertIn("1:Noise:0", initial["units"])
        self.assertIn("1:Noise:0", after["units"])
        self.assertIn("0:Knight:0", after["units"])

    def test_same_card_respawn_keeps_ordinal(self):
        frames, _ = capture(case())
        a = Aligner()
        a.state(frames[2])
        state = deepcopy(frames[2])
        state["units"][0]["id"] = 50
        state["units"][0]["spawn_order"] = 50
        self.assertIn("0:Noise:1", a.state(state)["units"])

    def test_missing_tick_rejected(self):
        left, _ = capture(case())
        broken = left[:3] + left[4:]
        with self.assertRaisesRegex(ValueError, "every tick"):
            compare_traces(broken, broken)

    def test_missing_tail_and_spawn(self):
        left, _ = capture(case())
        self.assertEqual(compare_traces(left, left[:-1]).field, "trace.length")
        right = deepcopy(left)
        right[2]["units"].clear()
        self.assertEqual(compare_traces(left, right).event_type, "spawn_or_despawn")

    def test_tolerance_exact_default_and_nonfinite(self):
        left, _ = capture(case())
        right = deepcopy(left)
        right[1]["units"][0]["x"] += 2
        self.assertIsNotNone(compare_traces(left, right))
        self.assertIsNone(compare_traces(left, right, {"units.*.x": 2}))
        self.assertIsNotNone(compare_traces(left, right, {"units.*.x": 1}))
        self.assertTrue(list(differences(float("nan"), float("nan"))))
        self.assertTrue(list(differences(True, 1)))
        self.assertTrue(list(differences(-0.0, 0.0)))
        self.assertTrue(list(differences(1, 1.0)))

    def test_unknown_target_and_duplicate_id_fail(self):
        frames, _ = capture(case())
        bad = deepcopy(frames[2])
        bad["units"][0]["target"] = 99999
        with self.assertRaisesRegex(ValueError, "unresolved"):
            Aligner().state(bad)
        bad["units"].append(deepcopy(bad["units"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            Aligner().state(bad)

    def test_elixir_clock_shield_status_tower_result(self):
        base, _ = capture(case())
        changes = [("elixir", [1, 2]), ("clock", {"tick_ms": 51}),
                   ("result", {"terminal": False, "winner": None, "crowns": [1, 0]})]
        for field, value in changes:
            right = deepcopy(base)
            right[8][field] = value
            self.assertEqual(compare_traces(base, right).tick, 8)
        for field, value in (("shield", 5), ("status", {"buffs": [["Freeze", 900]]})):
            right = deepcopy(base)
            right[8]["units"][0][field] = value
            self.assertEqual(compare_traces(base, right).tick, 8)
        towers = deepcopy(base)
        for f in towers:
            f["towers"] = [dict(id=100, spawn_order=-1, side=0, card="tower-0", form=0,
                                 x=0, y=0, hp=100, shield=0, target=None, status={"buffs": []})]
        right = deepcopy(towers)
        right[3]["towers"][0]["hp"] -= 1
        self.assertTrue(compare_traces(towers, right).field.startswith("towers."))


class MinimizerTests(unittest.TestCase):
    def test_shrinks_to_planted_interaction_and_replays(self):
        s = case()
        original = compare_traces(capture(s)[0], capture(s, True)[0])
        def predicate(trial):
            d = compare_traces(capture(trial)[0], capture(trial, True)[0])
            return d is not None and signature(d) == signature(original)
        minimal, info = minimize(s, predicate)
        self.assertEqual([p["card"] for p in minimal["plays"]], ["Knight", "Archers"])
        self.assertEqual(minimal["duration_ticks"], 6)
        self.assertEqual(s, case())
        self.assertTrue(predicate(json.loads(json.dumps(minimal))))
        for i in range(2):
            trial = deepcopy(minimal)
            del trial["plays"][i]
            self.assertFalse(predicate(trial))
        self.assertGreater(info["predicate_calls"], 1)

    def test_removes_initial_units_and_no_bug_is_refused(self):
        s = case()
        s["plays"] = []
        s["units"] = [dict(side=0, card="Noise", hp=100), dict(side=0, card="Knight", hp=100),
                      dict(side=1, card="Archers", hp=100)]
        def predicate(trial):
            return compare_traces(capture(trial)[0], capture(trial, True)[0]) is not None
        minimal, _ = minimize(s, predicate)
        self.assertEqual([u["card"] for u in minimal["units"]], ["Knight", "Archers"])
        self.assertEqual(minimal["duration_ticks"], 1)
        with self.assertRaises(ValueError):
            minimize(case(), lambda s: False)
        s["policy"] = {"seed": 1}
        with self.assertRaises(ValueError):
            minimize(s, lambda s: True)


class GeneratorTests(unittest.TestCase):
    def test_determinism_all_suites_and_ranges(self):
        cards, _ = catalog()
        names = ["Knight", "Archer", "Fireball", "Tesla", "Skeletons", "Goblins", "Giant", "Musketeer"]
        first = list(unit_suites(1, names, cards))
        random.seed(234)
        self.assertEqual(first, list(unit_suites(1, names, cards)))
        self.assertEqual(sum(s["suite"] == "duel" for s in first), len(names)**2)
        self.assertEqual({s["suite"] for s in first}, {"single", "duel", "spell_group", "building", "forms"})
        for s in first:
            validate(s)
        for seed in range(10):
            s = random_scenario(seed, cards, names)
            self.assertEqual(s, random_scenario(seed, cards, names))
            self.assertTrue(200 <= s["duration_ticks"] <= 600)
            self.assertTrue(all(len(d) == 8 for d in s["decks"]))
            validate(s)
        self.assertNotEqual(random_scenario(1, cards, names), random_scenario(2, cards, names))
        self.assertEqual(random_scenario(1, cards, names, full=True)["duration_ticks"], 7200)

    def test_census_ranking_and_missing_mapping(self):
        cards, _ = catalog()
        with artifacts() as t:
            p = Path(t)/"census.json"
            p.write_text(json.dumps({"card_usage": [{"card": "Giant", "n": 2}, {"card": "Archers", "n": 9}]}))
            names = chosen_cards(cards, census=p, top=1)
            self.assertIn("Archer", names)
            self.assertNotIn("Giant", names)
            with self.assertRaises(ValueError):
                chosen_cards(cards, census=p, top=60)
        with self.assertRaisesRegex(ValueError, "unmapped"):
            chosen_cards(cards, names=["made-up"])

    def test_legal_policy_freezes_and_replays_identically(self):
        s = scenario(1, "skirmish", "policy", duration=600)
        s["fake_terminal_tick"] = 1000
        s["policy"] = dict(seed=5, interval=10, ability=False)
        frames, result = capture(s)
        self.assertTrue(result["scenario"]["plays"])
        self.assertNotIn("policy", result["scenario"])
        replay, replay_result = capture(result["scenario"])
        self.assertIsNone(compare_traces(frames, replay))
        self.assertEqual(replay_result["fixed_rejections"], 0)
        self.assertEqual(frames, capture(s)[0])
        self.assertTrue(all(min(f["elixir"]) >= 0 for f in frames))

    def test_validation_rejects_duplicate_same_side_tick(self):
        s = case()
        s["plays"].insert(1, deepcopy(s["plays"][0]))
        with self.assertRaisesRegex(ValueError, "at most one"):
            validate(s)


class ReportTests(unittest.TestCase):
    def test_attribution_stable_and_ranked(self):
        d = compare_traces(capture(case())[0], capture(case(), True)[0]).json()
        changed = deepcopy(d)
        changed["field"] = changed["field"].replace(":0", ":17")
        other = deepcopy(d)
        other["field"] = "elixir[0]"
        grouped = attribute([dict(id="b", divergence=d), dict(id="a", divergence=changed), dict(id="c", divergence=other)])
        self.assertEqual([r["frequency"] for r in grouped], [2, 1])
        self.assertEqual(grouped[0]["repros"], ["a", "b"])

    def test_metrics_denominators_completion_and_history(self):
        rows = [dict(suite="full", exact=True, completed=True, result_match=True, status="ok"),
                dict(suite="full", exact=False, completed=False, result_match=False, status="error"),
                dict(suite="skirmish", exact=True, status="ok")]
        report = metrics(rows, {"oracle": "wheel"})
        self.assertEqual(report["full_match_trace_exact"]["percent"], 50)
        self.assertEqual(report["full_match_result_match"]["total"], 2)
        self.assertFalse(report["owner_goal_proven"])
        self.assertFalse(report["all_sanity_exact"])
        self.assertEqual(report["short_horizon_exact"]["percent"], 100)
        with artifacts() as t:
            a = save_history(Path(t), report)
            b = save_history(Path(t), report)
            self.assertNotEqual(a, b)
            self.assertEqual(json.loads(a.read_text()), report)

    def test_ci_boundaries_and_goal_never_certifies_mock(self):
        self.assertIsNone(proportion(0, 0)["percent"])
        self.assertAlmostEqual(proportion(0, 1000)["ci95_percent"][1], .3826758, places=5)
        self.assertLess(proportion(1000, 1000)["ci95_percent"][0], 100)
        rows = [dict(suite="full", exact=True, completed=True, result_match=True)]*1000
        self.assertFalse(metrics(rows, {"oracle": "wheel"})["observed_threshold_met"])
        self.assertTrue(metrics(rows, {"oracle": "native"})["observed_threshold_met"])
        self.assertFalse(metrics(rows, {"oracle": "native"})["owner_goal_proven"])


ENTITY_FIELDS = ["uid", "team", "kind", "card_id", "tower_slot", "x", "y", "hp", "max_hp", "radius",
                 "flying", "deploy_ticks", "stun_ticks", "knockback_ticks", "footprint", "target_uid", "attack_phase",
                 "facing", "shield", "buffs", "status_flags", "level", "mount_uid", "charge", "dest_x", "dest_y",
                 "ability_ticks", "unit_type"]


class MockBattle:
    def __init__(self, *args, **kwargs):
        self.tick = 0
        self.commands = []
        self.options = kwargs

    def catalogue_json(self):
        return json.dumps([["Knight", False], ["Archer", False]])

    def unit_types_json(self):
        return '["Knight"]'

    def provenance(self):
        return ["fixture", "clean"]

    def reset(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.tick = 0

    def check_deploy(self, *args):
        return 0

    def step(self, commands, ticks):
        self.commands.extend(commands)
        self.tick += ticks
        return [(0, 0, self.tick, c[2], c[3]) for c in commands]

    def state_json(self):
        e = [2, 0, 0, 0, -1, 9000*18, 10000*18, 100, 100, 1, False, 3, 2, 1,
             None, -1, 0, [0, 1], 10, [["Freeze", 100]], 16, 11, -1, 0, -1, -1, 4, 0]
        return json.dumps(dict(tick=self.tick, entities=[e], players=[dict(team=i, elixir_milli=5000,
                            hand=[0, 1, -1, -1], crowns=0) for i in (0, 1)], projectiles=[], spells=[],
                            game_over=False, winner=-1, tick_ms=50, regular_ticks=3600,
                            overtime_ticks=2400, overtime=False))


class AdapterTests(unittest.TestCase):
    def test_fork_public_contract_and_form_level_seed(self):
        module = SimpleNamespace(Battle=MockBattle, CATALOGUE_FIELDS=["name", "champion"],
                    ENTITY_FIELDS=ENTITY_FIELDS, PROJECTILE_FIELDS=[], HAND_SIZE=4, __version__="fixture")
        engine = ForkEngine(module)
        s = scenario(77, "single", "contract", [[dict(card="Knight", form=2, level=13)],
                                                   [dict(card="Archer", form=0, level=9)]])
        engine.reset(s)
        self.assertEqual(engine.battle.args[:4], (77, [[0], [1]], 0, 0))
        self.assertEqual(engine.battle.kwargs["forms"], [[2], [0]])
        self.assertEqual(engine.battle.kwargs["levels"], [[13], [9]])
        self.assertTrue(engine.can_deploy(0, "Knight", 2, 1, 2))
        self.assertFalse(engine.can_deploy(0, "Knight", 0, 1, 2))
        self.assertTrue(engine.deploy(0, "Knight", 2, 180, 360, 0)["accepted"])
        self.assertTrue(engine.ability(0, "Knight", 0)["accepted"])
        self.assertEqual(engine.battle.commands[-1], (0, 4, 0, 0))
        state = engine.state()
        self.assertEqual(state["units"][0]["status"]["deploy_ms"], 150)
        self.assertEqual(state["units"][0]["shield"], 10)
        self.assertEqual(state["elixir"], [50000, 50000])
        engine.step(2)
        self.assertEqual(engine.state()["tick"], 2)
        with self.assertRaises(ValueError):
            engine.deploy(0, "Knight", 2, 1, 2, 99)
        s["tower_troops"][0] = 42
        with self.assertRaises(Unsupported):
            engine.reset(s)

    def test_native_old_manifest_fails_before_connection(self):
        with self.assertRaisesRegex(Unsupported, "160402012"):
            NativeEngine()

    def test_native_mock_binding_replay_and_coordinates(self):
        class Env:
            def __init__(self):
                self.tick = 0
                self.closed = False
            def reset(self, replay, warmup_steps):
                self.replay = replay
                self.warmup = warmup_steps
            def observe(self):
                e = dict(id="ptr1", entity_id=5000001, creation_ordinal=1, side=0, card_id=26000000,
                         base_card_id=26000000, card_form="hero", target=None, x=9000, y=10000,
                         hp=100, max_hp=100, level=11, buffs=[dict(name="Freeze", remaining_ms=100, shield_hp=4)],
                         ability_available=True, ability_cooldown_remaining_ms=0, ability_pending_ms=0,
                         event_timer_ms=0, attack_progress_ms=0, attack_load_timer_ms=0)
                return dict(coherent=True, tick=self.tick, entities=[e], players=[dict(side=i, elixir_raw=50000) for i in (0, 1)],
                            episode=dict(terminated=False, winner=None, crowns=[0, 0]))
            def act(self, **kwargs):
                self.action = kwargs
                return {"accepted": True}
            probe = act
            def use_ability(self, **kwargs):
                self.ability = kwargs
                return {"accepted": True}
            def step(self, n):
                self.tick += n
            def close(self):
                self.closed = True
        with artifacts() as t:
            p = Path(t)/"mock-manifest.json"
            p.write_text(json.dumps({"runtime_version": "160402012", "kind": "TEST_FIXTURE_NOT_RUNTIME"}))
            env = Env()
            engine = NativeEngine(manifest=p, env=env)
            s = scenario(42, "single", "mock")
            s["decks"][0][0]["form"] = 2
            engine.reset(s)
            self.assertEqual(env.replay["rndSeed"], 42)
            self.assertEqual(env.replay["battle"]["deck0"]["sp"][0], {"d": 26000000, "l": 10, "el": 2})
            self.assertEqual(env.warmup, 0)
            engine.deploy(0, "Knight", 2, 9000*18, 10000*18, 0)
            self.assertEqual(env.action, dict(side=0, deck_index=0, x=9000, y=10000))
            engine.ability(0, "Knight", 0)
            self.assertEqual(env.ability["entity_id"], 5000001)
            state = engine.state()
            self.assertEqual(state["units"][0]["shield"], 4)
            self.assertEqual(state["units"][0]["x"], 9000*18)
            self.assertNotIn("extra", projection(state, "common"))
            engine.close()
            self.assertTrue(env.closed)
            with self.assertRaises(Unsupported):
                engine._xy(1, 2)


class WorkerTests(unittest.TestCase):
    def test_incomplete_full_match_and_unreached_play_never_pass(self):
        with artifacts() as t:
            a = Worker(sys.executable, "fake", Path(t)/"a")
            b = Worker(sys.executable, "fake", Path(t)/"b")
            try:
                s = case()
                s["suite"] = "full"
                row, _ = paired(a, b, s)
                self.assertFalse(row["exact"])
                self.assertFalse(row["result_match"])
                self.assertEqual(row["status"], "coverage_incomplete")
                s = case()
                s["duration_ticks"] = 100
                s["plays"].append(play(90, 0, "Noise"))
                row, _ = paired(a, b, s)
                self.assertEqual(row["coverage"]["oracle_unexecuted_plays"], 1)
                self.assertFalse(row["exact"])
            finally:
                a.close()
                b.close()

    def test_separate_processes_identical_and_planted(self):
        with artifacts() as t:
            a = Worker(sys.executable, "fake", Path(t)/"a")
            b = Worker(sys.executable, "fake", Path(t)/"b")
            c = Worker(sys.executable, "fake-bug", Path(t)/"c")
            try:
                row, frozen = paired(a, b, case())
                self.assertTrue(row["exact"])
                self.assertEqual(frozen, case())
                row, _ = paired(c, b, case())
                self.assertFalse(row["exact"])
                self.assertEqual(row["divergence"]["tick"], 6)
                full = case()
                full.update(suite="full", duration_ticks=100)
                row, _ = paired(c, b, full)
                self.assertTrue(row["completed"])
                self.assertFalse(row["result_match"])
            finally:
                for w in (a, b, c):
                    w.close()

    def test_cli_history_and_repro_roundtrip(self):
        from scratchpad.gauntlet.L74.diffsim.cli import main
        with artifacts() as t:
            base = Path(t)
            src = base/"input.json"
            src.write_text(json.dumps(case()))
            result = main(["--candidate", "fake-bug", "--oracle", "fake", "--repro", str(src),
                           "--out", str(base/"out"), "--history", str(base/"history"), "--minimize-limit", "1"])
            self.assertEqual(result, 1)
            minimal = json.loads((base/"out/repros/000000.json").read_text())
            self.assertEqual(len(minimal["plays"]), 2)
            self.assertEqual(minimal["duration_ticks"], 6)
            report = json.loads((base/"out/report.json").read_text())
            self.assertEqual(report["minimized_repros"], 1)
            self.assertEqual(len(list((base/"history").glob("*.json"))), 1)
            self.assertEqual(json.loads((base/"out/attribution.json").read_text())[0]["frequency"], 1)

    def test_cli_success_and_coverage_failure_keep_denominator(self):
        from scratchpad.gauntlet.L74.diffsim.cli import main
        with artifacts() as t:
            base = Path(t)
            src = base/"input.json"
            src.write_text(json.dumps(case()))
            args = ["--candidate", "fake", "--oracle", "fake", "--repro", str(src),
                    "--out", str(base/"out"), "--history", str(base/"history")]
            self.assertEqual(main(args), 0)
            report = json.loads((base/"out/report.json").read_text())
            self.assertEqual(report["suites"]["skirmish"]["successes"], 1)
            self.assertFalse(report["owner_goal_proven"])

    def test_full_native_diagnostics_survive_common_projection(self):
        full, common = [], []
        s = case()
        execute(FakeEngine(), s, common.append, "common", full.append)
        self.assertEqual(len(full), len(common))
        self.assertIsNone(compare_traces(common, full))


if __name__ == "__main__":
    unittest.main()

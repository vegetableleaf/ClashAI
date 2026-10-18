"""B6 stage B: live_play --iw-press head (ability_head_live.py). Two venvs, each class skips what it cannot import:
    research/ext/Royale/.venv/Scripts/python.exe -m unittest scratchpad/gauntlet/L74/ability_live/test_ability_live.py
        -> the SIM parity classes (royale_env: the live builder vs RoyalePoolEnv._ability_head_features on the SAME state)
    icebow/.venv/Scripts/python.exe -m unittest scratchpad/gauntlet/L74/ability_live/test_ability_live.py
        -> the live_play classes (fake match: head presses / holds, refusals, rule + never identical to PRE)
"""
from __future__ import annotations

import collections
import contextlib
import json
import queue
import random
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
LIVE = REPO / "scratchpad/gauntlet/L68/live_reader"
for p in (str(REPO), str(LIVE)):
    if p not in sys.path:
        sys.path.insert(0, p)
import ability_head_live as AL  # noqa: E402

try:
    from pipeline import royale_env as RE
    from royalegym.protocol import EMPTY_CARD, EntityKind
except ImportError:                       # icebow venv: no royalegym
    RE = None
try:
    import torch
    import live_play as lp
    from pipeline import rl_royale as RL
except ImportError:                       # Royale venv: no cv2
    lp = None
APK = REPO / "scratchpad/gauntlet/L74/apktables/out/parser/data/derived/cards-160402017-20261006.json"


class TestConstants(unittest.TestCase):
    def test_width_cards_scale_radius(self):
        self.assertEqual(AL.ABILITY_FEAT_N, 44)
        if RE is not None:
            self.assertEqual((AL.ABILITY_CARDS, AL.V2_SCALE, AL.ABILITY_FEAT_N),
                             (RE.ABILITY_CARDS, RE._V2_SCALE, RE.ABILITY_FEAT_N))
        if not APK.is_file():
            self.skipTest("card table not in this checkout")
        def max_radius(e):                                            # = royale_env._max_radius
            if isinstance(e, dict):
                return max([int(e.get("radius_milli") or 0)] + [max_radius(v) for v in e.values()])
            return max([0] + [max_radius(v) for v in e]) if isinstance(e, list) else 0
        radius = {}
        for f in json.loads(APK.read_text(encoding="utf-8"))["hero_forms"]:
            r = max_radius(f["ability"]["effect"])
            if r or f.get("range_milli") is not None:                 # royale_env._ability_radius, in tiles
                radius[f["form_of"]] = round((r or f["range_milli"] + 1500) / 1000, 3)
        radius.pop("Goblins")                                         # its button belongs to a flag building
        self.assertEqual(radius, AL.HERO_RADIUS)


# ------------------------------------------------------------------------------------------- SIM parity
def reader_body(e):
    """A RoyaleSim entity as the memory reader reports it: 1000 units per tile, crown towers card_id -1 + kind 12/13,
    buildings kind 13, troops kind 15 (a card-less body: card_id -1, kind 15, skipped by both builders)."""
    tower = e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)
    kind = 12 if e.kind == EntityKind.KING_TOWER else 13 if tower or e.kind == EntityKind.BUILDING else 15
    if e.card_id == EMPTY_CARD and not tower:
        kind = 15
    return dict(side=e.team, x=e.x / RE.SCALE, y=e.y / RE.SCALE, card_id=-1 if tower or e.card_id == EMPTY_CARD
                else e.card_id, hp=e.hp, max_hp=e.max_hp, kind=kind)


def sim_stand_in(tick, names, body_elixir, radius):
    """What RoyalePoolEnv._ability_head_features reads of the env (v2 policy, no engine)."""
    env = SimpleNamespace(tick=tick, names=names, ids={v: k for k, v in names.items()}, ability_policy="v2",
                          _body_elixir=body_elixir, _hero_radius=radius, _ability_uid={}, _last_play={}, _units=None)
    for m in ("_v2_info", "_ability_features", "_ability_radius"):
        setattr(env, m, types.MethodType(getattr(RE.RoyalePoolEnv, m), env))
    return env


@unittest.skipIf(RE is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestSimParity(unittest.TestCase):
    def test_random_boards_match_the_sim_builder(self):
        """400 random boards (both sides, every phase, towers down, units / buildings / card-less bodies at all
        distances, HP at level 11): the live builder == RoyalePoolEnv._ability_head_features, all 44 values."""
        names = {1: "IceWizard", 2: "Knight", 3: "Cannon", 4: "Skeletons", 5: "Valkyrie", 6: "Golem"}
        value = {1: 3., 2: 3., 3: 3., 4: 1 / 3, 5: 4., 6: 8.}
        S = RE.SCALE * 1000
        rng = random.Random(7)
        for k in range(400):
            side, tick, cid = k % 2, rng.randrange(0, 6000), rng.choice((1, 5))
            towers = [(s, kd, x, y) for s, ys in ((0, (3, 6.5)), (1, (29, 25.5)))
                      for kd, x, y in ((EntityKind.KING_TOWER, 9, ys[0]), (EntityKind.PRINCESS_TOWER, 3.5, ys[1]),
                                       (EntityKind.PRINCESS_TOWER, 14.5, ys[1]))]
            mhp = {EntityKind.KING_TOWER: 4824, EntityKind.PRINCESS_TOWER: 3052}      # level 11 (factor 1)
            ents = [SimpleNamespace(uid=i, team=s, kind=kd, card_id=EMPTY_CARD, x=round(x * S), y=round(y * S),
                                    hp=0 if rng.random() < .15 else mhp[kd], max_hp=mhp[kd], status_flags=0)
                    for i, (s, kd, x, y) in enumerate(towers)]
            hero = SimpleNamespace(uid=99, team=side, kind=EntityKind.TROOP, card_id=cid, x=rng.randrange(0, 18 * S),
                                   y=rng.randrange(0, 32 * S), hp=rng.randrange(1, 900), max_hp=900, status_flags=16)
            ents.append(hero)
            for i in range(rng.randrange(0, 14)):
                kd = rng.choice((EntityKind.TROOP, EntityKind.TROOP, EntityKind.BUILDING))
                ents.append(SimpleNamespace(uid=100 + i, team=rng.randrange(2), kind=kd,
                                            card_id=rng.choice((2, 3, 4, 6, EMPTY_CARD)),
                                            x=hero.x + rng.randrange(-8 * S, 8 * S), y=hero.y + rng.randrange(-8 * S, 8 * S),
                                            hp=rng.choice((0, rng.randrange(1, 4000))), max_hp=4000, status_flags=0))
            players = [SimpleNamespace(elixir_milli=rng.randrange(2000, 10001), crowns=0) for _ in (0, 1)]
            st = SimpleNamespace(entities=ents, players=players)
            for s in (0, 1):                                   # the engine's count: a king = 3, else princesses down
                down = [e.kind for e in ents[:6] if e.team == 1 - s and e.hp <= 0]
                players[s].crowns = 3 if EntityKind.KING_TOWER in down else len(down)
            rd = [reader_body(e) for e in ents]
            env = sim_stand_in(tick, names, value, {1: 2500 * RE.SCALE, 5: 5500 * RE.SCALE})
            dep = tick - rng.randrange(0, 1200)
            env._last_play[(side, cid)] = dep
            sim = RE.RoyalePoolEnv._ability_head_features(env, side, 0, cid, hero, st)
            live = AL.head_features(rd, side, tick, players[side].elixir_milli / 1000, reader_body(hero), names[cid], dep,
                                    0, name_of=names.get, value_of=lambda n: value[env.ids[n]])
            self.assertEqual(len(sim), 44)
            for j, (a, b) in enumerate(zip(sim, live)):
                self.assertAlmostEqual(a, b, places=9, msg=f"board {k} feature {j}")

    def test_real_engine_hero_match(self):
        """Real RoyaleSim hero matches (Hero Valkyrie, v2, label mode, learner side 0 and 1): at EVERY learner decision
        with a pressable button, the live builder on the reader translation of the engine state == the SIM's option
        features. (The scripted lane keeps enemy troops > 10 tiles from the hero: features 4-7 / 14-15 are covered by
        the random boards above, not here.)"""
        for learner_side in (0, 1):
            self._real_match(learner_side)

    def _real_match(self, learner_side):
        from pipeline.tests import test_ability_head as T
        env, pairs = T._env(), []
        orig = env.ability_options

        def spy(side, rule=None):
            out = orig(side, rule)
            st = env.core.state()
            for o in out:
                _, cid, uid = o["cmd"]
                hero = next(e for e in st.entities if e.uid == uid)
                info = env._ability_uid[(side, uid)]
                live = AL.head_features([reader_body(e) for e in st.entities], side, int(env.tick),
                                        st.players[side].elixir_milli / 1000, reader_body(hero), env.names[cid],
                                        info["dep"], info["presses"], name_of=env.names.get,
                                        value_of=lambda n: env._body_elixir.get(env.ids.get(n), 0.))
                pairs.append((int(env.tick), o["feat"], live))
            return out
        env.ability_options = spy
        T._drive(env, T.VALK, T.VALK, delay=26, ability={"mode": "label"}, learner_side=learner_side)
        self.assertGreater(len(pairs), 3)
        for tick, sim, live in pairs:
            for j, (a, b) in enumerate(zip(sim, live)):
                self.assertAlmostEqual(a, b, places=6, msg=f"tick {tick} feature {j}")


# ------------------------------------------------------------------------------------------- live_play
IW, IW_FORM = 26000023, 203000023
BUTTON = (818, 1224)


def frame(tick, elixir=7.0):
    """My side 1 (my half y > 16000), Hero Ice Wizard played (not in hand), two enemy Knights 1 tile from it."""
    me = {"side": 1, "hand_deck_indices": [1, 2, 3, 4], "elixir_raw": int(elixir * 1e4), "next_deck_index": 5,
          "deck_card_ids": [IW] + [26000000] * 7, "deck_form_flags": [2] + [0] * 7}
    opp = dict(me, side=0, hand_deck_indices=[-1] * 4)
    t = lambda s, x, y, k, hp: dict(side=s, x=x, y=y, card_id=-1, hp=hp, max_hp=hp, kind=k, address=f"t{s}{x}")  # noqa: E731
    ents = [t(0, 9000, 3000, 12, 4824), t(0, 3500, 6500, 13, 3052), t(0, 14500, 6500, 13, 3052),
            t(1, 9000, 29000, 12, 4824), t(1, 3500, 25500, 13, 3052), t(1, 14500, 25500, 13, 3052),
            dict(side=1, x=9000, y=22000, card_id=IW_FORM, hp=600, max_hp=700, kind=15, address="iw"),
            dict(side=0, x=9000, y=21000, card_id=26000000, hp=1500, max_hp=1766, kind=15, address="k1"),
            dict(side=0, x=9500, y=21200, card_id=26000000, hp=1500, max_hp=1766, kind=15, address="k2")]
    return json.dumps({"battle_active": True, "coherent": True, "game_tick": tick, "sample_monotonic_us": tick * 50000,
                       "players": [me, opp], "entities": ents}) + "\n"


class FakePilot:
    gate_tau = 0.35

    def __init__(self, logit=None):
        from pipeline.decision_options import DecisionOptions
        self.decision_options, self.match_seed, self.feature_version = DecisionOptions(), 0, 4
        self.public = SimpleNamespace(own_events=[dict(card="ice-wizard", tick=100, side=1, accepted=True,
                                                       ability=False)])
        self.decided = []
        if logit is not None:                          # an AbilityHead on g width 4 that always says `logit`
            h = RL.AbilityHead(4)
            with torch.no_grad():
                h.net[2].bias.fill_(logit)
            self.ability = {"head": h.eval(), "mode": "greedy"}

    def observe(self, f):
        return None

    def decide(self, f):
        self.last_g = (int(f["game_tick"]), torch.zeros(1, 4))
        self.decided.append(int(f["game_tick"]))
        return {"play": False, "p_play": 0.0, "gate_tau": self.gate_tau, "public_audit": {}}

    def record_play(self, *a):
        pass

    def record_ability(self, *a, **k):
        pass


class SyncQ:
    """queue.Queue whose every frame is 'newest' (empty() True): the fake match is deterministic."""
    def __init__(self):
        self.items, self.cv = collections.deque(), threading.Condition()

    def put(self, x):
        with self.cv:
            self.items.append(x)
            self.cv.notify()

    def get(self, timeout=None):
        with self.cv:
            if not self.cv.wait_for(lambda: self.items, timeout):
                raise queue.Empty
            return self.items.popleft()

    def empty(self):
        return True

    def qsize(self):
        return 0


def fake_match(mod, tmp, pilot, rule=(True, "test rule"), **extra):
    """One fake match of module ``mod`` (live_play or PRE's) -> (adb shell commands, log events, should_press calls)."""
    cmds, calls = [], []
    stream = iter([frame(t) for t in range(150, 400, 2)])
    button = SimpleNamespace(want=False, blue=1.0, grey=0.0, point=BUTTON, ts=0.0, stop=lambda: None,
                             fresh_state=lambda: "ready")
    a = SimpleNamespace(tau=.35, leak=9.5, dry_run=False, ckpt="x", extrapolate=0, no_opp_counter=True, ckpt_source="t",
                        ckpt_sha256="t", public_audit=False, menu_guard=False, no_ability=False, reader="v2",
                        interval_ms=100, max_seconds=60, no_iw_pro_gate=False, **extra)
    with contextlib.ExitStack() as es:
        for name, value in (("HERE", Path(tmp)), ("adb", lambda *a, **k: cmds.append(a[-1]) or ""),
                            ("HeroButton", lambda *a, **k: button), ("READERS", {"v2": ("sampler", "")}),
                            ("should_press", lambda *a, **k: calls.append(1) or rule)):
            es.enter_context(mock.patch.object(mod, name, value))
        es.enter_context(mock.patch.object(mod.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
            stdout=stream, stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None)))
        es.enter_context(mock.patch.object(mod.time, "sleep", lambda s: None))
        es.enter_context(mock.patch("queue.Queue", SyncQ))
        mod.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
        mod.play_match(a, pilot, mod.Layout(900, 1600), "cpu", None, record=False)
    ev = [json.loads(x) for x in next(Path(tmp).glob("live_play_*.jsonl")).read_text().splitlines()]
    return cmds, ev, calls


TAP = f"input tap {BUTTON[0]} {BUTTON[1]}"


PRE = "8c70811"          # HEAD at dispatch: live_play before --iw-press head (the rule / never reference)
WALL = ("latency_s", "tap_ms", "recv_age_ms", "decide_ms", "sample_age_ms", "tap_end_ms", "seconds")


def head_module():
    """PRE's live_play.py as a module (the reference for 'rule / never unchanged')."""
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:scratchpad/gauntlet/L68/live_reader/live_play.py"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    if src.returncode:
        raise unittest.SkipTest(f"git show failed: {src.stderr.strip()}")
    mod = types.ModuleType("live_play_head")
    mod.__file__ = str(LIVE / "live_play.py")
    exec(compile(src.stdout, "live_play_head", "exec"), mod.__dict__)
    return mod


@unittest.skipIf(lp is None, "live_play not importable (run in icebow/.venv)")
class TestLivePlay(unittest.TestCase):
    def run_match(self, mod=None, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            return fake_match(mod or lp, tmp, **kw)

    def test_head_press_logs_taps_and_confirms_as_the_rule(self):
        pilot = FakePilot(logit=100.0)
        cmds, ev, calls = self.run_match(pilot=pilot, iw_press="head")
        ab = [e for e in ev if e["event"] == "ability"]
        self.assertTrue(ab and not calls)                            # the head pressed; should_press never ran
        self.assertEqual(cmds.count(TAP), len(ab))
        self.assertTrue(all(e["why"] == "head p=1.0000" and e["tap"] == list(BUTTON) and len(e["head_feat"]) == 44
                            for e in ab))
        self.assertTrue(all(e["tick"] in pilot.decided for e in ab))   # decided on that frame's model decision (its g)
        self.assertEqual(ev[0]["iw_press"], "head")
        un = [e["tick"] for e in ev if e["event"] == "ability_unconfirmed"]
        self.assertTrue(un and all(b - a > lp.CONFIRM_TICKS for a, b in zip([e["tick"] for e in ab], un)))
        f = ab[0]["head_feat"]                                       # the frame's board, as SIM builds it
        self.assertEqual(f[4] * 5, 2)                                # 2 Knights within 3 tiles of the hero
        self.assertAlmostEqual(f[0] * 30, (ab[0]["tick"] - 100) / 20, places=2)   # seconds since the deploy event
        self.assertEqual(f[18 + AL.ABILITY_CARDS.index("IceWizard")], 1.0)

    def test_head_hold_never_taps_and_logs_at_most_once_a_second(self):
        cmds, ev, calls = self.run_match(pilot=FakePilot(logit=-100.0), iw_press="head")
        held = [e["tick"] for e in ev if e["event"] == "ability_held"]
        self.assertEqual((cmds.count(TAP), calls), (0, []))
        self.assertFalse(any(e["event"] == "ability" for e in ev))
        self.assertTrue(held and all(b - a >= 20 for a, b in zip(held, held[1:])))
        self.assertTrue(all(e["why"] == "head p=0.0000" for e in ev if e["event"] == "ability_held"))

    def test_rule_and_never_are_identical_to_pre(self):
        head = head_module()
        for mode in ({}, {"iw_press": "rule"}, {"iw_press": "never"}):
            got = [self.run_match(mod=m, pilot=FakePilot(), **mode) for m in (lp, head)]
            (t1, e1, c1), (t2, e2, c2) = got
            strip = lambda ev: [{k: v for k, v in e.items() if k not in WALL} for e in ev]  # noqa: E731
            self.assertEqual((t1, strip(e1), c1), (t2, strip(e2), c2), mode)
            self.assertTrue(c1)                                       # the rule ran
            self.assertNotIn("iw_press", e1[0])

    def test_no_decision_without_a_hero_or_after_its_one_charge(self):
        """The SIM asks the head only while the engine would accept the press; live 'ready' reads lie (10-17 logs)."""
        f = json.loads(frame(300))
        pilot = FakePilot(logit=100.0)
        g = lambda: torch.zeros(1, 4)  # noqa: E731
        self.assertEqual(AL.decide_board(f, 1, {IW}, 7.0, lambda c, t: (100, 1), g, pilot.ability),
                         (False, "head spent", None))
        no_hero = dict(f, entities=[e for e in f["entities"] if e["card_id"] != IW_FORM])
        self.assertEqual(AL.decide_board(no_hero, 1, {IW}, 7.0, lambda c, t: (100, 0), g, pilot.ability),
                         (False, "head hero_unseen", None))
        self.assertEqual(AL.decide_board(f, 1, {IW}, 7.0, lambda c, t: (100, 0), g, pilot.ability)[:2],
                         (True, "head p=1.0000"))
        pilot.public.own_events.append(dict(card="IceWizard", tick=250, side=1, accepted=True, ability=True))
        self.assertEqual(AL.deploy_state(pilot, "IceWizard", 300), (100, 1))      # record_ability's catalogue name

    def test_refuses_a_checkpoint_without_a_head_or_of_another_width(self):
        pilot = SimpleNamespace(model=SimpleNamespace(value_head=torch.nn.Linear(8, 3)))
        with tempfile.TemporaryDirectory() as tmp:
            none, other = Path(tmp) / "none.pt", Path(tmp) / "w4.pt"
            torch.save({"rl": {}}, none)
            torch.save({"rl": {"ability_head": RL.AbilityHead(4).state_dict(),
                               "ability": {"d_g": 4, "hidden": 64, "n_feat": 44}}}, other)
            with self.assertRaisesRegex(SystemExit, "has none"):
                AL.load_head(none, "cpu", pilot)
            with self.assertRaisesRegex(SystemExit, "width 4"):
                AL.load_head(other, "cpu", pilot)
            pilot.model.value_head = torch.nn.Linear(4, 3)
            self.assertEqual(AL.load_head(other, "cpu", pilot)["mode"], "greedy")


if __name__ == "__main__":
    unittest.main()

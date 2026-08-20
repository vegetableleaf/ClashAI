"""DrillEnv: run one `Scenario` as a short episode, scored by the ORDINARY match reward.

Subclassing `SimMatchEnv` rather than writing a bespoke trainer is the whole design. A drill with
its own reward would produce a policy that is good at drills; reusing the match's terms means a
drill only CONCENTRATES EXPERIENCE on a state distribution the policy rarely reaches by itself --
it never changes what "good" means. That is what makes the skills transfer back into full play
instead of having to be un-learned.

WHAT THE DRILL CHANGES
  * reset() builds the scenario's board instead of a fresh match, and installs a scripted opponent
    that plays only the scenario's spawns.
  * the agent's hand is restricted to the cards the interaction needs (optional per scenario).
  * the episode ends the moment `success` or `failure` fires, or at `time_limit` -- so a rep costs
    seconds of simulated time rather than three minutes.
  * `info` reports the verdict, so a runner can measure pass RATE, which is the number that says
    whether a skill is actually mastered.

WHAT IT DELIBERATELY DOES NOT CHANGE
  * the reward terms, the observation, the action space, or the engine. A drill is the same game.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .engine import Unit, build_spec
from .env import SimMatchEnv
from . import scenarios as sc


def deploy_unit(eng, team: int, db, base: str, x: float, y: float, level: int = 11) -> bool:
    """Put a card on the board THROUGH THE ENGINE'S OWN DEPLOY PATH.

    Constructing `Unit(spec=...)` by hand looks equivalent and is not: `eng.deploy` is what knows
    about squad COUNTS, deploy timers and Evolution forms. Building the unit directly spawned a
    Skeleton Army as a single 81 HP skeleton, so every count-based card in a drill was quietly the
    wrong card. Elixir is topped up first -- a scripted spawn is scenery, and must never be refused
    for cost.
    """
    try:
        spec = build_spec(db, base, int(level))
    except Exception:  # noqa: BLE001 -- an unknown card is a bad scenario, not a dead run
        return False
    eng.elixir[team] = max(float(eng.elixir[team]), float(spec.elixir) + 1.0)
    ok = bool(eng.deploy(team, spec, float(x), float(y)))
    if ok:
        for u in eng.units:                            # scenarios start the interaction, not the wait
            if u.team == team and getattr(u, "deploy_left", 0.0) > 0.0:
                u.deploy_left = 0.0
    return ok


class _ScriptedOpponent:
    """Plays exactly the scenario's spawns, at their scripted times, and nothing else.

    A real opponent reacts, which is the point of full-match training and the enemy of a drill:
    if the opponent varies its answer, a failed rep tells you nothing about the skill you were
    rehearsing. Variation belongs in the scenario's declared `randomise` list, where it is
    controlled, not in the opponent's judgement.
    """

    def __init__(self, spawns, db, level: int = 11):
        self._todo = sorted(spawns, key=lambda s: s[4])
        self._db = db
        self._level = int(level)
        self.deck_keys = [s[0] for s in spawns]      # some reward paths ask what they hold
        self.placed = 0
        self.total = sum(1 for s in spawns if s[1] == 1)

    def act(self, eng) -> None:
        while self._todo and self._todo[0][4] <= eng.t:
            base, team, x, y, _t = self._todo.pop(0)
            if team != 1:
                continue                              # our side is placed at reset, not acted
            if deploy_unit(eng, 1, self._db, base, float(x), float(y), self._level):
                self.placed += 1


class DrillEnv(SimMatchEnv):
    """A SimMatchEnv pinned to one Scenario."""

    def __init__(self, cfg, scenario: sc.Scenario, seed: int = 0, level: int = 11):
        super().__init__(cfg, seed=seed)
        self.scenario = scenario
        self._level = int(level)
        self._drill: dict = {}
        self.last_verdict: Optional[str] = None

    # -- setup ---------------------------------------------------------------------------
    def _place_scenario(self) -> None:
        s = self.scenario
        rng = self.rng
        mirror = ("lane" in s.randomise) and bool(rng.random() < 0.5)
        jitter = float(rng.uniform(-0.6, 0.6)) if "timing" in s.randomise else 0.0
        spawns = []
        for base, team, x, y, t in s.spawns:
            if mirror:
                x = 1.0 - float(x)
            spawns.append((base, team, float(x), float(y), max(0.0, float(t) + jitter)))
        # our side is placed immediately; the opponent's are scripted
        for base, team, x, y, t in spawns:
            if team == 0:
                deploy_unit(self.eng, 0, self.eng.db, base, x, y, self._level)
        self.opponent = _ScriptedOpponent([sp for sp in spawns if sp[1] == 1],
                                          self.eng.db, self._level)
        elix = float(s.elixir)
        if "elixir" in s.randomise:
            elix = max(0.0, min(10.0, elix + float(rng.uniform(-2.0, 2.0))))
        self.eng.elixir[0] = elix
        self.eng.elixir[1] = 10.0                      # the script pays for its own spawns

    def _restrict_hand(self) -> None:
        """Deal only the cards the interaction needs.

        The point is not to make the drill easy -- it is that a rep must fail for the RIGHT
        reason. With the whole deck in hand, a missed king-activation could mean "did not know to
        Tornado" or merely "drew Skeletons", and the two are indistinguishable in the pass rate.
        """
        want = {str(b) for b in (self.scenario.hand or ())}
        if not want:
            return
        # `cycle` holds SLOT indices, not card ids -- _slot_card_id(slot) maps one to the other,
        # and a slot can present either its base card or its Evolution. Filling cycle with card
        # ids indexes slot_evo_id out of range, which is exactly what it did on the first run.
        wanted_slots = []
        for slot in range(self.n_slots):
            cid = self._slot_card_id(slot)
            key = str(self.deck_keys[cid]) if 0 <= cid < len(self.deck_keys) else ""
            if key in want or key.replace("_evo", "") in want:
                wanted_slots.append(slot)
        if wanted_slots:
            rest = [s for s in self.cycle if s not in wanted_slots]
            self.cycle = wanted_slots + rest

    def reset(self) -> np.ndarray:
        obs = super().reset()
        self.eng.units.clear()                         # a drill starts from ITS board, not a match
        self._place_scenario()
        self._restrict_hand()
        self._drill = {
            "t0": float(self.eng.t),
            "princess_hp0": sum(float(t.hp) for t in sc.our_princesses(self.eng)),
            "enemy_tower_hp0": sum(float(t.hp) for t in self.eng.towers[1][:2]),
            "spent": 0.0,
        }
        self.last_verdict = None
        return self._obs() if hasattr(self, "_obs") else obs

    # -- the episode ---------------------------------------------------------------------
    def _verdict(self) -> Optional[str]:
        s, eng, st = self.scenario, self.eng, self._drill
        # NOT ARMED YET -> no verdict. The scripted opponent places its spawns from inside step(),
        # so the board is empty on the first tick and a predicate like "no enemy is alive" is
        # trivially TRUE there. log_the_ground_swarm passed 15/15 that way, resolving before the
        # swarm existed -- measuring a race, not a skill.
        opp = getattr(self, "opponent", None)
        if getattr(opp, "total", 0) and getattr(opp, "placed", 0) < opp.total:
            return None
        if not st.get("armed"):
            if not any(u.team == 1 and u.hp > 0 for u in eng.units):
                return None
            st["armed"] = True
        # FAILURE IS CHECKED FIRST, deliberately: several drills can satisfy both at once (the
        # king wakes on the same tick the princess takes its first hit), and in that race the
        # interaction did NOT do its job.
        if s.failure is not None and s.failure(eng, st):
            return "fail"
        if s.success is not None and s.success(eng, st):
            return "pass"
        if (float(eng.t) - float(st.get("t0", 0.0))) >= float(s.time_limit):
            return "timeout"
        return None

    def step(self, action):
        pre = float(self.eng.elixir[0])
        obs, reward, done, info = super().step(action)
        spent = max(0.0, pre - float(self.eng.elixir[0]))
        self._drill["spent"] = float(self._drill.get("spent", 0.0)) + spent
        if not done:
            v = self._verdict()
            if v is not None:
                self.last_verdict = v
                done = True
                info = dict(info or {})
                info["drill"] = self.scenario.name
                info["verdict"] = v
                info["elapsed"] = float(self.eng.t) - float(self._drill.get("t0", 0.0))
                info["spent"] = float(self._drill.get("spent", 0.0))
        else:
            self.last_verdict = self.last_verdict or "ended"
            info = dict(info or {})
            info.setdefault("drill", self.scenario.name)
            info.setdefault("verdict", self.last_verdict)
        return obs, reward, done, info


def run_drill(cfg, scenario: sc.Scenario, policy=None, reps: int = 50, seed: int = 0,
              level: int = 11) -> dict:
    """Play `reps` repetitions and report the pass rate.

    A pass RATE is the honest measure of whether a skill is mastered -- a mean reward hides the
    difference between "solved it every time" and "solved it half the time and farmed shaping in
    the rest". `policy` is any callable (obs, env) -> action; None plays nothing, which is the
    baseline every drill should be measured against (some interactions succeed by accident, and a
    drill nobody can fail teaches nothing).
    """
    env = DrillEnv(cfg, scenario, seed=seed, level=level)
    out = {"name": scenario.name, "tier": scenario.tier, "reps": int(reps),
           "pass": 0, "fail": 0, "timeout": 0, "reward": 0.0, "elapsed": 0.0, "spent": 0.0}
    for _ in range(int(reps)):
        obs = env.reset()
        done, total = False, 0.0
        info: dict = {}
        while not done:
            action = (0, 0, 0) if policy is None else policy(obs, env)
            obs, r, done, info = env.step(action)
            total += float(r)
        v = (info or {}).get("verdict", "timeout")
        out[v] = out.get(v, 0) + 1
        out["reward"] += total
        out["elapsed"] += float((info or {}).get("elapsed", 0.0))
        out["spent"] += float((info or {}).get("spent", 0.0))
    n = max(1, int(reps))
    out["pass_rate"] = out["pass"] / n
    out["reward"] /= n
    out["elapsed"] /= n
    out["spent"] /= n
    return out

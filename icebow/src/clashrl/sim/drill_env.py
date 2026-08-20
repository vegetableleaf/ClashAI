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

    def __init__(self, cfg, scenario, seed: int = 0, level: int = 11):
        super().__init__(cfg, seed=seed)
        # `scenario` may be None for DrillMixEnv, which picks one per episode in reset().
        self.scenario = scenario
        self._level = int(level)
        self._drill: dict = {}
        self.last_verdict: Optional[str] = None

    # -- setup ---------------------------------------------------------------------------
    def _place_scenario(self) -> None:
        s = self.scenario
        rng = self.rng
        mirror = ("lane" in s.randomise) and bool(rng.random() < 0.5)
        self._drill_mirrored = bool(mirror)   # the reference line has to flip with the board
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
        if self.scenario is not None and self.scenario.setup is not None:
            # After the board, so a setup can reach the bodies it just placed by name.
            self.scenario.setup(self)
        self._drill = {
            "t0": float(self.eng.t),
            "princess_hp0": sum(float(t.hp) for t in sc.our_princesses(self.eng)),
            "enemy_tower_hp0": sum(float(t.hp) for t in self.eng.towers[1][:2]),
            "spent": 0.0,
            "plays": [],
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
            # ...but a scenario that scripts NO enemies is armed at once. Waiting for an enemy that
            # is never coming made `hog_send_on_a_quiet_board` unresolvable: the Hog was sent, it
            # crossed, and the drill sat there because the guard was still waiting for something to
            # arm against. A QUIET BOARD IS THE BOARD in that drill, not a missing one.
            if getattr(opp, "total", 0) and not any(u.team == 1 and u.hp > 0 for u in eng.units):
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
        # THE PLAY LEDGER. Elixir dropping is the evidence the deploy actually happened -- the
        # action is only a REQUEST, and the engine refuses it for cost, for an illegal cell, or for
        # a card that is not really in hand. Recording on the request instead would make "played"
        # mean "asked to play", the same fiction that made a third of live 6-elixir plays imaginary.
        try:
            want, cid, cell = int(action[0]), int(action[1]), int(action[2])
        except Exception:  # noqa: BLE001 -- a malformed action is not a play
            want = 0
        if want and spent > 1e-6 and 0 <= cid < len(self.deck_keys):
            gw = int(self.gw)
            nx, ny = self.actions.cell_center(cell % gw, cell // gw)
            self._drill.setdefault("plays", []).append(
                {"t": float(self.eng.t) - float(self._drill.get("t0", 0.0)),
                 "base": str(self.deck_keys[cid]).replace("_evo", ""),
                 "card": str(self.deck_keys[cid]), "x": float(nx), "y": float(ny),
                 "elixir": float(spent)})
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


def doctrine_policy(obs, env):
    """The reference policy for a drill: play what the DOCTRINE would play, where it says.

    This is the yardstick every scenario is measured against. A drill is only evidence of a
    learnable skill if doing nothing FAILS it and the doctrine PASSES it -- if both score the same,
    the scenario is measuring the board rather than the play, which is exactly how two of the first
    four drills came to pass 15/15 on an empty action.

    The card is chosen by the doctrine too, not just the cell. An oracle that took the first
    affordable card in hand scored the Hog push-veto drill at 28% by cheerfully sending the Hog
    into the push -- measuring the oracle, not the drill.
    """
    from . import doctrine

    hand = [c for c in env._hand_ids() if 0 <= c < len(env.specs)]
    want = {str(b) for b in (getattr(env.scenario, "hand", ()) or ())}
    if want:                                          # restricted hand -> the drill named the card
        hand = [c for c in hand
                if str(env.deck_keys[c]).replace("_evo", "") in want] or hand
    hand = [c for c in hand if float(env.eng.elixir[0]) >= float(env.specs[c].elixir)]
    if not hand:
        return (0, 0, 0)
    # WHETHER to play is always the doctrine's call; the scenario's `hand` only narrows WHICH.
    # These were tangled at first -- a restricted hand skipped the prior entirely and simply
    # played the first card that had a cell -- which made the triage drill unpassable by
    # construction: the reference policy could not express "hold", the one answer being rehearsed.
    try:
        pri = doctrine.doctrine_cards(env) or {}
    except Exception:                                 # noqa: BLE001 -- a silent prior is not a crash
        pri = {}
    if not pri:
        # THE DOCTRINE NOMINATES NOTHING -> HOLD. Falling through to "play the first affordable
        # card" is what an untrained policy does, not a reference one. Triage is a tier ABOVE
        # counters: not spending is a real answer, and it has to be one the oracle can give.
        return (0, 0, 0)
    ranked = [c for c in sorted(hand, key=lambda c: -float(pri.get(c, 0.0)))]
    if float(pri.get(ranked[0], 0.0)) <= 0.0:
        return (0, 0, 0)                              # nothing IN HAND is nominated -> hold
    hand = ranked
    for cid in hand:
        try:
            cells = doctrine.doctrine_cells(env, cid)
        except Exception:                             # noqa: BLE001
            cells = None
        if not cells:
            continue
        best = (max(cells, key=lambda kv: kv[1])[0] if isinstance(cells, list)
                else max(cells, key=cells.get))
        return (1, int(cid), int(best))
    return (0, 0, 0)



def scripted_policy(scenario):
    """Play a scenario's REFERENCE LINE -- the hand-written answer, in order, on its own clock.

    The point is diagnostic. When a drill scores 0% for both the do-nothing baseline and the
    doctrine oracle, those are two very different worlds: either nothing can pass it (the scenario
    is broken) or the doctrine cannot find the answer (a finding about the doctrine). Only a line
    known to be correct separates them.
    """
    plan = list(getattr(scenario, "reference", ()) or ())
    state = {"i": 0}

    def _policy(obs, env):
        # NEW EPISODE -> REWIND THE LINE. `run_drill` reuses one policy object for every rep, so a
        # cursor that only ever advances plays the line once and then sits out the remaining reps:
        # 1 pass in 20 is exactly the 5% this scored before. Elapsed time falling is the episode
        # boundary, and it is the only signal the policy gets.
        elapsed = float(env.eng.t) - float(env._drill.get("t0", 0.0))
        if elapsed < float(state.get("last", 1e9)):
            state["i"] = 0
        state["last"] = elapsed
        if state["i"] >= len(plan):
            return (0, 0, 0)
        base, x, y, t = plan[state["i"]]
        if elapsed < float(t):
            return (0, 0, 0)
        cid = next((c for c in env._hand_ids()
                    if str(env.deck_keys[c]).replace("_evo", "") == str(base)), None)
        if cid is None or float(env.eng.elixir[0]) < float(env.specs[cid].elixir):
            return (0, 0, 0)                       # not yet affordable / not yet drawn: wait
        # MIRROR WITH THE BOARD. `randomise=("lane",...)` flips the scenario's spawns, so a line
        # written for the left lane has to flip with them or it answers the wrong side.
        nx = float(x)
        if getattr(env, "_drill_mirrored", False):
            nx = 1.0 - nx
        state["i"] += 1
        return (1, int(cid), int(env.actions.cell_at(nx, float(y))))

    return _policy

def report(cfg, names=None, reps=25, seed=5, policy=None, level=11):
    """Run every registered drill baseline-vs-oracle and return the rows.

    Prints a table because the pass RATE is the number that says whether a skill is mastered -- a
    mean reward hides the difference between "solved it every time" and "solved half and farmed
    shaping in the rest".
    """
    rows = []
    todo = list(names) if names else sc.names()
    print("%-30s %8s %8s %8s %8s   %s"
          % ("drill", "nothing", "scripted", "doctrine", "policy", "verdict"))
    print("-" * 94)
    for name in todo:
        s = sc.get(name)
        base = run_drill(cfg, s, policy=None, reps=reps, seed=seed, level=level)
        ref = (run_drill(cfg, s, policy=scripted_policy(s), reps=reps, seed=seed, level=level)
               if getattr(s, "reference", ()) else None)
        doc = run_drill(cfg, s, policy=doctrine_policy, reps=reps, seed=seed, level=level)
        pol = (run_drill(cfg, s, policy=policy, reps=reps, seed=seed, level=level)
               if policy is not None else None)
        b, d = base["pass_rate"], doc["pass_rate"]
        r = ref["pass_rate"] if ref else None
        # The three columns answer three different questions, and collapsing them loses the one
        # that matters most: whether a drill nobody passed is broken or merely hard.
        best = max([x for x in (r, d) if x is not None], default=d)
        # A RESTRAINT DRILL declares itself by having no reference line: its correct play is to
        # play nothing, so a high do-nothing score is the DESIGN and not a defect. Reading those
        # as "not discriminating" would delete exactly the drills that teach triage -- the tier
        # the deck kept skipping -- because a random policy still fails them badly.
        if r is None and not getattr(s, "reference", ()) and b >= 0.5:
            verdict = ("restraint drill (correct play is NONE) -- doctrine agrees"
                       if d >= 0.5 else
                       "restraint drill (correct play is NONE) -- DOCTRINE SPENDS ANYWAY")
        elif r is not None and r < 0.5 and b < 0.5:
            verdict = "UNWINNABLE -- even the reference line fails; fix the scenario"
        elif b >= 0.5 and best >= 0.5 and abs(best - b) < 0.2:
            verdict = "NOT DISCRIMINATING -- the board resolves itself"
        elif best < b:
            verdict = "inverted (correct when the right play is NO play)"
        elif r is not None and r >= 0.5 and d < 0.3:
            verdict = "DOCTRINE GAP -- winnable, but the prior does not find it"
        elif abs(best - b) < 0.2:
            verdict = "NOT DISCRIMINATING -- baseline matches the best line"
        else:
            verdict = "ok"
        print("%-30s %7.0f%% %8s %7.0f%% %8s   %s"
              % (name, 100 * b, ("%.0f%%" % (100 * r)) if r is not None else "-", 100 * d,
                 ("%.0f%%" % (100 * pol["pass_rate"])) if pol else "-", verdict))
        rows.append({"name": name, "tier": s.tier, "baseline": b, "doctrine": d,
                     "reference": r, "policy": (pol["pass_rate"] if pol else None),
                     "verdict": verdict})
    return rows


class DrillMixEnv(DrillEnv):
    """A training env that plays a DRILL some fraction of episodes and a full match the rest.

    Mixing rather than staging is deliberate. A drill concentrates experience on states the policy
    rarely reaches by itself; it is not a different game, and it must not become one. Interleaving
    keeps the full-match terms (the phase machine, the crown terms, the double-elixir flip) in the
    same gradient as the rehearsed skill, so the skill is learned IN CONTEXT instead of having to
    survive a transfer afterwards.

    The choice is made per EPISODE, inside reset(), so a single object serves both the in-process
    pool and the remote workers -- both of which just build envs and call reset().
    """

    def __init__(self, cfg, seed: int = 0, level: int = 11, frac=None, tiers=None):
        sc.load_all()                                  # registry is filled by import side-effect
        pool = sc.all_scenarios()
        super().__init__(cfg, pool[0] if pool else None, seed=seed, level=level)
        self.drill_frac = (float(cfg.get("sim", "drill_frac", default=0.0))
                           if frac is None else float(frac))
        want = tiers if tiers is not None else (cfg.get("sim", "drill_tiers", default=None) or None)
        self._pool = [s for s in pool if not want or s.tier in set(want)]
        self._in_drill = False

    def reset(self):
        self._in_drill = bool(self._pool) and float(self.rng.random()) < self.drill_frac
        if not self._in_drill:
            return SimMatchEnv.reset(self)
        self.scenario = self._pool[int(self.rng.integers(len(self._pool)))
                                   if hasattr(self.rng, "integers")
                                   else int(self.rng.random() * len(self._pool)) % len(self._pool)]
        return DrillEnv.reset(self)

    def step(self, action):
        if not self._in_drill:
            return SimMatchEnv.step(self, action)
        return DrillEnv.step(self, action)


def make_train_env(cfg, seed: int = 0, level: int = 11):
    """The env a trainer should build: a plain match, or a drill mix when one is configured.

    Returns a bare SimMatchEnv when `sim.drill_frac` is 0, so a run that has not opted in is
    byte-for-byte the run it was before.
    """
    try:
        frac = float(cfg.get("sim", "drill_frac", default=0.0))
    except Exception:  # noqa: BLE001
        frac = 0.0
    if frac <= 0.0:
        return SimMatchEnv(cfg, seed=seed)
    return DrillMixEnv(cfg, seed=seed, level=level)

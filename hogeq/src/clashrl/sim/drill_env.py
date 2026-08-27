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

import os

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


# Cards used purely as DISTRACTORS on a drill board. Chosen to be ordinary, cheap-to-medium threats
# that a real match is full of and that no drill is ABOUT, so they add board state without turning
# into a second interaction the grader might confuse for the first.
# ENV OVERRIDE ONLY. The real switch is `sim.drill_play_out` in config.yaml; env wins when set so
# a command-line A/B needs no config edit, and None means "defer to config".
def _env_flag(name):
    """Parse a boolean ENV VAR properly. `bool(os.environ.get(name))` is True for ANY non-empty
    string -- INCLUDING "0" and "false" -- so the override could only ever turn a flag ON. This
    flag exists for command-line A/Bs, so `CLASHRL_DRILL_PLAY_OUT=0` silently produced the
    TREATMENT arm and any A/B run that way compared the feature against itself. Same family as
    `--drill-frac 0.0` and `--workers 0`: a falsy value that the code could not express."""
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() not in ("", "0", "false", "no", "off")


_PLAY_OUT_ENV = _env_flag("CLASHRL_DRILL_PLAY_OUT")
_PLAY_OUT_ANNOUNCED = False

_NOISE_CARDS = frozenset((
    "knight", "archers", "spear_goblins", "goblins", "minions", "bomber", "musketeer",
    "barbarians", "mega_minion", "fire_spirit", "ice_spirit", "bats", "skeletons",
))


class _ScriptedOpponent:
    """Plays exactly the scenario's spawns, at their scripted times, and nothing else.

    A real opponent reacts, which is the point of full-match training and the enemy of a drill:
    if the opponent varies its answer, a failed rep tells you nothing about the skill you were
    rehearsing. Variation belongs in the scenario's declared `randomise` list, where it is
    controlled, not in the opponent's judgement.
    """

    def __init__(self, spawns, db, level: int = 11):
        # Each spawn carries its OWN level: (base, team, x, y, t, level). A single level for the
        # whole script cannot express a ladder opponent, whose cards are individually levelled.
        self._todo = sorted(spawns, key=lambda s: s[4])
        self._db = db
        self._level = int(level)
        self.deck_keys = [s[0] for s in spawns]      # some reward paths ask what they hold
        self.placed = 0
        self.total = sum(1 for s in spawns if s[1] == 1)

    def act(self, eng) -> None:
        while self._todo and self._todo[0][4] <= eng.t:
            sp = self._todo.pop(0)
            base, team, x, y = sp[0], sp[1], sp[2], sp[3]
            lvl = int(sp[5]) if len(sp) > 5 else self._level
            if team != 1:
                continue                              # our side is placed at reset, not acted
            if deploy_unit(eng, 1, self._db, base, float(x), float(y), lvl):
                self.placed += 1


def compose_components(pool, rng, n_max=3):
    """Pick 2..n_max scenarios and lay them out as one board.

    Lanes ALTERNATE so two components do not spawn on top of each other, and each component gets a
    START OFFSET so the number of live interactions rises and falls within the episode rather than
    being fixed at N.
    """
    names = list(pool)
    if len(names) < 2:
        return []
    n = 2 + int(float(rng.random()) * max(1, n_max - 1))
    n = max(2, min(n_max, min(n, len(names))))
    picked, seen = [], set()
    while len(picked) < n and len(seen) < len(names):
        j = int(float(rng.random()) * len(names)) % len(names)
        if j in seen:
            continue
        seen.add(j)
        picked.append(names[j])
    out = []
    for i, s in enumerate(picked):
        # SIMULTANEOUS BY DEFAULT. Consecutive components are barely different from two separate
        # drills -- the policy answers one, then the other, and never has to hold both. The offset
        # is bimodal: often exactly 0 so several interactions land AT ONCE and the policy must
        # triage between them, otherwise a short overlap while the first is still live. Either way
        # the board carries more than one decision at a time, which a real match always does.
        if i == 0:
            offset = 0.0
        elif float(rng.random()) < 0.45:
            offset = 0.0                               # land together: triage under pressure
        else:
            offset = float(rng.uniform(0.6, 3.5))      # overlapping, not sequential
        out.append({"scenario": s, "lane": i % 2, "offset": round(offset, 1), "tag": i})
    return out


def compound_verdict(env):
    """(verdict, per-component results) for a compound episode.

    Two levels, per the owner's spec. Each component is graded by ITS OWN predicates against ONLY
    its own units -- the `_drill_component` filter makes `enemy_units` component-local, so a Hog
    belonging to interaction 2 cannot satisfy interaction 1's "no enemy alive". Then the OVERALL
    board is graded on what the tower actually paid, because acing two interactions while the third
    takes the tower down is not playing the board well.
    """
    comps = getattr(env, "_components", None)
    if not comps:
        return None, []
    results = []
    for c in comps:
        s = c["scenario"]
        st = c.setdefault("state", dict(env._drill))
        st["t0"] = env._drill.get("t0", 0.0)
        env.eng._drill_component = c["tag"]
        try:
            if c.get("done") is None:
                if s.success is not None and s.success(env.eng, st):
                    c["done"] = "pass"
                elif s.failure is not None and s.failure(env.eng, st):
                    c["done"] = "fail"
        finally:
            env.eng._drill_component = None
        results.append(c.get("done"))
    elapsed = float(env.eng.t) - float(env._drill.get("t0", 0.0))
    limit = max(float(c["scenario"].time_limit) + float(c["offset"]) for c in comps)
    if elapsed < limit and any(r is None for r in results):
        return None, results                        # still playing out
    passed = sum(1 for r in results if r == "pass")
    need = float(env.cfg.get("sim", "drill_compound_pass_frac", default=0.6))
    bar = float(env.cfg.get("sim", "drill_compound_hp_frac", default=0.45))
    hp0 = float(env._drill.get("compound_hp0") or 1.0)
    lost = hp0 - sum(float(t.hp) for t in env.eng.towers[0][:2])
    held = lost <= bar * hp0                        # OVERALL: did the towers survive the board
    ok = (passed >= need * len(results)) and held
    return ("pass" if ok else "fail"), results


class _ComponentOpponent:
    """Scripted opponent for a COMPOUND board: each spawn carries its component tag, so the unit it
    creates can be attributed to the interaction it belongs to."""

    def __init__(self, spawns, db):
        self._todo = sorted(spawns, key=lambda s: s[4])
        self._db = db
        self.deck_keys = [s[0] for s in spawns]
        self.placed = 0
        self.total = sum(1 for s in spawns if s[1] == 1)

    def act(self, eng) -> None:
        while self._todo and self._todo[0][4] <= eng.t:
            base, team, x, y, _t, lvl, tag = self._todo.pop(0)
            if team != 1:
                continue
            before = {id(u) for u in eng.units}
            if deploy_unit(eng, 1, self._db, base, float(x), float(y), int(lvl)):
                self.placed += 1
                for u in eng.units:
                    if id(u) not in before:
                        u.drill_tag = int(tag)


class DrillEnv(SimMatchEnv):
    """A SimMatchEnv pinned to one Scenario."""

    def __init__(self, cfg, scenario, seed: int = 0, level=None):
        super().__init__(cfg, seed=seed)
        # `scenario` may be None for DrillMixEnv, which picks one per episode in reset().
        self.scenario = scenario
        # None = roll each enemy's level from the ladder distribution the full sim uses, which is
        # what makes a drill the same fight as a match. An int PINS every spawn to that level, the
        # same fair-eval override make_opponent(level=...) offers.
        self._level = None if level is None else int(level)
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
            # LEVEL PER SPAWN: the enemy rolls a ladder level (or the fair-eval pin), and OUR
            # pre-placed bodies are our own cards at our own levels -- a level 11 Knight standing
            # beside the level 16 one from hand is the same mismatch this fixes.
            lvl = self._our_level(base) if team == 0 else self._enemy_level()
            spawns.append((base, team, float(x), float(y),
                           max(0.0, float(t) + jitter), int(lvl)))
        # THE DRILL'S LANE, from the first enemy spawn AFTER mirroring. Noise goes in the other
        # one and the HP predicates read only this tower, so a distractor chipping the far side
        # cannot read as this drill's answer failing.
        lane = None
        for base, team, x, y, t, lvl in spawns:
            if team == 1:
                lane = 0 if float(x) < 0.5 else 1
                break
        self._drill_lane = lane
        # our side is placed immediately; the opponent's are scripted
        for base, team, x, y, t, lvl in spawns:
            if team == 0:
                deploy_unit(self.eng, 0, self.eng.db, base, x, y, lvl)
        self.opponent = _ScriptedOpponent([sp for sp in spawns if sp[1] == 1],
                                          self.eng.db, 11)
        elix = float(s.elixir)
        if "elixir" in s.randomise:
            elix = max(0.0, min(10.0, elix + float(rng.uniform(-2.0, 2.0))))
        self.eng.elixir[0] = elix
        self.eng.elixir[1] = 10.0                      # the script pays for its own spawns
        self._place_noise(lane)

    def _place_noise(self, lane) -> None:
        """Distractor cards in the OTHER lane -- a board with more than one thing on it.

        A clean single-interaction drill has exactly one moment that matters, so WAIT is correct
        for most of its steps. Measured, training 30% of steps on that taught the gate to wait
        everywhere: plays per step fell 10.4% -> 5.9% and the policy dropped from 10% winrate to 0,
        below an untrained net. Real boards always have something else on them, and the owner's
        read is that this specificity is why the drills did not transfer.

        The distractors are TAGGED, so `enemy_units()` hides them from every predicate while the
        engine simulates them and the policy sees them. They land in the opposite lane so the
        lane-aware HP predicates stay about the drill's own interaction.
        """
        n = float(self.cfg.get("sim", "drill_noise", default=0.0))
        if n <= 0.0 or lane is None:
            return
        pool = [k for k in getattr(self.eng.db, "cards", {})
                if str(k) in _NOISE_CARDS]
        if not pool:
            return
        far_x = 0.806 if int(lane) == 0 else 0.194     # the lane the drill is NOT about
        rng = self.rng
        k = int(n) + (1 if float(rng.random()) < (n - int(n)) else 0)
        for _i in range(max(0, k)):
            base = pool[int(float(rng.random()) * len(pool)) % len(pool)]
            team = 1 if float(rng.random()) < 0.75 else 0        # mostly theirs, sometimes ours
            x = min(0.95, max(0.05, far_x + float(rng.uniform(-0.06, 0.06))))
            y = float(rng.uniform(0.30, 0.46)) if team == 1 else float(rng.uniform(0.60, 0.75))
            before = {id(u) for u in self.eng.units}
            if deploy_unit(self.eng, team, self.eng.db, str(base), x, y, self._enemy_level()
                           if team == 1 else self._our_level(str(base))):
                # TAG EVERY BODY THE CARD PRODUCED. Matching one unit by position missed the rest
                # of a squad -- bats is five units, archers two -- and an untagged distractor is
                # visible to the GRADER, which is the one thing noise must never be.
                for u in self.eng.units:
                    if id(u) not in before:
                        u.drill_noise = True

    def _play_slot(self, card_id: int) -> None:
        """One play per DEALT CARD in a restricted-hand drill.

        `SimMatchEnv._play_slot` sends a played slot to the back of the cycle, which is right for a
        real 8-card deck and wrong here: a drill dealt one or two cards has nothing else in the
        cycle, so the card is back in hand immediately and can be replayed for as long as the
        elixir lasts. Measured, that is exactly how several doctrine columns were passing --
        tornado three times in two seconds, ice_spirit five times -- while the drill's own
        single-cast reference line scored 0%. The trainer explores in here too, so it was a
        strategy the policy could learn as well as the oracle.

        A real hand is 4 of 8: replaying a card costs three other plays. With one or two dealt that
        is unreachable, so the honest model is that the card is spent. No reference line in either
        deck replays a card, so nothing's own answer becomes unplayable; matchup drills declare no
        hand at all and keep the ordinary cycle.
        """
        super()._play_slot(card_id)
        if not (self.scenario is not None and getattr(self.scenario, "hand", ())):
            return
        slot = self.slot_of.get(card_id)
        if slot is not None and slot in self.cycle:
            self.cycle.remove(slot)

    def _apply_evo_charge(self) -> None:
        """Bank each slot's Evolution charge for THIS drill, before the hand is restricted.

        WHY IT HAS TO EXIST. `SimMatchEnv` presents a slot's Evolution once `evo_charge` reaches
        `slot_cycles` (env.py `_slot_card_id`), and `reset()` starts every slot at zero -- which
        is right for a match, where 8 cards cycle and the second lap arrives on its own. A
        restricted-hand drill deals one or two cards and `DrillEnv._play_slot` then REMOVES the
        slot from the cycle (deliberately: see its docstring), so the charge can reach 1 and never
        the 2 an Evolution needs. MEASURED: an evolution was presented in 0 of 26 icebow drills
        and 0 of 24 hogeq drills, against a match that first presents one after 9 plays.

        The default is unchanged and stays unchanged on purpose: every existing reference line was
        written against the BASE card, and silently swapping in an Evolution would change what a
        drill's answer IS while leaving its recorded answer in place. `Scenario.evo_charged` is
        the opt-in; naming an `<base>_evo` key in `hand` is the other, because that declaration
        was previously ignored -- `_restrict_hand` matches on the identity the slot CURRENTLY
        presents, which at charge 0 is the base.
        """
        want = getattr(self, "_compound_evo", None)
        if want is None:
            want = getattr(self.scenario, "evo_charged", None) if self.scenario is not None else None
        # ...plus any slot whose EVOLUTION is named outright in the hand this drill will be dealt.
        named = {str(b) for b in (getattr(self, "_compound_hand", None)
                                  or (self.scenario.hand if self.scenario is not None else ())
                                  or ()) if str(b).endswith("_evo")}
        if want is None and not named:
            return
        keys = None if want is True else {str(k) for k in (want or ())} | named
        for slot in range(self.n_slots):
            evo = self.slot_evo_id[slot]
            if evo < 0:
                continue
            ekey = str(self.deck_keys[evo])
            if keys is not None and ekey not in keys and ekey.replace("_evo", "") not in keys:
                continue
            self.evo_charge[slot] = int(self.slot_cycles[slot])

    def _enemy_level(self) -> int:
        """A ladder opponent's card level, rolled the way `make_opponent` rolls it.

        Drills used to hardcode 11 while our own hand plays at real account levels (up to 16) and
        match training rolls the enemy from [13,14,15,16] -- so every drill was a fight our cards
        could not lose in the way the real one can. Level 11 -> 14 is +32% HP and +32% damage, and
        it changes the ANSWER: `skeletons_kill_the_miner`'s reference line passes 100% at 11 and 0%
        at 14.
        """
        if self._level is not None:
            return int(self._level)
        lv = list(self.cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16]))
        lw = list(self.cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1]))
        if not lv:
            return 11
        tot = float(sum(float(w) for w in lw)) or 1.0
        r, acc = float(self.rng.random()) * tot, 0.0
        for l_i, w_i in zip(lv, lw):
            acc += float(w_i)
            if r <= acc:
                return int(l_i)
        return int(lv[-1])

    def _our_level(self, base: str) -> int:
        """The level OUR deck actually plays this card at -- our pre-placed units are our cards."""
        try:
            for k, lv in zip(self.deck_keys, self.deck_card_levels):
                if str(k).replace("_evo", "") == str(base):
                    return int(lv)
        except Exception:  # noqa: BLE001
            pass
        return int(self._level) if self._level is not None else 11

    def _subgoal_stage(self):
        """Which start state to use, from the curriculum's own per-drill pass rate.

        Nearest the goal while the drill is unreachable, walking backwards as it is mastered, and
        the full drill once the policy can pass it. Returns None for the drill exactly as written.
        """
        s = getattr(self, "scenario", None)
        stages = list(getattr(s, "subgoals", ()) or ()) if s is not None else []
        if not stages:
            return None
        p = None
        if hasattr(self, "_pass_rate"):
            p = self._pass_rate(getattr(s, "name", ""))
        if p is None:
            return stages[0]                            # unseen: start from the easiest stage
        if p >= 0.60:
            return None                                 # mastered: the whole sequence, as written
        # walk backwards through the stages as the pass rate climbs toward 0.60
        idx = min(len(stages) - 1, int((p / 0.60) * len(stages)))
        return stages[idx]

    def _apply_subgoal(self) -> None:
        """Move the episode's start toward the moment that matters."""
        st = self._subgoal_stage()
        if not st:
            return
        if "elixir" in st:
            self.eng.elixir[0] = float(st["elixir"])
        skip = float(st.get("skip_s", 0.0) or 0.0)
        if skip > 0.0:
            # Let the scripted spawns that were due actually happen, so the board looks the way it
            # would have at that moment rather than being empty with a shifted clock.
            dt = float(getattr(self, "sub_dt", 0.1)) or 0.1
            steps = int(max(0.0, skip) / dt)
            for _ in range(min(steps, 600)):
                if getattr(self, "opponent", None) is not None:
                    self.opponent.act(self.eng)
                self.eng.advance(dt)          # the engine's own name for a physics sub-tick
        # THE SKIP MUST BE TRANSPARENT TO THE PREDICATES. Several of these drills grade on ELAPSED
        # TIME -- hold_the_spell fails if the Log is played before 4.5s -- so restarting the clock at
        # the new start turned the correct play into a too-early one and made the drill unpassable:
        # measured, 6% -> 0%. Backdating t0 by the skip means the episode simply BEGINS four seconds
        # in, which is what a subgoal is supposed to mean.
        self._subgoal_skip = skip
        self._drill_subgoal = st

    def _restrict_hand(self) -> None:
        """Deal only the cards the interaction needs.

        The point is not to make the drill easy -- it is that a rep must fail for the RIGHT
        reason. With the whole deck in hand, a missed king-activation could mean "did not know to
        Tornado" or merely "drew Skeletons", and the two are indistinguishable in the pass rate.
        """
        want = {str(b) for b in (getattr(self, "_compound_hand", None)
                                 or (self.scenario.hand if self.scenario is not None else ()) or ())}
        if not want:
            return
        # `cycle` holds SLOT indices, not card ids -- _slot_card_id(slot) maps one to the other,
        # and a slot can present either its base card or its Evolution. Filling cycle with card
        # ids indexes slot_evo_id out of range, which is exactly what it did on the first run.
        # ORDERED BY THE SCENARIO'S OWN DECLARATION, not by slot index. The hand is `cycle[:4]`, so
        # with more than four wanted cards which ones are actually dealt was decided by deck layout
        # -- a drill could open without the card it is named for. Declared order is what a drill
        # author expects to be dealt.
        order = {str(b): i for i, b in enumerate(self.scenario.hand or ())}
        wanted_slots = []
        for slot in range(self.n_slots):
            cid = self._slot_card_id(slot)
            key = str(self.deck_keys[cid]) if 0 <= cid < len(self.deck_keys) else ""
            base = key.replace("_evo", "")
            if key in want or base in want:
                wanted_slots.append((order.get(key, order.get(base, 99)), slot))
        wanted_slots = [s for _i, s in sorted(wanted_slots)]
        if wanted_slots:
            # ONLY these. `cycle[:4]` is the hand, so putting the wanted slots FIRST and keeping the
            # rest -- which is what this did -- left three other deck cards in hand and playable.
            # Measured on nado_king_activation, the policy answered the Hog with the rest of the
            # deck and collected +1.0 threat_response a time for it, so episodes that never
            # performed the drill's technique out-earned the ones that did. A drill that deals
            # cards it does not name is not measuring the interaction it is named after.
            #
            # The scenarios are checked against this: every reference line is playable from its own
            # declared hand, so the drill's answer is never the thing this rules out.
            self.cycle = list(wanted_slots)

    def drill_prior_gate(self):
        """P(play) the REFERENCE LINE would use right now, or None when it has no opinion.

        The gate is the only head without an exploration prior, and it is the one the timing drills
        turn on. Sampled from the policy alone it sits near 50/50 per step, so a drill that is
        passed by holding for twelve steps and then playing is reached with probability ~0.5^12 --
        measured, zero passes in 60 episodes for every hold drill, which is why they never taught
        anything however the reward was tuned.

        The line already knows: each reference step carries the time it is played at. Before the
        next step's time this says HOLD, after it says PLAY, and once the line is finished it says
        hold -- a drill's line is the whole answer, so anything past it is extra spending.
        """
        s = getattr(self, "scenario", None)
        ref = list(getattr(s, "reference", ()) or ()) if s is not None else []
        if not ref:
            return None
        i = len(self._drill.get("plays", ()))
        if i >= len(ref):
            return 0.02                                  # line complete -- further plays are waste
        try:
            t_next = float(ref[i][3])
        except Exception:  # noqa: BLE001 -- a reference without a clock cannot time anything
            return None
        # CANNOT NOMINATE WHAT THE LINE CANNOT PAY FOR. bank_to_six_then_bow opens at 2 elixir with a
        # 6-cost X-Bow written at t=0 ("first thing" -- you cannot bank before the match starts), so
        # a purely clock-based prior nominated PLAY from the opening tick and the card head, which
        # can only choose among AFFORDABLE cards, picked the cheap ones the drill fails you for
        # dumping the bar on: 0 passes in 60, the prior itself driving the failure. Holding until the
        # card is affordable also survives `randomise=("elixir",)`, which moves the moment the bank
        # fills by a couple of seconds every episode.
        base_next = str(ref[i][0])
        for cid, key in enumerate(self.deck_keys):
            if str(key).replace("_evo", "") != base_next:
                continue
            if float(self.eng.elixir[0]) < float(self.specs[cid].elixir):
                return 0.02
            break
        # One agent step of slack, so the prior does not sit one tick behind the line it mirrors.
        now = float(self.eng.t) - float(self._drill.get("t0", 0.0))
        return 0.90 if now >= t_next - 0.3 else 0.03

    def drill_prior_cells(self, card_id: int):
        """[(cell, weight)] for the REFERENCE play of this card, or None.

        A drill carries the hand-written correct line precisely so the report can prove the
        scenario is winnable. The same line is what exploration needs: nine of these drills never
        pass by chance, so without it there is no positive example and nothing to learn from.
        Offered as a PRIOR (it competes inside the sampling mixture), never forced -- the policy
        still has to choose it, and the stored log-prob stays the mixture's so PPO is unaffected.
        """
        s = getattr(self, "scenario", None)
        if s is None or not getattr(s, "reference", ()):
            return None
        base = str(self.deck_keys[card_id]).replace("_evo", "") if 0 <= card_id < len(self.deck_keys) else ""
        out = []
        for step in s.reference:
            if str(step[0]) != base:
                continue
            nx = float(step[1])
            if getattr(self, "_drill_mirrored", False):
                nx = 1.0 - nx                      # the line flips with the board, as in scripted_policy
            try:
                out.append((int(self.actions.cell_at(nx, float(step[2]))), 1.0))
            except Exception:  # noqa: BLE001 -- a bad reference must not break the rollout
                continue
        return out or None

    def reset(self) -> np.ndarray:
        obs = super().reset()
        self.eng.units.clear()                         # a drill starts from ITS board, not a match
        self._subgoal_skip = 0.0
        self._components = self._pick_components()
        # A COMPOUND EPISODE'S DECLARATIONS MUST NOT OUTLIVE IT. `_compound_hand` was assigned in
        # `_place_components` and never cleared, so after one compound episode every later
        # single-scenario drill in the same env was dealt the compound hand instead of its own --
        # `_restrict_hand` reads `_compound_hand or scenario.hand`, and the stale value wins.
        # Latent today (`sim.drill_compound_frac` is 0.0 in both decks) and found while adding the
        # evolution twin beside it.
        self._compound_hand = None
        self._compound_evo = None
        if self._components:
            self._place_components()
        else:
            self._place_scenario()
        self._apply_evo_charge()      # BEFORE the hand: _restrict_hand matches on the
        self._restrict_hand()         # identity a slot currently presents, base or Evolution
        self._apply_subgoal()
        if self.scenario is not None and self.scenario.setup is not None:
            # After the board, so a setup can reach the bodies it just placed by name.
            self.scenario.setup(self)
        self._drill = {
            "t0": float(self.eng.t) - float(getattr(self, "_subgoal_skip", 0.0) or 0.0),
            "lane": getattr(self, "_drill_lane", None),
            "princess_hp0": sum(float(t.hp) for t in sc.our_princesses(
                self.eng, {"lane": getattr(self, "_drill_lane", None)})),
            "enemy_tower_hp0": sum(float(t.hp) for t in self.eng.towers[1][:2]),
            "spent": 0.0,
            "plays": [],
            # OVERALL bar for a compound board: what both towers were worth at the start.
            "compound_hp0": sum(float(t.hp) for t in self.eng.towers[0][:2]),
        }
        self.last_verdict = None
        return self._obs() if hasattr(self, "_obs") else obs

    # -- the episode ---------------------------------------------------------------------
    def _pick_components(self):
        """The components of a COMPOUND episode, or [] for an ordinary single-interaction drill.

        Gated on `sim.drill_compound_frac` and off by default, so every drill measured so far keeps
        its meaning. Only scenarios that declare a hand are eligible: a matchup already IS a
        multi-interaction board and composing two of them stacks two full decks of intent.
        """
        frac = float(self.cfg.get("sim", "drill_compound_frac", default=0.0))
        if frac <= 0.0 or float(self.rng.random()) >= frac:
            return []
        pool = [s for s in sc.all_scenarios() if getattr(s, "hand", ())]
        n_max = int(self.cfg.get("sim", "drill_compound_n", default=3))
        return compose_components(pool, self.rng, n_max=n_max)

    def _place_components(self) -> None:
        """Lay every component on the board, lane-separated, time-staggered and TAGGED."""
        rng = self.rng
        all_spawns, our_hand = [], []
        for c in self._components:
            s = c["scenario"]
            our_hand.extend(list(s.hand or ()))
            flip = (c["lane"] == 1)
            for base, team, x, y, t in s.spawns:
                nx = (1.0 - float(x)) if flip else float(x)
                lvl = self._our_level(base) if team == 0 else self._enemy_level()
                all_spawns.append((base, team, nx, float(y),
                                   max(0.0, float(t) + float(c["offset"])), int(lvl), c["tag"]))
        for base, team, x, y, t, lvl, tag in all_spawns:
            if team != 0:
                continue
            before = {id(u) for u in self.eng.units}
            if deploy_unit(self.eng, 0, self.eng.db, base, x, y, lvl):
                for u in self.eng.units:
                    if id(u) not in before:
                        u.drill_tag = tag
        self.opponent = _ComponentOpponent([sp for sp in all_spawns if sp[1] == 1],
                                           self.eng.db)
        self._drill_lane = None                        # a compound board spans both lanes
        # The union of the components' hands, so every interaction on the board is answerable.
        self._compound_hand = tuple(dict.fromkeys(our_hand))
        # ...and the union of their evolution declarations, read by `_apply_evo_charge` exactly as
        # `_compound_hand` is read by `_restrict_hand`. True from any component wins outright.
        _evos = [getattr(c["scenario"], "evo_charged", None) for c in self._components]
        if any(e is True for e in _evos):
            self._compound_evo = True
        else:
            _keys = tuple(dict.fromkeys(k for e in _evos if e for k in e))
            self._compound_evo = _keys or None
        self.eng.elixir[0] = min(10.0, max(float(c["scenario"].elixir) for c in self._components))
        self.eng.elixir[1] = 10.0

    def _play_out(self) -> bool:
        """Does a drill CONTINUE as an ordinary match once its verdict is recorded?

        `sim.drill_play_out`, with CLASHRL_DRILL_PLAY_OUT overriding it for a command-line A/B.

        Root-cause fix for the two-population problem: a drill averages 18.4 s against a match's
        180 s+, one critic has to value both, and measured that wrecks it (value loss 1.3-1.8 mixed
        vs 0.38-0.56 matches-alone). Splitting the critic recovered only ~30% and shrinking
        drill_frac did not help at all, because both compensate downstream for a length mismatch
        instead of removing it. Playing the drill out makes episode length, return scale and critic
        targets match automatically.

        Announced ONCE per process: a flag that can silently do nothing is how the icebow version
        spent its life being read from an env var while its own comment named a config key.
        """
        if _PLAY_OUT_ENV is not None:
            v = _PLAY_OUT_ENV
        else:
            try:
                v = bool(self.cfg.get("sim", "drill_play_out", default=False))
            except Exception:  # noqa: BLE001
                v = False
        global _PLAY_OUT_ANNOUNCED
        if not _PLAY_OUT_ANNOUNCED:
            _PLAY_OUT_ANNOUNCED = True
            print("[drill] play-out %s -- drills %s"
                  % ("ON" if v else "off",
                     "continue as ordinary matches after their verdict"
                     if v else "END at their verdict (episode ~18s vs a match's ~180s)"))
        return v

    def _verdict(self) -> Optional[str]:
        if getattr(self, "_components", None):
            v, _res = compound_verdict(self)
            return v
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
        self._drill["steps"] = int(self._drill.get("steps", 0)) + 1
        obs, reward, done, info = super().step(action)
        spent = max(0.0, pre - float(self.eng.elixir[0]))
        self._drill["spent"] = float(self._drill.get("spent", 0.0)) + spent
        # HITS TAKEN, because an HP bar cannot survive the ladder level roll. Enemy levels vary
        # 13-16 (+-32% damage), so for a drill whose play buys ONE denied hit the effect is smaller
        # than the spread the roll alone produces, and the two outcomes overlap however the bar is
        # placed. A COUNT does not move with level: an Ice Spirit denies a hit at 13 and at 16.
        # One step per connection at a 0.6s period against a 1.6s hit speed.
        now_hp = sum(float(t.hp) for t in sc.our_princesses(self.eng, self._drill))
        was_hp = float(self._drill.get("_hp_prev", now_hp))
        if now_hp < was_hp - 1e-6:
            self._drill["hits_taken"] = int(self._drill.get("hits_taken", 0)) + 1
        self._drill["_hp_prev"] = now_hp
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
            # `last_verdict is None` guard: under play-out the episode continues, so this block is
            # re-entered on later steps and would otherwise re-stamp the verdict every tick.
            if v is not None and self.last_verdict is None:
                self.last_verdict = v
                # PLAY OUT: record the verdict at its natural moment but let the episode CONTINUE
                # as an ordinary match instead of ending here. Ending early is what creates the
                # 18s-vs-180s mismatch that miscalibrates the shared critic.
                done = bool(done) or not self._play_out()
                info = dict(info or {})
                info["drill"] = self.scenario.name
                info["verdict"] = v
                info["elapsed"] = float(self.eng.t) - float(self._drill.get("t0", 0.0))
                info["ep_steps"] = int(self._drill.get("steps", 0))
                info["spent"] = float(self._drill.get("spent", 0.0))
        else:
            self.last_verdict = self.last_verdict or "ended"
            info = dict(info or {})
            info.setdefault("drill", self.scenario.name)
            info.setdefault("verdict", self.last_verdict)
        return obs, reward, done, info


def run_drill(cfg, scenario: sc.Scenario, policy=None, reps: int = 50, seed: int = 0,
              level=None) -> dict:
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
            state.pop("t0", None)
        state["last"] = elapsed
        # THE LINE WAITS FOR THE BOARD IT ANSWERS. Scenario timings are jittered (`randomise`
        # includes "timing"), so a line written against a fixed clock fires before the enemy
        # exists on some reps -- and then measures something else entirely: a Firecracker played
        # into an empty board is correctly billed -1.0 as support-played-alone, and a Log rolled
        # through empty ground is correctly billed as a whiff. Both showed up as the reward
        # "failing to price" a drill it was in fact pricing right. Timings are therefore relative
        # to the first scripted enemy appearing, not to the episode clock.
        if getattr(env, "opponent", None) is not None and getattr(env.opponent, "total", 0):
            # THE DRILL'S OWN enemies, not the distractors: `sc.enemy_units` skips tagged noise.
            # Scanning every team-1 unit let a distractor satisfy this check, so the line fired
            # before the threat it answers even existed -- measured, reference columns fell from
            # 100% to 53-93% the moment noise was switched on.
            if not sc.enemy_units(env.eng):
                return (0, 0, 0)                   # nothing has arrived yet: hold the line
        # NOTE the clock is NOT re-based. Holding for the enemy fixes the too-early case; shifting
        # the whole line to "seconds after it arrives" breaks the opposite one -- tesla_late_not_early
        # deliberately waits out an arrival at t=9, and a re-based 8.4s put it at t=17.4, long past
        # the moment it was meant to answer. The line fires at max(its own time, the enemy existing).
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

def report(cfg, names=None, reps=25, seed=5, policy=None, level=None, reward_mode=False):
    """Run every registered drill baseline-vs-oracle and return the rows.

    Prints a table because the pass RATE is the number that says whether a skill is mastered -- a
    mean reward hides the difference between "solved it every time" and "solved half and farmed
    shaping in the rest".
    """
    rows = []
    todo = list(names) if names else sc.names()
    if reward_mode:
        # DOES THE REWARD PAY FOR THE CORRECT PLAY? A drill only teaches if passing it earns more
        # than failing it. Where the two are equal the interaction is UNPRICED: the policy can be
        # given the state a thousand times and there is no gradient toward the right answer, so
        # mixing that drill into training buys nothing. This is the direct test, per drill, and it
        # replaces arguing about which reward term ought to fire.
        print("%-30s %9s %9s %9s   %s"
              % ("drill", "R(nothing)", "R(correct)", "delta", "priced?"))
        print("-" * 88)
    else:
        print("%-30s %8s %8s %8s %8s   %s"
              % ("drill", "nothing", "scripted", "doctrine", "policy", "verdict"))
        print("-" * 94)
    for name in todo:
        s = sc.get(name)
        base = run_drill(cfg, s, policy=None, reps=reps, seed=seed, level=level)
        if reward_mode:
            ref = (run_drill(cfg, s, policy=scripted_policy(s), reps=reps, seed=seed, level=level)
                   if getattr(s, "reference", ()) else None)
            rb = float(base["reward"])
            rr = float(ref["reward"]) if ref else None
            if rr is None:
                # A restraint drill has no reference line; its "correct play" IS the baseline,
                # so the question does not apply and reporting a delta would invent one.
                verdict, delta = "restraint drill (no reference)", None
            else:
                delta = rr - rb
                verdict = ("UNPRICED -- the correct play earns no more than doing nothing"
                           if delta <= 0.05 else
                           ("weak (%.2f)" % delta if delta < 0.5 else "priced"))
            print("%-30s %9.2f %9s %9s   %s"
                  % (name, rb, ("%.2f" % rr) if rr is not None else "-",
                     ("%+.2f" % delta) if delta is not None else "-", verdict))
            rows.append({"name": name, "tier": s.tier, "r_nothing": rb, "r_correct": rr,
                         "delta": delta, "verdict": verdict, "graded_by": list(s.graded_by)})
            continue
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
        elif r is not None and r < 0.5 and d < 0.5 and b < 0.5:
            # UNWINNABLE means NOTHING passed it -- not merely that the hand-written line is worse
            # than the doctrine. On the matchup drills the prior scores 62-94% where a scripted
            # line scores 25%, which says the scenario is fine and the line is naive: a 34-second
            # multi-wave sequence is not something four fixed coordinates can answer.
            verdict = "UNWINNABLE -- nothing passes it (reference, doctrine and baseline all fail)"
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

    def __init__(self, cfg, seed: int = 0, level=None, frac=None, tiers=None):
        sc.load_all()                                  # registry is filled by import side-effect
        pool = sc.all_scenarios()
        super().__init__(cfg, pool[0] if pool else None, seed=seed, level=level)
        # TARGET SHARE OF TRAINING STEPS, not of episodes. See the module note: a drill is ~19
        # steps against a match's ~186, so picking drills half the time still left them at 8% of
        # the gradient -- and split across 28 scenarios, none of them ever had enough signal.
        self.drill_frac = (float(cfg.get("sim", "drill_frac", default=0.0))
                           if frac is None else float(frac))
        # RUNNING MEAN EPISODE LENGTHS, and the SEED MATTERS FOR THE WHOLE EARLY RUN.
        # _episode_prob solves `target_step_share = p*Ld / (p*Ld + (1-p)*Lm)` for p, so a stale Ld
        # mis-sets the mix until the running mean catches up -- and with drill_play_out ON, 20.0 is
        # not merely stale, it is wrong by ~25x. MEASURED in icebow at 25 episodes with play-out and
        # the old seed: drills took 81% of STEPS against a configured 30%, because the solver still
        # thought a drill cost 20 steps while each one now runs a full match. Seeding Ld = Lm under
        # play-out makes p = target immediately -- with equal lengths the episode share and the step
        # share are the same number, which is the whole point of the flag.
        _po = False
        try:
            _e = _env_flag("CLASHRL_DRILL_PLAY_OUT")
            _po = _e if _e is not None else bool(cfg.get("sim", "drill_play_out", default=False))
        except Exception:  # noqa: BLE001
            _po = False
        self._len_match = 186.0
        self._len_drill = self._len_match if _po else 20.0
        self._n_drill = self._n_match = 0
        self._ep_steps = 0
        want = tiers if tiers is not None else (cfg.get("sim", "drill_tiers", default=None) or None)
        self._pool = [s for s in pool if not want or s.tier in set(want)]
        # DRILL_ONLY: restrict to named scenarios. Exists for the diagnostic that separates "this
        # policy cannot learn a drill" from "28 drills are competing for one policy" -- a question
        # the aggregate pass rate cannot answer, because drills that trade off against each other
        # hold the mean flat while individual ones move a long way.
        only = cfg.get("sim", "drill_only", default=None) or None
        if only:
            keep = {str(n) for n in only}
            self._pool = [s for s in self._pool if s.name in keep] or self._pool
        self._in_drill = False
        self._pass_ema = {}                             # per-drill pass rate, for the curriculum

    def _episode_prob(self) -> float:
        """Episode probability that delivers the configured share of STEPS.

        Solving `target = p*Ld / (p*Ld + (1-p)*Lm)` for p gives

            p = target * Lm / (Ld * (1 - target) + target * Lm)

        With the measured 19-step drill and 186-step match, a 30% step share needs p ~= 0.80 --
        four episodes in five. Nobody would guess that from the outside, which is why the knob
        counting episodes went unnoticed for two runs.
        """
        t = max(0.0, min(0.95, float(self.drill_frac)))
        if t <= 0.0:
            return 0.0
        ld, lm = max(1.0, self._len_drill), max(1.0, self._len_match)
        return max(0.0, min(0.98, t * lm / (ld * (1.0 - t) + t * lm)))


    def reset(self):
        # fold the episode that just ended into the length estimates (they drift: drills lengthen
        # as the policy stops failing them instantly, matches shorten as it starts winning)
        if self._ep_steps > 0:
            if self._in_drill:
                self._n_drill += 1
                self._len_drill += (self._ep_steps - self._len_drill) / min(50, self._n_drill)
            else:
                self._n_match += 1
                self._len_match += (self._ep_steps - self._len_match) / min(50, self._n_match)
        self._ep_steps = 0
        self._in_drill = bool(self._pool) and float(self.rng.random()) < self._episode_prob()
        if not self._in_drill:
            return SimMatchEnv.reset(self)
        # CURRICULUM: weighted by reachability, never zero for any drill.
        w = [self._curriculum_weight(getattr(s, "name", "")) for s in self._pool]
        tot = sum(w) or 1.0
        r, acc, idx = float(self.rng.random()) * tot, 0.0, len(self._pool) - 1
        for j, wj in enumerate(w):
            acc += wj
            if r <= acc:
                idx = j
                break
        self.scenario = self._pool[idx]
        return DrillEnv.reset(self)

    # -- curriculum ----------------------------------------------------------------------
    def _pass_rate(self, name):
        """Per-drill pass rate, EMA. None until the drill has been seen enough to mean anything."""
        st = self._pass_ema.get(str(name))
        if st is None or st[1] < 4:
            return None
        return st[0]

    def _note_verdict(self, name, verdict) -> None:
        p, n = self._pass_ema.get(str(name), (0.5, 0))
        hit = 1.0 if verdict == "pass" else 0.0
        self._pass_ema[str(name)] = (p + 0.12 * (hit - p), n + 1)

    def _curriculum_weight(self, name) -> float:
        """How often to draw this drill. Peaks in the LEARNABLE BAND, never reaches zero.

        A drill at 100% teaches nothing new and one at 2% produces nothing to learn from, but
        neither is dropped: the floor keeps every drill in the mix so a mastered skill is not
        forgotten and an unreachable one is still being attempted while its scaffolding rises.
        """
        p = self._pass_rate(name)
        if p is None:
            return 1.0                                  # unseen: sample it normally
        if p < 0.15:
            return 0.6                                  # still attempted, and its prior is rising
        if p > 0.85:
            return 0.35                                 # mastered: keep it warm, stop spending on it
        return 1.6                                      # the band where learning can actually happen

    def drill_floor_scale(self) -> float:
        """Multiplier on the trainer's drill exploration floors, from THIS drill's pass rate.

        Opposite directions on purpose:
          * below 15% -- the successes are not being generated, so scaffold HARDER (the owner's
            "nudge"); without it the drill is stuck no matter how long training runs.
          * above 85% -- the prior is winning it, and at r ~ 0.0125 the policy learns almost nothing
            from a win it did not produce. Weakening the prior moves mu toward pi so the win teaches.
        """
        s = getattr(self, "scenario", None)
        if s is None:
            return 1.0
        p = self._pass_rate(getattr(s, "name", ""))
        if p is None:
            return 1.0
        if p < 0.15:
            return 1.4
        if p > 0.85:
            return 0.45
        return 1.0

    def step(self, action):
        self._ep_steps += 1
        if not self._in_drill:
            return SimMatchEnv.step(self, action)
        out = DrillEnv.step(self, action)
        # FEED THE CURRICULUM. The verdict is the only evidence of what this policy can currently
        # reach, and both the sampling weight and the scaffolding strength key off it.
        info = out[3] if isinstance(out, tuple) and len(out) > 3 else None
        if isinstance(info, dict) and info.get("verdict") and self.scenario is not None:
            self._note_verdict(getattr(self.scenario, "name", ""), info.get("verdict"))
        return out


def make_train_env(cfg, seed: int = 0, level=None, frac=None):
    """The env a trainer should build: a plain match, or a drill mix when one is configured.

    Returns a bare SimMatchEnv when `sim.drill_frac` is 0, so a run that has not opted in is
    byte-for-byte the run it was before.
    """
    # `frac` ARRIVES FROM THE CALLER when there is one, because the rollout workers re-read
    # config.yaml from disk in their own process and would otherwise ignore an in-memory override
    # -- which is exactly what `--drill-frac` is. Falling back to the config keeps a plain run
    # byte-for-byte what it was.
    if frac is None:
        try:
            frac = float(cfg.get("sim", "drill_frac", default=0.0))
        except Exception:  # noqa: BLE001
            frac = 0.0
    frac = float(frac or 0.0)
    if frac <= 0.0:
        return SimMatchEnv(cfg, seed=seed)
    return DrillMixEnv(cfg, seed=seed, level=level, frac=frac)


def outcomes(cfg, names=None, reps=60, seed=5, level=None):
    """Per drill: the mean episode reward of each OUTCOME, under the trainer's own exploration.

    The acceptance test for a drill is not "does the right play beat idling" -- that is
    `--reward`, and a drill can pass it while still paying most for the wrong outcome. It is
    "does PASSING pay more than anything else", because that is the comparison the optimiser
    actually makes.
    """
    import random as _rnd
    from . import doctrine as _doc
    rows = []
    todo = list(names) if names else sc.names()
    _rnd.seed(int(seed))

    def _explore(obs, env):
        """The trainer's DRILL sampling mixture, so the outcome mix is the one training sees."""
        hand = [c for c in env._hand_ids()
                if 0 <= c < len(env.specs)
                and float(env.eng.elixir[0]) >= float(env.specs[c].elixir)]
        # PLAY/HOLD, with the same drill timing prior the trainer blends into its gate (0.6 of the
        # decision, from the drill's reference line). Without it this sampler holds at a flat 0.55
        # per step and the timing drills are unreachable here even once training can pass them.
        p_play = 0.55
        try:
            pg = env.drill_prior_gate() if hasattr(env, "drill_prior_gate") else None
        except Exception:  # noqa: BLE001
            pg = None
        if pg is not None:
            gf = float(cfg.get("sim", "ppo_drill_gate_floor", default=0.85))
            p_play = (1.0 - gf) * p_play + gf * float(pg)
        if not hand or _rnd.random() >= p_play:
            return (0, 0, 0)
        cid = _rnd.choice(hand)
        if _rnd.random() < 0.75 and _rnd.random() < 0.6:
            try:
                dc = _doc.doctrine_cells(env, cid)
            except Exception:  # noqa: BLE001
                dc = None
            if dc:
                tot = sum(w for _c, w in dc)
                r, acc = _rnd.random() * tot, 0.0
                for c, w in dc:
                    acc += w
                    if r <= acc:
                        return (1, cid, int(c))
        return (1, cid, _rnd.randrange(env.n_cells))

    print("%-30s %16s %16s %16s   %s"
          % ("drill", "PASS", "fail", "timeout", "is passing best?"))
    print("-" * 100)
    for name in todo:
        s = sc.get(name)
        got = {}
        for k in range(int(reps)):
            env = DrillEnv(cfg, s, seed=7000 + k, level=level)
            obs = env.reset()
            done, tot, info = False, 0.0, {}
            while not done:
                obs, r, done, info = env.step(_explore(obs, env))
                tot += float(r)
            got.setdefault((info or {}).get("verdict", "?"), []).append(tot)
        mean = {k: sum(v) / len(v) for k, v in got.items() if v}
        n = {k: len(v) for k, v in got.items()}

        # A RESTRAINT DRILL IS PASSED BY DOING NOTHING, so exploration -- which plays something in
        # most episodes -- can never record a pass, and calling that "nothing to learn from" would
        # be exactly backwards. Score the do-nothing line; if it is this drill's correct answer, it
        # IS the passing behaviour and belongs in the PASS column.
        restraint = False
        if "pass" not in mean:
            idle = []
            for k in range(max(6, int(reps) // 6)):
                env = DrillEnv(cfg, s, seed=7000 + k, level=level)
                env.reset()
                done, tot, info = False, 0.0, {}
                while not done:
                    _o, r, done, info = env.step((0, 0, 0))
                    tot += float(r)
                idle.append((tot, (info or {}).get("verdict", "?")))
            # A MAJORITY, not unanimity: these drills randomise lane, timing and elixir, and now
            # carry noise, so one stray timeout in seven is normal and must not erase the column.
            if idle and sum(1 for _t, v in idle if v == "pass") >= 0.7 * len(idle):
                restraint = True
                got["pass"] = [t for t, _v in idle]
                mean["pass"] = sum(got["pass"]) / len(got["pass"])
                n["pass"] = len(got["pass"])

        p = mean.get("pass")

        def _sem2(key):
            """Squared standard error of `key`'s mean -- the width the comparison has to clear."""
            v = got.get(key) or []
            if len(v) < 2:
                return float("inf")            # one episode says nothing about its own spread
            m = sum(v) / len(v)
            return (sum((x - m) ** 2 for x in v) / (len(v) - 1)) / len(v)

        # A RIVAL OUTCOME ONLY COUNTS IF THE EVIDENCE IS THERE. Comparing bare means failed drills
        # on two-episode flukes (timeout +5.55 from n=2 against pass +2.15 from n=13), which would
        # have sent this rewriting reward terms that are working.
        MIN_N = 5
        rivals = [(k, mean[k]) for k in mean if k != "pass"]
        if p is None:
            verdict = "NO PASSES -- nothing to learn from"
        else:
            beat, weak = None, None
            for k, m in sorted(rivals, key=lambda kv: -kv[1]):
                if m <= p:
                    continue
                lead = m - p
                if n.get(k, 0) >= MIN_N and lead > 2.0 * ((_sem2(k) + _sem2("pass")) ** 0.5):
                    beat = (k, m)
                    break
                if weak is None:
                    weak = (k, m)
            if beat:
                verdict = "NO -- '%s' pays more (%+.2f vs %+.2f)" % (beat[0], beat[1], p)
            elif weak:
                verdict = "yes (weak: '%s' %+.2f n=%d not significant)" % (
                    weak[0], weak[1], n.get(weak[0], 0))
            else:
                verdict = "yes" + (" (restraint: PASS column is the do-nothing line)"
                                   if restraint else "")
        def _c(k):
            return ("%+.2f (n=%d)" % (mean[k], n[k])) if k in mean else "-"
        print("%-30s %16s %16s %16s   %s"
              % (name, _c("pass"), _c("fail"), _c("timeout"), verdict))
        rows.append({"name": name, "mean": mean, "n": n, "verdict": verdict})
    bad = [r for r in rows if not r["verdict"].startswith("yes")]
    if bad:
        print("")
        print("%d drill(s) do NOT pay most for passing -- each needs the reward term underneath it "
              "corrected, not the drill:" % len(bad))
        for r in bad:
            print("   %-30s %s" % (r["name"], r["verdict"]))
    return rows

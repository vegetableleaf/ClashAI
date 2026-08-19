"""A local LLM that suggests which card to explore with, inside the live RL loop.

WHY THIS CAN EXIST AT ALL (and why I first said it could not)
------------------------------------------------------------
The first latency measurement said a local call cost 2.4-3.8 s against a 1.0 s decision budget,
which would have made this impossible. That number was wrong, and the cause was the measuring
harness, not the model:

  * the URL said `localhost`, which on Windows resolves to ::1 first and waits for that to fail
    before falling back to 127.0.0.1 -- about 2 s, every call; and
  * every call opened a fresh TCP connection instead of reusing one.

Fixing both drops a 7B model to 0.589 s p50, and a 0.5B model to 0.347 s. On the TINY models size
barely moved the number, which is what gave the artefact away -- compute was never the 2.4 s. It
does matter once the model and the prompt are real: with the doctrine prompt below, qwen2.5 7B
sits at 0.590 s p50 / 0.823 s tail while gemma3 4B takes 3.020 s. So this module keeps ONE
persistent connection to the NUMERIC address, never a hostname.

WHERE IT PLUGS IN, AND WHY THAT IS SAFE
---------------------------------------
It replaces the RANDOM card in train_rl's epsilon-exploration branch, not the policy's greedy
choice. The live trainer is Double-DQN, which is OFF-POLICY: the behaviour policy that fills the
replay buffer does not have to match the policy being learned, and no importance correction is
needed. (The sim's PPO is on-policy and could not take this without storing a mixture log-prob --
which is why the sim gets the offline doctrine table instead.) So the effect here is that
exploration stops being uniform noise and starts being plausible play, and the Q-learner gets a
replay buffer of sensible actions to learn from.

It is an ADVISOR, not an oracle. On tools/llm_eval.py the live model scores 6/10 on this project's
own doctrine cases -- far better than the uniform-random pick it replaces, and it never touches the
greedy action, so a bad suggestion costs one exploration step rather than a match. The ceiling
there is the PROMPT more than the model: adding the deck's decision rules took gemma3 4B from
3/10 to 8/10, which is why the prompt below states rules and not just card roles.

HARD RULES
----------
  * NEVER blocks the live loop. A timeout, a dead server, a malformed reply -- any failure returns
    None and the caller falls back to its normal random choice. The bot is blind between decisions,
    so a stall is worse than a bad suggestion.
  * Off unless switched on (train.llm_advisor).
  * Records its own latency and hit rate, because an advisor that has quietly stopped answering
    should be visible rather than silently degrading into the random baseline.
"""
from __future__ import annotations

import json
import time

#: The advisor's way of saying "play nothing". A real answer, not a failure -- callers must be
#: able to tell it apart from "the advisor did not respond", which falls back to random instead.
HOLD = "hold"


class LLMAdvisor:
    """Suggests a card to explore with. Fails to None, never raises into the caller."""

    def __init__(self, cfg=None, model=None, timeout=None, host="127.0.0.1", port=11434):
        g = (lambda *a, **k: None) if cfg is None else cfg.get
        self.model = model or g("train", "llm_advisor_model", default="qwen2.5:latest")
        # Budget, not a hope: act_period is 1.0 s and the bot cannot see during the call.
        self.timeout = float(timeout if timeout is not None
                             else (g("train", "llm_advisor_timeout_s", default=0.9) or 0.9))
        self.host, self.port = host, int(port)
        self._conn = None
        self.calls = self.hits = self.fails = 0
        self.total_s = 0.0
        self.last_error = None
        # CIRCUIT BREAKER. A dead server still costs ~510 ms per call to discover, and that is
        # half the decision budget burned to learn nothing. After this many CONSECUTIVE failures
        # the advisor switches itself off for the rest of the session and the loop silently
        # reverts to its normal random exploration -- degraded, not stalled.
        self.max_consecutive_fails = int(g("train", "llm_advisor_max_fails", default=5) or 5)
        self._streak = 0
        self.disabled = False

    # -- transport ------------------------------------------------------
    def _connection(self):
        import http.client
        if self._conn is None:
            # NUMERIC address deliberately: a hostname costs ~2 s per call to the IPv6 fallback.
            self._conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        return self._conn

    def _reset(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:  # noqa: BLE001
            pass
        self._conn = None

    # -- the ask --------------------------------------------------------
    def suggest_plan(self, situation: str, hand: list, elixir: float):
        """An ORDERED answer of one to three cards, or [] -- a defence, not a single card.

        Counters in this game are rarely one-to-one. A Giant with a Musketeer behind it is not
        answered by any single card in this hand; it is answered by Tesla to hold the Giant and
        then the Firecracker or Log for the support. Asking "the single best card" cannot express
        that, and worse, it distorts the FIRST card too: the best opener of a good two-card defence
        is frequently not the best card considered alone (Skeletons first only make sense because
        the Mighty Miner is coming behind them).

        The live loop plays one card per decision, so a combination is necessarily a SEQUENCE
        across consecutive decisions. This returns that sequence; the caller commits to it and
        spends it in order, re-planning when the board changes underneath it.
        """
        return self._ask(situation, hand, elixir, plan=True)

    def suggest(self, situation: str, hand: list, elixir: float):
        """Single-card form, kept for callers that only take one action."""
        got = self._ask(situation, hand, elixir, plan=False)
        return got[0] if got else None

    def _ask(self, situation: str, hand: list, elixir: float, plan: bool):
        if not hand or self.disabled:
            return []
        # SHARP RULES, not just roles. Measured on tools/llm_eval.py, putting the deck's actual
        # decision rules in the prompt moved gemma3:4b from 3/10 to 8/10 -- the ceiling was the
        # PROMPT, not the model.
        #
        # It is not free, though, and an earlier note here wrongly said it was. That claim came
        # from measuring 60 vs 191 tokens on 0.5B/1B models, where the difference vanished into
        # per-request overhead. On a real model it does not: this prompt takes gemma3:4b from
        # 1.006 s to 3.020 s, which is why gemma3 cannot be the live advisor despite scoring
        # better. qwen2.5 7B holds 0.590 s p50 with it, with a 0.823 s tail -- hence the timeout
        # default below.
        prompt = (
            "Clash Royale, HOG EQ CYCLE deck (2.75 average cost). This deck wins by CONSTANT "
            "PRESSURE: cycle back to the Hog Rider and send it at the BRIDGE again and again, "
            "defending for less than the opponent spends. Banking elixir is WRONG here -- a "
            "quiet enemy board is the attack window, not a reason to wait.\n\n"
            "STEP 1 -- MUST ANYTHING BE ANSWERED? Your tower kills small things alone: a lone "
            "Skeletons, Spear Goblins, Goblins, Bats or Ice Spirit deserves NOTHING. Answer "
            "only: a win condition (Hog, Giant, Balloon, Miner, Ram Rider, Graveyard), a tank, "
            "THREE OR MORE units together, an elixir collector (earthquake it), or a building "
            "that will pull your Hog.\n\n"
            "STEP 2 -- NOTHING TO ANSWER? Then 'hold' is almost always WRONG:\n"
            "- 4+ elixir: hog_rider at the bridge. After a defence send it the SAME lane behind "
            "your surviving troops; the instant they commit a tank in the back or a pump, send "
            "it the OPPOSITE lane.\n"
            "- under 4: cycle skeletons or ice_spirit in the back rather than leak at 10.\n"
            "- 'hold' ONLY below 3 elixir, or while their fresh full Hog counter (building or "
            "Mini Pekka in cycle) makes a commitment punishable.\n\n"
            "STEP 3 -- DEFENDING: cheapest card that works.\n"
            "skeletons 1: distract/surround, reset a charge, kite a dash unit to the CENTRE.\n"
            "ice_spirit 1: freeze a push for a beat; escort the Hog (freeze the defender = an "
            "extra hit).\n"
            "the_log 2: THREE OR MORE ground swarm, strip a shield, knock a unit into your "
            "defender. Cannot hit air.\n"
            "earthquake 3: THEIR BUILDING, cast to clip their tower too; every pump on sight; "
            "X-Bow setups. Never on air, never alone on a full Inferno Tower, rarely on defence "
            "(the 50%% slow on a big ground push, in a pinch).\n"
            "firecracker 3: air and grouped pushes, from DEPTH behind your line -- never at the "
            "bridge; kite melee chasers 4-6 tiles from the bridge, staggered to the other lane.\n"
            "tesla 4: THE answer to their win condition -- it pulls and SURVIVES. Centre, 3 "
            "tiles from the river; 1 tile from the river against Earthquake decks.\n"
            "mighty_miner 4: melts tanks (damage ramps on ONE target); place him ON the tank "
            "with skeletons distracting. Useless against swarms.\n"
            "mighty_miner_ability 1: pop it when he is swarmed, to dodge a spell, or to swap "
            "lanes and lead a counter-attack.\n"
            "hog_rider 4: the win condition. BRIDGE ONLY, never from the back.\n\n"
            "Never spend more than the push cost. Space defenders so ONE enemy spell cannot hit "
            "two of them.\n\n"
            "%s\nHAND: %s\nELIXIR: %.0f/10\n\n%s"
            % (situation, ", ".join(hand), elixir,
               "List the cards to play IN ORDER, one if one is enough, or just hold." if plan
               else "Pick the single best card, or hold to play nothing.")
        )
        # "hold" IS AN ANSWER. The schema used to be enum=hand, which made declining to play
        # structurally impossible: the prompt said "or hold" and the grammar forbade it, so on
        # every exploration step the model was forced to name a card even when the board deserved
        # none. That is exactly the reported failure -- cards spammed at an empty board -- and no
        # amount of prompt wording could fix a constraint in the grammar.
        opts = list(hand) + [HOLD]
        schema = ({"type": "object",
                   "properties": {"cards": {"type": "array", "minItems": 1, "maxItems": 3,
                                            "items": {"type": "string", "enum": opts}}},
                   "required": ["cards"]}
                  if plan else
                  {"type": "object",
                   "properties": {"card": {"type": "string", "enum": opts}},
                   "required": ["card"]})
        body = json.dumps({"model": self.model,
                           "messages": [{"role": "user", "content": prompt}],
                           "format": schema, "stream": False, "keep_alive": "60m",
                           "options": {"temperature": 0.0, "num_predict": 48 if plan else 16}})
        self.calls += 1
        t0 = time.time()
        try:
            c = self._connection()
            c.request("POST", "/api/chat", body=body,
                      headers={"Content-Type": "application/json"})
            raw = c.getresponse().read()
            msg = json.loads(json.loads(raw)["message"]["content"])
            got = msg.get("cards") if plan else [msg.get("card")]
        except Exception as e:  # noqa: BLE001
            # Any failure at all: drop the connection so the next call starts clean, and let the
            # caller fall back. A live loop must never wait on this.
            self._reset()
            self._note_fail("%s: %s" % (type(e).__name__, e))
            self.total_s += time.time() - t0
            return []
        self.total_s += time.time() - t0
        out = []
        for c_ in (got or []):
            if c_ == HOLD:
                out = [HOLD]                  # a decision, and it ends the sequence
                break
            if c_ in hand and c_ not in out:
                out.append(c_)
        if out:
            self.hits += 1
            self._streak = 0
            return out
        self._note_fail("reply outside the hand: %r" % (got,))
        return []

    def _note_fail(self, why):
        self.fails += 1
        self.last_error = why
        self._streak += 1
        if self._streak >= self.max_consecutive_fails:
            self.disabled = True

    def warmup(self, seconds: float = 60.0):
        """Force the model into VRAM before the match starts, and report reachability.

        The FIRST call to a cold model pays its load -- seconds for a 4.7 GB 7B -- which is far
        past the in-match budget. Without this the opening exploration steps of every session all
        time out, and five of them in a row would trip the circuit breaker and disable the advisor
        for the rest of the run: it would look exactly like a broken advisor while being nothing
        but a cold one. Measured: a startup probe at the 0.9 s in-match budget FAILED against a
        model that answers in 0.59 s once resident.

        Returns the answer, or None if the model really is unreachable. Session counters are reset
        afterwards so the warm-up does not colour the stats.
        """
        keep, self.timeout = self.timeout, float(seconds)
        self._reset()                     # the pooled connection carries the old, short timeout
        try:
            got = self.suggest("ENEMY: nothing recognised on your half.",
                               ["skeletons", "the_log"], 10)
        finally:
            self.timeout = keep
            self._reset()
            self.calls = self.hits = self.fails = 0
            self.total_s = 0.0
            self._streak = 0
            self.disabled = False
        return got

    # -- reporting ------------------------------------------------------
    def stats(self) -> str:
        if not self.calls:
            return "llm-advisor: no calls"
        return ("llm-advisor %s: %d calls, %d answered (%.0f%%), %d failed, mean %.0f ms%s%s"
                % (self.model, self.calls, self.hits, 100.0 * self.hits / self.calls,
                   self.fails, 1000.0 * self.total_s / self.calls,
                   " [DISABLED after %d consecutive failures]" % self.max_consecutive_fails
                   if self.disabled else "",
                   "" if not self.last_error else ", last error %s" % self.last_error))

    def close(self):
        self._reset()

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



def _parse_card(text, hand):
    """Lenient read of a FREE-TEXT reply (the fast path sends no JSON schema).

    Accepts `tornado`, `"tornado"`, `Tornado.`, `play tornado`; longest names are matched first so
    `tesla_evo` never reads as `tesla`. Anything unrecognised is returned as-is and rejected by the
    caller's hand check -- a wrong word must fail loudly to the fallback, not silently pick a card.
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    first = raw.splitlines()[0].strip().strip('"').strip("'")
    t = first.lower().replace(" ", "_").strip(".,;:!?'\"")
    if t == HOLD or t in hand:
        return t
    low = raw.lower().replace(" ", "_")
    for c in sorted(list(hand) + [HOLD], key=len, reverse=True):
        if c in low:
            return c
    return t


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
        # ...and how long it rests before trying again (see _note_fail).
        self.cooldown_s = float(g("train", "llm_advisor_cooldown_s", default=30.0) or 30.0)
        self.cooldown_max_s = float(g("train", "llm_advisor_cooldown_max_s", default=300.0) or 300.0)
        self._cooldown_until = 0.0
        self._cooldowns = 0

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
        answered by any single card in an icebow hand; it is answered by Tesla to hold the Giant
        and then Log or Ice Wizard for the support. Asking "the single best card" cannot express
        that, and worse, it distorts the FIRST card too: the best opener of a good two-card defence
        is frequently not the best card considered alone (Knight first only makes sense if the Log
        is coming behind it).

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
        if self._cooldown_until and time.time() < self._cooldown_until:
            return []                     # resting after a failure streak; costs the loop nothing
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
            "Clash Royale, ICEBOW deck (X-Bow control). Win by defending for LESS elixir than the "
            "attack cost, then chipping with the X-Bow.\n\n"
            "STEP 1 -- IS IT WORTH A CARD? Your tower kills small things by itself. If the enemy "
            "board is only a lone Skeletons, Spear Goblins, Goblins, Bats, Bomber, Guards, Ice "
            "Wizard or Dart Goblin, answer 'hold' and spend NOTHING -- logging a lone Skeletons is "
            "a textbook waste. Spend a card ONLY on: a tank, a win condition (Hog, Giant, Royal "
            "Giant, Balloon, Graveyard, Miner, Ram Rider), THREE OR MORE units together, an elixir "
            "collector, or something that outranges your tower (Princess, Mortar, X-Bow).\n\n"
            "STEP 2 -- CHEAPEST CARD THAT ACTUALLY WORKS:\n"
            "skeletons 1: distract a tank, reset a charge.\n"
            "the_log 2: THREE OR MORE ground swarm units, or reset a charge, or a tombstone at "
            "half health. Cannot hit air. NOT for one or two small units.\n"
            "ice_wizard 3: slow a whole group. knight 3: body-block one ground attacker.\n"
            "tornado 3: bunch enemies for splash, drag an attacker into your own King Tower to "
            "wake it, or pull defenders off your bow. Barely moves a Giant or Golem -- a TANK in "
            "front of a Hog means rocket, not tornado.\n"
            "tesla 4: THE answer to a committed push -- it pulls and SURVIVES. Use it on tanks "
            "and win conditions.\n"
            "rocket 6: 4+ elixir of GROUPED support, a FRESH elixir collector, or the weaker "
            "tower in overtime. Never on cheap bodies, never on their King.\n"
            "ALSO rocket when knight AND tesla are both OUT of hand and a 4+ elixir enemy is "
            "in your half, or when stopping the push needs 7+ elixir of chained cards -- but "
            "only if the target dies (not a royal giant, not a shield) and you can still "
            "defend. Giant skeleton wants the tesla.\n"
            "THEY ARE BUILDING IN THE BACK (a tank or support parked behind their towers, "
            "nothing across the river yet)? That is NOT a quiet board. With a full bar the "
            "offensive bow is blocked by a push that is already paid for -- play the x_bow "
            "BEHIND THE BRIDGE IN THE CENTRE instead, a defensive bow that shreds the push as it "
            "lands.\n"
            "x_bow 6: the win condition, NOT a defence -- only on a quiet board with 6+ elixir, "
            "never into a committed push, and NEVER a defensive/mid-map bow against a rocket "
            "deck (they rocket the bow, then your tower).\n\n"
            "AIR TRUTH: balloon, lava_hound, minions, mega_minion, bats and every dragon FLY. "
            "knight, skeletons, the_log and x_bow can NEVER touch a flying unit. Air is answered "
            "by tesla, ice_wizard, tornado -- or rocket only on a GROUPED air push.\n"
            "wall_breakers: the_log or skeletons the moment they cross. NEVER rocket them "
            "(6 elixir for their 2).\n\n"
            "Read the push as a whole: a tank with support wants the building for the tank AND an "
            "answer for the support. Defence is minimising damage, not preventing it -- never "
            "spend more elixir than the push cost.\n\n"
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
        # FAST PATH for the single-card question (2026-08-19, measured): the JSON object costs 10
        # generated tokens where the bare name costs 3, and at ~44 ms/token that difference alone
        # is what pushed p50 (0.855 s) past the 0.90 s budget and made the advisor time out. Free
        # text + the hand validation below measures p50 0.400 s with identical answers. The PLAN
        # path keeps the schema: a multi-card sequence needs the structure, and it is off by
        # default anyway.
        if plan:
            body = json.dumps({"model": self.model,
                               "messages": [{"role": "user", "content": prompt}],
                               "format": schema, "stream": False, "keep_alive": "60m",
                               "options": {"temperature": 0.0, "num_predict": 48}})
        else:
            body = json.dumps({"model": self.model,
                               # WORDING IS LOAD-BEARING, measured on the 13 engine-verified
                               # cases: this exact line scores 11/13, while ending it with
                               # "...or hold" scores 3/13 -- the model then holds 11 times, because
                               # the last words of a prompt pull hard -- and appending nothing at
                               # all scores 0/13 (it answers in prose the parser cannot read).
                               # Do not "tidy" this line.
                               "messages": [{"role": "user", "content": prompt
                                             + "\nAnswer with the card name only."}],
                               "stream": False, "keep_alive": "60m",
                               "options": {"temperature": 0.0, "num_predict": 6,
                                           "stop": ["\n"]}})
        self.calls += 1
        t0 = time.time()
        try:
            c = self._connection()
            c.request("POST", "/api/chat", body=body,
                      headers={"Content-Type": "application/json"})
            raw = c.getresponse().read()
            content = json.loads(raw)["message"]["content"]
            if plan:
                got = json.loads(content).get("cards")
            else:
                got = [_parse_card(content, hand)]
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
            self._cooldowns = 0           # one good answer clears the backoff entirely
            self._cooldown_until = 0.0
            return out
        self._note_fail("reply outside the hand: %r" % (got,))
        return []

    def _note_fail(self, why):
        self.fails += 1
        self.last_error = why
        self._streak += 1
        if self._streak >= self.max_consecutive_fails:
            # COOLDOWN, NOT DEATH (2026-08-19). This used to set disabled=True for the whole
            # session: with a budget the model was only just missing, five consecutive timeouts
            # arrived within the first handful of exploration steps and EVERY later decision fell
            # back to a uniform-random card -- the reported "advisor keeps timing out so the model
            # plays randomly". Resting is right (a dead server costs ~510 ms per call to rediscover
            # and the bot is blind for it); never trying again is not. Backoff doubles per relapse
            # so a genuinely dead server is still only probed occasionally.
            self._cooldowns += 1
            rest = min(self.cooldown_s * (2 ** (self._cooldowns - 1)), self.cooldown_max_s)
            self._cooldown_until = time.time() + rest
            self._streak = 0

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
            self._cooldown_until = 0.0
            self._cooldowns = 0
        return got

    # -- reporting ------------------------------------------------------
    def stats(self) -> str:
        if not self.calls:
            return "llm-advisor: no calls"
        return ("llm-advisor %s: %d calls, %d answered (%.0f%%), %d failed, mean %.0f ms%s%s"
                % (self.model, self.calls, self.hits, 100.0 * self.hits / self.calls,
                   self.fails, 1000.0 * self.total_s / self.calls,
                   (" [DISABLED]" if self.disabled else
                    " [resting %.0fs after %d consecutive failures]"
                    % (max(0.0, self._cooldown_until - time.time()), self.max_consecutive_fails)
                    if self._cooldown_until > time.time() else ""),
                   "" if not self.last_error else ", last error %s" % self.last_error))

    def close(self):
        self._reset()

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
    def suggest(self, situation: str, hand: list, elixir: float):
        """Return a card name from ``hand``, or None. None means "caller decides as usual"."""
        if not hand or self.disabled:
            return None
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
            "Clash Royale, ICEBOW deck (X-Bow control). Apply this doctrine:\n"
            "- x_bow: the win condition and your tower damage. Do NOT plant it into a push that is "
            "already committed -- it dies before it fires.\n"
            "- tesla: the defensive building; it pulls attackers and SURVIVES, so it is the answer "
            "to a committed push.\n"
            "- ice_wizard: slows a whole group at once. knight: cheap mini-tank, bodies-blocks.\n"
            "- skeletons: 1 elixir -- distract a tank so your defence gets free seconds, reset a "
            "charge, or cycle.\n"
            "- the_log: clears cheap GROUND swarms and resets charges; CANNOT hit air. Always log "
            "a tombstone at half health.\n"
            "- rocket: only on 4+ elixir support, a FRESH elixir collector, or chipping the weaker "
            "tower in overtime. NEVER on cheap bodies a 1-3 cost card handles. Never on their KING.\n"
            "- tornado: bunch enemies for splash, drag an attacker into your own King Tower to wake "
            "it, or pull defenders off your bow. It barely moves a Giant or Golem -- if a TANK is "
            "in front of a Hog, use ROCKET, not tornado.\n\n"
            "%s\nHAND: %s\nELIXIR: %.0f/10\n\nPick the single best card to play now."
            % (situation, ", ".join(hand), elixir)
        )
        schema = {"type": "object",
                  "properties": {"card": {"type": "string", "enum": list(hand)}},
                  "required": ["card"]}
        body = json.dumps({"model": self.model,
                           "messages": [{"role": "user", "content": prompt}],
                           "format": schema, "stream": False, "keep_alive": "60m",
                           "options": {"temperature": 0.0, "num_predict": 16}})
        self.calls += 1
        t0 = time.time()
        try:
            c = self._connection()
            c.request("POST", "/api/chat", body=body,
                      headers={"Content-Type": "application/json"})
            raw = c.getresponse().read()
            got = json.loads(json.loads(raw)["message"]["content"]).get("card")
        except Exception as e:  # noqa: BLE001
            # Any failure at all: drop the connection so the next call starts clean, and let the
            # caller fall back. A live loop must never wait on this.
            self._reset()
            self._note_fail("%s: %s" % (type(e).__name__, e))
            self.total_s += time.time() - t0
            return None
        self.total_s += time.time() - t0
        if got in hand:
            self.hits += 1
            self._streak = 0
            return got
        self._note_fail("reply outside the hand: %r" % (got,))
        return None

    def _note_fail(self, why):
        self.fails += 1
        self.last_error = why
        self._streak += 1
        if self._streak >= self.max_consecutive_fails:
            self.disabled = True

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

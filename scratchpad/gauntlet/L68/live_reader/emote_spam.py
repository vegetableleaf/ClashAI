"""--emote-spam (L74, owner 2026-10-10; reactive since owner 2026-10-14): emotes / quick-chat phrases on the card-tap channel.

Calibrated live (Classic 1v1, 900x1600): chat button (88, 1365) opens a panel over the HAND AREA (2 x 4 emotes above
3 x 2 quick-chat phrases, measured on the lead's 10-10 screenshot; the bottom-right emote at (710, 1195) was tapped live).
Tapping an emote or phrase sends it and closes the panel. The game's cooldown is 1.3 s; --emote-interval-s (3.0 live)
spaces EVERY emote, reaction or idle, on one shared clock. live_play wires the clock to its tap channel.

Owner 2026-10-14 reactions (Reactions): match start "Good luck!" then the bottom-left emote; 800+ damage on one own tower
in a push -> bottom 3rd; own tower lost -> top-left; enemy tower taken -> bottom 2nd or "Well played!"; opponent plays a
7+ elixir card -> "Wow!" or top 2nd; own X-Bow locks an enemy tower -> "Thanks!" or top 3rd; match end: win -> bottom-right,
loss -> top-right. Otherwise, during WAIT, a random one of the 8 emotes with probability --emote-idle-p per second.
"""
import math
import random
import time


CHAT_XY, SCREEN = (88, 1365), (900, 1600)
EMOTES = {"tl": (234, 1060), "t2": (393, 1060), "t3": (551, 1060), "tr": (710, 1060),
          "bl": (234, 1195), "b2": (393, 1195), "b3": (551, 1195), "br": (710, 1195)}
PHRASES = {"good_luck": (293, 1382), "well_played": (530, 1382), "wow": (765, 1382), "thanks": (293, 1468)}
TARGETS = {**EMOTES, **PHRASES}
# event -> alternatives (equal probability); an alternative is a sequence, sent one per interval
REACTIONS = {"start": [("good_luck", "bl")], "tower_damage": [("b3",)], "tower_lost": [("tl",)],
             "tower_taken": [("b2",), ("well_played",)], "big_card": [("wow",), ("t2",)],
             "xbow_lock": [("thanks",), ("t3",)], "win": [("br",)], "loss": [("tr",)]}
HOLD_S = 0.6          # card taps wait until this long after an emote's first tap: the panel is closed by then
MIN_INTERVAL_S = 1.3  # the game's emote cooldown
IDLE_ROLL_S = 1.0     # idle emotes: one roll per second of eligible WAIT
STALE_S = 8.0         # a queued reaction not sent within this long is dropped
PUSH_DMG, PUSH_GAP_TICKS = 800, 100   # one own tower loses 800+ HP with no gap > 5 s between hits
BIG_CARD = 7.0
KING, PRINCESS = 12, 13               # crown towers: card_id -1 and these kinds (pipeline/live_mem.py)
XBOW_REACH = {KING: 13500, PRINCESS: 13000}   # X-Bow range 11.5 tiles + the tower's half size, raw units (1 tile = 1000)
LOCK_HITS, LOCK_TICKS = 3, 40         # ponytail: no target ids in the reader -> "lock" = the tower lost HP on >= 3 frames
                                      # in 2 s while an own X-Bow reaches it; a troop hitting it too can trigger it


def emote_due(now, last_t, interval_s, play, busy, p_play, tau, guard):
    """True = send an emote at this decision. play: the model decided to play (not WAIT); busy: a follow-up / pending
    play / ability tap is outstanding; guard x tau: skip when the model is close to playing (0 = no guard)."""
    if play or busy or now - last_t < interval_s:
        return False
    return not (guard > 0 and p_play >= guard * tau)


def hold_s(now, last_t):
    """Seconds a card tap must still wait after an emote whose first tap was at last_t."""
    return max(0.0, last_t + HOLD_S - now)


def emote_cmd(w, h, gap_ms, target="br"):
    """The two-tap shell command (chat button, then the emote / phrase), scaled to the screen like Layout does."""
    (cx, cy), (ex, ey) = [(round(x * w / SCREEN[0]), round(y * h / SCREEN[1])) for x, y in (CHAT_XY, TARGETS[target])]
    sleep = f" sleep {gap_ms / 1000:g};" if gap_ms > 0 else ""
    return f"input tap {cx} {cy};{sleep} input tap {ex} {ey}"


class EmoteClock:
    """One clock for the serial live input channel, retained across matches.

    An attempt is dispatch of the whole chat + emote command, not each constituent
    tap. Device execution times are unknown; measure host dispatch with monotonic.
    """

    def __init__(self):
        self.last_t = float("-inf")

    def ready(self, interval_s, *, busy, p_play, tau, guard):
        return emote_due(time.monotonic(), self.last_t, interval_s, False, busy, p_play, tau, guard)

    def fire(self, send, cmd):
        self.last_t = time.monotonic()                 # before dispatch, never rolled back on failure
        return send(cmd)                               # no logging / other blocking work before the attempt

    def attempt(self, send, cmd, interval_s, *, busy, p_play, tau, guard):
        """None = skipped; otherwise return send's success. Failures consume the interval."""
        if not self.ready(interval_s, busy=busy, p_play=p_play, tau=tau, guard=guard):
            return None
        return self.fire(send, cmd)

    def wait_s(self, interval_s):
        return max(0.0, self.last_t + interval_s - time.monotonic())

    def hold(self):
        return hold_s(time.monotonic(), self.last_t)


class Reactions:
    """Per match: board events -> queued emotes (owner 2026-10-14), and the idle roll."""

    def __init__(self, idle_p, rng=None, xbow_ids=(27000008,)):
        self.idle_p, self.rng, self.xbow_ids = idle_p, rng or random.Random(), set(xbow_ids)
        self.queue = []                                # [kind, target, queued monotonic], oldest first
        self.started, self.next_roll = False, float("-inf")
        self.hp, self.acc, self.last_hit, self.hits = {}, {}, {}, {}
        self.alive, self.drop = None, {0: 0, 1: 0}
        self.locked, self.n_plays, self.towers, self.side = set(), 0, [], None

    def push(self, kind, now):
        if any(q[0] == kind for q in self.queue):
            return
        if kind == "tower_lost":                       # the loss says it; drop a queued damage reaction
            self.queue = [q for q in self.queue if q[0] != "tower_damage"]
        self.queue += [[kind, t, now] for t in self.rng.choice(REACTIONS[kind])]

    def pick(self, now):
        """(kind, target) to send now: the oldest queued reaction, else an idle roll; None = nothing."""
        self.queue = [q for q in self.queue if now - q[2] <= STALE_S]
        if self.queue:
            kind, target, _ = self.queue.pop(0)
            return kind, target
        if now < self.next_roll:
            return None
        self.next_roll = now + IDLE_ROLL_S
        return ("idle", self.rng.choice(tuple(EMOTES))) if self.rng.random() < self.idle_p else None

    def observe(self, f, side, tick, plays, now):
        """One active single-hand frame. plays: the public observer's opponent plays this match (dicts with 'card')."""
        self.side = side
        if not self.started:
            self.started = True
            self.push("start", now)
        towers = [e for e in f["entities"] if e.get("card_id") == -1 and e.get("kind") in (KING, PRINCESS)]
        self.towers = towers
        for e in towers:
            a, hp = e["address"], e["hp"]
            prev, self.hp[a] = self.hp.get(a), hp
            if prev is None or hp >= prev:
                continue
            self.hits[a] = [k for k in self.hits.get(a, []) if tick - k <= LOCK_TICKS] + [tick]
            if e["side"] == side:
                if tick - self.last_hit.get(a, -10 ** 9) > PUSH_GAP_TICKS:
                    self.acc[a] = 0
                before = self.acc.get(a, 0)
                self.acc[a], self.last_hit[a] = before + prev - hp, tick
                if before < PUSH_DMG <= self.acc[a]:
                    self.push("tower_damage", now)
        kings = [e for e in towers if e["kind"] == KING and e["hp"] > 0]
        if len({e["side"] for e in kings}) == 2:       # both kings seen: a missing princess is a real loss, not a glitch
            alive = {s: sum(e["side"] == s and e["kind"] == PRINCESS and e["hp"] > 0 for e in towers) for s in (0, 1)}
            self.alive = self.alive or alive
            for s in (0, 1):
                self.drop[s] = self.drop[s] + 1 if alive[s] < self.alive[s] else 0
                if self.drop[s] >= 3:                  # 3 frames in a row
                    self.push("tower_lost" if s == side else "tower_taken", now)
                    self.alive[s], self.drop[s] = alive[s], 0
        if len(plays) < self.n_plays:                  # the observer restarted
            self.n_plays = 0
        if any((card_cost(p.get("card")) or 0) >= BIG_CARD for p in plays[self.n_plays:]):
            self.push("big_card", now)
        self.n_plays = len(plays)
        for x in f["entities"]:
            if x["side"] != side or x.get("card_id") not in self.xbow_ids or x["hp"] <= 0 or x["address"] in self.locked:
                continue
            if any(t["side"] != side and t["hp"] > 0 and len(self.hits.get(t["address"], [])) >= LOCK_HITS
                   and tick - self.hits[t["address"]][-LOCK_HITS] <= LOCK_TICKS
                   and math.hypot(t["x"] - x["x"], t["y"] - x["y"]) <= XBOW_REACH[t["kind"]] for t in towers):
                self.locked.add(x["address"])
                self.push("xbow_lock", now)

    def result(self):
        """'win' / 'loss' / None from the last single-hand frame's towers: crowns, then the lowest tower HP on a tie."""
        if self.side is None or not self.towers:
            return None
        up = {s: [e["hp"] for e in self.towers if e["side"] == s and e["hp"] > 0] for s in (0, 1)}
        mine, theirs = up[self.side], up[1 - self.side]
        diff = len(mine) - len(theirs)
        if diff == 0 and mine and theirs:
            diff = min(mine) - min(theirs)
        return "win" if diff > 0 else "loss" if diff < 0 else None


def card_cost(card):
    from pipeline.opp_elixir_count import card_cost as cost   # lazy: live_play has the repo root on sys.path
    return cost(card) if card else None


CLOCK = EmoteClock()                                   # shared by every live match and both input transports

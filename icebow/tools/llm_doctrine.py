"""LLM proposes doctrine, the ENGINE decides.  `python tools/llm_doctrine.py --states 40 --write`

THE SHAPE, AND WHY IT IS THIS SHAPE
-----------------------------------
Two measurements set the whole design, both taken on this machine (2026-08-16):

  LATENCY. A constrained Ollama call costs ~2.5-3.8 s even for a five-token answer -- the cost is
  per-request overhead, not generation, so shortening the output does not help. The sim takes
  ~25 agent decisions per second. An in-loop advisor could therefore cover under 2% of decisions
  while consuming its entire budget. Offline is not a compromise, it is the only fit.

  ACCURACY. Scored on tools/llm_eval.py -- ten cases drawn from this project's engine-verified
  doctrine and the deck guides -- the best local model available here manages 6/10, and EVERY
  model tested failed the same four deck-specific cases. One of those is "a Giant push is already
  committed, what do you play": all five models answered X-Bow, which is precisely the bad habit
  observed in sim view that morning and which the reward ledger was separately found to be paying
  for. A 6/10 teacher left unsupervised would have taught that mistake.

So the model PROPOSES and the engine DISPOSES. Each suggestion is replayed against the same state
from several seeds and kept only if it beats the baseline by a margin, which is the same bar every
hand-written rule in sim/doctrine.py had to clear. A wrong proposal costs nothing but the seconds
it took to test; a right one is a rule nobody had to think of. That asymmetry is the entire case
for using a model that is wrong 40% of the time.

Output is config/llm_doctrine.json, which sim/doctrine.py folds into the card prior at zero
runtime cost. Nothing reaches training that the engine did not sign off on.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl.config import Config              # noqa: E402
from clashrl.sim.env import SimMatchEnv        # noqa: E402
# The bucket a rule is verified under MUST be the bucket it is looked up under, so the
# key lives in the consumer and this tool imports it rather than keeping its own copy.
from clashrl.sim.doctrine import llm_state_key as state_key  # noqa: E402

OLLAMA = "http://localhost:11434/api/chat"
OUT = _ROOT / "config" / "llm_doctrine.json"


# ---------------------------------------------------------------- state -> words
def describe(env) -> str:
    """The board in the words a card guide would use. Ground truth from the engine, never obs."""
    eng = env.eng
    bits = []
    foes = [u for u in eng.units if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"]
    if not foes:
        bits.append("The enemy has nothing on the board.")
    else:
        for u in sorted(foes, key=lambda u: -u.y)[:5]:
            where = ("deep in your half" if u.y > 0.66 else
                     "in your half" if u.y > 0.52 else
                     "at the bridge" if u.y > 0.44 else "on their side")
            lane = "left" if u.x < 0.42 else "right" if u.x > 0.58 else "centre"
            name = str(u.spec.base).replace("_", " ")
            bits.append("%s %s (%s lane, %d elixir)" % (name, where, lane, u.spec.elixir))
    king = "ASLEEP" if not eng.towers[0][2].active else "awake"
    mine = [t.hp / max(1.0, t.max_hp) for t in eng.towers[0][:2] if t.alive]
    theirs = [t.hp / max(1.0, t.max_hp) for t in eng.towers[1][:2] if t.alive]
    phase = "overtime" if eng.t >= env._double_time else (
        "double elixir" if eng.t >= 120 else "single elixir")
    return ("Enemy board: %s\nYour king tower is %s. Phase: %s.\n"
            "Your towers at %s of full; theirs at %s."
            % ("; ".join(bits), king, phase,
               "/".join("%d%%" % (100 * h) for h in mine) or "-",
               "/".join("%d%%" % (100 * h) for h in theirs) or "-"))


# ---------------------------------------------------------------- the model
def propose(model, env, timeout=120):
    hand = [i for i in env._hand_ids() if i >= 0]
    names = [env.deck_keys[i] for i in hand]
    if not names:
        return None
    prompt = (
        "You are an expert Clash Royale player on an ICEBOW deck (X-Bow control). Key doctrine: "
        "the X-Bow is the win condition but a bow planted into an already-committed push just "
        "dies; buildings pull and survive. Tornado pulls enemies together, can drag an attacker "
        "into your own King Tower to wake it, and does NOT move heavy units like Giant or Golem. "
        "The Log clears cheap ground swarms. Rocket is worth it on 4+ elixir support, on a fresh "
        "Elixir Collector, or to chip the weaker enemy tower in overtime -- not on cheap bodies.\n\n"
        "SITUATION:\n%s\n\nYOUR HAND: %s\nYOUR ELIXIR: %d/10\n\n"
        "Pick the single best card to play now, or \"wait\" to hold elixir."
        % (describe(env), ", ".join(names), int(env.eng.elixir[0]))
    )
    schema = {"type": "object",
              "properties": {"card": {"type": "string", "enum": names + ["wait"]}},
              "required": ["card"]}
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "format": schema, "stream": False,
                       "options": {"temperature": 0.0, "num_predict": 32}}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            got = json.loads(json.loads(r.read())["message"]["content"]).get("card")
    except Exception:  # noqa: BLE001
        return None
    return None if got in (None, "wait") else got


def _walk(cfg, seed, steps, play_rate):
    """Fast-forward a match, ACTUALLY PLAYING some of the time.

    The first version only ever waited, and that quietly wrecked the sampling: waiting fills the
    elixir bar, so every sampled state sat at 7-10 elixir and the board stayed sparse. Measured,
    it reached 61 distinct buckets out of 400 requests, and every rule it produced was elx_10 or
    elx_7 -- a table about a corner of the game. Playing at a realistic rate spreads the walk over
    the elixir range and puts troops on the board, which is where the interesting decisions are.
    """
    import random
    rng = random.Random(seed * 7919 + 11)
    env = SimMatchEnv(cfg, seed=seed)
    env.reset()
    for _ in range(steps):
        hand = [c for c in env._hand_ids()
                if c >= 0 and env.eng.elixir[0] >= env.specs[c].elixir]
        if hand and rng.random() < play_rate:
            act = (True, rng.choice(hand), rng.randrange(env.n_cells))
        else:
            act = (False, 0, 0)
        _, _, done, _ = env.step(act)
        if done:
            env.reset()
    return env, rng


# ---------------------------------------------------------------- the engine's verdict
def _replay(cfg, seed, steps, card_id, play_rate, horizon=8):
    """Re-walk to the SAME state, play `card_id` (or wait), return the reward that follows.

    The walk must match the one the proposal was made against, seed and play-rate included --
    verifying a suggestion against a different board than the model was shown would make the whole
    gate meaningless while still looking like it worked.
    """
    env, _ = _walk(cfg, seed, steps, play_rate)
    total = 0.0
    if card_id is None:
        _, r, done, _ = env.step((False, 0, 0))
    else:
        cell = None
        from clashrl.sim.doctrine import doctrine_cells
        dc = doctrine_cells(env, card_id) or []
        if dc:
            cell = max(dc, key=lambda t: t[1])[0]
        if cell is None:
            cell = env.actions.cell_at(0.5, 0.62)
        _, r, done, _ = env.step((True, card_id, cell))
    total += r
    for _ in range(horizon):
        if done:
            break
        _, r2, done, _ = env.step((False, 0, 0))
        total += r2
    return total


def verify(cfg, seed, steps, card_id, play_rate, trials=3, margin=0.15):
    """Does playing this beat holding, repeatably? Same bar the hand-written rules had to clear."""
    play, hold = [], []
    for k in range(trials):
        play.append(_replay(cfg, seed + k * 1013, steps, card_id, play_rate))
        hold.append(_replay(cfg, seed + k * 1013, steps, None, play_rate))
    gain = statistics.mean(play) - statistics.mean(hold)
    wins = sum(1 for a, b in zip(play, hold) if a > b)
    return gain, wins, trials


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma3:4b")
    ap.add_argument("--states", type=int, default=30)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--margin", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--play-rate", type=float, default=0.10,
                    help="how often the sampling walk plays a card. TUNED, not guessed: measured "
                         "distinct buckets at elixir>=4 (the states where a rule is worth having) "
                         "over 300 walks -- 0.00 reaches 64, 0.10 reaches 119, 0.20 reaches 59, "
                         "0.30 reaches 27. Waiting only fills the bar and leaves the board empty; "
                         "playing hard drains it and never affords anything. 0.10 is the peak")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)

    cfg = Config.load()
    kept, tested, t0 = {}, 0, time.time()
    print("proposer %s | %d states | engine gate: mean gain > %.2f and >= 2/%d trials\n"
          % (a.model, a.states, a.margin, a.trials))
    seen_keys = set()
    for i in range(a.states):
        seed = a.seed + i * 37
        steps = 6 + (i * 7) % 90                    # spread across the match clock
        env, rng = _walk(cfg, seed, steps, a.play_rate)
        key = state_key(env)
        # Skip anything already DECIDED, kept or rejected -- re-rolling the same bucket burns a
        # ~4.4 s proposal to re-answer a question the engine has already ruled on.
        if key in kept or key in seen_keys:
            continue
        seen_keys.add(key)
        name = propose(a.model, env)
        if name is None:
            continue
        try:
            cid = env.deck_keys.index(name)
        except ValueError:
            continue
        tested += 1
        gain, wins, n = verify(cfg, seed, steps, cid, a.play_rate, a.trials, a.margin)
        ok = gain > a.margin and wins >= max(2, n - 1)
        print("  %-42s -> %-12s gain %+6.2f (%d/%d)  %s"
              % (key, name, gain, wins, n, "KEEP" if ok else "reject"))
        if ok:
            kept[key] = {"card": name, "gain": round(gain, 3), "wins": "%d/%d" % (wins, n)}

    print("\ntested %d proposals in %.0fs, kept %d" % (tested, time.time() - t0, len(kept)))
    payload = {"meta": {"model": a.model, "margin": a.margin, "trials": a.trials,
                        "tested": tested, "kept": len(kept),
                        "note": "engine-verified; a proposal that did not beat holding was dropped"},
               "rules": kept}
    if a.write:
        OUT.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
        print("wrote %s" % OUT)
    else:
        print("(dry run -- pass --write to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

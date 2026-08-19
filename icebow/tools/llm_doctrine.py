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
import os
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
        bits.append("nothing")
    else:
        # GROUPED BY CARD. Listing bodies made a Goblin Gang appear as five separate 3-elixir
        # cards, which reads as a 15-elixir push; the model was being told a swarm was a monster.
        groups = {}
        for u in sorted(foes, key=lambda u: -u.y):
            where = ("deep in your half" if u.y > 0.66 else
                     "in your half" if u.y > 0.52 else
                     "at the bridge" if u.y > 0.44 else "on their side")
            lane = "left" if u.x < 0.42 else "right" if u.x > 0.58 else "centre"
            k = (str(u.spec.base).replace("_", " "), where, lane, int(u.spec.elixir))
            groups[k] = groups.get(k, 0) + 1
        for (name, where, lane, cost), n in list(groups.items())[:5]:
            bits.append("%s%s %s (%s lane, %d elixir card)"
                        % (name, " x%d" % n if n > 1 else "", where, lane, cost))
    # YOUR OWN UNITS. Omitting these made every synergy unreachable: a model that cannot see its
    # own Tesla holding a push cannot reason that Skeletons would buy that Tesla another second,
    # and a model that cannot see its own bow cannot know it needs protecting. The first version
    # described only the enemy, which is why the proposals read as isolated card picks.
    allies = [u for u in eng.units if u.team == 0 and u.hp > 0]
    by = {}
    for u in allies:
        nm = str(u.spec.base).replace("_", " ")
        by[nm] = by.get(nm, 0) + 1
    mine_txt = (", ".join("%s%s" % (k, " x%d" % v if v > 1 else "") for k, v in by.items())
                if by else "nothing")
    king = "ASLEEP" if not eng.towers[0][2].active else "awake"
    mine = [t.hp / max(1.0, t.max_hp) for t in eng.towers[0][:2] if t.alive]
    theirs = [t.hp / max(1.0, t.max_hp) for t in eng.towers[1][:2] if t.alive]
    phase = "overtime" if eng.t >= env._double_time else (
        "double elixir" if eng.t >= 120 else "single elixir")
    return ("ENEMY on the board: %s\n"
            "YOUR units already out: %s\n"
            "Your king tower is %s. Phase: %s.\n"
            "Your towers at %s of full; theirs at %s."
            % ("; ".join(bits), mine_txt, king, phase,
               "/".join("%d%%" % (100 * h) for h in mine) or "-",
               "/".join("%d%%" % (100 * h) for h in theirs) or "-"))


def _next_card(env) -> str:
    """The card cycling in after the current hand. Combos are two cards, so whether the second
    half is about to arrive is part of choosing the first -- holding Tornado for a Rocket that is
    four cards away is a different decision from holding it for one that is next."""
    try:
        return env.deck_keys[env._slot_card_id(env.cycle[4])]
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------- the model
def propose(model, env, timeout=120):
    hand = [i for i in env._hand_ids() if i >= 0]
    names = [env.deck_keys[i] for i in hand]
    if not names:
        return None
    # EVERY card gets a line, and they are ROLES rather than "play this when". An earlier prompt
    # described only X-Bow, Tornado, Log and Rocket -- and the model then picked from exactly
    # those four: measured over 40 states, tornado 94% of the times it was offered, log 71%,
    # rocket 67%, while skeletons, ice wizard and tesla were chosen ZERO times out of 40 offers
    # between them. Those three are the deck's whole defensive core, so the table would have
    # taught an all-spell playstyle that never defends. A model picks what it has been told
    # exists, so an omission in this string is a hole in the doctrine it can propose.
    prompt = (
        "You are an expert Clash Royale player on an ICEBOW deck (X-Bow control). The eight cards "
        "and what each is FOR:\n"
        "- x_bow (6): THE WIN CONDITION and your main source of tower damage -- when you can "
        "afford it and the lane is not already full of enemies, putting the bow down is usually "
        "the strongest play in the deck. The one caveat: do not plant it INTO a push that is "
        "already committed, because it dies before it fires.\n"
        "- tesla (4): the main defensive building. It pulls attackers off your towers and "
        "survives; centre placement covers both lanes.\n"
        "- ice_wizard (3): cheap ranged support that SLOWS everything it hits; melts swarms and "
        "buys your buildings time.\n"
        "- knight (3): cheap mini-tank. Bodies-block a push, absorb hits, protect a bow or a "
        "ranged support.\n"
        "- skeletons (1): one elixir. Distract and reset a charging unit, kite a tank, or cycle "
        "back to a key card.\n"
        "- the_log (2): rolls through cheap GROUND swarms, resets charges, knocks back. Cannot "
        "touch air.\n"
        "- rocket (6): big damage. Worth it on 4+ elixir of grouped support, a fresh Elixir "
        "Collector, or the weaker enemy tower in overtime -- and ALSO when knight and tesla "
        "are both out of your hand and a 4+ elixir enemy is already in your half, or when "
        "stopping a push would take 7+ elixir of chained cards. Only if the target actually "
        "dies (never a royal giant, never a shield) and you can still defend afterwards. "
        "Not on cheap bodies, not on their King, and a giant skeleton wants the tesla.\n"
        "- tornado (3): pulls enemies together for splash, drags an attacker into your own King "
        "Tower to wake it, pulls defenders off your bow. Barely moves Giant or Golem.\n\n"
        "\nThis deck wins on COMBINATIONS, not on single cards. A card is often the right play "
        "BECAUSE of what is already on the board:\n"
        "- Skeletons are rarely the whole answer, but they distract a tank so your Tesla or Ice "
        "Wizard gets extra free seconds on it, they add the last damage onto something your "
        "defence is already chewing through, they reset a charge, and they cycle you back to a "
        "key card for 1 elixir.\n"
        "- Tornado + Rocket: the pull bunches a push so one Rocket hits all of it.\n"
        "- Tornado + Ice Wizard: bunch them, then the slow lands on the whole group at once.\n"
        "- Tornado + Tesla: drag a building-targeting attacker into your Tesla's range.\n"
        "- Tornado + X-Bow: pull enemy defenders OFF your bow so it locks onto the tower.\n"
        "- Knight + The Log: the Knight bodies the front of a push, the Log clears the swarm "
        "behind it.\n"
        "- Knight or Skeletons in front of Ice Wizard / Tesla: cheap bodies keep the ranged "
        "damage alive.\n"
        "- Tesla or Knight next to an offensive X-Bow: the bow does nothing if it dies first.\n"
        "- Rocket + The Log: finishing chip on a tower that is nearly down.\n\n"
        "Defence usually wins this deck the game, and defence is usually TWO cards, not one. "
        "Prefer the card that combines with what you already have out.\n\n"
        "SITUATION:\n%s\n\nYOUR HAND: %s\nNEXT CARD AFTER THIS: %s\nYOUR ELIXIR: %d/10\n\n"
        "List up to THREE cards worth playing right now, BEST FIRST. Include a card if it is a "
        "reasonable play, even if you are unsure -- another system tests each one and keeps only "
        "what actually works, so a wrong candidate costs nothing and a missing one costs a rule. "
        "Use \"wait\" only if holding elixir genuinely beats every card in hand."
        % (describe(env), ", ".join(names), _next_card(env), int(env.eng.elixir[0]))
    )
    # A RANKED SHORTLIST, not one pick. Tuning the prompt toward any single card just moved the
    # probability mass around -- pushing X-Bow from 6% to 18% pulled Ice Wizard from 31% to 8% and
    # the Log to zero -- because "name the one best card" forces the model to spend all its
    # confidence in one place. Asking for three candidates converts a CALIBRATION problem the
    # model is bad at into a COVERAGE problem it is good at: it only has to include the right card
    # somewhere in three, and the engine decides which of them actually wins. Measured against the
    # gate, the model's single pick disagreed badly with the engine (it proposed the bow 6% of the
    # time in states where a bow cleared the gate 88% of the time).
    schema = {"type": "object",
              "properties": {"cards": {"type": "array", "minItems": 1, "maxItems": 3,
                                       "items": {"type": "string", "enum": names + ["wait"]}}},
              "required": ["cards"]}
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "format": schema, "stream": False,
                       # num_gpu 0 -> CPU inference when the GPU is owned by a detector
                       # training run (a 3.3 GB model forced into a contested 8 GB card can OOM
                       # the TRAINING process, which costs hours; slow proposals cost nothing).
                       "options": ({"temperature": 0.0, "num_predict": 32, "num_gpu": 0}
                                   if os.environ.get("LLMDOC_CPU") else
                                   {"temperature": 0.0, "num_predict": 32})}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            got = json.loads(json.loads(r.read())["message"]["content"]).get("cards") or []
    except Exception:  # noqa: BLE001
        return []
    out = []
    for c in got:                       # keep order, drop "wait" and duplicates
        if c != "wait" and c in names and c not in out:
            out.append(c)
    return out


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
        shortlist = propose(a.model, env)
        if not shortlist:
            continue
        tested += 1
        # Test every candidate and keep the BEST that clears the bar -- the model supplies breadth,
        # the engine supplies the ranking. This is the point of asking for a shortlist: the model's
        # own ordering was measurably poor (it named the bow 6% of the time in states where a bow
        # cleared the gate 88% of the time), but its top three usually CONTAIN the right card.
        best = None
        for name in shortlist:
            try:
                cid = env.deck_keys.index(name)
            except ValueError:
                continue
            gain, wins, n = verify(cfg, seed, steps, cid, a.play_rate, a.trials, a.margin)
            if gain > a.margin and wins >= max(2, n - 1) and (best is None or gain > best[1]):
                best = (name, gain, wins, n)
        if best is None:
            print("  %-42s -> %-28s all rejected" % (key, "/".join(shortlist)))
        else:
            name, gain, wins, n = best
            rank = shortlist.index(name) + 1
            print("  %-42s -> %-12s gain %+6.2f (%d/%d)  KEEP (their #%d of %d)"
                  % (key, name, gain, wins, n, rank, len(shortlist)))
            kept[key] = {"card": name, "gain": round(gain, 3), "wins": "%d/%d" % (wins, n),
                         "rank": rank}

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

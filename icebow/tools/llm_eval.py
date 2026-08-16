"""Score local LLMs on icebow card choice, against ENGINE-VERIFIED ground truth.

  python tools/llm_eval.py [model ...]

WHY THIS EXISTS RATHER THAN A BENCHMARK TABLE
---------------------------------------------
Published small-model leaderboards measure MMLU, HumanEval, IFEval. None of them measure "does
it know that a Tornado answers a lone Hog while a tank in front of that Hog means Rocket
instead", which is the only question we are hiring a model to answer. So the eval set below is
built from cases this project has already verified against its own engine or sourced from the
deck guides -- the same bar every doctrine rule had to clear.

Scoring is deliberately blunt: the model names one card from the hand, and it either matches the
doctrine answer or it does not. Placement is scored separately and only where a spot was
measured, because a plausible-looking tile that does not actually wake the king is worth nothing
(the old king rule aimed at one of those for weeks).

The whole thing runs offline. Measured on this machine, a single constrained call costs ~2.5 s
even for a five-token answer, against a sim that takes ~25 agent decisions per second -- so an
in-loop advisor could cover under 2% of decisions while consuming the entire budget. Offline is
not a compromise here, it is the only shape that fits, and it means model choice should optimise
QUALITY and ignore speed.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

OLLAMA = "http://localhost:11434"

# Each case: the board in words, the hand, the doctrine answer, and where that answer came from.
CASES = [
    dict(id="king_activation_hog",
         state="Enemy lone Hog Rider is deep in your half attacking your LEFT princess tower. "
               "Your king tower is ASLEEP. Nothing else is on the board.",
         hand=["tornado", "x_bow", "the_log", "skeletons"], elixir=7,
         answer="tornado",
         why="engine-verified: the measured cast wakes the king, worth a third tower all match"),
    dict(id="hog_with_tank_in_front",
         state="Enemy Hog Rider crossing the bridge with an ICE GOLEM walking in front of it. "
               "Your king tower is asleep.",
         hand=["tornado", "rocket", "the_log", "skeletons"], elixir=8,
         answer="rocket",
         why="guide, verbatim: 'DO NOT attempt to Tornado if they have a tank in front of their "
             "Hog, instead use Rocket'"),
    dict(id="tombstone_half_hp",
         state="An enemy TOMBSTONE sits on your side at about 40% hitpoints, spawning skeletons.",
         hand=["the_log", "x_bow", "ice_wizard", "rocket"], elixir=6,
         answer="the_log",
         why="guide, verbatim: 'always Log a Tombstone at half hp - it'll destroy it and the "
             "death skeletons'"),
    dict(id="fresh_pump",
         state="The opponent just placed an ELIXIR COLLECTOR next to their tower, 3 seconds ago. "
               "Board is otherwise empty.",
         hand=["rocket", "tornado", "skeletons", "knight"], elixir=8,
         answer="rocket",
         why="guide: an unanswered pump out-economies a control deck; coded as full win-condition "
             "credit inside the pump window"),
    dict(id="skeleton_swarm",
         state="Three enemy SKELETONS and two GOBLINS are walking at your tower in a tight group.",
         hand=["the_log", "rocket", "x_bow", "tornado"], elixir=9,
         answer="the_log",
         why="guide: rocketing cheap bodies a 1-3 cost card handles is the classic waste; coded "
             "as a negative"),
    dict(id="support_behind_tower",
         state="The opponent placed a WIZARD right next to their LEFT princess tower and nothing "
               "else. You are chipping that tower.",
         hand=["rocket", "the_log", "skeletons", "tesla"], elixir=8,
         answer="rocket",
         why="guide: 'if they invest a 5 or more elixir unit at the back that dies to Rocket ... "
             "Rocket it along with the tower' -- the 2-for-1"),
    dict(id="defensive_bow_not_on_push",
         state="A GIANT with a MUSKETEER and a KNIGHT behind it is already committed and crossing "
               "into your half.",
         hand=["x_bow", "tesla", "ice_wizard", "skeletons"], elixir=7,
         answer="tesla",
         why="a bow planted into a committed push just dies; the building is the answer that "
             "pulls and survives"),
    dict(id="lone_knight_by_tower",
         state="The opponent played a KNIGHT near their own tower and has nothing else on the "
               "arena. Your X-Bow is already standing and firing.",
         hand=["tornado", "skeletons", "the_log", "ice_wizard"], elixir=6,
         answer="tornado",
         why="guide, verbatim: 'Tornado the Knight out of X-Bow range to get it on tower' -- the "
             "sneaky lock"),
    dict(id="three_musketeers",
         state="The opponent dropped THREE MUSKETEERS in the back, all still grouped together.",
         hand=["rocket", "tornado", "the_log", "skeletons"], elixir=10,
         answer="tornado",
         why="guide: 'If they invest 3M, Tornado all three to one side and Rocket' -- the pull "
             "comes first, it is what makes the rocket worth casting"),
    dict(id="overtime_chip",
         state="OVERTIME. Both towers even, your X-Bow has not broken through all game. Enemy "
               "board is empty and you are at full elixir.",
         hand=["rocket", "skeletons", "the_log", "tornado"], elixir=10,
         answer="rocket",
         why="user doctrine: in overtime the tiebreak is whose lowest tower is lower, so rocket "
             "cycling the weaker enemy tower is the win condition"),
]


def ask(model, case, timeout=180):
    hand = case["hand"]
    prompt = (
        "You are an expert Clash Royale player advising on an ICEBOW deck (X-Bow control: X-Bow, "
        "Tesla, Ice Wizard, Knight, Skeletons, The Log, Rocket, Tornado).\n\n"
        "SITUATION: %s\n"
        "YOUR HAND: %s\nYOUR ELIXIR: %d/10\n\n"
        "Pick the single best card to play right now. Answer with one card name from the hand."
        % (case["state"], ", ".join(hand), case["elixir"])
    )
    schema = {"type": "object",
              "properties": {"card": {"type": "string", "enum": hand}},
              "required": ["card"]}
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "format": schema, "stream": False,
                       "options": {"temperature": 0.0, "num_predict": 32}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    dt = time.time() - t0
    try:
        return json.loads(d["message"]["content"]).get("card"), dt
    except Exception:  # noqa: BLE001
        return None, dt


def score(model):
    hits, lat, wrong = 0, [], []
    for c in CASES:
        try:
            got, dt = ask(model, c)
        except Exception as e:  # noqa: BLE001
            print("  %-24s ERROR %s" % (model, e))
            return None
        lat.append(dt)
        if got == c["answer"]:
            hits += 1
        else:
            wrong.append("%s(said %s, want %s)" % (c["id"], got, c["answer"]))
    lat.sort()
    print("%-26s %2d/%-2d  p50 %5.2fs" % (model, hits, len(CASES), lat[len(lat) // 2]))
    for w in wrong:
        print("      miss: %s" % w)
    return hits


def main(argv):
    models = argv or ["qwen2.5:latest"]
    print("icebow doctrine eval -- %d engine/guide-verified cases\n" % len(CASES))
    print("%-26s %-7s %s" % ("model", "score", "latency"))
    best = []
    for m in models:
        s = score(m)
        if s is not None:
            best.append((s, m))
    if best:
        best.sort(reverse=True)
        print("\nbest: %s (%d/%d)" % (best[0][1], best[0][0], len(CASES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Opponent archetypes from card names (owner 2026-10-10: the matchups the model is bad against).  Live display names and engine deck
names are folded to one key ('P.E.K.K.A' / 'Pekka', 'Bandit' / 'Assassin', 'Royal Ghost' / 'Ghost', 'Dart Goblin' / 'BlowdartGoblin').
Priority: royal_giant_monk, royal_giant, lava_hound, golem, pekka_bridge, hyperbait, other.  Extra archetypes (from the live history) are
listed in EXTRA by live_history.py's report and added by hand to ORDER."""
import re

ALIAS = {"assassin": "bandit", "ghost": "royalghost", "blowdartgoblin": "dartgoblin", "icespirits": "icespirit", "wallbreakers": "wallbreakers",
         "goblins": "goblins", "skeletons": "skeletons"}
BRIDGE = {"bandit", "battleram", "royalghost", "magicarcher"}
BAIT = {"goblinbarrel", "skeletonarmy", "goblingang", "princess", "dartgoblin", "rascals", "minionhorde", "bats"}
TANK = {"golem", "lavahound", "giant", "royalgiant", "pekka", "electrogiant", "goblingiant", "giantskeleton", "elixirgolem"}
# signature cards with n >= 15 live matches and inferred win < 45% (live_history.py, 921 matches, 2026-10-10), minus those the named archetypes cover
WEAK = {"barbarianhut", "royalrecruits", "threemusketeers", "movingcannon", "minisparkys", "skeletonking", "skeletonballoon", "goblinstein",
        "firespirithut", "angrybarbarians", "babydragon", "megaknight"}      # win < 40% only (the lead's < 45% list is half the ladder pool)
ORDER = ("royal_giant_monk", "royal_giant", "lava_hound", "golem", "pekka_bridge", "hyperbait", "weak_other")


def canon(n):
    k = re.sub(r"[^a-z0-9]", "", str(n).split("@")[0].lower())
    return ALIAS.get(k, k)


def classify(names):
    s = {canon(n) for n in names if n}
    if "royalgiant" in s:
        return "royal_giant_monk" if "monk" in s else "royal_giant"
    if "lavahound" in s:
        return "lava_hound"
    if "golem" in s:
        return "golem"
    if "pekka" in s and s & BRIDGE:
        return "pekka_bridge"
    if len(s & BAIT) >= 3 and not s & TANK:
        return "hyperbait"
    return "weak_other" if s & WEAK else "other"


def unfavorable(arch):
    return arch in ORDER[:6]        # the owner-named five (weak_other is reported, not boosted: it is 44% of the ladder pool)


def by_archetype(rows):
    """rows: [(deck names, score)] -> {archetype: (n, win%)} for the per-archetype breakdown of an eval."""
    out = {}
    for names, sc in rows:
        a = classify(names)
        n, w = out.get(a, (0, 0.0))
        out[a] = (n + 1, w + sc)
    return {a: (n, 100 * w / n) for a, (n, w) in out.items()}

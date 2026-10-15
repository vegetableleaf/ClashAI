"""
names are folded to one key ('P.E.K.K.A' / 'Pekka', 'Bandit' / 'Assassin', 'Royal Ghost' / 'Ghost', 'Dart Goblin' / 'BlowdartGoblin').
listed in EXTRA by live_history.py's report and added by hand to ORDER.

'EliteArcher' (= Magic Archer, royale_env.py) and ``ARCH_IDS`` (the critic context's archetype index)."""
import re

ALIAS = {"assassin": "bandit", "ghost": "royalghost", "blowdartgoblin": "dartgoblin", "icespirits": "icespirit", "wallbreakers": "wallbreakers",
         "goblins": "goblins", "skeletons": "skeletons",
         "elitearcher": "magicarcher"}                     # RoyaleSim's Magic Archer
BRIDGE = {"bandit", "battleram", "royalghost", "magicarcher"}
BAIT = {"goblinbarrel", "skeletonarmy", "goblingang", "princess", "dartgoblin", "rascals", "minionhorde", "bats"}
TANK = {"golem", "lavahound", "giant", "royalgiant", "pekka", "electrogiant", "goblingiant", "giantskeleton", "elixirgolem"}
WEAK = {"barbarianhut", "royalrecruits", "threemusketeers", "movingcannon", "minisparkys", "skeletonking", "skeletonballoon", "goblinstein",
        "firespirithut", "angrybarbarians", "babydragon", "megaknight"}      # win < 40% only (the lead's < 45% list is half the ladder pool)
ORDER = ("royal_giant_monk", "royal_giant", "lava_hound", "golem", "pekka_bridge", "hyperbait", "weak_other")
ARCH_IDS = ("none_seen",) + ORDER + ("other",)              # critic_ctx arch_id = index here (none_seen: no foe card yet)


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

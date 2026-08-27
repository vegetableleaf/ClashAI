"""How far does the stale-crown-damage problem spread?

Finding that motivated this: for Rocket the wiki publishes crown_dmg_11 = 371, which is exactly
25% x 1484 -- the PRE-1/6/2026 percentage -- while the same page's balance history says the value
is now 23%. The vardefine table lags its own history. Our cards_stats.json imported the vardefine
on 2026-08-14, so the sim inherited the stale number.

That means RE-RUNNING cards-import would NOT fix it. This sweep checks every damage spell: pull
dmg_11 and crown_dmg_11 from the vardefines, pull the most recent "Crown Tower damage to N%" from
the balance history, and flag every card where crown_dmg_11 != round(dmg_11 * N%).

2026-08-26 (I4), after the R2 sweep measured this tool's blind spots (stat_diffs.jsonl, CROWN
bucket -- every one of these is a real page, not a hypothetical):

* the regex demanded the literal "of the full damage"; Fireball's and Vines' current entries say
  "of ITS full damage" (decision #3) and every one of Arrows' four crown entries says "of THEIR
  full damage", so all three always fell through to an older entry or to "no % in history";
* Giant Snowball wraps the phrase in a category link -- "[[:Category:Crown Towers|Crown Tower]]
  damage to 25% of the full damage" -- so the contiguous "Crown Tower damage" prefix never
  matched; Earthquake says "of the full TROOP damage";
* Freeze, Rage, Vines, Goblin Drill and the spell EVOLUTIONS (zap_evo, giant_snowball_evo,
  goblin_drill_evo carry their own vardefines) were simply not in CARDS;
* Goblin Drill's family is spawn_11/spawn_crown_11, and its 4/8/2026 entry has no percentage at
  all: "the Goblin Drill spawn damage to towers has been removed entirely (from 30% of the full
  spawn damage)" -- i.e. the current value is 0 and the vardefine still says 26.

⚠ 2026-08-26 (I5) -- WHAT THIS TOOL AUDITS WAS WRONG, and it is the reason the tool could never
go green. Until now it compared the wiki's vardefine against the wiki's own balance history: a
statement about FANDOM, not about us. Nothing we can do to our knowledge base changes it -- the
15 stale vardefines it printed will still be stale tomorrow, because we do not edit the wiki. As
a gate ("red before the fix, green after") it was unachievable by construction.

So it now audits OUR KB. For each card it still derives the current percentage from the wiki's
dated history -- that part was always right, and it is the only place the live figure exists --
but the number it CHECKS is `build_spec(...).spell_tower_dmg`, against `round(our full damage x
that percentage)`. That is a statement about the sim, it is exactly what I5 fixed, and it fails
if anybody ever imports the stale vardefine back over a pin.

The wiki-vs-wiki finding is still printed, because it is the whole justification for
config/import_pins.json existing -- but it is CONTEXT now, not the exit code.

Exit code: 1 if OUR value disagrees with the wiki's own current percentage, outside the
documented OVERRIDES; else 0.
"""
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from clashrl.cards import CardDB              # noqa: E402
import clashrl.sim.engine as E                # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WIKI = "https://clashroyale.fandom.com/api.php"
UA = "ClashBot/1.0 (crown-damage audit; github vegetableleaf/ClashAI)"

# (wiki page, our KB key). The key is what makes this an audit OF THE SIM.
CARDS = [("Rocket", "rocket"), ("The Log", "the_log"), ("Earthquake", "earthquake"),
         ("Fireball", "fireball"), ("Arrows", "arrows"), ("Zap", "zap"),
         ("Zap/Evolution", "zap_evo"), ("Lightning", "lightning"), ("Poison", "poison"),
         ("Freeze", "freeze"), ("Rage", "rage"), ("Vines", "vines"),
         ("Giant Snowball", "giant_snowball"), ("Giant Snowball/Evolution", "giant_snowball_evo"),
         ("Barbarian Barrel", "barbarian_barrel"), ("Royal Delivery", "royal_delivery"),
         ("Tornado", "tornado"), ("Goblin Drill", "goblin_drill"),
         ("Goblin Drill/Evolution", "goblin_drill_evo")]

# DELIBERATE, DOCUMENTED disagreements between our value and the percentage rule. One entry.
OVERRIDES = {
    ("earthquake", "crown"):
        "OWNER OVERRIDE, knowingly inconsistent (decisions.md #5 + the batch review). 49 is 58% "
        "of the SUPERSEDED damage 84 (84*0.58 = 48.7 -> 49); against the ruled damage 81 the "
        "same 58% gives 47, and 49/81 is 60.5%. The wiki's own crown_dmg_11 is 53. All three "
        "numbers were put to the owner and 49 was chosen.",
}

# "Crown Tower damage to N% of the full damage", tolerating everything the pages actually write:
# an optional category-link tail on "Crown Tower(s)]]", capitalised Damage, a possessive, and
# the/its/their + optional "troop" before "full damage" (Earthquake). The LAST match in page
# order is the current value -- history sections are chronological.
_PCT = re.compile(r"[Cc]rown [Tt]owers?(?:\]\])?'?s? [Dd]amage to (\d+(?:\.\d+)?)% of "
                  r"(?:the|its|their) full (?:troop )?damage")
# The spawn-damage family (Goblin Drill): either a percentage or an outright removal.
_SPAWN_PCT = re.compile(r"[Ss]pawn damage to (?:[Cc]rown )?[Tt]owers? to (\d+(?:\.\d+)?)% of "
                        r"the full spawn damage")
_SPAWN_GONE = re.compile(r"[Ss]pawn damage to (?:[Cc]rown )?[Tt]owers? has been removed entirely")


def raw(title):
    url = WIKI + "?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "wikitext",
         "formatversion": "2", "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "error" in d:
        return None
    return d["parse"]["wikitext"]


def spawn_events(t):
    """(position, pct) for every spawn-crown change, page order; removal counts as 0%."""
    ev = [(m.start(), float(m.group(1))) for m in _SPAWN_PCT.finditer(t)]
    ev += [(m.start(), 0.0) for m in _SPAWN_GONE.finditer(t)]
    return sorted(ev)


def ours(db, key, label):
    """(our full damage, our crown-tower damage) for one family, or (None, None).

    Both come from build_spec, not from the raw row, because the engine is what the audit is
    about: `spell_tower_dmg` is what actually hits a crown tower, after the fallbacks.
    """
    try:
        s = E.build_spec(db, key, 11)
    except Exception:  # noqa: BLE001
        return None, None
    if label == "spawn-crown":
        return (s.spawn_dmg or None), s.spawn_crown_dmg
    if s.kind == "spell":
        return (s.spell_dmg or None), s.spell_tower_dmg
    return (s.hit_dmg or None), s.tower_hit_dmg


def audit(title, key, wdmg, wcrown, pcts, label, db):
    """One family's verdict line.

    Returns (our_stale, wiki_stale): our_stale is the exit-code finding, wiki_stale is the
    context line that motivated the pin registry.
    """
    odmg, ocrown = ours(db, key, label)
    if not pcts:
        print("%-24s %7.0f %7.0f %7s %7s %7s   no %% in history [%s]"
              % (title, wdmg, wcrown, "-" if odmg is None else "%.0f" % odmg,
                 "-" if ocrown is None else "%.0f" % ocrown, "-", label))
        return None, None
    cur = pcts[-1]
    wiki_exp = round(wdmg * cur / 100.0)
    wiki_stale = None if abs(wiki_exp - wcrown) <= 1 else (title, wcrown, wiki_exp, cur, label)
    if odmg is None or ocrown is None:
        print("%-24s %7.0f %7.0f %7s %7s %7s   NOT IN THE KB [%s]"
              % (title, wdmg, wcrown, "-", "-", "-", label))
        return None, wiki_stale
    exp = round(odmg * cur / 100.0)
    ok = abs(exp - ocrown) <= 1
    why = OVERRIDES.get((key, label))
    verdict = "ok" if ok else ("OVERRIDE" if why else "** OUR VALUE IS STALE **")
    print("%-24s %7.0f %7.0f %7.0f %7.0f %7.0f   %s [%s]"
          % (title, wdmg, wcrown, odmg, ocrown, exp, verdict, label))
    return (None if (ok or why) else (title, key, ocrown, exp, cur, label)), wiki_stale


def main(argv=()) -> int:
    # `--kb <path to a cards.yaml>` audits ANOTHER checkout of the KB. That is what makes the
    # red-then-green negative control reproducible instead of a story: point it at the pre-I5
    # configs (git worktree, or `git show 0905104:...` into a temp dir) and it must go RED.
    kb = None
    for i, a in enumerate(argv):
        if a == "--kb" and i + 1 < len(argv):
            kb = Path(argv[i + 1])
    db = CardDB(path=kb) if kb else CardDB()
    if kb:
        print("auditing the KB at %s" % kb)
    print("%-24s %7s %7s %7s %7s %7s   %s"
          % ("card", "w_dmg", "w_crown", "our_dmg", "our_cr", "expect", "verdict"))
    print("-" * 96)
    bad, stale, overrides = [], [], []
    for title, key in CARDS:
        t = raw(title)
        if not t:
            print("%-24s  (page not readable)" % title)
            continue
        vs = dict(re.findall(r"\{\{#vardefine:\s*([A-Za-z_0-9]+)\s*\|\s*([^}|]+?)\s*\}\}", t))

        def num(k):
            try:
                return float(vs.get(k))
            except (TypeError, ValueError):
                return None

        checked = False
        dmg, crown = num("dmg_11"), num("crown_dmg_11")
        if dmg is not None and crown is not None:
            checked = True
            b, w = audit(title, key, dmg, crown,
                         [float(m) for m in _PCT.findall(t)], "crown", db)
            bad += [b] if b else []
            stale += [w] if w else []
            if (key, "crown") in OVERRIDES:
                overrides.append((title, key, "crown"))
        sdmg, scrown = num("spawn_11"), num("spawn_crown_11")
        if sdmg is not None and scrown is not None:
            checked = True
            b, w = audit(title, key, sdmg, scrown,
                         [p for _, p in spawn_events(t)], "spawn-crown", db)
            bad += [b] if b else []
            stale += [w] if w else []
        if not checked:
            print("%-24s  (no complete dmg_11+crown_dmg_11 or spawn_11+spawn_crown_11 pair)" % title)

    print()
    if stale:
        print("CONTEXT -- the WIKI's own vardefine disagrees with the WIKI's own balance history "
              "(%d):" % len(stale))
        for t, c, e, p, label in stale:
            print("   %-24s vardefine %.0f  ->  should be %.0f  (%.0f%% of full, %s)"
                  % (t, c, e, p, label))
        print("   This is not our bug and we cannot fix it -- we do not edit the wiki. It is the")
        print("   whole reason config/import_pins.json exists: a re-import would otherwise write")
        print("   these numbers straight back over the curated ones.")
        print()
    for title, key, label in overrides:
        print("DELIBERATE OVERRIDE  %s [%s]: %s" % (title, label, OVERRIDES[(key, label)]))
    if overrides:
        print()
    if bad:
        print("STALE IN OUR KB (%d) -- these are ours to fix:" % len(bad))
        for t, key, c, e, p, label in bad:
            print("   %-24s %s = %.0f  ->  should be %.0f  (%.0f%% of full, %s)"
                  % (t, key, c, e, p, label))
        return 1
    print("no discrepancies in our KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

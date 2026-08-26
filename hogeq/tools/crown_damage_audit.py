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

Exit code: 1 if any stale vardefine was found (so the negative control is mechanical), else 0.
"""
import io
import json
import re
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WIKI = "https://clashroyale.fandom.com/api.php"
UA = "ClashBot/1.0 (crown-damage audit; github vegetableleaf/ClashAI)"

CARDS = ["Rocket", "The Log", "Earthquake", "Fireball", "Arrows", "Zap", "Zap/Evolution",
         "Lightning", "Poison", "Freeze", "Rage", "Vines", "Giant Snowball",
         "Giant Snowball/Evolution", "Barbarian Barrel", "Royal Delivery", "Tornado",
         "Goblin Drill", "Goblin Drill/Evolution"]

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


def audit(title, dmg, crown, pcts, label):
    """One family's verdict line; returns the stale tuple or None."""
    if not pcts:
        print("%-24s %8.0f %8.0f %7s %9s   no %% in history [%s]"
              % (title, dmg, crown, "-", "-", label))
        return None
    cur = pcts[-1]
    exp = round(dmg * cur / 100.0)
    ok = abs(exp - crown) <= 1
    print("%-24s %8.0f %8.0f %6.0f%% %9.0f   %s [%s]"
          % (title, dmg, crown, cur, exp, "ok" if ok else "** STALE vardefine **", label))
    return None if ok else (title, crown, exp, cur, label)


def main() -> int:
    print("%-24s %8s %8s %7s %9s   %s" % ("card", "dmg_11", "crown_11", "cur%", "expected", "verdict"))
    print("-" * 88)
    stale = []
    for title in CARDS:
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
            s = audit(title, dmg, crown, [float(m) for m in _PCT.findall(t)], "crown")
            if s:
                stale.append(s)
        sdmg, scrown = num("spawn_11"), num("spawn_crown_11")
        if sdmg is not None and scrown is not None:
            checked = True
            s = audit(title, sdmg, scrown, [p for _, p in spawn_events(t)], "spawn-crown")
            if s:
                stale.append(s)
        if not checked:
            print("%-24s  (no complete dmg_11+crown_dmg_11 or spawn_11+spawn_crown_11 pair)" % title)

    print()
    if stale:
        print("STALE (wiki vardefine disagrees with the wiki's OWN balance history):")
        for t, c, e, p, label in stale:
            print("   %-24s vardefine %.0f  ->  should be %.0f  (%.0f%% of full, %s)"
                  % (t, c, e, p, label))
        print()
        print("Consequence: cards_stats.json imports the VARDEFINE, so re-running cards-import")
        print("re-imports the stale number. The fix has to be a curated override (import pin),")
        print("not a re-import. See config/import_pins.json.")
        return 1
    print("no discrepancies found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

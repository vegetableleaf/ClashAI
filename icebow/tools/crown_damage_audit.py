"""How far does the stale-crown-damage problem spread?

Finding that motivated this: for Rocket the wiki publishes crown_dmg_11 = 371, which is exactly
25% x 1484 -- the PRE-1/6/2026 percentage -- while the same page's balance history says the value
is now 23%. The vardefine table lags its own history. Our cards_stats.json imported the vardefine
on 2026-08-14, so the sim inherited the stale number.

That means RE-RUNNING cards-import would NOT fix it. This sweep checks every damage spell: pull
dmg_11 and crown_dmg_11 from the vardefines, pull the most recent "Crown Tower damage to N%" from
the balance history, and flag every card where crown_dmg_11 != round(dmg_11 * N%).
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

CARDS = ["Rocket", "The Log", "Earthquake", "Fireball", "Arrows", "Zap", "Lightning",
         "Poison", "Giant Snowball", "Barbarian Barrel", "Royal Delivery", "Tornado"]


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


print("%-18s %8s %8s %7s %9s   %s" % ("card", "dmg_11", "crown_11", "cur%", "expected", "verdict"))
print("-" * 82)
stale = []
for title in CARDS:
    t = raw(title)
    if not t:
        print("%-18s  (page not readable)" % title)
        continue
    vs = dict(re.findall(r"\{\{#vardefine:\s*([A-Za-z_0-9]+)\s*\|\s*([^}|]+?)\s*\}\}", t))
    try:
        dmg = float(vs.get("dmg_11"))
        crown = float(vs.get("crown_dmg_11"))
    except (TypeError, ValueError):
        print("%-18s  (no dmg_11/crown_dmg_11 vardefine)" % title)
        continue
    # every "Crown Tower damage to N% of the full damage" in history, in page order;
    # the LAST one is the current value
    pcts = re.findall(r"[Cc]rown [Tt]ower [Dd]amage to (\d+(?:\.\d+)?)% of the full damage", t)
    if not pcts:
        print("%-18s %8.0f %8.0f %7s %9s   no %% in history" % (title, dmg, crown, "-", "-"))
        continue
    cur = float(pcts[-1])
    exp = round(dmg * cur / 100.0)
    ok = abs(exp - crown) <= 1
    if not ok:
        stale.append((title, crown, exp, cur))
    print("%-18s %8.0f %8.0f %6.0f%% %9.0f   %s"
          % (title, dmg, crown, cur, exp, "ok" if ok else "** STALE vardefine **"))

print()
if stale:
    print("STALE (wiki vardefine disagrees with the wiki's OWN balance history):")
    for t, c, e, p in stale:
        print("   %-18s vardefine %.0f  ->  should be %.0f  (%.0f%% of full)" % (t, c, e, p))
    print()
    print("Consequence: cards_stats.json imports the VARDEFINE, so re-running cards-import")
    print("re-imports the stale number. The fix has to be a curated override, not a re-import.")
else:
    print("no discrepancies found")

"""Import current card stats by scraping the Clash Royale Fandom wiki (MediaWiki API).

The wiki is community-maintained and up to date (it reflects recent balance
changes that other datasets lag on). Each card page defines its LEVEL-11 stats as
MediaWiki variables -- {{#vardefine: hp_11 | 1766 }}, dmg_11, crown_dmg_11,
atk_speed, life -- plus a {{Card Infobox|Cost=|Rarity=|Type=}}. This enumerates
card pages via the Troop/Building/Spell/Champion card categories -- including each
card's ``<Card>/Evolution`` subpage (evolutions live there and are keyed
``<base>_evo``) and the Champion (hero) cards -- parses those values, and writes
`config/cards_stats.json` (level 11). Curated `config/cards.yaml` overlays it
(flags, abilities, deck). Re-run after balance updates: `run.py cards-import`.

Behavioural attributes (air/ground targeting, splash, etc.) live in page prose,
not structured fields, so those stay curated; this importer fills the reliable
numeric stats + elixir/rarity/type.
"""
from __future__ import annotations

import datetime
import json
import re
import time
import urllib.parse
import urllib.request

WIKI = "https://clashroyale.fandom.com/api.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ClashBotResearch/1.0"
CATEGORIES = ["Category:Troop Cards", "Category:Building Cards", "Category:Spell Cards",
              "Category:Champion Cards"]
# Cards the wiki files under "Removed Cards" exist ONLY in limited-time event modes (party_*,
# super_*, Santa Hog Rider, Wizard Trio, Terry ...) or were delisted outright (Heal, Warmth,
# Baby Goblins). None of them can appear in a trophy-ladder match, so importing them poisons
# every downstream consumer: the sim builds opponent decks the bot will never face, the detector
# taxonomy burns class slots that can never be labelled, and the threat model reasons about
# cards that do not exist. Every genuine ladder card carries an Arena category instead, so this
# one category is a clean and complete separator -- verified 2026-08-07 against all 180 imported
# cards, which produced no false positives and no misses.
EXCLUDE_CATEGORY = "Category:Removed Cards"
_EVO = "/Evolution"
_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")
_VARDEF = re.compile(r"\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}|]+?)\s*\}\}")
_INFOBOX = re.compile(r"\|\s*(Cost|Rarity|Type)\s*=\s*([^\n|}]+)")


def _key(name: str) -> str:
    return (str(name).strip().lower()
            .replace(" ", "_").replace("-", "_").replace(".", "").replace("'", ""))


def _api(params: dict):
    url = WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _members(cat: str):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": 500}
        if cont:
            p["cmcontinue"] = cont
        d = _api(p)
        for m in d.get("query", {}).get("categorymembers", []):
            t = m["title"]
            if ":" in t:
                continue                        # skip subcategories / namespaced pages
            if "/" in t and not t.endswith(_EVO):
                continue                        # skip subpages except the Evolution variant
            out.append(t)
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            return out


def _wikitext(page: str) -> str:
    return _api({"action": "parse", "page": page, "prop": "wikitext"})["parse"]["wikitext"]["*"]


def _lit(v):
    return float(v) if v is not None and _NUM.match(str(v).strip()) else None


def _pick(vd: dict, base: str):
    """Level-11 value for a stat, trying `<base>_11` then `<base>_base`."""
    for suf in (f"{base}_11", f"{base}_base"):
        val = _lit(vd.get(suf))
        if val is not None:
            return val
    return None


def _parse_card(page: str, wt: str) -> dict:
    vd = {k: v.strip() for k, v in _VARDEF.findall(wt)}
    info = {k: v.strip() for k, v in _INFOBOX.findall(wt)}

    hp, dmg, atk = _pick(vd, "hp"), _pick(vd, "dmg"), _lit(vd.get("atk_speed"))
    crown = _pick(vd, "crown_dmg")
    if hp is None:                       # multi-unit pages prefix vars, e.g. golem_hp_11
        prefixed = {}
        for k, v in vd.items():
            m = re.fullmatch(r"([a-z0-9]+)_hp_(?:11|base)", k)
            lv = _lit(v)
            if m and lv is not None:
                prefixed[m.group(1)] = lv
        if prefixed:
            main = max(prefixed, key=lambda k: prefixed[k])     # main unit = highest HP
            hp = prefixed[main]
            dmg = dmg or _lit(vd.get(f"{main}_dmg_11")) or _lit(vd.get(f"{main}_dmg_base"))
            atk = atk or _lit(vd.get(f"{main}_atk_speed"))

    cost = info.get("Cost", "")
    entry = {
        "display": page,
        "elixir": int(cost) if cost.isdigit() else None,
        "rarity": (info.get("Rarity") or "").lower() or None,
        "kind": (info.get("Type") or "").lower() or None,
        "hitpoints": int(hp) if hp is not None else None,
        "damage": int(dmg) if dmg is not None else None,
        "hit_speed": atk,
        "dps": round(dmg / atk) if (dmg and atk) else None,
        "crown_tower_damage": int(crown) if crown is not None else None,
        "lifetime_s": _lit(vd.get("life")),
    }
    return {k: v for k, v in entry.items() if v is not None}


def import_cards(cfg) -> None:
    print("[cards-import] scraping the Clash Royale Fandom wiki (level 11)...")
    names: list = []
    champions: set = set()
    for cat in CATEGORIES:
        try:
            m = _members(cat)
            names += m
            if "Champion" in cat:
                champions.update(m)
            print(f"[cards-import] {cat}: {len(m)} pages")
        except Exception as exc:  # noqa: BLE001
            print(f"[cards-import] {cat} failed: {exc}")
    names = sorted(set(names))
    if not names:
        print("[cards-import] no card pages found (wiki category names may have changed).")
        return

    try:
        removed = set(_members(EXCLUDE_CATEGORY))
    except Exception as exc:  # noqa: BLE001 -- better to import everything than to import nothing
        removed = set()
        print(f"[cards-import] WARNING: could not read {EXCLUDE_CATEGORY} ({exc}); "
              "event-only cards may slip in.")
    if removed:
        # an Evolution subpage is dropped with its base card
        skipped = [n for n in names if n in removed or n.split(_EVO)[0] in removed]
        names = [n for n in names if n not in skipped]
        print(f"[cards-import] skipping {len(skipped)} event-only/removed cards: "
              f"{', '.join(sorted(skipped)[:6])}{'...' if len(skipped) > 6 else ''}")

    out: dict = {}
    fails: list = []
    n_evo = n_champ = 0
    for i, name in enumerate(names):
        try:
            entry = _parse_card(name, _wikitext(name))
            if name.endswith(_EVO):
                base = name[: -len(_EVO)]
                entry["display"] = f"Evo {base}"
                entry["evolution"] = True
                entry["base"] = _key(base)
                out[_key(base) + "_evo"] = entry
                n_evo += 1
            else:
                if name in champions:
                    entry["champion"] = True
                    n_champ += 1
                out[_key(name)] = entry
        except Exception:  # noqa: BLE001
            fails.append(name)
        time.sleep(0.15)  # be polite to the wiki
        if (i + 1) % 25 == 0:
            print(f"[cards-import]   {i + 1}/{len(names)} pages...")

    path = cfg.path("config", "cards_stats.json")
    meta = {
        "level": 11,
        "source": "clashroyale.fandom.com (MediaWiki, level-11 vardefines)",
        "generated": datetime.date.today().isoformat(),
        "count": len(out),
        "champions": n_champ,
        "evolutions": n_evo,
    }
    path.write_text(json.dumps({"meta": meta, "cards": out}, indent=1), encoding="utf-8")

    hp = sum(1 for v in out.values() if "hitpoints" in v)
    dmg = sum(1 for v in out.values() if "damage" in v)
    print(f"[cards-import] wrote {len(out)} cards to {path} ({hp} with hitpoints, {dmg} with "
          f"damage; {n_champ} champions, {n_evo} evolutions).")
    if fails:
        print(f"[cards-import] {len(fails)} pages could not be parsed: {', '.join(fails[:12])}"
              + (" ..." if len(fails) > 12 else ""))
    print("[cards-import] curated config/cards.yaml overlays this (flags/abilities/deck).")

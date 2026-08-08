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

Behavioural attributes that live only in page prose (splash shape, abilities) stay
curated; this importer fills the reliable numeric stats + elixir/rarity/type, plus
the per-unit ATTRIBUTES TABLE (count / transport / speed / range / targets /
projectile geometry / charge) -- see ``_parse_attr_tables``.
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

# --- the per-unit ATTRIBUTES TABLE -----------------------------------------------------------
# Every card page carries a wikitable id="unit-attributes-table" holding the fields that are NOT
# vardefines: Count, Transport (air/ground), Speed, Range, Target, Deploy Time, and -- for anything
# that shoots -- Projectile Speed/Radius/Range, Splash Radius and Charge Range. These were
# previously taken from RoyaleAPI's cr-api-data, which has been DEAD SINCE 2023-10-18 (last commit),
# so it predates every card and balance change since and misses the newer cards entirely.
_ATTR_TABLE = re.compile(r"\{\|[^\n]*unit-attributes-table.*?\n\|\}", re.S)
_ICON = re.compile(r"\{\{Icon\|[^}]*\}\}")
_PAREN = re.compile(r"\(([\d.]+)\)")
_ANYNUM = re.compile(r"-?\d+(?:\.\d+)?")
# A card whose extra table rows are things it spawns WHEN IT DIES (Golem -> Golemites, Lava Hound
# -> Pups, Battle Ram -> Barbarians, Skeleton Barrel -> Skeletons, Goblin Giant -> Spear Goblins)
# must NOT add those to its DEPLOY count; a card that fields several unit types AT ONCE (Goblin
# Gang 3+3, Rascals 1+2, Goblinstein 1+1) must. The wiki states the trigger in prose, and the
# phrasings vary enough that this has to be generous -- "When he is defeated", "Once it reaches a
# building or it is destroyed", "When defeated ... splits into", "reveal the two Barbarians".
_DEATH_SPAWN = re.compile(
    r"(?:when|once|after|if)\b[^.]{0,70}\b(?:destroyed|defeated|dies|die)"
    r"|upon death|splits? into|reveals? the|drops?,[^.]*spawning", re.I)
# Spirits: "It launches itself at its target when attacking, destroying itself on impact."
_KAMIKAZE = re.compile(r"destroying itself on impact|launches itself at its target", re.I)
# CR speed ratings are quoted as "Very Fast (120)"; 60 of these units = 1 tile/second.
_SPEED_UNITS_PER_TILE = 60.0


def _cell(s: str) -> str:
    s = _ICON.sub("", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r'scope\s*=\s*"[^"]*"\s*\|?', "", s)
    s = re.sub(r"\{\{Rarity\|([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)
    return " ".join(s.split()).strip(" |")


def _tiles(v):
    """'Melee: Short (0.5)' -> 0.5; '6' -> 6.0; 'Very Fast (120)' -> 120.0."""
    if not v:
        return None
    m = _PAREN.search(v)
    if m:
        return float(m.group(1))
    m = _ANYNUM.search(v)
    return float(m.group(0)) if m else None


def _attr_rows(wt: str) -> list:
    """Every row of every unit-attributes table on the page, as header->value dicts."""
    rows_out = []
    for tb in _ATTR_TABLE.findall(wt):
        heads, rows = [], []
        for line in tb.splitlines():
            ls = line.strip()
            if ls.startswith("!"):
                heads += [_cell(c) for c in ls.lstrip("!").split("!!")]
            elif ls.startswith("|") and not ls.startswith(("|-", "|}", "|+", "{|")):
                cells = [_cell(c) for c in ls.lstrip("|").split("||")]
                # a row's trailing cells are often on their own continuation lines
                if rows and len(rows[-1]) < len(heads):
                    rows[-1] += cells
                else:
                    rows.append(cells)
        rows_out += [dict(zip(heads, r)) for r in rows]
    return rows_out


def _parse_attr_tables(wt: str) -> dict:
    rows = _attr_rows(wt)
    # THE CARD'S OWN table is the one carrying Cost -- every card page leads with it. A SPAWNER page
    # then has a SECOND table for the unit it summons, which has no Cost. Keying on Cost is what
    # separates them. The old filter (Transport OR Range OR Radius) skipped a spawner's own table
    # entirely, because it lists "Spawn Range" rather than "Range" and never carries Transport -- so
    # units[0] became the SPAWNED troop and its stats were written as the card's. goblin_hut ended up
    # with a Spear Goblin's 133 hp / 5.0 range / 2.0 speed; a `kind: building` with a MOVEMENT SPEED
    # is the tell. Same for tombstone (a Skeleton), barbarian_hut (a Barbarian), goblin_drill and
    # goblin_cage.
    owns = [r for r in rows if r.get("Cost")]
    spawned = [r for r in rows if not r.get("Cost") and r.get("Transport")]
    units = owns or [r for r in rows if r.get("Transport") or r.get("Range") or r.get("Radius")]
    if not units:
        return {}

    def _n(r):
        m = _ANYNUM.search(r.get("Count") or "")
        return int(m.group()) if m else 1

    main = units[0]
    intro = wt.split("==Strategy==")[0]
    bodies = [r for r in units if r.get("Transport")]
    count = sum(_n(r) for r in bodies) if (len(bodies) > 1 and not _DEATH_SPAWN.search(intro)) \
        else _n(main)

    target = (main.get("Target") or "").lower()
    attacks = None
    if "building" in target:
        attacks = ["buildings"]
    elif "air" in target and "ground" in target:
        attacks = ["air", "ground"]
    elif "ground" in target:
        attacks = ["ground"]
    elif "air" in target:
        attacks = ["air"]

    speed = _tiles(main.get("Speed"))
    out = {
        "count": count,
        "movement": ("air" if (main.get("Transport") or "").lower() == "air" else "ground")
                    if main.get("Transport") else None,
        "speed_tiles": round(speed / _SPEED_UNITS_PER_TILE, 3) if speed else None,
        "range_tiles": _tiles(main.get("Range")),
        "attacks": attacks,
        "deploy_time": _tiles(main.get("Deploy Time")),
        "projectile_speed": _tiles(main.get("Projectile Speed")),
        "projectile_radius": _tiles(main.get("Projectile Radius")),
        "projectile_range": _tiles(main.get("Projectile Range")),
        "splash_radius": _tiles(main.get("Splash Radius")),
        "radius_tiles": _tiles(main.get("Radius")),          # spells: the blast footprint
        # SPAWNER parameters, straight off the card's own table. Goblin Hut only summons "when an
        # enemy is within range" (Spawn Range 6) -- it stopped spawning automatically in the May 2025
        # update, so the gate is real and not cosmetic. Buildings that spawn unconditionally simply
        # have no Spawn Range column.
        "spawn_interval_s": _tiles(main.get("Spawn Speed")),
        "spawn_delay_s": _tiles(main.get("Spawn Delay")),
        "spawn_range_tiles": _tiles(main.get("Spawn Range")),
    }
    if spawned:                      # the summoned troop's own row (never has Cost)
        sp = spawned[0]
        sp_speed = _tiles(sp.get("Speed"))
        out["spawn_unit_stats"] = {k: v for k, v in {
            "range_tiles": _tiles(sp.get("Range")),
            "speed_tiles": round(sp_speed / _SPEED_UNITS_PER_TILE, 3) if sp_speed else None,
            "hit_speed": _tiles(sp.get("Hit Speed")),
            "flying": (sp.get("Transport") or "").lower() == "air" or None,
        }.items() if v is not None}
    def _any(col):
        """First non-empty value of `col` across ANY table on the page.

        These columns do not live on the card's own Cost row -- `Cycles` sits on an Evolution's
        separate table, `Death Damage Splash Radius` on a death-effect table -- so they must be
        searched page-wide rather than read off `main`.
        """
        for r in rows:
            if r.get(col):
                return r[col]
        return None

    cyc = _ANYNUM.search(_any("Cycles") or "")
    pct = _ANYNUM.search(_any("Slowdown") or "")
    out.update({
        # EVOLUTION CYCLES: how many base plays charge the Evolution. Four cards were sitting on an
        # UNVERIFIED guess of 1; the wiki publishes 2 for Musketeer / Valkyrie / Archers / Skeletons.
        "evo_cycles": int(cyc.group()) if cyc else None,
        "death_radius_tiles": _tiles(_any("Death Damage Splash Radius")),
        "stun_duration_s": _tiles(_any("Stun Duration")),
        "freeze_duration_s": _tiles(_any("Freeze Duration")),
        "slow_duration_s": _tiles(_any("Slow Duration")),
        "slow_pct": float(pct.group()) if pct else None,
        "jump_time_s": _tiles(_any("Jump Time")),
        "dash_time_s": _tiles(_any("Dash Time")),
        "projectile_width_tiles": _tiles(_any("Projectile Width")),
    })
    if _KAMIKAZE.search(intro):
        out["kamikaze"] = True       # spirits: leap at the target, hit once, die on impact
    charge = next((r for r in rows if r.get("Charge Range")), None)
    if charge:
        out["charge_range"] = _tiles(charge.get("Charge Range"))
        cs = _tiles(charge.get("Speed"))
        out["charge_speed_tiles"] = round(cs / _SPEED_UNITS_PER_TILE, 3) if cs else None
    return {k: v for k, v in out.items() if v is not None}


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
    # A SPAWNER page defines HP for BOTH the card and the unit it summons, and which one gets the
    # bare `hp_11` is NOT consistent: goblin_hut/tombstone/barbarian_hut/goblin_drill put the
    # BUILDING behind a prefix (hut_/tomb_/drill_) and the SPAWNED unit on bare hp_11, while
    # goblin_cage does the reverse. Taking bare hp_11 therefore gave four buildings their spawned
    # troop's hitpoints. The one rule that holds on every page today is that the card's OWN body is
    # the tankier of the two -- which is also the rule the old prefixed-only fallback already used,
    # it just never applied when a bare hp_11 happened to exist.
    hp_vars = {}
    for k, v in vd.items():
        m = re.fullmatch(r"(?:([a-z0-9]+)_)?hp_(?:11|base)", k)
        lv = _lit(v)
        if m and lv is not None:
            hp_vars.setdefault(m.group(1) or "", lv)
    if hp_vars:
        pref = max(hp_vars, key=lambda k: hp_vars[k])
        hp = hp_vars[pref]
        if pref:                     # damage/attack MUST come from the same unit as the hitpoints,
            p = f"{pref}_"           # with no fallback to the bare vars (those are the spawned unit)
            dmg = _lit(vd.get(f"{p}dmg_11")) or _lit(vd.get(f"{p}dmg_base"))
            atk = _lit(vd.get(f"{p}atk_speed"))
    # RAMP-UP DAMAGE (Inferno Tower / Inferno Dragon / Mighty Miner). These cards publish NO plain
    # `dmg_11`; their damage is staged as `1_dmg_11` / `2_dmg_11` / `3_dmg_11`, climbing while they
    # stay locked on one target. The importer only ever looked for the bare key, so all three came
    # out with damage None -> dps 0 and dealt NO DAMAGE AT ALL in the sim, to towers or to troops.
    stages = {}
    for k, v in vd.items():
        m = re.fullmatch(r"([123])_dmg_(?:11|base)", k)
        lv = _lit(v)
        if m and lv is not None:
            stages.setdefault(int(m.group(1)), lv)
    damage_stages = [stages[i] for i in sorted(stages)] if stages else None
    # A RAMP CLIMBS. Void uses the same `N_dmg_11` naming for something else entirely -- damage
    # against 1 troop vs 2 troops, which DESCENDS (696 -> 294) -- so requiring a strictly increasing
    # series is what separates a real ramp from a same-shaped key that means the opposite.
    if damage_stages and (len(damage_stages) < 2
                          or any(b <= a for a, b in zip(damage_stages, damage_stages[1:]))):
        damage_stages = None
    if damage_stages and dmg is None:
        dmg = damage_stages[0]       # stage 1 is the opening damage, before any ramp

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
        "damage_stages": damage_stages,
        # SECONDARY DAMAGE + SHIELD, all level-scaled vardefines the importer never read. The engine
        # was guessing a shield as a fraction of hitpoints and had no death damage at all, so a
        # Balloon or Giant Skeleton dying was silent -- which is most of what those cards are for.
        # `Shield_11` is capitalised on Royal Recruits, hence the case-insensitive lookup.
        "shield_hp": _pick(vd, "shield") or _pick({k.lower(): v for k, v in vd.items()}, "shield"),
        "death_damage": _pick(vd, "death"),
        "charge_damage": _pick(vd, "charge"),      # Prince 783 / Dark Prince 532 on a completed charge
        "dash_damage": _pick(vd, "dash"),          # Bandit 389
        "jump_damage": _pick(vd, "jump"),          # Mega Knight 537 on landing
        "spawn_damage": _pick(vd, "spawn"),        # Mega Knight 430 / Goblin Drill 84 on surfacing
        "spawn_crown_damage": _pick(vd, "spawn_crown"),
        "hits_per_attack": _lit(vd.get("dmg_hits")),   # Electro Dragon chains to 3
    }
    entry.update(_parse_attr_tables(wt))
    if re.search(r"\b(?:jump|hop|leap)\w*\s+(?:over|across)\s+(?:the\s+)?river",
                 wt.split("==Strategy==")[0], re.I):
        entry["river_jump"] = True          # crosses the river without using a bridge
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
    cnt = sum(1 for v in out.values() if "count" in v)
    air = sum(1 for v in out.values() if v.get("movement") == "air")
    proj = sum(1 for v in out.values() if "projectile_speed" in v)
    jump = sorted(k for k, v in out.items() if v.get("river_jump"))
    kami = sorted(k for k, v in out.items() if v.get("kamikaze"))
    print(f"[cards-import] wrote {len(out)} cards to {path} ({hp} with hitpoints, {dmg} with "
          f"damage; {n_champ} champions, {n_evo} evolutions).")
    print(f"[cards-import]   attributes table: {cnt} counts, {air} air units, "
          f"{proj} with projectiles")
    print(f"[cards-import]   river-jumpers: {', '.join(jump) or 'none'}")
    print(f"[cards-import]   kamikaze: {', '.join(kami) or 'none'}")
    if fails:
        print(f"[cards-import] {len(fails)} pages could not be parsed: {', '.join(fails[:12])}"
              + (" ..." if len(fails) > 12 else ""))
    print("[cards-import] curated config/cards.yaml overlays this (flags/abilities/deck).")

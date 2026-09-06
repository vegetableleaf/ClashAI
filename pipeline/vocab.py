"""Unit / spell vocabulary shared by the engine and live adapters (S0 step 2, L63).

Canonical unit identity = the detector's 230 class names (``icebow/config/detect_classes.yaml``,
byte-identical to the weights' ``model.names``; id = position). Live is the lower-information side, so
its vocabulary is the contract's. Engine-only names are appended after id 229. Engine display names
(native_core CARD_NAMES = live catalog display_name) reach the vocab through the same rules
``scratchpad/gauntlet/L61/build_bc_v2.py:44-69`` uses (``_ALIAS_INV`` + CamelCase -> snake), plus a
``(name, max_hp)`` rule for the six detector-only sub-spawn classes the engine names by parent card.
"""
from __future__ import annotations

import re
from typing import Optional

# The 230 detector classes, in class-id order. Frozen copy of icebow/config/detect_classes.yaml
# (2026-09-06); tests/test_obs_contract.py asserts the copy still matches the yaml.
DETECTOR_CLASSES: tuple[str, ...] = (
    "tornado", "tesla", "ice_wizard", "x_bow", "rocket", "knight", "the_log", "skeletons", "archer_queen",
    "archers", "arrows", "baby_dragon", "balloon", "bandit", "barbarian_barrel", "barbarian_hut",
    "barbarians", "bats", "battle_healer", "battle_ram", "berserker", "bomb_tower", "bomber",
    "boss_bandit", "bowler", "cannon", "cannon_cart", "clone", "dark_prince", "dart_goblin", "earthquake",
    "electro_dragon", "electro_giant", "electro_spirit", "electro_wizard", "elite_barbarians",
    "elixir_blob", "elixir_collector", "elixir_golem", "elixir_golemite", "executioner", "fire_spirit",
    "fireball", "firecracker", "fisherman", "flying_machine", "freeze", "furnace", "giant",
    "giant_skeleton", "giant_snowball", "goblin_barrel", "goblin_cage", "goblin_curse",
    "goblin_demolisher", "goblin_drill", "goblin_gang", "goblin_giant", "goblin_hut", "goblin_machine",
    "goblins", "goblinstein", "golden_knight", "golem", "golemite", "graveyard", "guards", "heal_spirit",
    "hog_rider", "hunter", "ice_golem", "ice_spirit", "inferno_dragon", "inferno_tower", "lava_hound",
    "lava_pups", "lightning", "little_prince", "lumberjack", "magic_archer", "mega_knight", "mega_minion",
    "mighty_miner", "miner", "mini_pekka", "minion_horde", "minions", "mirror", "monk", "mortar",
    "mother_witch", "mother_witch_hog", "musketeer", "night_witch", "pekka", "phoenix", "poison", "prince",
    "princess", "rage", "ram_rider", "rascals", "ronin", "royal_delivery", "royal_ghost", "royal_giant",
    "royal_hogs", "royal_recruit", "royal_recruits", "rune_giant", "skeleton_army", "skeleton_barrel",
    "skeleton_dragons", "skeleton_king", "sparky", "spear_goblins", "spirit_empress", "suspicious_bush",
    "three_musketeers", "tombstone", "valkyrie", "vines", "void", "wall_breakers", "witch", "wizard",
    "zap", "zappies", "archers_evo", "baby_dragon_evo", "barbarians_evo", "bats_evo", "battle_ram_evo",
    "bomber_evo", "cannon_evo", "dart_goblin_evo", "electro_dragon_evo", "elite_barbarians_evo",
    "executioner_evo", "firecracker_evo", "furnace_evo", "giant_snowball_evo", "goblin_barrel_evo",
    "goblin_cage_evo", "goblin_drill_evo", "goblin_giant_evo", "hunter_evo", "ice_spirit_evo",
    "inferno_dragon_evo", "knight_evo", "lumberjack_evo", "mega_knight_evo", "minion_horde_evo",
    "mortar_evo", "musketeer_evo", "pekka_evo", "princess_evo", "royal_ghost_evo", "royal_giant_evo",
    "royal_hogs_evo", "royal_recruits_evo", "skeleton_army_evo", "skeleton_barrel_evo", "skeletons_evo",
    "tesla_evo", "valkyrie_evo", "wall_breakers_evo", "witch_evo", "wizard_evo", "zap_evo", "balloon_hero",
    "barbarian_barrel_hero", "berserker_hero", "bowler_hero", "dark_prince_hero", "giant_hero",
    "goblins_hero", "ice_golem_hero", "knight_hero", "magic_archer_hero", "mega_minion_hero",
    "mini_pekka_hero", "musketeer_hero", "tombstone_hero", "valkyrie_hero", "wizard_hero",
    "archer_queen_ability", "boss_bandit_ability", "goblinstein_ability", "golden_knight_ability",
    "little_prince_ability", "mighty_miner_ability", "monk_ability", "skeleton_king_ability",
    "balloon_hero_ability", "barbarian_barrel_hero_ability", "berserker_hero_ability",
    "bowler_hero_ability", "dark_prince_hero_ability", "giant_hero_ability", "goblins_hero_ability",
    "ice_golem_hero_ability", "knight_hero_ability", "magic_archer_hero_ability",
    "mega_minion_hero_ability", "mini_pekka_hero_ability", "musketeer_hero_ability",
    "tombstone_hero_ability", "valkyrie_hero_ability", "wizard_hero_ability", "arrows_aoe",
    "barbarian_barrel_aoe", "clone_aoe", "earthquake_aoe", "fireball_aoe", "freeze_aoe",
    "giant_snowball_aoe", "goblin_barrel_aoe", "goblin_curse_aoe", "graveyard_aoe", "lightning_aoe",
    "poison_aoe", "rage_aoe", "rocket_aoe", "royal_delivery_aoe", "the_log_aoe", "tornado_aoe",
    "vines_aoe", "void_aoe", "zap_aoe",
)

# Engine names with NO detector class (catalog display_name / form_name -> appended vocab id).
# Found by running the alias rules over all 152 catalog cards + the 101 names in
# icebow/data/bc_pro_v2/name_stats.json: MergeMaiden_Mounted is the only one ever recorded;
# DarkElixir_Bottle is a not-in-use catalog card; CHAR_DISABLED_* are placeholders (-> None).
ENGINE_ONLY_CLASSES: tuple[str, ...] = ("spirit_empress_air", "dark_elixir_bottle")

UNIT_VOCAB: list[str] = list(DETECTOR_CLASSES) + list(ENGINE_ONLY_CLASSES)
_ID: dict[str, int] = {n: i for i, n in enumerate(UNIT_VOCAB)}
N_DETECTOR = len(DETECTOR_CLASSES)      # 230
N_VOCAB = len(UNIT_VOCAB)               # 232

# The 46 detector spell classes (26 card-art/projectile + 20 ``_aoe`` ground effects), derived from
# CardDB.kind(card_threat.base_key(cls)) == "spell" over the 230 classes (2026-09-06; test asserts).
SPELL_CLASSES: frozenset[str] = frozenset((
    "tornado", "rocket", "the_log", "arrows", "barbarian_barrel", "clone", "earthquake", "fireball", "freeze",
    "giant_snowball", "goblin_barrel", "goblin_curse", "graveyard", "lightning", "mirror", "poison", "rage",
    "royal_delivery", "vines", "void", "zap", "giant_snowball_evo", "goblin_barrel_evo", "zap_evo",
    "barbarian_barrel_hero", "barbarian_barrel_hero_ability", "arrows_aoe", "barbarian_barrel_aoe", "clone_aoe",
    "earthquake_aoe", "fireball_aoe", "freeze_aoe", "giant_snowball_aoe", "goblin_barrel_aoe", "goblin_curse_aoe",
    "graveyard_aoe", "lightning_aoe", "poison_aoe", "rage_aoe", "rocket_aoe", "royal_delivery_aoe", "the_log_aoe",
    "tornado_aoe", "vines_aoe", "void_aoe", "zap_aoe",
))
_SPELL_IDS: frozenset[int] = frozenset(_ID[n] for n in SPELL_CLASSES)
AOE_CLASSES: frozenset[str] = frozenset(n for n in SPELL_CLASSES if n.endswith("_aoe"))

# The 19 detector building classes (same derivation, kind == "building"); everything else is a troop.
BUILDING_CLASSES: frozenset[str] = frozenset((
    "tesla", "x_bow", "barbarian_hut", "bomb_tower", "cannon", "elixir_collector", "goblin_cage", "goblin_drill",
    "goblin_hut", "inferno_tower", "mortar", "tombstone", "cannon_evo", "goblin_cage_evo", "goblin_drill_evo",
    "mortar_evo", "tesla_evo", "tombstone_hero", "tombstone_hero_ability",
))


def kind_of(cls_id: int) -> str:
    """'spell' | 'building' | 'troop' (engine-only names count as troops)."""
    n = UNIT_VOCAB[cls_id]
    return "spell" if n in SPELL_CLASSES else "building" if n in BUILDING_CLASSES else "troop"

_SUFFIXES = ("_ability", "_hero", "_evo", "_aoe")


def unit_id(name: str) -> int:
    """Vocab id of a class name; KeyError if unknown."""
    return _ID[name]


def is_spell(cls_id: int) -> bool:
    return cls_id in _SPELL_IDS


def base_key(name: str) -> str:
    """Strip detector suffixes fully (``knight_hero_ability`` -> ``knight``); mirrors card_threat.base_key."""
    k = name
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if k.endswith(suf):
                k = k[: -len(suf)]
                changed = True
    return k


# engine display name -> detector/sim key. Copied verbatim from build_bc_v2.py:47-62 (itself
# replay_drive.SLUG_ALIASES inverted); that file is a scratchpad script, not an importable package.
# One row added: DarkElixir_Bottle (catalog, not in use; CamelCase->snake would give a double underscore).
_ALIAS_INV: dict[str, str] = {
    "AngryBarbarians": "elite_barbarians", "Archer": "archers", "Assassin": "bandit", "BarbLog": "barbarian_barrel",
    "MovingCannon": "cannon_cart", "BlowdartGoblin": "dart_goblin", "AxeMan": "executioner", "FireSpirits": "fire_spirit",
    "DartBarrell": "flying_machine", "FirespiritHut": "furnace", "Snowball": "giant_snowball", "SkeletonWarriors": "guards",
    "Heal": "heal_spirit", "IceGolemite": "ice_golem", "IceSpirits": "ice_spirit", "RageBarbarian": "lumberjack",
    "EliteArcher": "magic_archer", "WitchMother": "mother_witch", "DarkWitch": "night_witch", "Ghost": "royal_ghost",
    "GiantBuffer": "rune_giant", "SkeletonBalloon": "skeleton_barrel", "ZapMachine": "sparky", "MergeMaiden": "spirit_empress",
    "MergeMaiden_Normal": "spirit_empress", "MergeMaiden_Mounted": "spirit_empress_air", "Log": "the_log",
    "DarkMagic": "void", "MiniSparkys": "zappies", "Xbow": "x_bow", "Wallbreakers": "wall_breakers",
    "Elixir Collector": "elixir_collector", "Pekka": "pekka", "MiniPekka": "mini_pekka", "GlobalLightning": "lightning",
    "GlobalClone": "clone", "RoyalRecruits_Chess": "royal_recruits", "SkeletonWarriors_SpookyChess": "guards",
    "SuperArcher": "archers", "SuperEliteArcher": "magic_archer", "SuperHogRider": "hog_rider",
    "SuperHogRiderTerry": "hog_rider", "SuperIceGolemite": "ice_golem", "SuperKnight": "knight",
    "SuperLavaHound": "lava_hound", "SuperMiniPekka": "mini_pekka", "SuperWitch": "witch", "TriWizards": "wizard",
    "PrinceBuff": "prince", "GoblinPartyHut": "goblin_hut", "GoblinPartyRocket": "rocket", "GoblinRocketSilo": "goblin_hut",
    "BarbarianLauncher": "barbarian_barrel", "ElixirBarrel": "elixir_collector", "WarmSpell": "fireball",
    "DarkElixir_Bottle": "dark_elixir_bottle",
}


def engine_key(name: str) -> Optional[str]:
    """Engine display name -> vocab key (no sub-spawn split). None for crown towers ('-1'), the empty
    string, and catalog placeholders. Strips the recorder's ``@evolution`` deck-list suffix."""
    n = str(name).split("@", 1)[0]
    if not n or n == "-1" or n.startswith("CHAR_DISABLED"):
        return None
    if n in _ALIAS_INV:
        return _ALIAS_INV[n]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", n.replace(" ", "")).lower()


# (parent key, max_hp) -> detector sub-spawn class. The engine names every body by its parent card
# (obs_audit_engine.md 4.3); max_hp is the only separator. Thresholds sit between the measured
# level-11 values, survey over all 211 batch_v2 recordings (obs_contract_impl.md):
#   golem        5120 parent / 1039 golemite            (a) measured
#   lava_hound   3581 parent /  215 lava_pups           (a) measured
#   elixir_golem 1569 parent /  762 golemite / 360 blob (a) measured
#   royal_recruits: every body 547 -> royal_recruit     (a) measured (the card never appears as one entity)
#   mother_witch  529 parent; hog spawn NEVER seen      (b) UNTESTED -- 400 is a guess; TODO measure
def _sub_golem(mhp: float) -> str:
    return "golemite" if mhp < 2500 else "golem"                      # measured 5120 / 1039


def _sub_lava(mhp: float) -> str:
    return "lava_pups" if mhp < 1000 else "lava_hound"                # measured 3581 / 215


def _sub_egolem(mhp: float) -> str:
    if mhp >= 1100:                                                   # measured 1569
        return "elixir_golem"
    return "elixir_golemite" if mhp >= 500 else "elixir_blob"         # measured 762 / 360


def _sub_recruits(mhp: float) -> str:
    return "royal_recruit"                                            # measured: all bodies 547


def _sub_mwitch(mhp: float) -> str:
    # UNMEASURED: no cursed-hog body in any recording; 400 is a guess (parent measured at 529). TODO.
    return "mother_witch_hog" if mhp < 400 else "mother_witch"


_SUBSPAWN = {"golem": _sub_golem, "lava_hound": _sub_lava, "elixir_golem": _sub_egolem,
             "royal_recruits": _sub_recruits, "mother_witch": _sub_mwitch}

# Spawn-spell BODIES: the engine names the troops a spell drops by the SPELL (211-recording survey:
# BarbLog 716 x760, GoblinBarrel 202 x308 / 81 x41, Graveyard 81 x471, RoyalDelivery 547 x13). On screen
# they are the troop, so an entity carrying one of these names maps to the troop class. 'Clone' bodies
# (hp 1, x17) keep the clone id: the engine does not say what was cloned.
_SPELL_BODY = {"barbarian_barrel": "barbarians",       # (a) measured 716 = barbarian
               "goblin_barrel": "goblins",             # (a) measured 202 = goblin; the 81-hp body is (b) UNTESTED
               "graveyard": "skeletons",               # (a) measured 81 = skeleton
               "royal_delivery": "royal_recruit"}      # (a) measured 547 = one recruit


def engine_unit_id(name: str, max_hp: Optional[float] = None) -> Optional[int]:
    """Engine entity (display name, max_hp) -> vocab id; None when unmapped (towers, placeholders,
    names outside the vocab). With max_hp None a sub-spawn parent maps to the parent class."""
    k = engine_key(name)
    if k is None:
        return None
    if max_hp is not None and k in _SUBSPAWN:
        k = _SUBSPAWN[k](float(max_hp))
    elif max_hp is not None and k in _SPELL_BODY:
        k = _SPELL_BODY[k]
    return _ID.get(k)


def engine_spell_id(name: str) -> Optional[int]:
    """Engine ``effects`` entry name -> vocab id of its spell class, preferring the ``_aoe`` ground-effect
    class when the detector has one (that is what a ground effect looks like on screen). None for
    unit-attack effects (Xbow, IceWizard, ...) and tower shots ('-1'): they are not spells."""
    k = engine_key(name)
    if k is None:
        return None
    if k + "_aoe" in SPELL_CLASSES:
        return _ID[k + "_aoe"]
    return _ID[k] if k in SPELL_CLASSES else None

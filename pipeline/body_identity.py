"""Public body identity from catalog and measured calibration records.

This changes observations, never card choices. Exact catalog maximum-HP evidence
separates a spawned body from its originating card. Unrecognised or ambiguous
evidence retains the legacy identity and form. No current/future opponent state.

Level awareness (feature version 5): every table holds each body's exact catalog HP at every card level, tagged
with the level. When one HP value matches different identities at different levels, the tie is broken by (1) the
level of a same-side parent of that card on the same board, then (2) the card level implied by the side's tower
max HP (``level_of_factor``). Native and SIM are level 11 (factor exactly 1.0).
"""
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from pipeline import vocab
from pipeline.obs_contract import REPO

CATALOG = REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards.json'
CALIBRATION = CATALOG.parent.parent / 'calibration.json'
# Coverage boundary: each family has native replay witnesses (L73 identity census, scratchpad/gauntlet/L73/
# identity_fix/native_census.out). Observation normalisation, not a tactical preference or a spawn schedule.
# Graveyard needs no table: its bodies already map to skeletons (vocab._SPELL_BODY, measured 81 x8,502).
FAMILIES = frozenset(('witch', 'night_witch', 'furnace', 'goblin_hut', 'barbarian_hut', 'tombstone',
                      'goblin_drill', 'skeleton_barrel', 'goblin_giant', 'goblin_cage', 'phoenix',
                      'skeleton_king', 'mother_witch'))
BODY_ALIASES = {'Skeleton': 'skeletons', 'Bat': 'bats', 'Barbarian': 'barbarians', 'SpearGoblin': 'spear_goblins',
                # 2026-10-06 additions (catalog units.<name>.raw.Name):
                'Goblin': 'goblins', 'SpearGoblinGiant': 'spear_goblins', 'SkeletonKingSkeleton': 'skeletons',
                'VoodooHog': 'mother_witch_hog'}
# Body links the catalog CARD record does not carry, as catalog `units` keys. Evidence = native census (level 11):
#   GoblinDrill: the record's hitpoints (1000 -> 2560) is the underground GoblinDrillDig body; the surfaced drill is
#     units.GoblinDrill 513 -> 1313 (x1,250 native, kind 12) and spawns units.Goblin 79 -> 202 (x4,106). The 2560 and
#     1313 bodies are consecutive, not simultaneous (1 of 4,861 drill frames holds both) -> both are the drill (parent).
#   SkeletonKing: units.SkeletonKingSkeleton (summoned skeletons; see MEASURED_HP for their 1-HP reading).
#   Phoenix: units.PhoenixEgg 124 -> 317 (x320 native) -- no vocab class (child_no_class below).
#   WitchMother: units.VoodooHog 246 -> 629 (cursed hog; x2,499 native, always card_id -1 -> UNNAMED below).
#   SkeletonBalloon_EV1: the evolution record lists no death spawn, but native Evo Skeleton Barrels drop 81-HP
#     skeletons (x2,774, form 1) exactly like the base card's units.SkeletonContainerNew -> Skeleton.
EXTRA = {('goblin_drill', 0): (('GoblinDrill', 'parent'),), ('goblin_drill', 1): (('GoblinDrill_EV1', 'parent'),),
         ('skeleton_barrel', 1): (('SkeletonContainerNew', 'child'),),
         ('skeleton_king', 0): (('SkeletonKingSkeleton', 'child'),), ('phoenix', 0): (('PhoenixEgg', 'child'),),
         ('mother_witch', 0): (('VoodooHog', 'child'),)}
# MEASURED HP readings with no catalog formula. Skeleton King's summoned skeletons read max_hp 1 in native recordings
# (285 bodies in 24 SK replays, born in pairs ~10 ticks apart right after each logged SK ability, moving 6-10 tiles)
# and live (111 bodies); the catalog says 32 -> 81, which never appears under the SK name. Level independent.
MEASURED_HP = {('skeleton_king', 1): 'skeletons'}
# Bodies the engine/reader report with card_id -1 (no name): catalog unit -> vocab class, levels of the card that
# makes them. Native: 629 x176 (VoodooHog L11) and 202 x80 (Goblin L11); live: 915 (VoodooHog L15).
UNNAMED = (('VoodooHog', 'mother_witch_hog', 'WitchMother'), ('GoblinCurseGoblin', 'goblins', 'GoblinCurse'))
_CHILD_RANK = {'parent': 0, 'child': 1, 'child_no_class': 2}

# ---- L74 identity extension: OPT-IN, live only (live_play --identity-ext on -> GenPilot.identity_ext -> extension()).
# Off (the default) = resolve_board unchanged. Training data (gen_dataset_v32_fv5) never had it. Evidence:
# scratchpad/gauntlet/L74/identity/ (census.py = live census, native_scan.py = training corpora, wiki/ = api.php pages).
EXTENSION = False
# Reader card ids absent from the pinned live catalog (dropped today) -> catalog card name. Every live body's max_hp is
# that card's catalog HP at a playable level: 13000043 AngryBarbarians L14/15/16 (evo; HANDOFF 10-06 native proof),
# 203000042 ElectroWizard L11/14/16 (troop hero id = 203000000 + base id), 13000075 ElectroGiant L11/16 (evo, 10-06
# Shocktober post), 26000107 RoyaleSim MinionGiant L11/13 (released 2026-09-05). Form 0: the model was trained on these
# classes only in form 0 (an evo / hero form of them never occurs in gen_dataset_v32_fv5).
EXT_CARD_IDS = {'13000043': 'AngryBarbarians', '13000075': 'ElectroGiant', '203000042': 'ElectroWizard',
                '26000107': 'MinionGiant'}
# No vocab class -> closest learned class. Minion Giant (catalog: flying_height 3000, target_only_buildings, speed 60,
# 1817 HP at L11) vs Balloon (flying, buildings only, speed 60, 1676 HP); differs in range (4 tiles vs melee) and
# damage (189 / 1.5 s vs 640 / 2 s at L11).
EXT_CLASS = {'minion_giant': 'balloon'}
# (parent key, reader form) -> ((unit, level-1 HP or None = catalog units[unit], class or None = drop), ...): spawned /
# ability bodies the reader names by their card, given today the card's own class. HP x the parent's level multipliers
# reproduces every live value (census). Mortar evo shells spawn Goblins (catalog Mortar_EV1, wiki); Evo Royal Ghost
# Souldiers = skeleton HP / damage / speed (catalog Ghost_EV1_Summon_*, wiki 81 / 81 at L11; hit 1.8 s splash vs 1.1 s
# single); Little Prince's Guardienne = Knight-like (catalog ChampionGuard 625 / 91 / 1.2 s / speed 60 / range 1.2 vs
# Knight 690 / 79 / 1.2 s / 60 / 1.2; the wiki calls her "comparable to a Knight").
# Hero ability units: client-extracted stats in RoyaleSim 20261006 data/derived/cards.json hero_forms[*].tables.units
# (level 1; x2.56 = L11); nearest class = scratchpad/gauntlet/L74/identity/nearest.py (same transport / targets / reach /
# splash / kind, then |log| HP + DPS + speed): DarkPrinceHero_Mount 530 HP, buildings only, ground, speed 60, charge
# -> ram_rider (690, buildings, 60, charge; dist .54); MusketeerTurret 600 HP building, air + ground, 4 tiles, 10 s
# -> tesla (dist .66; goblin_hut .58 is a tie within noise, tesla kept); SkeletonTrooper 185 HP ground melee, targets
# ground, speed 120 -> bandit (354, ground melee, speed 90; dist .98); TombstoneHero_Monster_Active 1650 HP, buildings
# only, ground, speed 60 -> giant (1550, buildings, 45; dist .52). No class fits -> DROPPED (None): the Hero Goblins
# banner GoblinHero_Flag_Building (1000 HP, no attack, no movement; its 2 goblins read as goblins when they appear) and
# the Hero Magic Archer decoy EliteArcherHero_Dummy (106 HP, no damage, 7 s) -- today they read as an attacking goblin
# / Magic Archer.
EXT_BODIES = {('mortar', 1): (('Goblin', None, 'goblins'),),
              ('royal_ghost', 1): (('Ghost_EV1_Summon_Left', None, 'skeletons'),),
              ('little_prince', 0): (('ChampionGuard', None, 'knight'),),
              ('dark_prince', 2): (('DarkPrinceHero_Mount', 530, 'ram_rider'),),
              ('musketeer', 2): (('MusketeerTurret', 600, 'tesla'),),
              ('balloon', 2): (('SkeletonTrooper', 185, 'bandit'),),
              ('tombstone', 2): (('TombstoneHero_Monster_Active', 1650, 'giant'),),
              ('goblins', 2): (('GoblinHero_Flag_Building', 1000, None),),
              ('magic_archer', 2): (('EliteArcherHero_Dummy', 106, None),)}


@contextmanager
def extension(on=True):
    """resolve_board with the L74 extension inside the block (restored after, also on error)."""
    global EXTENSION
    old, EXTENSION = EXTENSION, bool(on)
    try:
        yield
    finally:
        EXTENSION = old


@dataclass(frozen=True)
class Identity:
    cls: int | None
    form: int
    reason: str
    how: str = 'exact'      # exact | parent_level | tower_level -- which evidence settled a multi-level tie


def child_names(record):
    names = set()
    for field in ('spawner', 'death_spawn'):
        value = record.get(field) or {}
        names.update(value[k] for k in ('character', 'character2') if value.get(k))
    for value in (record.get('action_graph') or {}).get('spawns', []):
        if value.startswith('CharacterType:'):
            names.add(value.split(':', 1)[1])
    return names


def body_key(name, units):
    unit = units.get(name)
    if unit is None:
        return None
    # Derived variants retain their underlying character name in raw.Name.
    base = (unit.get('raw') or {}).get('Name', name)
    key = BODY_ALIASES.get(base, vocab.engine_key(base))
    return key if key in vocab.UNIT_VOCAB else None


@lru_cache(maxsize=1)
def _catalog():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    # Recordings span table vintages. The simulator also applies the measured
    # client-value corrections, so retain both exact public HP interpretations.
    # Never replace an ambiguous maximum with a guessed body identity.
    calibration = json.loads(CALIBRATION.read_text(encoding='utf-8'))
    correction = calibration.get('cards', {}).get('CLIENT16402_VALUES', {}).get('value', {})
    calibrated = (correction.get('values', {})
                  if correction.get('arm') == 'client16402' and correction.get('table') == catalog.get('version')
                  else {})
    return catalog, calibrated


def _hitpoints(name, record):
    _, calibrated = _catalog()
    if record.get('hitpoints') is None:
        return set()
    values = {int(record['hitpoints'])}
    for n in (name, (record.get('raw') or {}).get('Name')):
        changed = calibrated.get(n, {}).get('Hitpoints')
        if isinstance(changed, int) and changed > 0:
            values.add(changed)
    return values


# MEASURED level 17 (a Mirror of a level-16 card): one live match (live_play_20261006_150923) holds Evo Witch bodies
# 1476 = 328 x 4.50 and 144 = 32 x 4.50 next to the same opponent's level-16 Witch 1341 / skeletons 130. The catalog
# multipliers stop at 409 (level 16); 450 continues its x1.10 steps.
MIRROR_LEVEL = (17, 450)


def _levels(record):
    """(level, multiplier percent) over the card's playable levels, plus the measured Mirror level 17."""
    ls = record['level_scaling']
    last = None
    for level in range(1 + ls['relative_level'], 1 + ls['relative_level'] + ls['level_count']):
        step = level - ls['base_level']
        if 0 <= step < len(ls['multiplier_percent_by_level']):
            last = level
            yield level, ls['multiplier_percent_by_level'][step]
    if last == MIRROR_LEVEL[0] - 1:
        yield MIRROR_LEVEL


def _descendants(names, units):
    """Spawned bodies, transitively (SkeletonContainerNew -> Skeleton, SpearGoblinGiant -> SpearGoblin)."""
    out, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in out:
            continue
        out.add(name)
        todo.extend(child_names(units.get(name) or {}))
    return out


@lru_cache(maxsize=1)
def tables():
    """{(family, form): {max_hp: {(cls, form, reason, level)}}} from the catalog (see module notes)."""
    catalog, _ = _catalog()
    units = catalog['units']
    canonical = {}
    for card in catalog['cards']:
        key = vocab.engine_key(card['name'])
        canonical.setdefault(key, card)
    rows = {(key, 0): canonical[key] for key in FAMILIES}
    for field, form in (('evolutions', 1), ('hero_forms', 2)):
        for card in catalog[field]:
            key = vocab.engine_key(card.get('form_of', ''))
            if key in FAMILIES:
                rows[key, form] = card
    result = {}
    for (parent, form), record in rows.items():
        pid = vocab.unit_id(parent)
        bodies = [(record['name'], record, 'parent')]
        for name, role in EXTRA.get((parent, form), ()):
            bodies.append((name, units[name], role))
        extra_children = {n for n, r in EXTRA.get((parent, form), ())}
        for name in _descendants(child_names(record) | extra_children, units) - {record['name']}:
            if name in units and all(name != b[0] for b in bodies):
                bodies.append((name, units[name], 'child'))
        possibilities = {}
        for level, multiplier in _levels(record):
            for name, rec, role in bodies:
                key = pid if role == 'parent' else body_key(name, units)
                if role == 'parent':
                    ident = (pid, form, 'parent', level)
                elif key is None or key == parent:
                    # A spawned body with no vocab class of its own (Goblin Brawler, Phoenix egg): keep the parent's
                    # class, but it is not the evolved/hero unit, so form 0 in every adapter.
                    ident = (pid, 0, 'child_no_class', level)
                else:
                    # A child is its own character, not the parent's evo/hero.
                    ident = (vocab.unit_id(key), 0, 'child', level)
                for base_hp in _hitpoints(name, rec):
                    hp = base_hp * multiplier // 100
                    if hp > 0:
                        possibilities.setdefault(hp, set()).add(ident)
        for (fam, hp), child in MEASURED_HP.items():
            if fam == parent:
                possibilities.setdefault(hp, set()).add((vocab.unit_id(child), 0, 'child', None))
        result[parent, form] = possibilities
    return result


@lru_cache(maxsize=1)
def unnamed_table():
    """{max_hp: {(cls, 0, 'unnamed', level)}} for card_id -1 troop bodies (UNNAMED)."""
    catalog, _ = _catalog()
    cards = {c['name']: c for c in catalog['cards']}
    out = {}
    for unit, cls, card in UNNAMED:
        for level, multiplier in _levels(cards[card]):
            for base_hp in _hitpoints(unit, catalog['units'][unit]):
                out.setdefault(base_hp * multiplier // 100, set()).add((vocab.unit_id(cls), 0, 'unnamed', level))
    return out


@lru_cache(maxsize=1)
def _multipliers():
    catalog, _ = _catalog()
    return catalog['cards'][0]['level_scaling']['multiplier_percent_by_level']


def level_of_factor(factor):
    """Card level whose HP multiplier relative to level 11 is nearest the tower factor (tower max / level-11 max).
    MEASURED live: princess 4424/3052 = 1.4496, king 7032/4824 = 1.4577 -> 15 (372/256 = 1.453; 14 = 1.324)."""
    if factor is None or not factor > 0:
        return None
    m = _multipliers()
    return 1 + min(range(len(m)), key=lambda i: abs(math.log(m[i] / m[10]) - math.log(factor)))


def _pick(cands, parent_levels=None, level=None):
    """Unique (cls, form) among candidates -> Identity, else None. Ties settled by parent level, then tower level."""
    def unique(cs, how):
        ids = {(c[0], c[1]) for c in cs}
        if len(ids) != 1:
            return None
        best = min(cs, key=lambda c: _CHILD_RANK.get(c[2], 3))
        return Identity(best[0], best[1], best[2], how)
    got = unique(cands, 'exact')
    if got is None and parent_levels:
        same = [c for c in cands if c[3] in parent_levels or c[3] is None]
        got = unique(same, 'parent_level') if same else None
    if got is None and level is not None:
        leveled = [c for c in cands if c[3] is not None]
        if leveled:
            near = min(abs(c[3] - level) for c in leveled)
            got = unique([c for c in leveled if abs(c[3] - level) == near], 'tower_level')
    return got


def _table_for(key, form):
    table = tables().get((key, int(form)))
    if table is None and key in FAMILIES and int(form) == 2:
        # SIM marks champions (Skeleton King) hero-form via status bit 16; native/live give them form 0.
        table = tables().get((key, 0))
    return table


def resolve(name, max_hp, form=0, *, level=None, parent_levels=None):
    if max_hp is not None and math.isfinite(float(max_hp)) and float(max_hp) <= 0:
        # Unreadable body (reader/native hp = max_hp = -1; every one measured is an Evo Witch or a Hero Tombstone):
        # its card, its own form, never an HP sub-spawn split (-1 would read as a Mother Witch hog).
        return Identity(vocab.engine_unit_id(str(name), None), int(form), 'unreadable')
    legacy = vocab.engine_unit_id(str(name), max_hp)
    key = vocab.engine_key(str(name))
    table = _table_for(key, form)
    if table is None:
        # SIM may already name a child directly. Recognise the same catalog
        # aliases without applying the originating parent's form to it.
        if name in BODY_ALIASES:
            return Identity(vocab.unit_id(BODY_ALIASES[name]), 0, 'explicit_child')
        return Identity(legacy, int(form), 'legacy')
    if max_hp is None or not math.isfinite(float(max_hp)) or int(max_hp) != float(max_hp):
        return Identity(legacy, int(form), 'unknown_hp')
    cands = table.get(int(max_hp), set())
    if not cands:
        # SIM children of an EVOLVED parent carry status 0 (form 0) where native/live children carry the evo id:
        # an Evo Goblin Giant's goblins (202, SIM sim_verify.json) exist only in the form-1 table. Children only.
        cands = {c for (k, f), t in tables().items() if k == key and f != int(form)
                 for c in t.get(int(max_hp), ()) if c[2] != 'parent'}
    got = _pick(cands, parent_levels, level)
    if got is None:
        return Identity(legacy, int(form), 'ambiguous_hp' if cands else 'unknown_hp')
    if got.reason == 'parent':
        # the parent keeps the form the adapter read (SIM champion bit included)
        return Identity(got.cls, int(form), got.reason, got.how)
    return got


def parent_levels(name, max_hp, form=0):
    """Levels at which this body is exactly a parent of its card (empty when it is not, or is ambiguous)."""
    table = _table_for(vocab.engine_key(str(name)), form)
    if table is None or max_hp is None or not float(max_hp) > 0 or int(max_hp) != float(max_hp):
        return set()
    cands = table.get(int(max_hp), set())
    if {c[2] for c in cands} != {'parent'}:
        return set()
    return {c[3] for c in cands}


def resolve_unnamed(max_hp, *, level=None):
    """card_id -1 troop body -> Identity, or Identity(None, ...) when the HP matches no catalog body unambiguously."""
    if max_hp is None or not float(max_hp) > 0 or int(max_hp) != float(max_hp):
        return Identity(None, 0, 'unknown_hp')
    cands = unnamed_table().get(int(max_hp), set())
    got = _pick(cands, None, level)
    return got if got is not None else Identity(None, 0, 'ambiguous_hp' if cands else 'unknown_hp')


@lru_cache(maxsize=1)
def ext_tables():
    """{(parent key, form): {max_hp: {(cls, form, 'parent' | 'ext_child', level)}}} for EXT_BODIES. The parent's own
    HP is in the table too, so a value both bodies reach is settled by level or stays as today."""
    catalog, _ = _catalog()
    units = catalog['units']
    rec = {}
    for card in catalog['cards']:
        rec.setdefault((vocab.engine_key(card['name']), 0), card)
    for field, form in (('evolutions', 1), ('hero_forms', 2)):
        for card in catalog[field]:
            rec.setdefault((vocab.engine_key(card.get('form_of', '')), form), card)
    out = {}
    for (key, form), bodies in EXT_BODIES.items():
        parent, table = rec[key, form], out.setdefault((key, form), {})
        for level, m in _levels(parent):
            for hp in _hitpoints(parent['name'], parent):
                table.setdefault(hp * m // 100, set()).add((vocab.unit_id(key), form, 'parent', level))
            for unit, base, cls in bodies:
                for hp in ({base} if base else _hitpoints(unit, units[unit])):
                    table.setdefault(hp * m // 100, set()).add(
                        (None if cls is None else vocab.unit_id(cls), 0, 'ext_child', level))
    return out


def _extend(body, ident, level):
    """One body's identity with the L74 extension (see EXTENSION); unchanged unless a rule matches."""
    side, name, mhp, form, unnamed = body
    if unnamed:
        return ident
    real = EXT_CARD_IDS.get(str(name))
    if real is not None:
        key = vocab.engine_key(real)
        return Identity(vocab.unit_id(EXT_CLASS.get(key, key)), 0, 'ext_card')
    if (ident.reason not in ('legacy', 'unknown_hp', 'ambiguous_hp') or mhp is None or not float(mhp) > 0
            or int(mhp) != float(mhp)):
        return ident
    table = ext_tables().get((vocab.engine_key(str(name)), int(form)))
    got = _pick(table.get(int(mhp), set()), None, level) if table else None
    return Identity(got.cls, 0, got.reason, got.how) if got is not None and got.reason == 'ext_child' else ident


def resolve_board(bodies, factor_by_side):
    """Feature version 5 identities for one board, in order.

    ``bodies``: (side, name, max_hp, form, unnamed) per body. ``factor_by_side``: tower max HP / level-11 tower
    max HP. A parent seen on the same board fixes its card's level for that side; unreadable bodies (max_hp <= 0)
    keep their card class and form (reason ``unreadable``; obs_contract gives them hp_frac None = hp_known 0)."""
    level = {s: level_of_factor(f) for s, f in factor_by_side.items()}
    seen = {}
    for side, name, mhp, form, unnamed in bodies:
        if not unnamed:
            seen.setdefault((int(side), vocab.engine_key(str(name))), set()).update(parent_levels(name, mhp, form))
    out = []
    for side, name, mhp, form, unnamed in bodies:
        lv = level.get(int(side))
        if unnamed:
            out.append(resolve_unnamed(mhp, level=lv))
            continue
        key = vocab.engine_key(str(name))
        f = factor_by_side.get(int(side), 1.0)
        if _table_for(key, form) is None and float(mhp) > 0 and abs(f - 1.0) > 0.02:
            # no catalog table (Golem / Lava Hound / Elixir Golem splits): the fv4 level-11 thresholds, same
            # tower-factor normalisation as fv4 (obs_contract, IDENTITY_AUDIT #5)
            mhp = float(mhp) / f
        out.append(resolve(str(name), float(mhp), form, level=lv, parent_levels=seen.get((int(side), key))))
    if EXTENSION:
        out = [_extend(b, ident, level.get(int(b[0]))) for b, ident in zip(bodies, out)]
    return out

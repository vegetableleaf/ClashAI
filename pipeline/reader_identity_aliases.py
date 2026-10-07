"""Narrow public reader identities witnessed after the pinned catalog snapshot.

No guessed ID ranges or tactical behavior. The existing hero-button side-by-side
measurement (L70 reader, October4) identifies 203000023 as Hero Ice Wizard.
"""

HERO_ICE_WIZARD_ID = 203000023
ICE_WIZARD_ID = 26000023


def extend_names(names):
    """Return a new lookup with the witnessed identity; preserve supplied data."""
    result = dict(names)
    if result.get(ICE_WIZARD_ID) != 'IceWizard':
        raise ValueError('Reader alias requires the known IceWizard base identity')
    if HERO_ICE_WIZARD_ID in result and result[HERO_ICE_WIZARD_ID] != 'IceWizard':
        raise ValueError('Reader Hero Ice Wizard identity conflicts with catalog')
    result[HERO_ICE_WIZARD_ID] = 'IceWizard'
    return result


def extend_forms(forms):
    """Form2 is explicit public identity evidence, independent of hidden decks."""
    result = dict(forms)
    if result.get(ICE_WIZARD_ID) != ('IceWizard', 0):
        raise ValueError('Reader alias requires the known IceWizard base form')
    if HERO_ICE_WIZARD_ID in result and result[HERO_ICE_WIZARD_ID] != ('IceWizard', 2):
        raise ValueError('Reader Hero Ice Wizard form conflicts with catalog')
    result[HERO_ICE_WIZARD_ID] = ('IceWizard', 2)
    return result


def dedupe_hero_bodies(frame, radius=500):
    """Reader v2 reports id 203000023 for the Hero Ice Wizard AND its FloatingCube (Codex's named reader, 2026-10-06:
    IceWizardHero / IceWizardHeroFloatingCube / IceWizardHero_IceCube all carry it). Named evidence (L73/hero_dedupe/,
    1,202 census + 146 sampler3 records): every FloatingCube (607/607) sits exactly on its owner Hero and has
    category == owner category + 1. Drop such a cube, whatever the list order. TWO real Heroes on one side do occur
    (49 named frame-sides, e.g. 10-06 ticks 3148-3348, 2.8 tiles apart, each with its own cube) and both are kept.
    Fallback when the category rule does not decide (no category field): the old rule, drop a later 203000023 within
    ``radius`` (0.5 tile) of a kept one. IceCube is NOT handled (see L73/hero_dedupe/). Frames with nothing dropped are
    returned unchanged (same object)."""
    ents = frame.get('entities') or ()
    hero = [e for e in ents if int(e.get('card_id', -1)) == HERO_ICE_WIZARD_ID]
    if not hero:
        return frame

    def near(k, e):
        return k is not e and k.get('side') == e.get('side') and \
            abs(k['x'] - e['x']) <= radius and abs(k['y'] - e['y']) <= radius

    def cube(e):
        c = e.get('category')
        return c is not None and any(k.get('category') == c - 1 and near(k, e) for k in hero)

    kept_hero, drop = [], set()
    for e in hero:
        if cube(e) or (e.get('category') is None and any(near(k, e) for k in kept_hero)):
            drop.add(id(e))
        else:
            kept_hero.append(e)
    if not drop:
        return frame
    out = dict(frame)
    out['entities'] = [e for e in ents if id(e) not in drop]
    return out

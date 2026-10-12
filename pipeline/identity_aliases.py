"""

No guessed ID ranges or tactical behavior. The existing hero-button side-by-side
"""

HERO_ICE_WIZARD_ID = 203000023
ICE_WIZARD_ID = 26000023
HERO_ICE_WIZARD_NAMES = ('IceWizardHero', 'IceWizardHeroFloatingCube', 'IceWizardHero_IceCube')


def extend_names(names):
    """Return a new lookup with the witnessed identity; preserve supplied data."""
    result = dict(names)
    if result.get(ICE_WIZARD_ID) != 'IceWizard':
        raise ValueError('Alias requires the known IceWizard base identity')
    if HERO_ICE_WIZARD_ID in result and result[HERO_ICE_WIZARD_ID] != 'IceWizard':
        raise ValueError('Hero Ice Wizard identity conflicts with catalog')
    result[HERO_ICE_WIZARD_ID] = 'IceWizard'
    return result


def extend_forms(forms):
    """Form2 is explicit public identity evidence, independent of hidden decks."""
    result = dict(forms)
    if result.get(ICE_WIZARD_ID) != ('IceWizard', 0):
        raise ValueError('Alias requires the known IceWizard base form')
    if HERO_ICE_WIZARD_ID in result and result[HERO_ICE_WIZARD_ID] != ('IceWizard', 2):
        raise ValueError('Hero Ice Wizard form conflicts with catalog')
    result[HERO_ICE_WIZARD_ID] = ('IceWizard', 2)
    return result


def dedupe_hero_bodies(frame, radius=500):
    """
    category == owner category + 1. Drop such a cube, whatever the list order. TWO real Heroes on one side do occur
    (49 named frame-sides, e.g. 10-06 ticks 3148-3348, 2.8 tiles apart, each with its own cube) and both are kept.
    Fallback when the category rule does not decide (no category field): the old rule, drop a later 203000023 within
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

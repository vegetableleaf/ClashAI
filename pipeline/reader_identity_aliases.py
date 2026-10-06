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
    """Reader v2 reports id 203000023 for the Hero Ice Wizard AND its co-located FloatingCube (measured 2026-10-06:
    1,702/1,702 sidebyside frames carry them as a pair, same kind/hp/max_hp/position, the Hero listed first; the cube's
    hp stays at max while the Hero's drops). The alias above made the model see TWO heroes. Keep the first such object
    per side and drop any later one within ``radius`` reader units (0.5 tile). Frames without a duplicate are returned
    unchanged (same object)."""
    ents = frame.get('entities') or ()
    kept, drop = [], False
    for e in ents:
        if int(e.get('card_id', -1)) == HERO_ICE_WIZARD_ID and any(
                int(k.get('card_id', -1)) == HERO_ICE_WIZARD_ID and k.get('side') == e.get('side')
                and abs(k['x'] - e['x']) <= radius and abs(k['y'] - e['y']) <= radius for k in kept):
            drop = True
            continue
        kept.append(e)
    if not drop:
        return frame
    out = dict(frame)
    out['entities'] = kept
    return out

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

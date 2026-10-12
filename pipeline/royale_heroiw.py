"""Source-reviewed, opt-in 0.1.33 adapter helpers; importing this needs no SIM."""
from .royale_runtime import RUNTIME_ID
from .reader_identity_aliases import HERO_ICE_WIZARD_ID, HERO_ICE_WIZARD_NAMES

ENABLED = RUNTIME_ID in ('20261012', '20261012-linux')
CARD_TABLE = 'client160402017_20261006'
ICEBOW = frozenset(('Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons'))


def engine_options():
    # RustEngine JSON-encodes values itself; Battle's direct API instead takes JSON text.
    return {'calibration_overrides': {'cards.CARD_TABLE': CARD_TABLE}} if ENABLED else {}


def deck_forms(names, forms):
    out = list(forms)
    if ENABLED and frozenset(names) == ICEBOW:
        out[list(names).index('IceWizard')] = 2
    return out


def public_identity(unit_name):
    if ENABLED and unit_name in (*HERO_ICE_WIZARD_NAMES, 'IceWizard_hero'):
        return HERO_ICE_WIZARD_ID
    return None


def controller_body(flags, champion=False):
    # 0.1.20 removed STATUS_HERO from champions and hero summons.
    return flags >= 0 and (bool(flags & 16) or (ENABLED and champion))


def selected_card_data():
    """Read the wheel's selected table, never a mutable source checkout."""
    import json
    import royalesim
    return json.loads(royalesim.EMBEDDED_CARDS_160402017_JSON)

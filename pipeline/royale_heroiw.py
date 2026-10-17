"""Source-reviewed, opt-in 0.1.33 adapter helpers; importing this needs no SIM."""
import os

from .royale_runtime import RUNTIME_ID
from .reader_identity_aliases import HERO_ICE_WIZARD_ID, HERO_ICE_WIZARD_NAMES

ENABLED = RUNTIME_ID in ('20261012', '20261012-linux', '20261016-linux',   # 20261016-linux: 0.1.35, same card table + forms
                       'fork36-linux')                                    # the 0.1.36-based fork: same table + forms
CARD_TABLE = 'client160402017_20261006'
ICEBOW = frozenset(('Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons'))


def engine_options():
    # RustEngine JSON-encodes values itself; Battle's direct API instead takes JSON text.
    return {'calibration_overrides': {'cards.CARD_TABLE': CARD_TABLE}} if ENABLED else {}


def deck_forms(names, forms):
    out = list(forms)
    if ENABLED and frozenset(names) == ICEBOW:
        mode = os.environ.get('ROYALE_HEROIW_FORM', 'hero')
        if mode not in ('hero', 'normal'):
            raise ValueError('ROYALE_HEROIW_FORM must be hero or normal')
        out[list(names).index('IceWizard')] = 0 if mode == 'normal' else 2
    return out


def press_mode():
    """SIM-only opt-in; unset/off preserves HEROIW's v2 generic IW fallback, never = the IW ability is never pressed."""
    mode = os.environ.get('ROYALE_HEROIW_PRESS', 'off')
    if mode not in ('off', 'live', 'never'):
        raise ValueError('ROYALE_HEROIW_PRESS must be off, live or never')
    if mode != 'off' and not ENABLED:
        raise ValueError(f'ROYALE_HEROIW_PRESS={mode} needs the Hero IW runtime')
    return mode


def live_press_enabled():
    return press_mode() == 'live'


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

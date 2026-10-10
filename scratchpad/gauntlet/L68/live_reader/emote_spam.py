"""--emote-spam (L74, owner 2026-10-10): during WAIT decisions, tap the chat button then the owner's emote.

Calibrated live (Classic 1v1, 900x1600): chat button (88, 1365) opens a panel over the HAND AREA; the emote at (710, 1195)
sends it and closes the panel. The emote cooldown is 1.3 s. Pure helpers; live_play wires them to its tap channel.
"""
CHAT_XY, EMOTE_XY, SCREEN = (88, 1365), (710, 1195), (900, 1600)
HOLD_S = 0.6          # card taps wait until this long after an emote's first tap: the panel is closed by then
MIN_INTERVAL_S = 1.3  # the game's emote cooldown


def emote_due(now, last_t, interval_s, play, busy, p_play, tau, guard):
    """True = send an emote at this decision. play: the model decided to play (not WAIT); busy: a follow-up / pending
    play / ability tap is outstanding; guard x tau: skip when the model is close to playing (0 = no guard)."""
    if play or busy or now - last_t < interval_s:
        return False
    return not (guard > 0 and p_play >= guard * tau)


def hold_s(now, last_t):
    """Seconds a card tap must still wait after an emote whose first tap was at last_t."""
    return max(0.0, last_t + HOLD_S - now)


def emote_cmd(w, h, gap_ms):
    """The two-tap shell command, scaled to the screen like Layout does."""
    (cx, cy), (ex, ey) = [(round(x * w / SCREEN[0]), round(y * h / SCREEN[1])) for x, y in (CHAT_XY, EMOTE_XY)]
    sleep = f" sleep {gap_ms / 1000:g};" if gap_ms > 0 else ""
    return f"input tap {cx} {cy};{sleep} input tap {ex} {ey}"

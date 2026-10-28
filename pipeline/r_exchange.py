"""R_exchange (plan1026 Pillar 3): dense, zero-sum, outcome-only exchange reward from PUBLIC board state.

NOT wired into training (gates X2-X4 come first). Pure functions, numpy only, no engine imports, so live logs,
HF replays re-driven on crforge, and SIM traces can all feed the same code through the Frame format below.

Frame (one per observed tick, ascending ticks), observer-relative:
    {"tick": int, "side": observer side 0/1, "elixir": own elixir (float or None),
     "opp_elixir": public-counter estimate of the opponent's elixir (float or None; NEVER the true value in a fit),
     "ents": [(side, card_id, hp, max_hp, key), ...]}      # every visible body incl. towers (card_id -1)
Towers: card_id -1; per side the one with the largest max_hp is the king. Tower HP never rises; a tower missing from
ents for GRACE ticks and 2 observations is destroyed.

Per side s (own = 0, opp = 1 in the output) the running LOSSES are, counted identically for both sides:
    princess   princess-tower HP lost, in princess towers (a destroyed princess = 1.0)
    king       king HP lost, in king towers
    king_on    king activated (king damaged or a princess down), 0/1
    crowns     crowns conceded (princess towers destroyed; 3 if the king falls)
    elixir     elixir destroyed: body value x HP fraction lost (damage from any source incl. spells), plus the
               remaining fraction when a body disappears (killed between frames); building lifetime decay and
               kamikaze bodies connecting (spirits, Wall Breakers, ...) are excluded. Live bodies carry the card id of
               the card that made them, so a body counts as a deployed body (value = card elixir / bodies per card)
               only if its max_hp >= MAIN_FRAC x the largest max_hp seen so far for that card and side (running max ->
               causal); smaller bodies (a Witch's skeletons, Golemites, hut spawns, Lava pups) are spawns, value 0
    leak       elixir leaked: regen wasted while elixir >= 10
Feature x_k = opp loss_k - own loss_k (our gain minus theirs), so a positive beta means "good for us".
"""
import numpy as np

FEATURES = ("princess", "king", "king_on", "crowns", "elixir", "leak")
TICKS_PER_S = 20
PHASES = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))      # fit phases (plan1026 1x / 2x / OT)
REGEN_BOUNDS = ((0, 1 / 56), (2400, 2 / 56), (4800, 3 / 56))              # elixir per tick: 1x, 2x (incl OT 1st min), 3x
FULL = 9.99
GRACE = 10          # a body unseen for >= GRACE ticks AND >= 2 observations is killed (reader dropouts last 1-2 frames;
                    # 2 observations keep sparse per-decision traces from killing a body on one missed read)
MAIN_FRAC = 0.5     # ponytail: HP-ratio main/spawn split; Battle Ram's barbarians pass it (overcount), Goblin Gang's
                    # spear goblins fail it (undercount). An engine "spawned by" flag would replace this.
MAX_DT = 40         # longer observation gaps are not credited as leak (reader stall, not a game state)


def phase_index(tick):
    return 0 if tick < 2400 else 1 if tick < 3600 else 2


def regen(tick):
    r = 0.0
    for t0, v in REGEN_BOUNDS:
        if tick >= t0:
            r = v
    return r


def running_losses(frames, values):
    """frames -> (ticks [T], losses [T, 2, 6]) running totals; side 0 = observer, 1 = opponent.

    values: {card_id: (elixir_per_body, decay_hp_per_tick_fraction or 0.0, kamikaze bool)}; unknown ids add nothing.
    """
    T = len(frames)
    out = np.zeros((T, 2, len(FEATURES)))
    ticks = np.zeros(T, int)
    tmax = [{}, {}]                                  # tower key -> (max_hp, is_king)
    tlast = [{}, {}]                                 # tower key -> last hp
    tmiss = [{}, {}]                                 # tower key -> [tick first missing, observations missing]
    bodies = {}                                      # key -> [rel_side, cid, last_hp, max_hp, last_tick, missing, value]
    pmax = {}                                        # (rel_side, cid) -> largest max_hp seen (the card's main body)
    acc = np.zeros((2, len(FEATURES)))
    prev_tick = None
    for i, f in enumerate(frames):
        t, me = int(f["tick"]), f["side"]
        dt = 0 if prev_tick is None else t - prev_tick
        seen = set()
        towers = [[], []]
        for side, cid, hp, mhp, key in f["ents"]:
            rs = 0 if side == me else 1
            if cid == -1:
                towers[rs].append((key, hp, mhp))
                continue
            k = (key, cid, side)
            seen.add(k)
            b = bodies.get(k)
            v = values.get(cid)
            if b is None or hp > b[2] + 0.5 * mhp:           # new body (or an address reused by a fresh one)
                pm = pmax[rs, cid] = max(pmax.get((rs, cid), 0), mhp)
                bodies[k] = [rs, cid, hp, mhp, t, None, v[0] if v and mhp >= MAIN_FRAC * pm else 0.0]
                continue
            b[5] = None
            if v and mhp > 0:
                drop = (b[2] - hp) / mhp - v[1] * (t - b[4])     # building decay is not destruction
                if drop > 0:
                    acc[rs, 4] += b[6] * drop
            b[2], b[4] = hp, t
        for k, b in list(bodies.items()):                 # disappearance -> killed between frames (after GRACE)
            if k in seen:
                continue
            b[5] = b[5] or [t, 0]
            b[5][1] += 1
            if t - b[5][0] >= GRACE and b[5][1] >= 2:
                v = values.get(b[1])
                if v and not v[2] and b[3] > 0:
                    acc[b[0], 4] += b[6] * max(0.0, b[2] / b[3] - v[1] * (b[5][0] - b[4]))
                del bodies[k]
        for rs in (0, 1):                                 # towers: first sight fixes the max and the king
            if not towers[rs]:                            # a side with no tower at all is a reader glitch
                continue
            if not tmax[rs] and towers[rs]:
                km = max(m for _, _, m in towers[rs])
                tmax[rs] = {key: (m, m == km) for key, _, m in towers[rs]}
            now = {key: hp for key, hp, _ in towers[rs]}
            for key, (m, _) in tmax[rs].items():
                if key in now:
                    tmiss[rs].pop(key, None)
                    tlast[rs][key] = min(tlast[rs].get(key, m), max(0, now[key]))
                    continue
                ms = tmiss[rs].setdefault(key, [t, 0])
                ms[1] += 1
                if t - ms[0] >= GRACE and ms[1] >= 2:
                    tlast[rs][key] = 0
                else:
                    tlast[rs].setdefault(key, m)
            pr = [1 - tlast[rs][k] / m for k, (m, king) in tmax[rs].items() if not king]
            kg = [1 - tlast[rs][k] / m for k, (m, king) in tmax[rs].items() if king]
            down = sum(x >= 1 for x in pr)
            acc[rs, 0] = sum(pr)
            acc[rs, 1] = sum(kg)
            acc[rs, 2] = float(bool(down) or (bool(kg) and kg[0] > 0))
            acc[rs, 3] = 3 if kg and kg[0] >= 1 else down
        if 0 < dt <= MAX_DT:                              # leak: own from own elixir, opp from the public estimate
            for rs, e in ((0, f.get("elixir")), (1, f.get("opp_elixir"))):
                if e is not None and e >= FULL:
                    acc[rs, 5] += regen(t) * dt
        out[i], ticks[i] = acc, t
        prev_tick = t
    return ticks, out


def features(losses):
    """[..., 2, F] losses -> [..., F] x = opp loss - own loss."""
    return losses[..., 1, :] - losses[..., 0, :]


def step_rewards(ticks, x, beta, scale=0.5, cap=0.5):
    """Per-step R_exchange in win units: r_t = scale * beta[phase(t)] . (x_t - x_{t-1}), cumulative clipped to +-cap.

    beta: [3 phases, F] fitted logistic coefficients (log-odds per unit; no intercept -> doing nothing earns nothing).
    scale 0.5 = d(2 sigmoid(z) - 1)/dz at z = 0, i.e. log-odds -> expected R_win units near an even match.
    The clip keeps |sum_t r_t| <= cap, so a loss with a good exchange always totals below a win.
    """
    beta = np.asarray(beta, float)
    dx = np.diff(np.vstack([np.zeros((1, x.shape[1])), x]), axis=0)
    ph = np.array([phase_index(t) for t in ticks], int)
    raw = scale * np.einsum("tf,tf->t", dx, beta[ph])
    cum = np.clip(np.cumsum(raw), -cap, cap)
    return np.diff(np.concatenate([[0.0], cum]))


def r_exchange(frames, values, beta, scale=0.5, cap=0.5):
    """Match trace -> (ticks, per-step R_exchange). The pure entry point for the pipeline."""
    ticks, L = running_losses(frames, values)
    return ticks, step_rewards(ticks, features(L), beta, scale, cap)

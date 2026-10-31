"""RECON-5: deck-constrained repair of a side's play sequence under the 4-card cycle (design: ../RECON.md section 12).

Facts used (all from the battle-log deck, which the extractor already puts in plan['decks']):
  - a side has 8 distinct deck cards: 4 in hand, 4 in the queue; a played card goes to the back of the queue, the queue's front
    enters the hand (our own deal obeys this on 137 / 139 records, RECON.md section 4);
  - so ONLY plays of deck cards exist, and after any prefix of plays the state is one of the 70 x 24 = 1680 (hand set, queue order).
An observed sequence that fits no deal means plays are MISSING (unseen), MIS-LABELLED (a Mirror copy reads as the mirrored card)
or INVENTED. The repair is a shortest path over those 1680 states: each observed play must be played from the hand (cost 0);
any unseen play of a hand card may be inserted before it (cost 1); with Mirror in the deck an observed play may instead be the
Mirror (cost 1). min cost = the fewest unseen plays that make the match legal; the optimal repairs are enumerated, not guessed.
  python -I cyc.py            # planted self-check
"""
import itertools

STATES = [(frozenset(h), tuple(q)) for h in itertools.combinations(range(8), 4)
          for q in itertools.permutations([i for i in range(8) if i not in h])]
IDX = {s: k for k, s in enumerate(STATES)}
INF = 10 ** 9


def _play(s, h):
    hand, q = s
    return (hand - {h} | {q[0]}, q[1:] + (h,))


# TR[state index] = {card: next state index} for every card in hand
TR = [{h: IDX[_play(s, h)] for h in s[0]} for s in STATES]


def deal_of(state):
    """The (hand + queue) order list the engine's `deals` field takes for a state."""
    return sorted(state[0]) + list(state[1])


def solve(seq, ins_cards=range(8), mirror=None, max_cost=INF, allow_drop=False):
    """Shortest repair of the observed deck-index sequence seq.
    ins_cards: cards an unseen play may be (default any); mirror: the deck index of Mirror (an observed play may be it, cost 1)
    -> (cost, fwd, back): fwd[i][s] = min cost to be in state s after seq[:i] (inserts before seq[i] included), back[i][s] = min
    cost from state s before seq[i] to the end; cost None when no repair <= max_cost exists."""
    n, S = len(seq), len(STATES)
    ins = tuple(ins_cards)

    def relax(layer):
        # inserts inside one layer: unit costs, so a plain BFS by cost levels
        for c in range(max_cost + 1 if max_cost < INF else 12):
            front = [s for s in range(S) if layer[s] == c]
            if not front:
                continue
            for s in front:
                for h in ins:
                    t = TR[s].get(h)
                    if t is not None and layer[t] > c + 1:
                        layer[t] = c + 1
        return layer

    fwd = [[0] * S]
    fwd[0] = relax(fwd[0])
    for i in range(n):
        nxt = [INF] * S
        for s in range(S):
            c = fwd[i][s]
            if c >= INF:
                continue
            t = TR[s].get(seq[i])
            if t is not None and nxt[t] > c:
                nxt[t] = c
            if mirror is not None:
                t = TR[s].get(mirror)
                if t is not None and nxt[t] > c + 1:
                    nxt[t] = c + 1
            if allow_drop and nxt[s] > c + 1:         # the observed play never happened (an invented / duplicated play)
                nxt[s] = c + 1
        fwd.append(relax(nxt))
    best = min(fwd[n])
    back = [None] * (n + 1)
    back[n] = [0] * S
    for i in range(n - 1, -1, -1):
        b = [INF] * S
        for s in range(S):
            t = TR[s].get(seq[i])
            if t is not None:
                b[s] = back[i + 1][t]
            if mirror is not None:
                t = TR[s].get(mirror)
                if t is not None:
                    b[s] = min(b[s], back[i + 1][t] + 1)
            if allow_drop:
                b[s] = min(b[s], back[i + 1][s] + 1)
        # inserts: b[s] = min(b[s], 1 + b[TR[s][h]]) iterated to a fixpoint (<= 12 levels)
        for _ in range(12):
            ch = False
            for s in range(S):
                for h in ins:
                    t = TR[s].get(h)
                    if t is not None and b[t] + 1 < b[s]:
                        b[s] = b[t] + 1
                        ch = True
            if not ch:
                break
        back[i] = b
    return (best if best < INF and best <= max_cost else None), fwd, back


def repairs(seq, ins_cards=range(8), mirror=None, cap=200, max_cost=INF, allow_drop=False):
    """Enumerate optimal repairs: -> (cost, [(inserts, relabels, deal)]) with inserts = [(i, card)] (an unseen play of `card` just
    before observed play i), relabels = [i] (observed play i is the Mirror), deal = the engine deal list of an initial state
    that realises it. At most `cap` distinct (inserts, relabels); cost None when no repair <= max_cost exists."""
    cost, fwd, back = solve(seq, ins_cards, mirror, max_cost, allow_drop)
    if cost is None:
        return None, []
    n, ins = len(seq), tuple(ins_cards)
    out, seen = [], set()

    def walk(i, s, c, acc, rel, start, dr=()):
        if len(out) >= cap:
            return
        if i == n:
            k = (tuple(acc), tuple(rel), dr)
            if c == cost and k not in seen:
                seen.add(k)
                out.append((list(acc), list(rel) + [('drop', j) for j in dr], deal_of(STATES[start])))
            return
        t = TR[s].get(seq[i])                          # play the observed card from the hand
        if t is not None and c + back[i + 1][t] == cost:
            walk(i + 1, t, c, acc, rel, start, dr)
        if mirror is not None:                         # ... or read it as the Mirror
            t = TR[s].get(mirror)
            if t is not None and c + 1 + back[i + 1][t] == cost:
                walk(i + 1, t, c + 1, acc, rel + [i], start, dr)
        if allow_drop and c + 1 + back[i + 1][s] == cost:   # ... or it never happened
            walk(i + 1, s, c + 1, acc, rel, start, dr + (i,))
        for h in ins:                                  # ... or an unseen play of a hand card comes first
            t = TR[s].get(h)
            if t is not None and c + 1 + back[i][t] == cost:
                walk(i, t, c + 1, acc + [(i, h)], rel, start, dr)

    for s0 in range(len(STATES)):
        if back[0][s0] == cost:
            walk(0, s0, 0, [], [], s0)
        if len(out) >= cap:
            break
    return cost, out


def fits(seq):
    cost, _, _ = solve(seq, ins_cards=(), max_cost=0)
    return cost == 0


# ------------------------------------------------------------------ planted self-check
def demo():
    # a legal sequence: no repair needed
    assert fits([0, 1, 2, 3, 4, 5, 6, 7, 0, 1])
    # a card replayed after only 3 others cannot fit ...
    bad = [0, 1, 2, 3, 0]
    assert not fits(bad)
    # ... and ONE unseen play of another deck card repairs it (the cycle says a 5th card was played in between)
    cost, reps = repairs(bad)
    assert cost == 1 and reps, (cost, reps)
    assert all(len(i) == 1 for i, _, _ in reps)
    # restricting the unseen card to a card already in the sequence cannot repair this (needs a card from the queue)
    c2, _ = repairs(bad, ins_cards=(0, 1, 2, 3))
    assert c2 is None or c2 > 1
    # planted: take a legal sequence, delete one play, the repair must be able to restore exactly that play
    full = [0, 1, 2, 3, 4] * 4           # a legal 5-card rotation: dropping any play makes a repeat 3 plays apart
    import random
    rnd = random.Random(5)
    ok = tried = 0
    for _ in range(12):
        k = rnd.randrange(len(full))
        cut = full[:k] + full[k + 1:]
        if fits(cut):
            continue
        cost, reps = repairs(cut, cap=500)
        assert cost == 1, (k, cost)
        tried += 1
        ok += any(i == [(k, full[k])] for i, _, _ in reps)   # the true missing play is among the optimal repairs
    assert tried >= 3 and ok == tried, (ok, tried)
    # a Mirror in the deck: card 7 = Mirror; seq plays 0 then (Mirror copy reads as) 0 again after 2 others
    m = [0, 1, 2, 0]
    cm, rm = repairs(m, mirror=7)
    assert cm == 1 and any(rel == [3] for _, rel, _ in rm), (cm, rm)
    # a wrong deck is rejected: a play of a card that is not one of the 8 (index 8) is never legal, whatever is inserted
    assert solve([0, 1, 2, 8], max_cost=4)[0] is None
    # and a play of a deck card the extractor could not place (-1) the same
    assert solve([0, -1, 2], max_cost=4)[0] is None
    print('ok cyc')


if __name__ == '__main__':
    demo()

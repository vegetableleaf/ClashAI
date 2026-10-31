"""RECON-6: the form of every play from the cycle count (design: ../RECON.md section 13).

crforge decides a play's form itself (MatchSide.item / count, core 16.635.3, tables spells_*.json): a card in the deck's EVOLUTION slot
(slot flag bit 0) counts its plays since its last evolved play and its play is evolved once the count reaches the evolved row's
DarkElixirCost (Knight 2: plain, plain, evolved, plain, ...; Giant 1: plain, evolved, ...); a card in the HERO slot (bit 1) plays in its
hero form whenever it is not evolved. The count moves on EVERY play the client gave (a refused play too). So the form of every play is a
function of the side's play sequence, the slot flags and the tables: the SIM spawns the Hero / EV1 body from that function, and the reader
shows the same form on the body (extractor `form`: 0 plain, 1 evolved, 2 hero; spells carry 0 = unobservable).

What this module adds (nothing here changes crforge or the comparator):
  predict(...)      the forms the rule gives for a card's play sequence
  align(...)        the cheapest explanation of an OBSERVED form sequence by the rule: every observed play is kept (cost 0, form must agree)
                    or deleted (cost 1: an invented play, or a Mirror copy read as the copied card -- it moves no count), or an unseen
                    play is inserted before it (cost 1). A DP over the count (<= 3 states); all optimal alignments are enumerated.
  form_repairs(...) engine-scorable plan variants for an OPPONENT side whose cycle fits but whose forms do not: delete = drop the play or read
                    it as the Mirror (the previous play is the same card), as RECON-5's cycle repair does for cycle failures.
  python -I forms.py   planted self-check
"""
import collections

EVOLVED, HERO = 1, 2


def rules(tab):
    """-> (need, hero): need[card] = DarkElixirCost of the card's evolved row when its row lists it (> 0), hero = cards whose row lists a hero form."""
    need, hero = {}, set()
    for f in ('spells_characters', 'spells_buildings', 'spells_other'):
        for name, row in tab.rows[f].items():
            es = (row.get('columns') or {}).get('EvolvedSpells') or []
            if name + '_EV1' in es:
                n = tab.col('spells_evolved', name + '_EV1').get('DarkElixirCost') or 0
                if n > 0:
                    need[name] = n
            if name + '_hero' in es:
                hero.add(name)
    return need, hero


def form_of(c, flag, n, hero_ok):
    """The form of the next play of a card with count c (MatchSide.item): evolved when its slot counts and c reached n, else hero in the hero slot."""
    if flag & 1 and n and c >= n:
        return EVOLVED
    return HERO if flag & 2 and hero_ok else 0


def step(c, f, flag, n):
    """The count after a play of form f (MatchSide.count): only an evolution slot counts; an evolved / hero play resets it."""
    if not flag & 1:
        return c
    return 0 if f else (c + 1 if c < n else c)


def predict(n_plays, flag, n, hero_ok):
    """The forms of a card's first n_plays plays."""
    c, out = 0, []
    for _ in range(n_plays):
        f = form_of(c, flag, n, hero_ok)
        out.append(f)
        c = step(c, f, flag, n)
    return out


def align(obs, flag, n, hero_ok, cap=64, ins_cost=1):
    """obs: observed forms of a card's plays in run order (None = unobservable: a spell). -> (cost, alts, n_alts_total).
    alts: optimal alignments, each a tuple of ('del', i) / ('ins', i) (an unseen play inserted before observed play i; trailing inserts are
    not generated: nothing observes them). cost 0 = the rule explains every observed form. ins_cost: what an unseen play costs (a deleted play
    costs 1; default 1); None = no insertion at all (the repair generator: an edit needs a play to act on)."""
    INF = 10 ** 6
    ic = INF if ins_cost is None else ins_cost
    S = (n if flag & 1 and n else 0) + 1                      # counts 0 .. n (n = 0: one state)
    L = len(obs)
    f = [[INF] * S for _ in range(L + 1)]
    f[0][0] = 0

    def relax(i):       # inserts before observed play i (not after the last one)
        if i >= L or ic >= INF:
            return
        for _ in range(2 * S):
            for c in range(S):
                if f[i][c] < INF:
                    t = step(c, form_of(c, flag, n, hero_ok), flag, n)
                    if f[i][t] > f[i][c] + ic:
                        f[i][t] = f[i][c] + ic

    relax(0)
    for i in range(L):
        for c in range(S):
            if f[i][c] >= INF:
                continue
            p = form_of(c, flag, n, hero_ok)
            if obs[i] is None or obs[i] == p:
                t = step(c, p, flag, n)
                f[i + 1][t] = min(f[i + 1][t], f[i][c])
            f[i + 1][c] = min(f[i + 1][c], f[i][c] + 1)         # delete observed play i
        relax(i + 1)
    best = min(f[L])
    if best >= INF:
        return None, [], 0
    alts, seen = [], set()

    def back(i, c, cost, ops):
        if len(alts) >= cap:
            return
        if i == 0 and c == 0 and cost == 0:
            alts.append(tuple(sorted(ops)))
            return
        if i > L or cost < 0:
            return
        if i > 0:       # observed play i-1 was matched (c came from c0 by a play of form p) or deleted
            for c0 in range(S):
                p = form_of(c0, flag, n, hero_ok)
                if step(c0, p, flag, n) == c and (obs[i - 1] is None or obs[i - 1] == p) and f[i - 1][c0] == cost:
                    back(i - 1, c0, cost, ops)
            if f[i - 1][c] == cost - 1:
                back(i - 1, c, cost - 1, ops + [('del', i - 1)])
        if i < L and ic < INF:       # an insert before observed play i led into (i, c)
            for c0 in range(S):
                if step(c0, form_of(c0, flag, n, hero_ok), flag, n) == c and f[i][c0] == cost - ic and c0 != c:
                    back(i, c0, cost - ic, ops + [('ins', i)])

    # f[i][c] holds the cost AFTER inserts before play i, so the backward walk must undo inserts first, then the play: handled above in that order
    for c in range(S):
        if f[L][c] == best:
            back(L, c, best, [])
    uniq = sorted(set(alts))
    return best, uniq, len(uniq)


# ------------------------------------------------------------------ records and plans
def side_plays(plays, deck, side):
    """The side's play events in run order (the order crforge runs commands: run tick, then list order): [(index into plays, play)]."""
    return sorted(((k, p) for k, p in enumerate(plays) if p['side'] == side and p['kind'] == 'play' and p.get('card') in deck),
                  key=lambda kp: (kp[1]['run_ticks'][0], kp[1]['tick'], kp[0]))


def observed(p, tab):
    """The reader's form of a play, or None when it cannot show one (a spell leaves no body of its form: extractor form is 0 by construction)."""
    return None if tab.is_spell(p['card']) else p.get('form', 0)


def analyse(rec, side, tab, ru=None):
    """Per deck card with a slot flag and a form rule: {card: (cost, alts, n plays, [play ranks])} for the record's extracted plays of side."""
    need, hero = ru or rules(tab)
    sd = rec['sides'][str(side)]
    out = {}
    pl = side_plays(rec['plays'], sd['deck'], side)
    for k, card in enumerate(sd['deck']):
        flag = sd['slot_flags'][k]
        if not flag or not card or (card not in need and card not in hero):
            continue
        mine = [(r, p) for r, (_, p) in enumerate(pl) if p['card'] == card]
        obs = [observed(p, tab) for _, p in mine]
        cost, alts, _ = align(obs, flag, need.get(card, 0), card in hero)
        out[card] = (cost, alts, len(mine), [r for r, _ in mine])
    return out


def plan_obs(rec, plan, side):
    """Observed form of each play command of the side (matched to the record's plays by card and extracted tick; commands the record does not
    carry -- RECON's own additions -- are unobserved)."""
    pool = collections.defaultdict(list)
    for p in rec['plays']:
        if p['side'] == side and p['kind'] == 'play':
            pool[(p['card'], p['tick'])].append(p)
    out = {}
    for k, c in enumerate(plan['cmds']):
        if c['side'] == side and c['kind'] == 'play':
            ps = pool.get((c['card'], c['_src'].get('tick')))
            out[k] = ps.pop(0) if ps else None
    return out


def plan_cost(rec, plan, side, tab, ru=None):
    """Form-alignment cost of a PLAN's play sequence for the side, summed over its cards with a form rule: 0 = the count rule explains every
    observed form of the plan's plays (plays RECON added are unobserved). Compare with the cost of the base plan: an edit that takes it to 0
    is corroborated by the forms (extra evidence next to the ablation; it is not the ablation)."""
    import recon
    need, hero = ru or rules(tab)
    deck, flags = plan['decks'][side], rec['sides'][str(side)]['slot_flags']
    ob = plan_obs(rec, plan, side)
    sq = recon.seq_of(plan, side)
    total = {}
    for k, card in enumerate(deck):
        if not flags[k] or card not in need and card not in hero:
            continue
        mine = [ci for _, ci in sq if plan['cmds'][ci]['card'] == card]
        obs = [None if ob.get(ci) is None else observed(ob[ci], tab) for ci in mine]
        c = align(obs, flags[k], need.get(card, 0), card in hero)[0]
        if c:
            total[card] = c
    return total


FORM_MAX_COST = 6         # deleted plays one repair may carry (a Mirror deck reads every mirrored play as the copied card: 192024 has 5)


def form_repairs(rec, plan, side, tab, e0, ru=None, cap=16, max_cost=FORM_MAX_COST):
    """Engine-scorable variants of `plan` for the OPPONENT `side` (its deal is not known) when the count rule explains its observed forms
    only with deleted plays: each deleted play is dropped (invented) or read as the Mirror (the side's previous play is the same card and
    its deck holds a Mirror: the copy moves no count). -> [(description, cost, plan)]. A variant is kept only when the side's play sequence
    then fits a deal (the new deal is set). Insert-only or mixed explanations (an unseen troop play) give no edit: where its place is
    unknown the engine-scored add (b) of recon.py is the generator for it."""
    import recon
    need, hero = ru or rules(tab)
    if not plan.get('_deal_unknown', (True, True))[side] or recon.deck_conflicts(plan, side):
        return []
    deck = plan['decks'][side]
    flags = rec['sides'][str(side)]['slot_flags']
    ob = plan_obs(rec, plan, side)
    sq = recon.seq_of(plan, side)                          # [(run, command index)] in run order
    mir = deck.index('Mirror') if 'Mirror' in deck else None
    out, seen = [], set()
    for k, card in enumerate(deck):
        flag = flags[k]
        if not flag or card not in need and card not in hero:
            continue
        mine = [r for r, (_, ci) in enumerate(sq) if plan['cmds'][ci]['card'] == card]
        obs = [None if ob.get(sq[r][1]) is None else observed(ob[sq[r][1]], tab) for r in mine]
        cost, alts, _ = align(obs, flag, need.get(card, 0), card in hero, ins_cost=None)      # deletions only: an edit needs a play to act on
        if not cost or cost > max_cost:
            continue
        for alt in alts:
            if any(op == 'ins' for op, _ in alt):
                continue
            dels = [mine[i] for _, i in alt]               # ranks in the side's run-ordered sequence
            for how in ('drop', 'mirror'):
                if how == 'mirror' and (mir is None or any(r == 0 or plan['cmds'][sq[r - 1][1]]['card'] != card for r in dels)):
                    continue
                key = (how, tuple(dels))
                if key in seen:
                    continue
                seen.add(key)
                p = dict(plan, cmds=[dict(c) for c in plan['cmds']], deals=list(plan['deals']))
                ks = [sq[r][1] for r in dels]
                if how == 'mirror':
                    for ci in ks:
                        p['cmds'][ci]['card'] = 'Mirror'
                        p['cmds'][ci]['level'] = plan['levels'][side][mir]
                else:
                    for ci in sorted(ks, reverse=True):
                        p = recon.apply_edit(p, {'op': 'drop', 'i': ci})
                        if p is None:
                            break
                    if p is None:
                        continue
                deal = recon.fitting_deal(recon.plays_of(p, side))
                if deal is None:
                    continue                                # the sequence still fits no deal: not a repair
                p['deals'][side] = deal
                p['_cycle_base'] = [recon.cycle_ok(p, s) for s in (0, 1)]
                if plan.get('_elixir_base', (True, True))[side] and not recon.elixir_ok(p, side, tab, e0):
                    continue
                what = '%s s%d %s R%s' % ('formdrop' if how == 'drop' else 'formmirror', side, card, ','.join(str(sq[r][0]) for r in dels))
                out.append((what, cost, p))
                if len(out) >= cap:
                    return out
    return out


# ------------------------------------------------------------------ self-check
def _selfcheck():
    n = 0
    # the rule (crforge MatchSide: Knight need 2 -> plain, plain, evolved; Giant need 1 -> alternate; hero slot -> always hero)
    assert predict(7, 1, 2, False) == [0, 0, 1, 0, 0, 1, 0]
    assert predict(5, 1, 1, False) == [0, 1, 0, 1, 0]
    assert predict(3, 2, 0, True) == [2, 2, 2]
    assert predict(3, 0, 2, False) == [0, 0, 0]             # a card outside the evolution slot never evolves
    n += 4
    # clean sequences cost 0
    for fl, nn, hh in ((1, 2, False), (1, 1, False), (2, 0, True), (1, 2, True)):
        for L in range(0, 9):
            c, alts, _ = align(predict(L, fl, nn, hh), fl, nn, hh)
            assert c == 0 and alts == [()], (fl, nn, L, c, alts)
            n += 1
    # a spell's plays are unobservable: any form pattern is explained
    assert align([None] * 5, 1, 2, False)[0] == 0
    n += 1
    # a wrong form (flip one observed form) is detected (cost > 0)
    base = predict(8, 1, 2, False)
    for i in range(8):
        bad = list(base)
        bad[i] = 1 - bad[i]
        assert align(bad, 1, 2, False)[0] >= 1, i
        n += 1
    # a missing play (delete one): cost 1, and the true gap is among the optimal alignments
    for i in range(1, 6):          # the last plays are not detectable: the shorter sequence is a valid prefix
        seq = base[:i] + base[i + 1:]
        c, alts, _ = align(seq, 1, 2, False)
        assert c == 1, (i, c)
        assert any(('ins', i) in a or ('ins', i - 1) in a or ('ins', i + 1) in a for a in alts), (i, alts)
        n += 2
    # an invented duplicate (insert a play of the wrong form... a plain copy of the previous play): cost 1, the duplicate or its twin is deleted
    for i in range(1, 8):
        seq = base[:i] + [base[i - 1]] + base[i:]
        c, alts, _ = align(seq, 1, 2, False)
        assert c == 1 and any(('del', i) in a or ('del', i - 1) in a for a in alts), (i, c, alts)
        n += 2
    print('ok', n)


if __name__ == '__main__':
    _selfcheck()

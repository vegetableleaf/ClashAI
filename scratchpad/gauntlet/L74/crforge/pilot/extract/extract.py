"""crforge Stage 1 extractor (ticket A2b-1): our live log + the official battle log -> crforge battle inputs.

    python -I extract.py match    --live LIVE.jsonl                    # one match -> JSON on stdout
    python -I extract.py validate --live LIVE.jsonl --rec REC.jsonl    # extracted plays vs a replay recording's plays
    python -I extract.py batch    --out OUT.jsonl [--since 20261019_0600]

Per match (the ScenarioPlan fields crforge ReplayBattle.build reads, plus what the J7 driver needs):
  decks       both sides, crforge row names in deck-slot order (API order = slot order: CRFORGE_S0 2c, 8/8 both sides)
  levels      per card, counted 1..16 across rarities = API level + 16 - maxLevel (exact, from the battle log)
  slot_flags  bit 0 evolution slot, bit 1 hero slot = API evolutionLevel 1 / 2
  towers      spawn group (API support card) + king / princess level, cross-checked against the live tick-0 max hp
              (crforge tower table: towers.tsv, LagProbe towers)
  words       low word of each account id (gen_jobs.word, the community tag decoding: b)
  deal        ours exact (gen_jobs.own_order, decision own_hand deck_index); the opponent's is not public live: null
  plays       both sides, from parity/fights.deployments (reused unedited): card, deck index, form, x / y in game units
              (= live millitiles, side 0 low y), tile, run_ticks [lo, hi] = the crforge run-tick candidates. crforge makes
              a play's first object 1 tick after its run tick (LagProbe: 13 / 13 cards, lag 1), which is the parity
              convention deployments already dates by (tick = creation - 1), so the frame gap's two ticks are the two
              candidates; a phase-3b capture dates a body's play exactly (lo = hi).
  rng_free    no deck holds Arrows / Princess / Hunter / SkeletonKing (crforge/live_attr.py rule, G0)
Never read: the opponent's hand or elixir (live logs carry an elixir estimate; it is not opened here).
"""
import argparse, collections, datetime as dt, itertools, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/seeds'))
from gen_jobs import id_names, own_order, word, BATTLELOG, LIVE  # noqa: E402
from scratchpad.gauntlet.L74.parity import fights  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

TABLES = Path(r'C:\Users\benpe\crforge_eval\cache\tables\16.402.22')
DRAWERS = {'Arrows', 'Princess', 'Hunter', 'SkeletonKing'}      # G0: the only Ladder cards that draw after the deal
OWN_PRINCESS = 4858                                             # main account, level-16 towers
OWN_TAG = "#20Q0UV0GPQ"                                         # live account (own-player-tag memory)
GROUPS = {'Tower Princess': 'King_PrincessTowers', 'Cannoneer': 'King_CannonTowers',
          'Dagger Duchess': 'King_KnifeTowers', 'Royal Chef': 'King_ChefTowers'}


def tower_table():
    """(group, level) -> (king hp, princess hp) from towers.tsv (crforge, LagProbe towers)."""
    out = {}
    for line in open(HERE / 'towers.tsv'):
        g, lv, *xs = line.split()
        hp = {int(x.split(':')[0]): int(x.split(':')[1]) for x in xs}
        out[g, int(lv)] = (hp[9000], hp[3500])
    return out


def table_shims(tables):
    """The three facts deployments takes from the RoyaleSim Engine, read from the crforge tables instead (no SIM on the
    laptop): area-effect life (ms) by spell, collision radius by unit, and own_unit (below, per match)."""
    rows = {}
    for f in ('spells_other', 'spells_characters', 'spells_buildings', 'characters', 'buildings', 'area_effect_objects'):
        rows[f] = json.load(open(Path(tables) / f'{f}.json'))['rows']
    def life(name):
        col = (rows['spells_other'].get(name) or {}).get('columns', {})
        ae = col.get('AreaEffectObject')
        if not ae and col.get('SummonCharacter'):
            # round 6.3a: Rage has no AreaEffectObject; its area is the RageBottle's DeathAreaEffect. Without this life is
            # None, deployments dates the area at first sighting, 1 tick late on 10 of 16 casts (CRFORGE_S0.md 6.4).
            ae = ((rows['buildings'].get(col['SummonCharacter']) or {}).get('columns') or {}).get('DeathAreaEffect')
        return (rows['area_effect_objects'].get(ae) or {}).get('columns', {}).get('LifeDuration') if ae else None
    def stats(name):
        r = rows['characters'].get(name) or rows['buildings'].get(name) or {}
        return {'collision_radius_milli': r.get('columns', {}).get('CollisionRadius')}
    return life, stats


def battles():
    """Ranked battle-log entries, de-duplicated, newest last."""
    seen, out = set(), []
    for line in open(BATTLELOG):
        b = json.loads(line)['battle']
        k = (b['battleTime'], b['opponent'][0]['tag'])
        if b['type'] == 'pathOfLegend' and k not in seen:
            seen.add(k); out.append(b)
    return sorted(out, key=lambda b: b['battleTime'])


def log_start(p):
    m = re.match(r'live_play_(\d{8}_\d{6})', p.name)
    return dt.datetime.strptime(m.group(1), '%Y%m%d_%H%M%S') + dt.timedelta(hours=4) if m else None  # EDT -> UTC


def battle_for(path, bl):
    """The battle-log entry this live log played: battle end 60..600 s after the log's start (gen_jobs rule), nearest."""
    t0 = log_start(Path(path))
    c = [((dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S') - t0).total_seconds(), b) for b in bl]
    c = [(s, b) for s, b in c if 60 <= s <= 600]
    return min(c, key=lambda x: x[0]) if c else (None, None)


def side_info(p, names, cat, tt, live_k, live_p):
    cards = p['cards']
    deck = [names.get(c['id'], '?' + c['name']) for c in cards]
    sup = (p.get('supportCards') or [{}])[0]
    group = GROUPS.get(sup.get('name'))
    lv = sup.get('level', 0) + 16 - sup.get('maxLevel', 16) if sup else None
    king = next((L for (g, L), (k, _) in tt.items() if g == group and k == live_k), None)
    flags = []
    if group is None:
        flags.append(f'tower_troop_unknown:{sup.get("name")}')
    elif tt.get((group, lv), (None, None))[1] != live_p:
        flags.append(f'princess_hp_mismatch:api_L{lv}_live{live_p}')
    if king is None:
        flags.append(f'king_hp_unmatched:{live_k}')
    return dict(deck=deck, api_ids=[c['id'] for c in cards],
                display=[(cat.get(c['id']) or {}).get('display_name') for c in cards],
                levels=[c['level'] + 16 - c['maxLevel'] for c in cards],
                slot_flags=[{1: 1, 2: 2}.get(c.get('evolutionLevel') or 0, 0) for c in cards],
                towers=dict(group=group, king_level=king, level=lv, king_hp=live_k, princess_hp=live_p),
                word=word(p['tag']), flags=flags)


def cycle_fail(deal, seq):
    """Index of the first play of `seq` (deck indices, in play order) not in hand under the 4-card cycle dealt `deal`,
    or None if every play is legal. A played card goes to the back of the queue; the queue's front enters the hand."""
    hand, queue = list(deal[:4]), list(deal[4:])
    for i, k in enumerate(seq):
        if k not in hand:
            return i
        hand.remove(k); hand.append(queue.pop(0)); queue.append(k)
    return None


def deals_fitting(seq):
    """(how many of the 8! deals make every play legal, one of them: first-play order when it fits). Public plays only."""
    first = list(dict.fromkeys(seq)); first += [k for k in range(8) if k not in first]
    n = sum(cycle_fail(d, seq) is None for d in itertools.permutations(range(8)))
    ex = first if cycle_fail(first, seq) is None else next((list(d) for d in itertools.permutations(range(8))
                                                             if cycle_fail(d, seq) is None), None)
    return n, ex


def unit_hp_table():
    """card row (base, _EV1, _hero) -> {level: set of body max hp} (crforge, LagProbe unithp -> unit_hp.tsv)."""
    out = collections.defaultdict(dict)
    for line in open(HERE / 'unit_hp.tsv'):
        row, lv, hps = line.split()
        out[row][int(lv)] = {int(h) for h in hps.split(',')}
    return out


FORM_SUFFIX = {1: '_EV1', 2: '_hero'}


def derive_sides(path, m, events, first, my, hp, names, cat, by_name, uhp, tt):
    """A2b-1b, no battle-log entry: both sides' deck / levels / flags / towers from the live log alone.
    Deck: ours exact from own_hand (deck_index + name + form, our own public data); the opponent's = the cards its
    extracted plays show (seen order; None for an unseen slot; inferred Zaps not counted). Slot flags: the highest form
    a card was seen in (1 evo, 2 hero); an unseen form reads 0. Levels: each body's first max hp looked up in crforge's
    unit table for its card row and form (unit_hp.tsv); the level most bodies of the card agree on; a card with no
    body (a spell) takes its side's modal body level ('mode'). Towers: tick-0 max hp in crforge's tower table."""
    base = lambda disp: names.get((by_name.get(disp) or {}).get('card_id'))
    own = {}
    for raw in open(path, 'rb'):
        if b'"decision"' in raw[:40]:
            for h in (json.loads(raw).get('public') or {}).get('own_hand', []):
                k = h['deck_index']
                own[k] = (h['name'], max(int(h.get('form', 0)), own.get(k, ('', 0))[1]))
    votes = collections.defaultdict(collections.Counter)
    bform = collections.Counter()       # (side, base card) -> highest form any of its bodies shows (spell plays carry 0)
    for s, cid, mx in first.values():
        c = cat.get(cid)
        if c is None:
            continue
        b0 = names.get(c['card_id'])
        if b0 is None:
            continue
        f = fights.form_of(cid, c)
        bform[s, b0] = max(bform[s, b0], f)
        row = b0 + FORM_SUFFIX[f] if f and (b0 + FORM_SUFFIX.get(f, '')) in uhp else b0
        lv = [L for L, hs in uhp.get(row, {}).items() if mx in hs]
        if len(lv) == 1:
            votes[s, b0][lv[0]] += 1
    out = {}
    for s in (0, 1):
        if s == my:
            deck = [base(own[k][0]) if k in own else None for k in range(8)]
            disp = [own[k][0] if k in own else None for k in range(8)]
            form = [own[k][1] if k in own else 0 for k in range(8)]
        else:
            seen = {}
            for e in events:
                if e['side'] == s and e['kind'] == 'play' and not e.get('inferred') and base(e['name']):
                    seen[e['name']] = max(seen.get(e['name'], 0), e.get('form', 0))
            disp = list(seen)[:8] + [None] * (8 - min(8, len(seen)))
            deck = [base(d) if d else None for d in disp]
            form = [max(seen.get(d, 0), bform[s, base(d)]) if d else 0 for d in disp]
        mode = collections.Counter(v.most_common(1)[0][0] for (ss, _), v in votes.items() if ss == s).most_common(1)
        mode = mode[0][0] if mode else 16
        lv = [votes[s, d].most_common(1)[0][0] if votes.get((s, d)) else (mode if d else None) for d in deck]
        src = ['hp' if votes.get((s, d)) else ('mode' if d else None) for d in deck]
        k_hp, p_hp = hp.get((s, True)), hp.get((s, False))
        tw = [(g, L) for (g, L), (k, p) in tt.items() if p == p_hp]
        king = next((L for (g, L), (k, _) in tt.items() if k == k_hp), None)
        flags = [] if len(tw) == 1 and king else [f'towers_unmatched:{k_hp}/{p_hp}:{len(tw)}']
        n = sum(d is not None for d in deck)
        if n < 8:
            flags.append(f'deck_seen:{n}')
        out[s] = dict(deck=deck, display=disp, levels=lv, level_src=src, slot_flags=[{1: 1, 2: 2}.get(f, 0) for f in form],
                      towers=dict(group=tw[0][0] if len(tw) == 1 else None, king_level=king,
                                  level=tw[0][1] if len(tw) == 1 else None, king_hp=k_hp, princess_hp=p_hp),
                      word=word(OWN_TAG) if s == my else None, flags=flags, deck_seen=n)
    return out


_SUMMON = None


def summoning_spells():
    """Spell cards that summon a unit (Rage's RageBottle): their area is not made by castSpell, so the round-1 made
    dating does not apply (as sme_live.fx_spells)."""
    global _SUMMON
    if _SUMMON is None:
        rows = json.load(open(Path(TABLES) / 'spells_other.json'))['rows']
        _SUMMON = {n for n, r in rows.items() if r['columns'].get('SummonCharacter')}
    return _SUMMON


def bottle_lag(card):
    """Ticks from a summoning spell's command to its area for crforge, when the summoned character is a bottle (a
    building whose DeathAreaEffect is the spell's area) that waits its DeployTime: Rage's RageBottle, 500 ms = 10.
    SME.md round 5.3: the reader lists no bottle, and the area's countdown dates the area (made); crforge makes the
    area on R + 10. None for every other card."""
    rows = json.load(open(Path(TABLES) / 'spells_other.json'))['rows']
    ch = ((rows.get(card) or {}).get('columns') or {}).get('SummonCharacter')
    b = (json.load(open(Path(TABLES) / 'buildings.json'))['rows'].get(ch) or {}).get('columns') or {}
    return b['DeployTime'] // 50 if ch and b.get('DeathAreaEffect') and b.get('DeployTime') else None


_COST = {}


def card_cost(name):
    """A card's elixir cost (ManaCost in the spells_* tables), 0 if none."""
    if not _COST:
        for f in ('spells_characters', 'spells_buildings', 'spells_other'):
            for n, r in json.load(open(Path(TABLES) / f'{f}.json'))['rows'].items():
                if r['columns'].get('ManaCost') is not None:
                    _COST.setdefault(n, r['columns']['ManaCost'])
    return _COST.get(name, 0)


def crforge_casts(path, plays, sides, my=None, fx=None):
    """Ability casts seen_casts does not give, dated for crforge (SME.md fix rounds 2.2 / 2.3 / 3.1; the rules live in
    crforge/pilot/sme so the SME layer and this extractor share one copy):
    - Golden Knight: one cast per dash burst (sme_live.gk_dashes);
    - Archer Queen / Boss Bandit / Goblinstein: from the phase-2 ability buffs (sme_live.buff_casts);
    - a hero Ice Golem 'cast' that is its death (same area card id) is dropped (sme_live.golem_death_cast);
    - a hero Ice Wizard 'cast' that is its deploy area (same card id) is dropped (sme_live.iw_deploy_cast,
      SME_IW_DEPLOY=1, round 6.7);
    - an opponent hero Ice Wizard cast is dated by its ability's first 50 ms area (sme_live.iw_area_cast,
      SME_IW_AREA=1, round 6.8);
    - opponent hero casts from the reader's pending rise / the hero Balloon throw from its projectile (sme_live.hero7_cast,
      SME_HERO7=1, round 7.1);
    - our own tap-dated card plays and presses on a shared drop dated by the elixir drop, split by card cost
      (sme_live.own_play_elixir / own_press_elixir, SME_OWNPLAY7=1, round 7.3);
    - a Rascals play whose girls stand on the back edge goes to the edge (sme_live.rascals_back, SME_RASCAL7=1, round 7.4);
    - a hero Ice Golem 'cast' whose areas all read <= 1000 ms is its death and is dropped (sme_live.golem_death_fx,
      SME_GOLEM7=1, round 7.2);
    - a hero Valkyrie cast_seen cast goes 1 tick earlier (sme_live.valk_shift, round 4.2);
    - our own ability presses are dated by our elixir drop (sme_live.own_press_elixir, round 5.1; with SME_OWN_CAST=1
      also the cast_seen ones on our side, round 6.2)."""
    sme_dir = str(HERE.parent / 'sme')
    if sme_dir not in sys.path:
        sys.path.insert(0, sme_dir)
    import live_frames
    import sme_live
    frames = {f['t']: f for f in live_frames.convert(path)}
    # hero Valkyrie cast_seen casts 1 tick earlier for crforge (charge on R+2; SME.md round 4.2, sme_live.valk_shift)
    # our own ability presses dated by our elixir drop (round 5.1, sme_live.own_press_elixir)
    # round 6.2: also our own cast_seen presses (no logged tap), and not on a drop that holds one of our card plays
    own_ticks = {t for q in plays if q['kind'] == 'play' and q['side'] == my for t in range(q['run_ticks'][0], q['run_ticks'][1] + 1)}
    rises = sme_live.pending_rises(path) if sme_live.HERO7 else []   # round 7.1
    # round 7.3: our card plays with their elixir cost (run window, ManaCost) for the shared-drop split and tap dating
    own_plays = [(q['run_ticks'][0], q['run_ticks'][1], card_cost(q['card'])) for q in plays if q['kind'] == 'play' and q['side'] == my]
    out = [sme_live.hero7_cast(sme_live.iw_area_cast(sme_live.own_press_elixir(
        sme_live.rascals_back(sme_live.own_play_elixir(sme_live.valk_shift(p), frames, my, own_plays), frames), frames, my,
        own_ticks, own_plays),
        fx, my), frames, rises, my) for p in plays
           if not sme_live.golem_death_cast(p, frames) and not sme_live.iw_deploy_cast(p, frames, plays)
           and not sme_live.golem_death_fx(p, fx)]
    if sme_live.IWPEND9:   # A2c-9N: an opponent hero Ice Wizard press held pending, window back to its last valid target
        vt = sme_live.iw_valid_ticks(path)
        out = [sme_live.iw_pending(p, vt, plays, my) for p in out]
    for g in sme_live.gk_dashes(frames) + sme_live.buff_casts(frames):
        deck = sides[g['side']]['deck']
        if g['card'] in deck:
            out.append(dict(g, deck_index=deck.index(g['card']), name=g['card'], form=0))
    return out


def reader_hidden(path, cat):
    """A2c round 8 (SME_HIDDEN=1): bodies that leave the reader's ents list while a reader projectile still targets their
    address, i.e. the game object lives on unlisted. Census on the 138 matches (round 8): exactly 2, both a hero Mini
    PEKKA 2 ticks into its ability cast (181217@3041, 213436@778); crforge's body equals every projectile target point
    and dies on the same frame as the game's. -> [{side, name (crforge character), last (last ents tick), end (last tick a
    projectile targets it), track {tick: [x, y]}}]. The track point is the target point of a projectile already seen in
    the frame before (a projectile fired this frame can carry its fire-time point); a frame with only new projectiles
    takes their point if they agree.
    SME-F1FIX (SME_HIDDEN_GEN=1): the key is the body's generation, not the raw address. A generation starts when an
    address is listed after a frame without it, or with another side / card id (the game reuses freed addresses:
    F1 000420's hero Mini PEKKA address is listed later by a 26000012 body, which hid its window). A projectile is charged
    to the generation current when it flies, and a generation's window ends at the first target point its body could
    not have reached from the previous one (GEN_STEP per tick + GEN_SLACK). A frame with only new projectiles gets no
    track point (the hardened comparator rejected 000420@1215, where the new shot's fire-time point lagged the body)."""
    gen = os.environ.get('SME_HIDDEN_GEN') == '1'
    last, prev, out_t = {}, set(), {}
    seen, cur_gen, listed = set(), {}, set()
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        here = set()
        for e in d['ents']:
            k = e[7]
            if gen:
                g = cur_gen.get(k)
                if g is None or k not in listed or last[g][1][0] != e[0] or last[g][1][3] != e[3]:
                    cur_gen[k] = g = (k, t)
                k = g
            last[k] = (t, e)
            here.add(e[7])
        listed = here
        cur = set()
        for pr in d['proj']:
            a = pr[9] if len(pr) > 9 else None
            k = cur_gen.get(a) if gen else a
            if a and k in last and a not in here:
                out_t.setdefault(k, {}).setdefault(t, []).append((pr[6] in prev, pr[4], pr[5]))
            cur.add(pr[6])
        prev = cur
    res = []
    for a, by_t in out_t.items():
        lt, e = last[a]
        ticks = sorted(t for t in by_t if t > lt)
        if not ticks:
            continue
        c = cat.get(e[3]) or {}
        name = c.get('hero_character') if e[3] == c.get('hero_form_id') else c.get('summon_character')
        track, kept, pt0 = {}, [], (lt, e[1], e[2])
        for t in ticks:
            pts = {(x, y) for o, x, y in by_t[t] if o} or {(x, y) for o, x, y in by_t[t]}
            if gen and pt0[1] is not None and all(abs(x - pt0[1]) + abs(y - pt0[2]) > GEN_STEP * (t - pt0[0]) + GEN_SLACK
                                                  for x, y in pts):
                break
            kept.append(t)
            if gen and not any(o for o, x, y in by_t[t]):
                continue   # only new projectiles: their fire-time point lags the body (000420@1215: 61 units off)
            if len(pts) == 1:
                track[str(t)] = list(pts.pop())
                pt0 = (t, *track[str(t)])
        if kept:
            res.append(dict(side=e[0], name=name, last=lt, end=kept[-1], track=track))
    return res


# ponytail: one speed bound for every body (Manhattan units per tick). The hero Mini PEKKA leap moves 457 per tick (181217
# 3047-3049), so 150 cut a real window; 1000 is about 2x the fastest seen. Per-character speeds if a real body trips it
GEN_STEP, GEN_SLACK = 1000, 1000


def own_charge_presses(path, plays, my, sides):
    """A2c round 8.7 (SME_CHARGE8=1): our own hero ability presses seen only as a charge drop. The reader's phase-2 unit
    row of our hero carries ability.own_action.charges_raw (our own side only). Census over the 138 matches: 122 drops,
    121 have an extracted own press within [drop - 30, drop + 2]; the other one is 225213@3588 (our hero Ice Wizard: no
    cast_seen, no tap; our elixir drops 2.0 on the same frame pair). Such a drop becomes a press with R in the frame pair
    [prev, drop - 1] (the cost is taken in step R, visible on line R + 1)."""
    presses = [q['tick'] for q in plays if q['kind'] == 'ability' and q['side'] == my]
    deck = sides[my]['deck']
    last, seen, add = {}, set(), []
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        for u in (d.get('phase2') or {}).get('units', []):
            oa = (u.get('ability') or {}).get('own_action')
            if u.get('side') != my or not oa or oa.get('charges_raw') is None:
                continue
            k, c = u.get('generation'), oa['charges_raw']
            card = str(u.get('name', ''))[:-4] if str(u.get('name', '')).endswith('Hero') else None
            if k in last and c < last[k][0] and card in deck and                     not any(-30 <= x - t <= 2 for x in presses):
                add.append(dict(side=my, kind='ability', card=card, deck_index=deck.index(card), name=card, form=0,
                                run_ticks=[last[k][1], t - 1], tick=t - 1, source='charge_drop'))
            last[k] = (c, t)
    return plays + add


def match(path, bl=None, names=None, cat=None, shims=None, tt=None, uhp=None, by_name=None, api=True):
    """-> (record, None) or (None, skip reason). api=False (A2b-1b): no battle-log entry; sides from derive_sides.
    With an entry, the record also carries 'derived' (derive_sides on the same log) to validate A2b-1b against."""
    path = Path(path)
    if api:
        bl = bl if bl is not None else battles()
        gap, b = battle_for(path, bl)
        if b is None:
            return None, 'no_battle_log_entry'
    else:
        gap, b = None, None
    m, why = fights.read_match(path)
    if m is None:
        return None, why
    my = m['side']
    t0 = m['frames'][0][1]
    hp = {(bd['side'], bd['id'][-1] == 'K'): bd['max_hp'] for bd in t0 if bd['tower']}
    if hp.get((my, False)) != OWN_PRINCESS:
        return None, f'not_main_account:{hp.get((my, False))}'
    end = next((json.loads(r) for r in open(path, 'rb') if b'"end"' in r[:20]), {})
    if not api and not end.get('towers'):
        return None, 'no_end_towers'          # an aborted log: no finished match
    crowns = ((end.get('towers') or {}).get('crowns_me'), (end.get('towers') or {}).get('crowns_opp'))
    api = (b['team'][0]['crowns'], b['opponent'][0]['crowns']) if b else None
    names = names or id_names(TABLES)
    if cat is None:
        cat, by_name = load_catalog()
    tt = tt or tower_table()
    uhp = uhp or unit_hp_table()
    life, stats = shims or table_shims(TABLES)
    # Plays the log began after (the reader starts at ~tick 150): a tick-0 frame holding only the towers makes the
    # first frame's bodies new, so deployments keeps them with the gap [0, first frame - 1] (flag pre_log).
    m['frames'] = [(0, [bd for bd in t0 if bd['tower']])] + m['frames']
    m['births'] = fights.phase3_births(path) if m['ext'] else {}
    first = {}
    for t, bodies in m['frames']:
        for bd in bodies:
            if not bd['tower']:
                first.setdefault(bd['id'], (bd['side'], bd['card_id'], bd['max_hp']))
    top = collections.Counter()                # own_unit shim: the largest max hp a body of the card is first seen with
    for s, cid, mx in first.values():
        c = cat.get(cid)
        if c and fights.form_of(cid, c) != 1:
            top[c['display_name']] = max(top[c['display_name']], mx)
    # ponytail: own_unit = "within the card's largest body size" (the SIM's per-level hp table is not on the laptop). It
    # gates H-NEARPARENT second plays (kept) and the Hero-Goblins exemption (lost: their goblins read as children of the
    # 3720-hp ability object; 4 opponent Hero Goblins decks in the battle log). Exact via crforge unit hp if it matters.
    # A looser "any first-seen hp" shim made the Hero IW's ice cube a play (10-26 validation: 1 extra own play).
    # round 6.9 (SME_UNIT_HP=1): a body whose max hp is the card's unit at some level (crforge unit_hp.tsv, base or hero
    # row) is also the card's own unit. That restores the Hero-Goblins exemption: 224856's opponent Hero Goblins (4 x 323
    # hp under the ability object) was dropped as role-children and never played (its first divergence, never healed).
    exact = collections.defaultdict(set)
    if os.environ.get('SME_UNIT_HP') == '1':
        for s, cid, mx in first.values():
            c = cat.get(cid)
            b0 = c and names.get(c['card_id'])
            for row in ((b0, b0 + '_hero') if b0 else ()):
                for hs in uhp.get(row, {}).values():
                    exact[c['display_name']] |= hs
    events, delay = fights.deployments(m, cat, life, own_unit=lambda n, h: h >= .45 * top.get(n, 0) > 0 or h in exact.get(n, ()),
                                       stats=stats)
    derived = derive_sides(path, m, events, first, my, hp, names, cat, by_name, uhp, tt)
    if b:
        sides = {my: side_info(b['team'][0], names, cat, tt, hp.get((my, True)), hp.get((my, False))),
                 1 - my: side_info(b['opponent'][0], names, cat, tt, hp.get((1 - my, True)), hp.get((1 - my, False)))}
    else:
        sides = derived
    sides[my]['role'], sides[1 - my]['role'] = 'us', 'opp'
    flags = [f'{s}:{f}' for s in sides for f in sides[s].pop('flags')]
    if b and any(len(sides[s]['deck']) != 8 for s in sides):
        return None, 'deck_size'
    if b and None not in crowns and crowns != api:
        flags.append(f'crowns_mismatch:live{crowns}_api{api}')
    plays, unplaced = [], []
    idx = {s: {d: k for k, d in enumerate(sides[s]['display']) if d} for s in sides}
    for e in events:
        k = idx[e['side']].get(e['name'])
        row = dict(side=e['side'], kind=e['kind'], card=None if k is None else sides[e['side']]['deck'][k], deck_index=k,
                   name=e['name'], form=e.get('form', 0), run_ticks=[e.get('lo', e['tick']), e.get('hi', e['tick'])],
                   tick=e['tick'], source=e['source'])
        if e.get('source') == 'spell_seen' and e.get('made') is not None and row['run_ticks'][0] == row['run_ticks'][1] \
                and row['card'] not in summoning_spells():   # Rage: a RageBottle unit, not castSpell (run11 vs run10)
            # crforge casts an area-effect spell in the command's own step (castSpell, opening cleanup), so its run
            # tick is the area's made tick; seen_casts gives RoyaleSim's made - 1 (Tornado already made: PULL_AREAS lag).
            # SME.md fix round 1 (A2c): measured on 138 live matches, Lightning/Earthquake/Poison 1 tick late otherwise.
            row['tick'] = e['made']
            row['run_ticks'] = [e['made'], e['made']]
            row['dated'] = 'fx_made'
        elif e.get('source') == 'spell_seen' and e.get('made') is not None and row['run_ticks'][0] == row['run_ticks'][1]                 and bottle_lag(row['card']):
            row['tick'] = e['made'] - bottle_lag(row['card'])
            row['run_ticks'] = [row['tick'], row['tick']]
            row['dated'] = 'bottle_made'
        if e['kind'] != 'ability':
            row.update(x=e['x'], y=e['y'], tile=[int(e['x']) // 1000, int(e['y']) // 1000], n=e.get('n'))
        if row['run_ticks'][0] == 0:
            row['pre_log'] = True
        if e.get('inferred'):
            row['inferred'] = True
        (plays if k is not None else unplaced).append(row)
    plays = crforge_casts(path, plays, sides, my, m.get('fx'))
    # A2c-BP (sme/bp_rules.py, SME_BP_* flags, all off by default): hero Valkyrie / Golden Knight / hero Giant casts
    # dated from the reader's charge / stun buff countdowns, Golden Knight pushes dropped, Rascals point from its girls
    import bp_rules  # crforge_casts put sme/ on sys.path
    if bp_rules.VALK or bp_rules.GK or bp_rules.GIANT or bp_rules.RASCALS or bp_rules.PRESS:
        import live_frames
        plays = bp_rules.apply(path, plays, sides, {f['t']: f for f in live_frames.convert(path)})
    import mech_rules  # A2c-M (sme/mech_rules.py, SME_MECH_* flags, all off by default; merged round 8)
    if mech_rules.GB or mech_rules.DRILL or mech_rules.HB or mech_rules.ZAP:
        import live_frames
        plays = mech_rules.apply(str(path), plays, sides, {f['t']: f for f in live_frames.convert(path)})
    if mech_rules.ZAP_ADD or mech_rules.ZAP_POINT:   # A2c-9Z: Zaps from ZapFreeze buff groups (SME_ZAP_ADD / SME_ZAP_POINT)
        plays = mech_rules.zap_buffs(str(path), plays, sides, stats)
    if os.environ.get('SME_CHARGE8') == '1':   # round 8.7
        plays = own_charge_presses(path, plays, my, sides)
    import sme_live  # round 9 (A2c-9T): an area's made tick from its later sightings (sme_live.fx_made_clock, SME_MADE9)
    plays = sme_live.fx_made_clock(path, plays)
    tz = []   # ENG-SME (SME_TOWER_ZAP): an unseen opponent Zap on a princess tower that vanishes at <= Zap damage
    if mech_rules.TOWER_ZAP:
        plays, tz, _ = mech_rules.tower_zaps(mech_rules.raw_frames(path), plays, sides, reader_hidden(path, cat))
    if mech_rules.TOMB_HERO:   # ENG-FIX (SME_TOMB_HERO): the hero Tombstone press from its monster's row swap
        plays = mech_rules.tomb_presses(str(path), plays, sides)
    if mech_rules.BB_RISE:   # ENG-FIX (SME_BB_RISE): a Boss Bandit press whose buff never shows, from its state-10 rise
        plays = mech_rules.bb_presses(str(path), plays, sides)
    build = next(((json.loads(r).get('phase2') or {}).get('build') for r in open(path, 'rb') if b'"phase2"' in r), None)
    # RNG-free: no deck card is a drawer. Without the API only seen cards are known; an unseen slot was never played (it
    # is unseen because no play of it was extracted), and G0's drawers draw only when played (crforge: Arrows / Princess
    # / Hunter shots, Skeleton King's soul pick), so it cannot draw -- unless a play of it was missed (opp_no_fitting_deal
    # and the missed-play rate on the 227 bound that).
    drawers = sorted(DRAWERS & (set(sides[0]['deck']) | set(sides[1]['deck'])))
    order = own_order(path)
    seq = {s: [p['deck_index'] for p in sorted(plays, key=lambda p: p['tick']) if p['side'] == s and p['kind'] == 'play']
           for s in (0, 1)}
    own_fail = cycle_fail(order, seq[my]) if order else 'no_deal'
    if own_fail is not None:
        flags.append(f'{my}:own_cycle_fail:{own_fail}')
    n_opp, opp_fit = deals_fitting(seq[1 - my])
    if not n_opp:
        flags.append(f'{1 - my}:opp_no_fitting_deal:0')
    extra = dict(derived={str(s): derived[s] for s in (0, 1)}) if b else dict(source='live_only')
    rec = dict(extra, own_cycle_fail=own_fail, opp_fitting_deals=n_opp, opp_deal_fit=opp_fit, match=path.stem,
                battle_time=b['battleTime'] if b else None, gap_s=gap, my_side=my, game_build=build,
                era='post_1019' if path.stem[10:23] >= fights.TABLE_1019_FROM else 'pre_1019', tables=TABLES.name,
                ext=m['ext'], phase3_births=bool(m['births']), first_frame_tick=m['frames'][1][0], own_delay=delay,
                sides={str(s): sides[s] for s in (0, 1)},
                deal={str(my): order, str(1 - my): None}, opp_deal='unknown_live' , rng_free=not drawers,
                drawers=drawers, crowns_api=api, plays=plays, unplaced=unplaced, flags=flags,
                own_taps=[dict(tick=p['tick'], name=p['name'], x=p['x'], y=p['y']) for p in m['plays']],
                **(dict(reader_hidden=reader_hidden(path, cat)) if os.environ.get('SME_HIDDEN') == '1' else {}),
                **(dict(tower_zap=tz) if tz else {}))
    if os.environ.get('SME_SAMETICK_ORDER') == '1':   # A2c-9R: same-tick plays of both sides in the reader's creation order
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sme' / 'bp9'))
        import live_frames
        import order_inputs
        rec = order_inputs.reorder(rec, [], fr=[(f['t'], f) for f in live_frames.convert(path)])
    return rec, None


def validate(live, rec):
    """Extracted plays vs the replay recording's hand-change plays (replay_rec/convert.hand_plays)."""
    sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/replay_rec'))
    import convert
    r, why = match(live)
    if r is None:
        raise SystemExit(why)
    _, frames = convert.battle_frames(Path(rec))
    truth = convert.hand_plays(frames)
    cyc = convert.cycle_check(frames, truth)
    p0 = {int(p['side']): p for p in frames[0]['players']}
    out = dict(match=r['match'], truth_plays=len(truth), truth_cycle_bad_frames=cyc, extracted=len(r['plays']),
               unplaced=len(r['unplaced']), first_frame_tick=r['first_frame_tick'])
    # inputs vs the recording's tick-0 state
    out['deck_ok'] = {s: r['sides'][str(s)]['api_ids'] == p0[s]['deck_card_ids'] for s in (0, 1)}
    out['slot_flags_ok'] = {s: r['sides'][str(s)]['slot_flags'] == p0[s]['deck_form_flags'] for s in (0, 1)}
    my = r['my_side']
    out['own_deal_ok'] = r['deal'][str(my)] == p0[my]['hand_deck_indices'] + p0[my]['cycle_deck_indices']
    opp = 1 - my
    seq = [p['deck_index'] for p in sorted(r['plays'], key=lambda p: p['tick']) if p['side'] == opp and p['kind'] == 'play']
    out['opp_true_deal_fits'] = cycle_fail(p0[opp]['hand_deck_indices'] + p0[opp]['cycle_deck_indices'], seq) is None
    out['opp_fitting_deals'] = r['opp_fitting_deals']
    # per-card levels vs the recording's body levels (every non-tower body; card matched by display name)
    cat = load_catalog()[0]
    lv, bad = collections.Counter(), collections.Counter()
    for f in frames:
        for e in f['entities']:
            c = cat.get(e.get('card_id', -1))
            disp = r['sides'][str(e['side'])]['display']
            if c is None or c['display_name'] not in disp or not e.get('level'):
                continue
            ok = r['sides'][str(e['side'])]['levels'][disp.index(c['display_name'])] == e['level']
            (lv if ok else bad)[e['side'], c['display_name']] += 1
    out['levels_ok_cards'] = len(set(lv) - set(bad)); out['levels_bad_cards'] = sorted(map(str, bad))
    # plays: pair each truth play with an unused extracted play of the same side and deck index, nearest tick (<= 60)
    ext = [p for p in r['plays'] if p['kind'] == 'play']
    used, rows = set(), []
    for t in truth:
        c = [(abs(p['tick'] - t['tick']), i) for i, p in enumerate(ext)
             if i not in used and p['side'] == t['side'] and p['deck_index'] == t['deck_index'] and abs(p['tick'] - t['tick']) <= 60]
        if not c:
            rows.append(dict(side=t['side'], card=t['card'], tick=t['tick'], match=None)); continue
        i = min(c)[1]; used.add(i); p = ext[i]
        d = dict(side=t['side'], card=t['card'], tick=t['tick'], match=i, src=p['source'], lo=p['run_ticks'][0],
                 hi=p['run_ticks'][1], dlo=p['run_ticks'][0] - t['tick'], dhi=p['run_ticks'][1] - t['tick'],
                 pre_log=p.get('pre_log', False),
                 # the replay shows the hand change on the play's first-object tick (run + 1, as phase-3 stamped plays
                 # show), so with the change first sampled on frame H after frame Hprev the true run tick is in
                 # [Hprev, H - 1] (2 ticks on a 2-tick sample)
                 window_ok=max(p['run_ticks'][0], int(frames[t['frame'] - 1]['game_tick'])) <= min(p['run_ticks'][1], t['tick'] - 1))
        if t['side'] == my:          # our own command point: the confirmed tap (exact intent; the game may snap it)
            tap = [q for q in r['own_taps'] if q['name'] == p['name'] and 0 <= p['tick'] - q['tick'] <= 100]
            if tap:
                d['tap_dxy'] = [round(p['x'] - tap[-1]['x']), round(p['y'] - tap[-1]['y'])]
        if t['x'] is not None:
            d.update(dxy=[round(p['x'] - t['x']), round(p['y'] - t['y'])],
                     tile_ok=p['tile'] == [int(t['x']) // 1000, int(t['y']) // 1000])
        rows.append(d)
    extra = [dict(side=p['side'], card=p['card'], tick=p['tick'], src=p['source']) for i, p in enumerate(ext) if i not in used]
    out['rows'], out['extra'] = rows, extra
    for s in (0, 1):
        R = [x for x in rows if x['side'] == s]
        hit = [x for x in R if x['match'] is not None]
        role = 'us' if s == my else 'opp'
        out[role] = dict(truth=len(R), matched=len(hit), extra=sum(e['side'] == s for e in extra),
                         d_run_lo=dict(collections.Counter(x['dlo'] for x in hit)),
                         d_run_hi=dict(collections.Counter(x['dhi'] for x in hit)),
                         tile_ok=sum(bool(x.get('tile_ok')) for x in hit), located=sum('dxy' in x for x in hit),
                         max_dxy=max((max(map(abs, x['dxy'])) for x in hit if 'dxy' in x), default=None),
                         window_ok=sum(x['window_ok'] for x in hit), exact_tick=sum(x['lo'] == x['hi'] for x in hit),
                         tap_checked=sum('tap_dxy' in x for x in hit),
                         tap_exact=sum(x.get('tap_dxy') == [0, 0] for x in hit),
                         tap_max=max((max(map(abs, x['tap_dxy'])) for x in hit if 'tap_dxy' in x), default=None))
    out['abilities_extracted'] = [(p['side'], p['name'], p['run_ticks']) for p in r['plays'] if p['kind'] == 'ability']
    return out


def batch(out, since):
    bl = battles()
    names, (cat, by_name), shims, tt, uhp = id_names(TABLES), load_catalog(), table_shims(TABLES), tower_table(), unit_hp_table()
    """Per Ranked battle at or after `since` (EDT stamp): the live log that played it (battle_for, the gen_jobs rule),
    extracted. Writes every extracted match; counts skips by reason."""
    stats, rows, skips = collections.Counter(), [], []
    logs = [p for p in LIVE.glob('live_play_2026*.jsonl') if re.match(r'live_play_\d{8}_\d{6}\.jsonl$', p.name)]
    cut = dt.datetime.strptime(since, '%Y%m%d_%H%M') + dt.timedelta(hours=4)        # EDT -> UTC
    for b in bl:
        end = dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S')
        if end < cut:
            continue
        stats['ranked_battles'] += 1
        c = [((end - log_start(p)).total_seconds(), p) for p in logs]
        c = [x for x in c if 60 <= x[0] <= 600]
        if not c:
            stats['no_live_log'] += 1; skips.append((b['battleTime'], 'no_live_log')); continue
        p = min(c, key=lambda x: x[0])[1]
        try:
            r, why = match(p, [b], names, cat, shims, tt, uhp, by_name)
        except Exception as e:      # one bad log must not stop the batch; counted and named
            r, why = None, f'error:{type(e).__name__}:{e}'[:160]
        if r is None:
            stats[why.split(':')[0]] += 1; skips.append((b['battleTime'], p.name, why)); continue
        rows.append(r)
    with open(out, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    free = [r for r in rows if r['rng_free']]
    stats = dict(stats)
    stats.update(main_matches=len(rows), rng_free=len(free),
                 rng_free_no_flags=sum(not r['flags'] for r in free),
                 rng_free_own_deal=sum(bool(r['deal'][str(r['my_side'])]) for r in free),
                 builds=dict(collections.Counter(r['game_build'] for r in rows)),
                 flags=dict(collections.Counter(f.split(':')[0] + ':' + f.split(':')[1] for r in rows for f in r['flags'])))
    stats['skips'] = skips
    return dict(stats)


_CTX = None


def _noapi(p):
    global _CTX
    if _CTX is None:
        names, (cat, by_name) = id_names(TABLES), load_catalog()
        _CTX = dict(names=names, cat=cat, by_name=by_name, shims=table_shims(TABLES), tt=tower_table(), uhp=unit_hp_table())
    try:
        return match(p, api=False, **_CTX)
    except Exception as e:      # one bad log must not stop the batch; counted and named
        return None, f'error:{type(e).__name__}:{e}'[:160]


def batch_noapi(out, since, workers):
    """A2b-1b: every post-`since` live log that no battle-log entry claims (battle_for: battle end 60..600 s after the log's
    start), extracted from the log alone (match api=False). Non-Ranked / short / other-account logs fall out on
    read_match, the 4858 main-account check or the missing end-of-match towers."""
    from concurrent.futures import ProcessPoolExecutor
    bl = battles()
    logs = sorted(p for p in LIVE.glob('live_play_2026*.jsonl') if re.match(r'live_play_\d{8}_\d{6}\.jsonl$', p.name)
                  and p.stem[10:23] >= since)
    claimed = {p for p in logs if battle_for(p, bl)[1] is not None}
    todo = [p for p in logs if p not in claimed]
    stats, rows = collections.Counter(logs=len(logs), api_claimed=len(claimed), todo=len(todo)), []
    with ProcessPoolExecutor(workers) as ex:
        for p, (r, why) in zip(todo, ex.map(_noapi, todo, chunksize=4)):
            if r is None:
                stats['skip:' + why.split(':')[0]] += 1
            else:
                rows.append(r)
    with open(out, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    return dict(stats, extracted=len(rows))


def usable(r, rule):
    """J7 usability of a record under a flag rule (EXTRACT.md table)."""
    opp = r['sides'][str(1 - r['my_side'])]
    clean_cycle = r['own_cycle_fail'] is None and r['opp_fitting_deals'] > 0
    return r['rng_free'] and {'any': True, 'cycle_ok': clean_cycle, 'deck8': clean_cycle and opp.get('deck_seen', 8) == 8,
                              'no_flags': not r['flags']}[rule]


def check_levels(api_jsonl):
    """A2b-1b validation on the API-backed records: derive_sides (log only) vs the battle log, per card."""
    R = [json.loads(l) for l in open(api_jsonl)]
    c, out = collections.Counter(), {}
    bad = collections.Counter()
    for r in R:
        for s in ('0', '1'):
            A, D = r['sides'][s], r['derived'][s]
            role = 'us' if int(s) == r['my_side'] else 'opp'
            api = dict(zip(A['deck'], zip(A['levels'], A['slot_flags'])))
            for d, lv, src, fl in zip(D['deck'], D['levels'], D['level_src'], D['slot_flags']):
                if d is None:
                    continue
                if d not in api:
                    c[role, 'seen_not_in_api_deck'] += 1; bad['not_in_deck', d] += 1; continue
                c[role, src, 'n'] += 1
                c[role, src, 'level_ok'] += lv == api[d][0]
                if lv != api[d][0]:
                    bad[role, src, d, lv - api[d][0]] += 1
                c[role, 'flag_ok'] += fl == api[d][1]; c[role, 'flag_n'] += 1
            c[role, 'decks'] += 1; c[role, 'deck8'] += D['deck_seen'] == 8
            c[role, 'towers_ok'] += (D['towers']['group'], D['towers']['level'], D['towers']['king_level']) == \
                (A['towers']['group'], A['towers']['level'], A['towers']['king_level'])
            c[role, 'unseen_api_cards'] += sum(x not in D['deck'] for x in A['deck'])
            c[role, 'unseen_flagged_slots'] += sum(x not in D['deck'] and api[x][1] != 0 for x in A['deck'])
        seen = set(x for s in '01' for x in r['derived'][s]['deck'] if x)
        live_rule = not (DRAWERS & seen)
        c['rng', live_rule, r['rng_free']] += 1
    out['counts'] = {' '.join(map(str, k)): v for k, v in sorted(c.items(), key=str)}
    out['worst'] = [(list(map(str, k)), v) for k, v in bad.most_common(15)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('match', 'validate', 'batch', 'batch_noapi', 'check_levels'))
    ap.add_argument('--workers', type=int, default=4); ap.add_argument('--api')
    ap.add_argument('--live'); ap.add_argument('--rec'); ap.add_argument('--out'); ap.add_argument('--since', default='20261019_0600')
    a = ap.parse_args()
    if a.cmd == 'match':
        r, why = match(a.live)
        print(json.dumps(r if r else dict(skip=why)))
    elif a.cmd == 'validate':
        print(json.dumps(validate(a.live, a.rec), default=str))
    elif a.cmd == 'batch_noapi':
        print(json.dumps(batch_noapi(a.out, a.since, a.workers)))
    elif a.cmd == 'check_levels':
        print(json.dumps(check_levels(a.api)))
    else:
        print(json.dumps(batch(a.out, a.since)))


if __name__ == '__main__':
    main()

"""B6 stage B: the LEARNED hero-ability press live (live_play.py --iw-press head).

The rl_royale ability head (B6 stage A, checkpoint rl["ability_head"]) decides from the trunk feature g of the pilot's
OWN decision on this frame + ABILITY_FEAT_N public board values of the hero. ``head_features`` is the live copy of
royale_env.RoyalePoolEnv._ability_head_features (+ _ability_features) on a reader frame (1000 units per tile) instead
of the engine state (18,000); scratchpad/gauntlet/L74/ability_live/test_ability_live.py pins it to the SIM builder on
the same states. Live substitutions (no engine here; each is approximate, not exact):
  * enemy troop HP (features 5, 7): reader HP / the enemy side's tower level factor (obs_contract's rule) -- the SIM
    plays every card at level 11
  * body elixir (15): unit_values.json (RoyaleAPI cost / units spawned), else the card cost (one body), else 0 -- SIM:
    the engine catalogue's elixir / count of the body's card
  * the hero Goblins flag is not skipped (the reader cannot tell it from a building)
The press is e1_eval.ability_decide's own rule, called on a one-match stand-in: greedy (p > 0.5, default) or, with
live_play --iw-press-head-decode sample, Bernoulli(p) as in training.
"""
from __future__ import annotations

from types import SimpleNamespace

# = royale_env.ABILITY_CARDS / _V2_SCALE / ABILITY_FEAT_N (royalegym-free copies; the test pins them)
ABILITY_CARDS = ("Giant", "Balloon", "Bowler", "Goblins", "Knight", "Musketeer", "Tombstone", "Valkyrie", "Wizard",
                 "Berserker", "BarbLog", "DarkPrince", "IceGolemite", "EliteArcher", "MegaMinion", "MiniPekka",
                 "ArcherQueen", "GoldenKnight", "SkeletonKing", "MightyMiner", "Monk", "LittlePrince", "Goblinstein",
                 "BossBandit", "IceWizard")
V2_SCALE = (30., 1., 10., 10., 5., 2000., 5., 2000., 1., 10., 10., 3., 3., 3.)
ABILITY_FEAT_N = 18 + len(ABILITY_CARDS) + 1
# royale_env._ability_radius in tiles: the largest radius_milli in the hero form's ability effect, else its attack range
# + 1.5 tiles (L74/apktables/.../cards-160402017-20261006.json hero_forms; the test recomputes it). Goblins (flag
# building), BarbLog, Tombstone: no range in the table -> absent (the head refuses to decide for them).
HERO_RADIUS = {"Musketeer": 7.5, "IceGolemite": 4.0, "Berserker": 2.3, "Balloon": 6.5, "Valkyrie": 5.5, "Wizard": 4.0,
               "MiniPekka": 2.3, "Knight": 6.5, "MegaMinion": 3.1, "Giant": 2.5, "EliteArcher": 1.0, "Bowler": 2.0,
               "DarkPrince": 2.7, "IceWizard": 2.5, "ElectroWizard": 6.5}
TOWER_KINDS = (12, 13)     # reader: card_id -1 + kind 12/13 = crown tower; card_id >= 0 + kind 12/13 = building
TILE = 1000.0              # reader units per tile


def _names() -> dict:
    from pipeline.obs_contract import _catalog_names
    return _catalog_names()


def body_elixir(name) -> float:
    """SIM: catalogue elixir / count of the body's card (0 unknown). Live: unit_values.json, else the card cost, else 0."""
    if not name:
        return 0.0
    from hero_button import unit_values
    v = unit_values().get(name)
    if v is None:
        from pipeline import vocab
        from pipeline.opp_elixir_count import card_cost
        v = card_cost(vocab.engine_key(name))
    return float(v or 0.0)


def _is_tower(e) -> bool:
    return int(e["card_id"]) < 0 and int(e["kind"]) in TOWER_KINDS


def level_factor(ents, side: int) -> float:
    """obs_contract.from_engine's card-level factor of ``side`` (its first tower's max HP / the level-11 HP; 1.0 when
    within 2 %): live HP / this = the SIM's level-11 HP."""
    for e in ents:
        if int(e["side"]) == side and _is_tower(e) and float(e["max_hp"]) > 0:
            f = float(e["max_hp"]) / (4824.0 if abs(float(e["x"]) - 9000.0) < 1500.0 else 3052.0)
            return f if abs(f - 1.0) > 0.02 else 1.0
    return 1.0


def crowns(ents) -> tuple[int, int]:
    """(side 0, side 1) crowns from the standing crown towers (reward_shaping.crowns; king by position, live_mem)."""
    from pipeline.reward_shaping import crowns as rs_crowns
    rows = [dict(side=int(e["side"]), type="king" if abs(float(e["x"]) - 9000.0) < 1500.0 else "princess", hp=e["hp"])
            for e in ents if _is_tower(e)]
    return rs_crowns({"episode": {"crown_towers": rows}})


def head_features(ents, side: int, tick: int, my_elixir: float, hero: dict, card: str, dep_tick: int, presses: int = 0,
                  name_of=None, value_of=None) -> list[float]:
    """royale_env._ability_head_features on reader bodies (dicts: side, x, y, card_id, hp, max_hp, kind). ``hero`` = my
    hero body, ``card`` its catalogue name, ``dep_tick`` its deploy tick (SIM v2: _last_play), ``presses`` its presses
    since. ``name_of`` card id -> name (default the catalogue), ``value_of`` name -> body elixir (default body_elixir)."""
    name_of = name_of or _names().get
    value_of = value_of or body_elixir
    hx, hy = float(hero["x"]), float(hero["y"])
    foes = [e for e in ents if int(e["side"]) != side and float(e["hp"]) > 0]
    lvl = level_factor(ents, 1 - side)
    units, structures, towers = [], [], []
    for u in foes:
        d = ((float(u["x"]) - hx) ** 2 + (float(u["y"]) - hy) ** 2) ** .5 / TILE
        if _is_tower(u):
            towers.append(d)
        elif int(u["card_id"]) < 0:
            continue
        elif int(u["kind"]) in TOWER_KINDS:
            structures.append(d)
        else:
            units.append((d, float(u["hp"]) / lvl))
    sd = structures + towers
    c = crowns(ents)
    f = [(tick - dep_tick) / 20, min(1., max(0., float(hero["hp"]) / max(1, float(hero["max_hp"])))),
         min((d for d, _ in units), default=40.), min(sd, default=40.),
         sum(d <= 3 for d, _ in units), sum(h for d, h in units if d <= 3),
         sum(d <= 5 for d, _ in units), sum(h for d, h in units if d <= 5),
         float(hy > 16 * TILE if side == 0 else hy < 16 * TILE),
         min(towers, default=40.), float(my_elixir), min(tick // 1200, 3),
         1 if tick < 2400 else (2 if tick < 4800 else 3), c[side] - c[1 - side]]
    f = [x / s for x, s in zip(f, V2_SCALE)]
    r2 = (HERO_RADIUS[card] * TILE) ** 2
    n = el = tower = 0
    for e in foes:
        if (float(e["x"]) - hx) ** 2 + (float(e["y"]) - hy) ** 2 > r2:
            continue
        if _is_tower(e):
            tower = 1
        elif int(e["card_id"]) >= 0:
            n += 1
            el += value_of(name_of(int(e["card_id"])))
    one = [0.] * (len(ABILITY_CARDS) + 1)
    one[ABILITY_CARDS.index(card) if card in ABILITY_CARDS else -1] = 1.
    return f + [n / 5, el / 10, float(tower), float(presses)] + one


def hero_of(frame, side: int, hids):
    """My hero body (hero_button.should_press's pick, hero_button.pick_hero: hero card ids or their reader form ids;
    the body carrying the phase-2 ability block, else the newest generation), or None."""
    from hero_button import hero_form_ids, pick_hero
    return pick_hero(frame, side, set(hids) | hero_form_ids(set(hids)))


def deploy_state(pilot, card: str, tick: int) -> tuple[int, int]:
    """(deploy tick, presses since) of my ``card`` from the pilot's confirmed own events (record_play / record_ability);
    no deploy seen -> (tick, 0), the SIM's fallback when it never saw the play."""
    from pipeline.dataset_gen import card_key
    pub = getattr(pilot, "public", None)
    if pub is None:
        return tick, 0
    key = card_key(card)
    ev = [e for e in pub.own_events if e.get("accepted", True) and int(e["tick"]) <= tick]
    deps = [int(e["tick"]) for e in ev if not e.get("ability") and card_key(e.get("card", "")) == key]
    dep = deps[-1] if deps else tick
    return dep, sum(1 for e in ev if e.get("ability") and int(e["tick"]) >= dep)


def head_press(ability: dict, g, feat) -> tuple[float, bool]:
    """(p, press) of e1_eval.ability_decide in ``ability["mode"]`` (greedy: p > 0.5) for one option ``feat`` with trunk
    feature ``g`` [1, d_g]."""
    from pipeline.e1_eval import ability_decide
    m = SimpleNamespace(_ability_opts=[{"cmd": 0, "feat": feat}], n_dec=0, side=0, _ability_commands={0: []},
                        rng_ability=ability.get("rng"))   # sample mode: the head's own seeded rng (load_head)
    ability_decide([m], {"g": g}, {"ability": ability})
    return float(m.ab_stats["p_sum"]), bool(m.ab_stats["presses"])


def decide_board(f, side: int, hids, my_elixir: float, deploy, g_of, ability) -> tuple[bool, str, list | None]:
    """One head decision on a (hero-deduped) reader frame ``f`` whose button reads ready. ``deploy(card, tick)`` ->
    (deploy tick, presses since); ``g_of()`` -> the trunk g of this frame's decision. -> (press, why, features | None).
    The SIM asks the head only while the engine would accept the press: hero alive, its one charge unspent (every hero
    form has max_charges 1) -- the live button reads 'ready' without a hero and after a press too (live logs 10-17)."""
    hero = hero_of(f, side, hids)
    if hero is None:
        return False, "head hero_unseen", None
    card = _names().get(int(hero["card_id"]), str(hero["card_id"]))
    if card not in HERO_RADIUS:
        return False, f"head no_radius {card}", None
    tick = int(f["game_tick"])
    dep, presses = deploy(card, tick)
    if presses:
        return False, "head spent", None
    feat = head_features(f["entities"], side, tick, my_elixir, hero, card, dep, presses)
    if ability.get("features") == "freeze":   # L74 press audit: the head was trained with the 'freeze' set
        feat = feat + freeze_features(f, side, hero, card, my_elixir)
    p, press = head_press(ability, g_of(), feat)
    return press, f"head p={p:.4f}", feat


# = royale_env FREEZE_FEAT_N / IW_MARKS / FREEZE_R_T / CUBE_AHEAD_T / MY_LINE_T (the test pins them)
FREEZE_FEAT_N = 11
IW_MARKS = frozenset(("IceWizardHeroCold", "IceWizardHeroSlow"))
FREEZE_R_T, CUBE_AHEAD_T, MY_LINE_T, IW_PRESS_COST = 2.5, 1.5, (6.5, 25.5), 2.0


def freeze_features(f, side: int, hero: dict, card: str, my_elixir: float, name_of=None, value_of=None,
                    cost_of=None) -> list[float]:
    """royale_env.RoyalePoolEnv._freeze_features on a reader frame (the 'freeze' head inputs; zeros unless Hero IW).
    Marks (IceWizardHeroCold / Slow) come from the merged reader's phase-2 buffs, the IW's attack target from its
    phase-3 attack row, joined on generation (entity 'category'); a frame without a valid block reads no mark / no
    target (the SIM always knows both). ``cost_of`` card name -> elixir (default opp_elixir_count.card_cost)."""
    if card != "IceWizard":
        return [0.] * FREEZE_FEAT_N
    from pipeline.royale_iw_policy import WINCONS
    name_of = name_of or _names().get
    value_of = value_of or body_elixir
    if cost_of is None:
        from pipeline import vocab
        from pipeline.opp_elixir_count import card_cost
        cost_of = lambda n: float(card_cost(vocab.engine_key(n)) or 0.)   # noqa: E731
    ents = f["entities"]
    foes = [e for e in ents if int(e["side"]) != side and float(e["hp"]) > 0 and int(e["card_id"]) >= 0
            and int(e["kind"]) not in TOWER_KINDS]
    p2, p3 = f.get("phase2") or {}, f.get("phase3") or {}
    buffs = {u.get("generation"): {n for b in u.get("buffs") or () for n in str(b.get("name", "")).split("|")}
             for u in (p2.get("units") or ()) if p2.get("valid")}
    marked = [e for e in foes if buffs.get(e.get("category"), set()) & IW_MARKS]
    d2 = lambda e, x, y: (float(e["x"]) - x) ** 2 + (float(e["y"]) - y) ** 2    # noqa: E731
    hx, hy = float(hero["x"]), float(hero["y"])
    tgt = min(marked, key=lambda e: d2(e, hx, hy)) if marked else None
    if tgt is None and p3.get("valid"):
        tg = next(((b.get("attack") or {}).get("target_gen") for b in p3.get("bodies") or ()
                   if b.get("generation") == hero.get("category") and b.get("attack")), None)
        tgt = next((e for e in ents if tg is not None and e.get("category") == tg and int(e["side"]) != side
                    and float(e["hp"]) > 0), None)

    def around(x, y):
        near = [e for e in foes if d2(e, x, y) <= (FREEZE_R_T * TILE) ** 2]
        return [len(near) / 5, sum(value_of(name_of(int(e["card_id"]))) for e in near) / 10,
                float(any(name_of(int(e["card_id"])) in WINCONS for e in near))]
    me = next(p for p in f["players"] if int(p["side"]) == side)
    hand = [me["deck_card_ids"][i] for i in me.get("hand_deck_indices") or () if i is not None and int(i) >= 0]
    cheap = min((cost_of(name_of(int(c)) or "") for c in hand), default=0.)
    tail = [float(bool(marked)), (float(my_elixir) - IW_PRESS_COST - cheap) / 10]
    if tgt is None:
        return [0.] * (FREEZE_FEAT_N - 2) + tail
    cx, cy = float(tgt["x"]), float(tgt["y"]) + (1 if side == 0 else -1) * CUBE_AHEAD_T * TILE
    return ([1.] + around(float(tgt["x"]), float(tgt["y"])) + around(cx, cy)
            + [abs(cy / TILE - MY_LINE_T[side]) / 10, float((cy > 16 * TILE) == (side == 1))] + tail)


def decide(pilot, frame, side: int, hids) -> tuple[bool, str, list | None]:
    """live_play --iw-press head, on a frame whose button reads ready and AFTER pilot.decide(frame) (its g):
    -> (press, why "head p=<p>", the 44 features or None when no decision was possible)."""
    from pipeline.reader_identity_aliases import dedupe_hero_bodies
    f = dedupe_hero_bodies(frame)
    g_tick, g = getattr(pilot, "last_g", (None, None))
    if g_tick != int(f["game_tick"]):        # g must be this frame's decision (live_play decides first)
        return False, f"head g_stale {g_tick}", None
    me = next(p for p in f["players"] if int(p["side"]) == side)
    return decide_board(f, side, hids, me["elixir_raw"] / 1e4, lambda c, t: deploy_state(pilot, c, t), lambda: g,
                        pilot.ability)


SAMPLE_SEED = 0     # --iw-press-head-decode sample: one rng per live process (a fixed seed: the draw sequence is reproducible)


def load_head(ckpt, device: str, pilot, decode: str = "greedy") -> dict:
    """The checkpoint's ability head (rl_royale.load_ability_head) for --iw-press head, decoded ``decode``: greedy
    (p > 0.5, default) or sample (Bernoulli(p) from ab["rng"], seeded SAMPLE_SEED); SystemExit (refusing) when it has
    none or its g width is not the model's."""
    import numpy as np
    from pipeline.rl_royale import load_ability_head
    if decode not in ("greedy", "sample"):
        raise SystemExit(f"refusing: --iw-press-head-decode must be greedy or sample, got {decode!r}")
    ab = load_ability_head(ckpt, str(device))
    if ab is None:
        raise SystemExit(f"refusing: --iw-press head needs a checkpoint with a learned ability head (rl['ability_head'], "
                         f"B6 stage A); {ckpt} has none -- use --iw-press rule")
    d_g = ab["head"].net[0].in_features - int(ab.get("n_feat", ABILITY_FEAT_N))   # 'freeze' heads read 55 values
    width = pilot.model.value_head.in_features
    if d_g != width:
        raise SystemExit(f"refusing: {ckpt}'s ability head reads g of width {d_g}, the model's g is {width}")
    if decode == "sample":
        ab.update(mode="sample", rng=np.random.default_rng(SAMPLE_SEED))
    return ab

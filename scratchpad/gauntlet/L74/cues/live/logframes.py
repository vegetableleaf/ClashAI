"""Reader-shaped frames (entities + cue blocks) rebuilt from a live log's 'frame' events (--log-frames)."""
import json

ENT = ("side", "x", "y", "card_id", "hp", "max_hp", "kind", "address")
ST = ("behavior_state_raw", "evo", "level", "category")
PROJ = ("side", "x", "y", "card_id", "target_x", "target_y", "address", "generation_key", "source", "target")
FX = ("side", "x", "y", "card_id", "remaining_ms", "level_raw", "address", "generation_key")


def frames(path):
    for line in open(path, encoding="utf-8"):
        if '"event": "frame"' not in line[:30]:
            continue
        e = json.loads(line)
        if e.get("ents") is None or "ents_state" not in e:
            continue
        ents = [dict(zip(ENT, a), **dict(zip(ST, b))) for a, b in zip(e["ents"], e["ents_state"])]
        f = dict(game_tick=int(e["tick"]), entities=ents, my_side=e["my_side"], elixir=e["elixir"],
                 projectiles=[dict(zip(PROJ, p)) for p in e.get("proj") or ()],
                 effects=[dict(zip(FX, p)) for p in e.get("fx") or ()])
        for k in ("cues_degraded", "phase2", "phase3"):
            if k in e:
                f[k] = e[k]
        yield f


def full_frames(path):
    """frames() + a players block rebuilt from the decision events (own hand by deck index, my elixir from the frame
    event; next card = the card that later fills a played slot, -1 after the last change; the opponent's hand hidden),
    so pipeline.live_gen*.GenPilot can decide on them. The deck card ids come from the catalog by display name."""
    import bisect
    from pipeline.obs_contract import _catalog_names
    decs, deck = [], {}
    for line in open(path, encoding="utf-8"):
        if '"event": "decision"' not in line[:40]:
            continue
        j = json.loads(line)
        oh = (j.get("public") or {}).get("own_hand") or []
        if len(oh) != 4:
            continue
        decs.append((int(j["tick"]), [int(h["deck_index"]) for h in oh]))
        for h in oh:
            deck[int(h["deck_index"])] = (h["name"], int(h.get("form", 0)))
    if len(deck) != 8 or not decs:
        return
    ids = {}
    for cid, name in sorted(_catalog_names().items()):
        ids.setdefault(name, cid)
    deck_ids = [ids[deck[i][0]] for i in range(8)]
    forms = [deck[i][1] for i in range(8)]
    changes = []                                   # (tick, deck index that entered a slot)
    for (t0, h0), (t1, h1) in zip(decs, decs[1:]):
        changes += [(t1, b) for a, b in zip(h0, h1) if a != b]
    ct = [t for t, _ in changes]
    dt = [t for t, _ in decs]
    for f in frames(path):
        t = f["game_tick"]
        hand = decs[max(0, bisect.bisect_right(dt, t) - 1)][1]
        k = bisect.bisect_right(ct, t)
        nxt = changes[k][1] if k < len(changes) else -1
        side = int(f["my_side"])
        me = dict(side=side, elixir_raw=int(round(f["elixir"] * 1e4)), next_deck_index=nxt, hand_deck_indices=list(hand),
                  cycle_deck_indices=[], deck_card_ids=deck_ids, deck_form_flags=forms)
        opp = dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4, cycle_deck_indices=[],
                   deck_card_ids=[], deck_form_flags=[])
        f.update(battle_active=True, coherent=True, failure="none", players=[me, opp] if side == 0 else [opp, me])
        yield f

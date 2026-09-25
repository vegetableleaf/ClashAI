"""live_mem: reader frame -> BoardState. Frame = probe1.jsonl line 1 (Training Camp, tick 206), trimmed."""
from pipeline import live_mem
from pipeline.obs_contract import MY_KING_Y, OPP_KING_Y

T = lambda cat, kind, side, x, y, hp, mhp, cid=-1, addr="0x1": {  # noqa: E731
    "address": addr, "category": cat, "kind": kind, "side": side, "x": x, "y": y, "card_id": cid, "level": 2,
    "hp": hp, "max_hp": mhp, "behavior_state_raw": 0}
FRAME = {
    "battle_active": True, "game_tick": 206, "failure": "none",
    "players": [
        {"side": 0, "elixir_raw": 96668, "next_deck_index": -1, "hand_deck_indices": [-1, -1, -1, -1],
         "cycle_deck_indices": [], "deck_card_ids": [], "deck_form_flags": []},
        {"side": 1, "elixir_raw": 66668, "next_deck_index": 5, "hand_deck_indices": [2, 1, 6, 7],
         "cycle_deck_indices": [5, 3, 4, 0],
         "deck_card_ids": [26000000, 27000001, 26000002, 28000001, 28000000, 26000003, 26000014, 26000018],
         "deck_form_flags": [0] * 8}],
    "entities": [
        T(5000000, 12, 0, 9000, 3000, 2568, 2568), T(5000001, 13, 0, 3500, 6500, 1512, 1512),
        T(5000002, 13, 0, 14500, 6500, 1512, 1512), T(5000003, 12, 1, 9000, 29000, 2736, 2736),
        T(5000004, 13, 1, 3500, 25500, 1624, 1624), T(5000005, 13, 1, 14500, 25500, 1000, 1624),
        T(5000006, 15, 1, 10705, 30133, 759, 759, cid=26000000, addr="0x7a58770b3570")],
}


def test_my_side_is_the_visible_hand():
    assert live_mem.my_side_of(FRAME) == 1


def test_board_state_mine_at_bottom_and_opponent_private_info_masked():
    bs = live_mem.board_state(FRAME)
    assert bs.opp_elixir is None                       # owner rule: never the bot's elixir
    assert abs(bs.my_elixir - 6.6668) < 1e-6 and bs.t_sec == 206 * 0.05
    assert [t.alive for t in bs.towers] == [True] * 6
    my_r = bs.towers[2]                                # my K, L, R, opp K, L, R -- after the side-1 mirror
    assert my_r.side == 0 and abs(my_r.hp_frac - 1.0) < 1e-9
    assert abs(bs.towers[1].hp_frac - 1000 / 1624) < 1e-9   # engine x 14500 mirrors to MY left lane
    (u,) = bs.units
    assert u.side == 0 and u.y > MY_KING_Y > OPP_KING_Y      # my knight, behind my king, me at the bottom
    assert all(h >= 0 for h in bs.my_hand) and bs.my_next >= 0
    assert bs.my_next == bs.deck[5]                    # next = deck index 5

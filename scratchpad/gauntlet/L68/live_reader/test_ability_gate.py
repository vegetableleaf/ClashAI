"""Perception fixes for the hero ability press (lead 2026-10-18): hero_button.press_gate (P1) + pick_hero (P2), on
frames logged live by Mark CXXXVIII (test_ability_gate_frames.json: the press frame's bodies, my IW phase-2 units and
hand; extracted from the live_play_20261017_*.jsonl rows named in each case)."""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hero_button as hb  # noqa: E402
from ability_head_live import hero_of  # noqa: E402
from pipeline.obs_contract import _catalog_names  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402

FR = json.loads((HERE / "test_ability_gate_frames.json").read_text(encoding="utf-8"))
HIDS = {hb.ICE_WIZARD}
IDS = HIDS | hb.hero_form_ids(HIDS)


def case(name, phase2=True):
    c = copy.deepcopy(FR[name])
    fake = {-9000 - k: n for k, n in enumerate(c["hand"])}
    f = dict(entities=c["entities"], game_tick=c["tick"],
             players=[dict(side=c["side"], deck_card_ids=list(fake), hand_deck_indices=list(range(len(fake))),
                           elixir_raw=c["elixir"] * 1e4)])
    if phase2:
        f["phase2"] = c["phase2"]
    return dedupe_hero_bodies(f), c["side"], {**_catalog_names(), **fake}


def first_listed(f, side):      # the pick before the fix
    return next(e for e in f["entities"] if e["side"] == side and int(e["card_id"]) in IDS)


def test_spent_charge_is_withheld():            # 201510 t=4425: state_raw 6, charges 0, button read ready (blue .41)
    f, side, _ = case("spent")
    assert hb.press_gate(f, side, HIDS, 0.41, 0) == "state"


def test_pending_press_is_withheld():           # 193851 t=3441: re-press 28 ticks after 3413, state_raw 7
    f, side, _ = case("pending")
    assert hb.press_gate(f, side, HIDS, 0.41, 0) == "state"


def test_ready_single_body_is_unchanged():      # 133526 t=675: one IW, Ready, charge 1 -> same body, same decision
    f, side, names = case("ready_one_body")
    assert hb.press_gate(f, side, HIDS, 0.41, 0) is None
    assert hb.pick_hero(f, side, IDS) is first_listed(f, side)
    assert hb.ice_wizard_should_press(f, side, hb.pick_hero(f, side, IDS), names)[0] is True


def test_wrong_body_is_rejudged_on_the_ability_body():
    f, side, names = case("wrong_body")         # 133526 t=2938: old pick = gen 5000043 (no ability), logged iw_wincon
    assert first_listed(f, side)["category"] == 5000043
    assert hb.ice_wizard_should_press(f, side, first_listed(f, side), names)[0] is True       # the logged press
    new = hb.pick_hero(f, side, IDS)
    assert new["category"] == 5000055 and hb.press_gate(f, side, HIDS, 0.41, 0) is None
    assert hb.ice_wizard_should_press(f, side, new, names) == (False, "iw_no_target")
    assert hero_of(f, side, HIDS) is new                                                       # the head path too
    f, side, names = case("wrong_body_pressed")  # 182814 t=3798: the ability body has its own clump -> still pressed
    assert hb.pick_hero(f, side, IDS)["category"] == 5000080
    assert hb.ice_wizard_should_press(f, side, hb.pick_hero(f, side, IDS), names)[0] is True


def test_no_phase2_takes_the_newest_body_then_the_old_rule():
    f, side, _ = case("wrong_body", phase2=False)
    assert hb.pick_hero(f, side, IDS)["category"] == 5000055 and hero_of(f, side, HIDS)["category"] == 5000055
    for e in f["entities"]:
        e.pop("category")                       # no generation either: the old first-listed pick
    assert hb.pick_hero(f, side, IDS) is first_listed(f, side)


def test_no_phase2_falls_back_to_memory_and_band():
    f, side, _ = case("ready_one_body", phase2=False)
    assert hb.press_gate(f, side, HIDS, 0.41, 0) is None            # real ready button (0.38-0.44), unpressed
    assert hb.press_gate(f, side, HIDS, 0.41, 1) == "stale"         # already pressed this deployment
    assert hb.press_gate(f, side, HIDS, 0.524, 0) == "band"         # arena floor read as 'ready' (blue > 0.48)
    assert hb.press_gate(f, side, HIDS, 0.38, 0) is None and hb.press_gate(f, side, HIDS, 0.44, 0) is None
    f["phase2"] = {"valid": False, "units": []}                     # an invalid block counts as absent
    assert hb.press_gate(f, side, HIDS, 0.524, 0) == "band"


def test_floor_misread_with_phase2_and_no_own_hero():
    f, side, _ = case("ready_one_body")
    f["entities"] = [e for e in f["entities"] if int(e["card_id"]) not in IDS]
    assert hb.press_gate(f, side, HIDS, 0.524, 0) == "state" and hb.pick_hero(f, side, IDS) is None


def test_only_the_older_body_left_is_withheld():   # the newer IW died: phase 2 lists no own ability block
    f, side, _ = case("wrong_body")
    for u in f["phase2"]["units"]:
        if u["generation"] == 5000055:
            u["ability"]["own_action"] = None
    assert hb.press_gate(f, side, HIDS, 0.41, 0) == "state"

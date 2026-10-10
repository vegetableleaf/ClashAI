import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

import drill_arms as A
import pro_when as P
import variant_search as V
import xl2_selectors as X
import xl2_stage as ST
from conftest import body


def state(t=3000, bodies=(), hand=("Log", "Rocket", "Tornado", "Knight"), own=()):
    return (t, 10., hand, list(bodies), dict(mK=1000, mL=1000, mR=1000, eK=1000, eL=1000, eR=1000), None, list(own), [])


def match(st, plays=()):
    return dict(file="replay_s0", S=[st], P=list(plays), twmax={k: 1000 for k in P.TOWERS})


def eb(name, x, y, value, uid=1, air=False):
    return (name, x, y, value, uid, 2900, 1., air)


def test_new_selectors(selectors):
    swarm = [eb("goblins", 4 + i * .2, 10, .5, i) for i in range(3)]
    rows = X.harvest(match(state(bodies=swarm)), selectors)
    assert any(r["drill"] == "D5" for r in rows)
    clump = [eb("knight", 4, 10, 3, i)[:-3] + (2900 + i, 1., False) for i in range(4)]
    rows = X.harvest(match(state(bodies=clump)), selectors)
    assert any(r["drill"] == "D6" for r in rows)
    # Threatened D7 moments must still enter the WHEN population with a DO target.
    assert any(r["drill"] == "D7" and r["kind"] == "hold" and r["target"] == 0 for r in rows)
    assert not any(r["drill"] == "D7" for r in X.harvest(match(state(t=100)), selectors))


@pytest.mark.parametrize("name", ["goblin_barrel", "skeleton_barrel", "skeleton_barrel_evo"])
def test_barrel_selector(selectors, name):
    st = state(bodies=[eb(name, 4, 8, 3, air=True)])
    assert any(r["drill"] == "D5" and r["info"].get("barrel") for r in X.harvest(match(st), selectors))
    assert not list(X.d5(None, 0, state(hand=("Knight",), bodies=st[3]), selectors))


def test_barrel_projectile():
    st = list(state()); st[7] = [("GoblinBarrel", 3.5, 6.5)]
    assert X.barrel_targets(st) == [(3.5, 6.5)]


def test_d8_selector(selectors):
    st = state(bodies=[eb("knight", 4, 25, 3)], own=[("x_bow", 4, 14, 1000, 1000)])
    assert any(r["drill"] == "D8" for r in X.harvest(match(st), selectors))


def test_d5_best_corridor(side, monkeypatch):
    from pipeline import decision_options as DO
    import sneaky_rule
    s, ctx = side
    monkeypatch.setattr(DO, "rocket_unit_table", lambda: {"goblins": (.5, 100, .5, .05), "giant": (5., 1000, .5, .05)})
    monkeypatch.setattr(sneaky_rule, "unit_params", lambda cls: ("troop", 60, .5))
    ctx["bs"].units = [body("goblins", 4 + .2 * i, 10) for i in range(3)] + [body("giant", 15, 10)]
    arms = A.build_arms(dict(drill="D5"), None, s, ctx)
    d = arms["do"]["root"]
    from pipeline.model_v3 import cell_xy
    x, y = cell_xy(d["cell"])
    x, y = 18 * x, 32 * (1 - y)
    assert d["slot"] == 6 and abs(x - 4) <= 2.7 and 0 <= 10 - y <= 10.6
    assert not arms["alt"]["root"]["play"]


def test_d5_air_only_and_missing_card(side, monkeypatch):
    from pipeline import decision_options as DO
    import sneaky_rule
    s, ctx = side
    monkeypatch.setattr(DO, "rocket_unit_table", lambda: {"minions": (1., 100, .5, .05)})
    monkeypatch.setattr(sneaky_rule, "unit_params", lambda cls: ("air", 60, .5))
    ctx["bs"].units = [body("minions", 4, 10)] * 3
    assert "_skip" in A.build_arms(dict(drill="D5"), None, s, ctx)
    ctx["allowed"][6] = False
    assert "_skip" in A.build_arms(dict(drill="D5"), None, s, ctx)


def test_d6_uses_deployed_impact_lead(side, monkeypatch):
    from pipeline import decision_options as DO
    from pipeline.model_v3 import cell_xy
    s, ctx = side
    # Four full-health moving Knights, 12 elixir. Real deployed aim implementation.
    monkeypatch.setattr(DO, "rocket_unit_table", lambda: {"knight": (3., 1000., .5, .05)})
    monkeypatch.setattr(DO, "rocket_radius_tiles", lambda: 2.0)
    ctx["bs"].units = [body("knight", 4 + i * .1, 12) for i in range(4)]
    arms = A.build_arms(dict(drill="D6"), None, s, ctx)
    d = arms["do"]["root"]
    x, y = cell_xy(d["cell"])
    assert d["slot"] == 4 and y * 32 > 20  # aimed forward in time, toward our tower
    assert not arms["alt"]["root"]["play"]
    ctx["bs"].units = ctx["bs"].units[:2]
    assert "_skip" in A.build_arms(dict(drill="D6"), None, s, ctx)


def test_d7_shared_mechanic(side):
    s, ctx = side
    arms = A.build_arms(dict(drill="D7"), None, s, ctx)
    assert arms["do"]["root"] == A.rocket_tower_choice(s, ctx["allowed"])
    assert arms["do"]["root"]["lane"] == "L"
    ctx["bs"].t_sec = 90
    assert "_skip" in A.build_arms(dict(drill="D7"), None, s, ctx)


def test_d8_shared_rule(side):
    import sneaky_rule
    s, ctx = side
    ctx["bs"].units = [body("x_bow", 4, 14, 0), body("knight", 4, 25)]
    expected = sneaky_rule.sneaky_lock_choice(NS(sneaky_lock="on"), ctx["bs"], s.deck.cards, ctx["allowed"], "floor")
    assert expected is not None
    arms = A.build_arms(dict(drill="D8"), None, s, ctx)
    assert arms["do"]["root"]["cell"] == expected[1]
    assert arms["do"]["root"]["slot"] == 0


@pytest.mark.parametrize("q", [.3, .5, .7])
def test_when_passthrough_and_boundary(side, q):
    s, ctx = side
    mo = dict(drill="D7", variant=f"DO_when_{q}", p_pro=q - .001)
    arms = A.build_arms(mo, None, s, ctx)
    assert arms["do"]["root"] == ctx["d"] == arms["alt"]["root"]
    assert arms["do"]["script"] is None
    mo["p_pro"] = q
    assert A.build_arms(mo, None, s, ctx)["do"]["root"]["slot"] == 4


def test_d4_best_air_at_best_cell(side):
    s, ctx = side
    arms = A.build_arms(dict(drill="D4", variant="DO_best_air", info=dict(fly=(4, 10), tower="mL")), None, s, ctx)
    assert arms["do"]["root"]["slot"] == 4  # Rocket is air-capable too
    assert arms["do"]["root"]["cell"] == 2303
    assert arms["alt"]["root"] == ctx["d"]


def test_public_features_ignore_truth():
    m = match(state(bodies=[eb("knight", 4, 10, 3)]), plays=[(2900, 2926, "Knight", 4, 10)])
    x = P.features(m, 0, P.opponent_estimates(m["S"])[0])
    altered = {**m, "opp_deck": ["secret"], "opx": [(0, "secret", 0, 0, 10)], "opp_elixir": 99, "opp_hand": ["secret"]}
    assert x == P.features(altered, 0, P.opponent_estimates(altered["S"])[0])
    assert len(x) == len(P.FEATURES)
    assert x[P.FEATURES.index("seconds_since_play")] == 5
    assert x[P.FEATURES.index("enemy_value_left")] == 3


def test_counter_no_future_leak():
    early = state(t=0)
    later = state(t=20, bodies=[eb("knight", 4, 10, 3)])
    values = P.opponent_estimates([early, later, state(t=40, bodies=later[3])])
    assert values[0] == 5
    assert values[1] == pytest.approx(5 + 1 / 2.81 - 3)
    assert values[2] == pytest.approx(values[1] + 1 / 2.81)


def test_public_lane_features_and_identity_resolution():
    st = state(t=100, bodies=[eb("knight", 4, 25, 3)])
    m = match(st)
    x = P.features(m, 0, 5)
    assert x[P.FEATURES.index("enemy_value_home")] == 0
    assert x[P.FEATURES.index("enemy_value_left")] == 3
    updated = list(st)
    updated[0] = 120
    b = list(st[3][0]); b[4], b[5] = 9999, 120
    updated[3] = [b]
    estimates = P.opponent_estimates([st, updated])
    assert estimates[1] == pytest.approx(estimates[0] + 1 / 2.81)


def test_numpy_fit_auc_and_serialization():
    rows = []
    for group in range(30):
        for n in range(10):
            x = [0.] * len(P.FEATURES)
            x[0] = n
            rows.append(dict(match=str(group), x=x, target=int(n >= 5)))
    model = P.fit(rows)
    assert model["heldout_auc"] == 1.0
    assert not set(model["train_matches"]) & set(model["heldout_matches"])
    loaded = json.loads(json.dumps(model))
    assert P.predict(loaded, rows[0]["x"]) < .1
    assert P.predict(loaded, rows[9]["x"]) > .9
    assert P.auc([0, 1], [.5, .5]) == .5
    assert P.auc([1, 1], [.5, .8]) is None


def test_fit_fails_honestly():
    with pytest.raises(ValueError, match="five"):
        P.fit([])
    with pytest.raises(ValueError, match="positive and negative"):
        P.fit([dict(match=str(i), x=[0.] * len(P.FEATURES), target=0) for i in range(10)])


def stats(mu, hw=.01):
    return dict(mean=mu, half_width=hw, n=50, matches=20)


@pytest.mark.parametrize("mu,hw,expected", [(0, 0, "none"), (.1, .1, "none"), (.11, .1, "do"), (-.11, .1, "alt"), (.8, None, "none")])
def test_label_rule(mu, hw, expected):
    assert V.label(stats(mu, hw)) == expected


def test_disjoint_seeds():
    assert V.validate_seeds(V.SEEDS)
    bad = copy.deepcopy(V.SEEDS); bad["test"]["lad"] = bad["dev"]["evo"]
    with pytest.raises(ValueError, match="overlapping"):
        V.validate_seeds(bad)


def test_search_test_used_once_and_not_for_selection(tmp_path):
    calls, path = [], tmp_path / "search.json"
    def evaluate(split, drill, variant):
        calls.append((split, variant))
        if split == "test":
            assert json.loads(path.read_text())["selected"] == "DO_when_0.5"
            return stats(-.2)
        return stats(.3 if variant == "DO_when_0.5" else .1)
    report = V.search("D4", evaluate, path)
    assert len(report["dev"]) == 5
    assert [x for x in calls if x[0] == "test"] == [("test", "DO_when_0.5")]
    assert report["label"] == "alt" and report["selected"] == "DO_when_0.5"
    with pytest.raises(FileExistsError):
        V.search("D4", evaluate, path)


def test_search_test_failure_no_retry(tmp_path):
    def evaluate(split, drill, variant):
        if split == "test":
            raise RuntimeError("test failed")
        return stats(.1)
    path = tmp_path / "search.json"
    with pytest.raises(RuntimeError):
        V.search("D5", evaluate, path)
    report = json.loads(path.read_text())
    assert report["label"] == "none" and "error" in report and report["selected"] == "DO"


def test_estimate_uses_binary_win_and_match_clusters():
    rows = []
    for tag, pairs in (("a", [("win", "loss"), ("loss", "win")]), ("b", [("draw", "loss")])):
        rows.append(dict(tag=tag, mech={"opps": [dict(drill="D5", variant="DO", t0=i, Ares=dict(outcome=a),
                          arms={"do": dict(outcome=b)}) for i, (b, a) in enumerate(pairs)]}))
    result = V.estimate(rows, "D5", "DO")
    assert result["n"] == 3 and result["matches"] == 2 and result["mean"] == 0
    with pytest.raises(ValueError, match="provenance"):
        V.estimate(rows, "D5", "DO_when_0.3")


def test_training_normalizes_own_alt_and_variant(tmp_path):
    md, rd = tmp_path / "matches", tmp_path / "rows"
    md.mkdir(); rd.mkdir()
    o = dict(drill="D5", t0=20, variant="DO_when_0.5", A=dict(play=True, slot=5, cell=42), Ares=dict(outcome="win"),
             arms={"do": dict(outcome="loss"), "alt": dict(outcome="loss")})
    (md / "matches.jsonl").write_text(json.dumps(dict(tag="s0:gen:16000", mech=dict(opps=[o]))) + "\n")
    np.savez(rd / "fork_D5_s0_gen_16000_20.npz", drill="D5", tick=20, variant="DO_when_0.5", do_play=1, do_slot=6, do_cell=99)
    sources = [dict(drill="D5", label="alt", matches=str(md), rows=str(rd), variant="DO_when_0.5", own_alt=True)]
    dest, rowsdir, counts = ST.assemble_training(tmp_path / "training", {"D5": "alt"}, sources)
    z = dict(np.load(next(rowsdir.glob("fork*.npz"))))
    assert int(z["alt_slot"]) == 5 and int(z["alt_cell"]) == 42 and counts == {"D5": 1}
    result = json.loads((dest / "matches.jsonl").read_text())
    assert result["mech"]["opps"][0]["arms"]["alt"]["outcome"] == "win"
    assert result["tag"].startswith("src0_")


def test_search_rejects_changed_dev_population(tmp_path):
    def evaluate(split, drill, variant):
        assert split == "dev"
        return {**stats(.1), "opportunity_sha256": variant}
    with pytest.raises(ValueError, match="same opportunity population"):
        V.search("D5", evaluate, tmp_path / "search.json")


def test_best_air_uses_same_eligibility_as_plain(side):
    s, ctx = side
    ctx["allowed"][1:3] = False  # Rocket remains affordable, but no baseline defender
    assert "_skip" in A.build_arms(dict(drill="D4", variant="DO_best_air"), None, s, ctx)


def test_read_matches_rejects_missing_and_failed_replay(tmp_path):
    f = tmp_path / "matches.jsonl"
    f.write_text(json.dumps(dict(seed=8000)) + "\n")
    with pytest.raises(ValueError, match="incomplete"):
        V.read_matches(tmp_path, (8000, 8002))
    f.write_text(json.dumps(dict(seed=8000, mech={"opps": [{"Acheck": {"end": {"h": "bad"}}, "Ares": {"end": {"h": "good"}}}]})) + "\n")
    with pytest.raises(ValueError, match="replay"):
        V.read_matches(tmp_path, (8000, 8001))


def test_fit_table_uses_second_card_tick_and_groups_sides(selectors, monkeypatch):
    m = match(state(t=100), plays=[(105, 131, "Knight", 4, 10), (130, 156, "Log", 4, 10)])
    monkeypatch.setattr(X, "harvest", lambda m: [dict(drill="D9", t=130, target=1)])
    rows = list(P.table([m, {**m, "file": "replay_s1"}]))
    assert rows[0]["match"] == rows[1]["match"] == "replay"
    assert rows[0]["x"][P.FEATURES.index("seconds_since_play")] == 1.25


@pytest.mark.parametrize("stage", ["S9XL2", "S10XL2"])
def test_stage_failure_still_writes_done_summary(tmp_path, monkeypatch, stage):
    # No prerequisite marker: fail before any simulator/checkpoint access.
    import sys
    monkeypatch.setattr(sys, "argv", ["xl2_stage.py", stage, "--repo", str(tmp_path), "--results", str(tmp_path),
                                     "--ckpt", "unused", "--models", "unused"])
    assert ST.main() == 1
    assert (tmp_path / stage / "DONE").exists()
    assert "must wait for S10XL/DONE" in (tmp_path / stage / "SUMMARY.txt").read_text()
    assert not (tmp_path / stage / "SUCCESS").exists()


def test_s10_does_not_train_after_failed_s9(tmp_path):
    with pytest.raises(ValueError, match="failed or is incomplete"):
        ST.s10(NS(results=str(tmp_path)), [])


def test_eval_requires_960_pairs_and_reports_archetypes(tmp_path):
    for census in ("evo", "lad"):
        for name, outcome in (("live", "loss"), ("candidate", "win")):
            path = tmp_path / f"{name}_{census}"
            path.mkdir()
            (path / "matches.jsonl").write_text("".join(json.dumps(dict(tag=f"s0:gen:{20000 + i}", outcome=outcome,
                                                   opp_deck=["golem", "lightning", "baby_dragon"])) + "\n" for i in range(480)))
    lines = ST.eval_verdict(str(tmp_path))
    assert "960 paired" in lines[0] and "archetype" in lines[1]
    assert lines[-1] == "VERDICT: candidate: ask owner to deploy"
    # Turning one result into a skipped result must fail the entire evaluation.
    path = tmp_path / "candidate_lad/matches.jsonl"
    rows = path.read_text().splitlines(); rows[0] = json.dumps(dict(tag="s0:gen:20000", skipped=True))
    path.write_text("\n".join(rows))
    with pytest.raises(ValueError, match="960 complete"):
        ST.eval_verdict(str(tmp_path))


def test_legacy_definitions_unchanged():
    from check_xl2 import verify
    verify()

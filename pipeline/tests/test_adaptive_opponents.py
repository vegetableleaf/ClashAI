"""Offline adaptive-opponent tests. Fake boards/policies only; never imports SIM."""
import copy
import hashlib
import io
import json
import re
import shlex
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest
import torch
import yaml

from pipeline import adaptive_opponents as A, e1_eval as E, rl_royale as R
from pipeline.tests import test_league as L
from scratchpad.gauntlet.L74.weekend.adaptive import driver as D


@pytest.fixture
def tmp_path():
    # Inherit the workspace ACL on restricted Windows, like weekend/tests.
    path = R.REPO / "scratchpad" / ("adaptive_test_" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def cfg(**kw):
    c = R.load_config(R.REPO / "pipeline/rl_royale.yaml", [], False)
    return {**c, "league": True, "opp_elixir": "counter", **kw}


def test_rating_math_and_order():
    assert A.update_rating(.5, "win") == pytest.approx(.525)
    assert A.update_rating(.5, "loss") == pytest.approx(.475)
    assert A.update_rating(.8, "draw") == pytest.approx(.785)
    a, b = {}, {}
    rows = [dict(league={"tag": "m", "opp": {"id": "o"}}, k=k, outcome=o)
            for k, o in enumerate(("win", "draw", "loss"))]
    A.update_ratings(a, rows)
    A.update_ratings(b, rows[::-1])
    assert a == b
    assert a["ratings"]["o"] == {"p": pytest.approx(.4975625), "games": 3}


def test_pfsp_weights_and_empirical_sampling():
    assert A.pfsp_weights([0, .5, 1]) == pytest.approx(np.array([1.05, .30, .05]) / 1.4)
    assert (A.pfsp_weights([1, 1]) > 0).all()
    c = cfg(league_pfsp="hard")
    state = {"ratings": {"init": {"p": 0}, "s1": {"p": 1}}}
    rng = np.random.default_rng(74)
    draws = [A.sample_opponent(rng, [], c, state)["id"] for _ in range(4000)]
    assert 0.93 < draws.count("init") / len(draws) < .97
    assert set(draws) == {"init", "s1"}
    with pytest.raises(ValueError):
        A.pfsp_weights([1], floor=0)


def test_pool_snapshots_external_and_frozen():
    c = cfg(league_pfsp="hard", league_external=["exploit.pt"])
    state = {"snapshots": [{"id": "snap1", "path": "snap.pt"}]}
    A.sync_pool(state, c)
    assert len(state["ratings"]) == 4
    assert len(A.opponent_pool(state["snapshots"], c, state)) == 4
    state["snapshots"].clear()  # evicting main snapshots cannot evict exploiters
    assert "exploit.pt" in [o["path"] for o in A.opponent_pool([], c, state)]
    frozen = {**c, "league_frozen_opponent": "frozen_c1.pt"}
    census = [{"engine": L.HOGEQ, "name": "hog", "bucket": "head"}]
    specs = R.sample_matchups(np.random.default_rng(2), 30, 0, [], frozen, census, np.array([1.]), state)
    assert {s["opp"]["path"] for s in specs} == {"frozen_c1.pt"}
    assert all(s["opp_deck"] == list(E.ICEBOW_ENGINE_DECK) for s in specs)


def test_resume_ratings_rng_via_real_checkpoint_methods(monkeypatch):
    # Borrow the real trainer stub but bypass filesystem setup: _rl_state and
    # _restore run unchanged, using a weights_only checkpoint in memory.
    c = cfg(league_pfsp="hard", league_external=["exp.pt"])
    model = L._tiny_gen(22)
    learner = R.Learner.__new__(R.Learner)
    learner.cfg, learner.model, learner.opt = c, model, torch.optim.Adam(model.parameters())
    learner.update, learner.beta = 4, .3
    learner.rng = np.random.default_rng(41)
    learner.visits, learner.train, learner.base = [], [], {}
    learner.run, learner.pool_sha, learner.runtime = "test", "pool", None
    learner.dev = torch.device("cpu")
    learner.guards, learner.log = R.Guards(c), lambda _: None
    learner.league = {"snapshots": [{"id": "snap", "path": "snapshot.pt"}],
                      "ratings": {"init": {"p": .85, "games": 30}}}
    A.sync_pool(learner.league, c)
    data = {"model": model.state_dict(), "rl": learner._rl_state()}
    buf = io.BytesIO()
    torch.save(data, buf)
    buf.seek(0)
    saved = torch.load(buf, weights_only=True)
    monkeypatch.setattr(torch, "load", lambda *a, **k: saved)
    restored = copy.deepcopy(learner)
    restored.league = {"snapshots": []}
    restored.rng = np.random.default_rng(9)
    restored._restore(Path("fake.pt"))
    assert restored.league == learner.league
    assert restored.rng.bit_generator.state == learner.rng.bit_generator.state
    assert [A.sample_opponent(restored.rng, [], c, restored.league) for _ in range(12)] == [
        A.sample_opponent(learner.rng, [], c, learner.league) for _ in range(12)]


def test_default_off_hash_and_rng_unchanged():
    c = R.load_config(R.REPO / "pipeline/rl_royale.yaml", [], False)
    old = {k: v for k, v in c.items() if k != "hero_abilities"}
    golden = hashlib.sha256(json.dumps(old, sort_keys=True, default=str).encode()).hexdigest()
    assert R.config_sha(c) == golden == R.config_sha({**c, **A.DEFAULTS})
    assert R.config_sha({**c, "opp_style": False, "league_pfsp": False}) == golden
    census = [{"engine": L.HOGEQ, "name": "hog", "bucket": "head"}]
    x, y = np.random.default_rng(4), np.random.default_rng(4)
    a = R.sample_matchups(x, 40, 1, [], c, census, np.array([1.]))
    b = R.sample_matchups(y, 40, 1, [], {**c, **A.DEFAULTS}, census, np.array([1.]))
    assert a == b and x.bit_generator.state == y.bit_generator.state
    assert A.style_config(c, 1, 0) is c
    assert R.config_sha({**c, "league_pfsp": "hard"}) != golden


@pytest.mark.parametrize("override", ["opp_style=on", "league_pfsp=hard"])
def test_config_cli_and_public_counter_required(override):
    with pytest.raises(ValueError, match="public opp_elixir"):
        R.load_config(R.REPO / "pipeline/rl_royale.yaml", ["league=true", override], False)
    c = R.load_config(R.REPO / "pipeline/rl_royale.yaml", ["league=true", "opp_elixir=counter", override], False)
    A.validate(c)


def test_style_determinism_and_ranges():
    c = cfg(opp_style="on")
    assert A.draw_style(c, 91, 2) == A.draw_style(c, 91, 2)
    assert A.draw_style(c, 91, 2) != A.draw_style(c, 91, 3)
    for seed in range(50):
        style = A.draw_style(c, seed)
        for name, v in style.items():
            lo, hi = A.DEFAULTS["opp_style_" + name]
            assert lo <= v <= hi
    styled = A.style_config({**c, "opp_style_aggression": [.1, .1], "opp_style_temperature": [1.2, 1.2]}, 0, 0)
    assert styled["tau"] == pytest.approx(c["tau"] - .1)
    assert styled["T"] == pytest.approx(c["T"] * 1.2)
    assert "_opp_style" not in c


def test_lane_bias_and_banking_public_only():
    net = NS(cell_logits=lambda enc, slot: torch.zeros((1, 2304)))
    p = torch.softmax(A.LanePolicy(net, .7, .5).cell_logits({}, None).double() / .5, -1).reshape(64, 36)
    assert (p[:, :18].sum() / p[:, 18:].sum()).item() == pytest.approx(np.exp(1.4), rel=1e-6)
    assert A.bank_wait(NS(my_elixir=2, units=[]), {"bank": 3})
    assert not A.bank_wait(NS(my_elixir=2, units=[NS(side=1, y=.6)]), {"bank": 3})
    assert A.bank_wait(NS(my_elixir=2, units=[NS(side=0, y=.6)]), {"bank": 3})
    assert not A.bank_wait(NS(my_elixir=5, units=[]), {"bank": 3})


@pytest.mark.parametrize("policy", ["sample", "live"])
def test_styles_only_opponent_real_selfplay_and_on_policy(policy):
    # Same policy object on both sides deliberately stresses group separation.
    net = E.GenPolicy(L._tiny_gen(31), L.VOCAB)
    learner_cfg = L._cfg(stall_elixir=None)
    oc = L._cfg(policy, record=False, stall_elixir=None, opp_style="on", opp_style_bank=[0, 0])
    jobs = [(0, L._spec(0, "o", 0), 0), (1, L._spec(1, "o", 1), 1)]
    spy = []
    result, _ = L._run(jobs, net, {"o": (net, oc)}, learner_cfg, n=2, spy=spy)
    assert len(result) == 2
    for r, m in zip(result, spy):
        assert "_opp_style" not in m.learner.cfg
        assert m.learner.cfg["tau"] == learner_cfg["tau"]
        assert m.learner.cfg["T"] == learner_cfg["T"]
        assert m.opp.traj == []
        assert "opp_style" in r
    batch, _ = R.collate(result)
    b = R.to_device(batch, "cpu")
    t = R.policy_terms(net.model, b, torch.arange(len(b["A"])), L.TAU, L.T)
    for key in ("lp_gate", "lp_card", "lp_cell"):
        assert (t[key] - b[key]).abs().max().item() < 1e-4


def test_spell_delay_lands_later_only_for_styled_opponent():
    # Exercise real SelfPlaySide queue logic, no engine runtime.
    s = E.SelfPlaySide.__new__(E.SelfPlaySide)
    s.cfg = {"decide_every": 10, "_opp_style": {}}
    s.env = NS(hero_abilities=False)
    s.delay, s.pipe, s.pending = 26, False, None
    s._record = lambda p, d: 100
    d = {"play": True, "slot": 0, "cell": 0, "_style_delay": 4}
    s.apply(.9, d)
    assert s.pending[0] == 130 and s.next_tick == 140
    s.cfg.pop("_opp_style")
    s.apply(.9, d)
    assert s.pending[0] == 126


def test_cycles_freeze_main_restart_exploiters_and_grow_pool():
    plans = D.cycle_plan()
    assert [p["main_target"] for p in plans] == [20, 40, 60]
    assert len({p["frozen"] for p in plans}) == 3
    main = {"rl": {"league": {"snapshots": [], "ratings": {"init": {"p": .6}}}, "optimizer": {"step": 20}}}
    external = []
    for p in plans:
        main_cfg = D.config_for(cfg(), "main", p, "decks.json", external)
        exp = D.config_for(cfg(), "exploiter", p, "decks.json", [])
        A.validate(main_cfg)
        A.validate(exp)
        assert main_cfg["league_external"] == external
        assert exp["init"] == str(D.FAST) and exp["max_updates"] == 15
        assert exp["league_frozen_opponent"] == p["frozen"]
        assert exp["advantage"] == "match_loo" and exp["shaping"] == "none"
        main = D.enroll(main, str(D.checkpoint(p["exploiter_run"])))
        external = main["rl"]["league"]["external"]
        assert len(external) == p["cycle"]
        assert main["rl"]["league"]["ratings"]["external:" + external[-1]] == {"p": .5, "games": 0}
        assert main["rl"]["league"]["ratings"]["init"]["p"] == .6
        assert main["rl"]["optimizer"] == {"step": 20}
    assert D.enroll(main, external[-1]) == main


def test_weighted_decks_and_fixed_eval():
    decks = {"decks": [{"engine": L.ICEBOW, "sides": 1}, {"engine": ["Golem"], "sides": 10},
                       {"engine": ["HogRider"], "sides": 90}]}
    weighted = D.weighted_sixty(decks)
    assert weighted["adaptive_unfavourable_share"] == pytest.approx(.6)
    assert len(weighted["decks"]) == 2
    cmd = D.eval_command("candidate.pt", "ev", D.EVO, 30000)
    assert cmd[cmd.index("--opp-gen") + 1] == str(D.CAL_C)
    assert cmd[cmd.index("--opp-T") + 1] == "0.1"
    assert cmd[cmd.index("--seeds") + 1] == "30000:30480"
    assert cmd[cmd.index("--census") + 1] == str(D.EVO)
    assert int(cmd[cmd.index("--workers") + 1]) <= 20
    assert all(flag in cmd for flag in D.LIVE_FLAGS)
    cal = (D.WEEKEND / "cal_run.sh").read_text()
    assert D.LIVE_FLAGS == shlex.split(re.search(r"LV=\((.*?)\)", cal, re.S)[1])
    assert D.config_for(cfg(), "main", D.cycle_plan()[0], "decks.json", [])["proagree_data_gen"] == str(D.DATA)


def test_training_rollouts_are_plain_model_no_live_rules():
    # Owner 10-11: training runs the PLAIN model (no LIVE_OPTIONS decision rules); only the final eval carries them.
    from pipeline import decision_options as DO, rl_royale as RL
    for phase in ("main", "exploiter"):
        c = D.config_for(cfg(), phase, D.cycle_plan()[0], "decks.json", [])
        assert not set(c) & set(DO.DecisionOptions.__dataclass_fields__)
        for kind in ("rollout", "screen"):
            base = {**c, "tau": .27, "afford_mask": True, "stall_seconds": 12, "obs": "live", "grid": 1,
                    "decide_every": 10, "T": .5}
            assert not DO.options_from_config(RL.actor_cfg(base, kind, 0, "cpu")).active


def test_shell_wait_locks_and_failure_contract():
    shell = (Path(D.__file__).parent / "run_adaptive.sh").read_text()
    assert shell.index("while [ ! -f /workspace/results/wk/ICEBOW_DONE ]") < shell.index("flock /workspace/gpu.lock")
    assert 'flock /workspace/gpu.lock flock /workspace/cpu.lock "$PY"' in shell
    assert "trap finish EXIT" in shell and "trap 'exit 143' TERM" in shell
    assert 'touch "$OUT/DONE"' in shell and '> "$OUT/SUMMARY.txt"' in shell
    assert shell.index("trap finish EXIT") < shell.index("while [ ! -f")
    assert "set -euo pipefail" in shell


def test_public_history_causal_side_and_length():
    from pipeline.dataset_gen import opponent_past, card_key
    from pipeline.public_observation import opponent_cycle
    gid = {card_key(c): i + 1 for i, c in enumerate(L.ICEBOW)}
    plays = [dict(card=c, side=0, tick=i, form=0, x=4000, y=8000, accepted=True) for i, c in enumerate(L.ICEBOW)]
    # Opponent is side 1: its history is the learner's public plays.
    p = opponent_past(plays, 8, 1, gid)
    assert p.shape == (3, 5)
    assert list(p[:, 0]) == [8, 7, 6]
    cyc = opponent_cycle(plays, 8, 1, gid)
    assert cyc.shape == (8, 4)
    assert list(cyc[:, 0]) == list(range(8, 0, -1))
    poison = [dict(plays[-1], tick=8), dict(plays[0], side=1), dict(plays[0], tick=7, accepted=False)]
    assert np.array_equal(p, opponent_past(plays + poison, 8, 1, gid))
    assert not opponent_past(plays, 8, 0, gid)[:, 0].any()
    # Repeated card occupies a play-history slot but only one cycle slot.
    repeated = plays + [dict(plays[-1], tick=9)]
    assert list(opponent_past(repeated, 10, 1, gid)[:, 0]) == [8, 8, 7]
    assert len(set(opponent_cycle(repeated, 10, 1, gid)[:, 0])) == 8


def test_rollout_records_per_match_style_and_ratings():
    learner = R.Learner.__new__(R.Learner)
    learner.cfg = cfg(league_pfsp="hard", opp_style="on", E=2, G=2)
    learner.rng, learner.model = np.random.default_rng(1), L._tiny_gen(11)
    learner.league = {"snapshots": []}
    learner.census = [{"engine": L.HOGEQ, "name": "hog", "bucket": "head"}]
    learner.census_p = np.array([1.])
    events = []
    learner.log = NS(json=events.append)

    def fake_actors(kind, update, sd, jobs):
        return ([dict(league=sp, k=g, outcome="win", opp_style=A.draw_style(learner.cfg, sp["seed"], g))
                 for i, sp, g in jobs], [], {})

    learner.actors = NS(run=fake_actors)
    rows, info = learner.rollout(3)
    assert len(rows) == len(events) == 4
    assert sum(v["games"] for v in learner.league["ratings"].values()) == 4
    assert all(r["event"] == "opponent_style" and r["update"] == 3 for r in events)


@pytest.mark.parametrize("continuation", [None, "restored", "fresh"])
def test_driver_all_cycles_and_eval_with_fake_training(tmp_path, monkeypatch, continuation):
    # Full orchestration, including persisted frozen copies, pool enrollment,
    # restart, graft command and paired report. Subprocesses are all replaced.
    monkeypatch.setattr(D, "REPO", tmp_path)
    for path in (D.FAST, D.OLD, D.CAL_C, D.EVO, D.LAD, D.DATA):
        p = tmp_path / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fixture")
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline/rl_royale.yaml").write_text(yaml.safe_dump(cfg()))
    calls, evals = [], []
    options = {}
    offset = 60 if continuation == "restored" else 0
    initial_external = 1 if continuation else 0
    if continuation:
        seed = {"model": {"w": torch.tensor([60.])}}
        if continuation == "restored":
            seed["rl"] = {"update": 60, "init": str(D.FAST), "optimizer": {"step": 60},
                          "league": {"snapshots": [], "external": [],
                                     "ratings": {"init": {"p": .72, "games": 900}}}}
        D.save_checkpoint(tmp_path / "seed.pt", seed)
        options = dict(init=Path("seed.pt"), extra_exploiters=[str(D.OLD)], cycles=3, tag="adapt2")

    def fake_train(c, name, out):
        path = tmp_path / D.checkpoint(name)
        if path.exists():
            ck = torch.load(path, weights_only=True)
        else:
            ck = {"model": {"w": torch.zeros(1)}, "rl": {"league": {"snapshots": [], "ratings": {},
                  "external": list(c["league_external"])}, "update": 0}}
            if continuation == "fresh" and "league_frozen_opponent" not in c:
                assert c["init"] == "seed.pt"
                ck["model"] = torch.load(tmp_path / c["init"], weights_only=True)["model"]
        if "league_frozen_opponent" in c:
            frozen = torch.load(tmp_path / c["league_frozen_opponent"], weights_only=True)
            assert "rl" not in frozen
            assert frozen["model"]["w"].item() == offset + 20 * (len(calls) // 2 + 1)
            assert c["init"] == str(D.FAST)
        else:
            assert len(c["league_external"]) == initial_external + len(calls) // 2
            if continuation == "restored":
                assert ck["rl"]["league"]["ratings"]["init"] == {"p": .72, "games": 900}
                assert ck["rl"]["optimizer"] == {"step": 60}
                if not calls:
                    assert ck["model"]["w"].item() == 60
                    assert ck["rl"]["update"] == 60
                assert c["init"] == str(D.FAST)
        ck["rl"]["update"] = c["max_updates"]
        ck["model"]["w"] = torch.tensor([float(c["max_updates"])])
        D.save_checkpoint(path, ck)
        D.save_checkpoint(path.with_name(f"{name}_u{c['max_updates']:04d}.pt"), ck)
        calls.append((name, c))
        return ck

    def fake_run(cmd, log):
        cmd = list(map(str, cmd))
        if "mk_weighted_decks.py" in cmd[1]:
            Path(cmd[3]).write_text(json.dumps({"decks": [{"engine": ["Golem"], "sides": 10},
                                                          {"engine": ["HogRider"], "sides": 90}]}))
        elif "graft_generic.py" in cmd[1]:
            assert cmd[3] == str(D.OLD)
            D.save_checkpoint(tmp_path / cmd[4], torch.load(tmp_path / cmd[2], weights_only=True))
        else:
            assert cmd[2] == "pipeline.search_s0"
            dest = Path(cmd[cmd.index("--out") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            rows = [dict(tag=str(i), outcome="win" if dest.name.startswith("adaptive") else "loss", opp_deck=["Golem"])
                    for i in range(480)]
            (dest / "matches.jsonl").write_text("\n".join(map(json.dumps, rows)))
            (dest / "summary.json").write_text("{}")
            evals.append(cmd)

    monkeypatch.setattr(D, "train", fake_train)
    monkeypatch.setattr(D, "run", fake_run)
    out = tmp_path / "ADAPT"
    D.execute(out, **options)
    assert len(calls) == 6 and len(evals) == 4
    state = json.loads((out / "cycles.json").read_text())
    assert state["completed"] == [1, 2, 3] and len(state["external"]) == 3 + initial_external
    assert [c["max_updates"] for name, c in calls[::2]] == [offset + u for u in (20, 40, 60)]
    if continuation:
        assert all(name.startswith("wk_adapt2_") for name, _ in calls)
        assert not (tmp_path / D.checkpoint("wk_adapt_main")).exists()
    assert (out / "SUMMARY.txt").read_text().startswith("VERDICT: Improvement shown.")
    assert "960 paired games" in (out / "SUMMARY.txt").read_text()
    D.execute(out, **options)  # completed phases are not trained/evaluated a second time
    assert len(calls) == 6 and len(evals) == 4
    p = out / "eval/adaptive_evo/matches.jsonl"
    original = p.read_text()
    p.write_text("\n".join(original.splitlines()[:-1]))
    with pytest.raises(ValueError, match="incomplete evaluation"):
        D.summary(out / "eval")
    rows = [json.loads(s) for s in original.splitlines()]
    rows[0]["opp_deck"] = ["HogRider"]
    p.write_text("\n".join(map(json.dumps, rows)))
    with pytest.raises(ValueError, match="pairing/decks differ"):
        D.summary(out / "eval")


def test_adapt2_options_and_names():
    a = D.parse_args(["--out", "out"])
    assert (a.init, a.extra_exploiters, a.cycles, a.tag, a.smoke) == (None, [], 3, "adapt", False)
    a = D.parse_args(["--out", "out", "--init", "main.pt", "--extra-exploiters", "a.pt, b.pt",
                      "--cycles", "4", "--tag", "adapt2"])
    assert (a.init, a.extra_exploiters, a.cycles, a.tag) == (Path("main.pt"), ["a.pt", "b.pt"], 4, "adapt2")
    plans = D.cycle_plan("wk_adapt2", 4, start_update=60)
    assert [p["main_target"] for p in plans] == [80, 100, 120, 140]
    assert plans[-1]["exploiter_run"] == "wk_adapt2_exp4"
    assert all(p["exploiter_init"] == str(D.FAST) and p["exploiter_target"] == 15 for p in plans)


def test_driver_defaults_match_pre_adapt2_bytes():
    # Golden independently captured from git 2bfafbf's driver. Normalize only
    # platform separators and the Python executable, not any experiment value.
    payload = {"plan": D.cycle_plan(), "configs": [
        D.config_for({}, phase, plan, "decks.json", [])
        for plan in D.cycle_plan() for phase in ("main", "exploiter")],
        "eval": [D.eval_command("candidate.pt", "eval", census, start)[1:]
                 for census, start in ((D.EVO, 30000), (D.LAD, 30480))]}
    data = json.dumps(payload, sort_keys=True, default=str).replace("\\\\", "/").encode()
    assert hashlib.sha256(data).hexdigest() == "a364b5ad03d882428ecc4a529cbeb1f848554b6e6700fd8ac24cce1259ee8fc7"


def test_adapt2_seed_preserves_league_and_grows_pool(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(D, "REPO", tmp_path)
    snap = D.CKROOT / "wk_adapt_main/wk_adapt_main_snap_u0060.pt"
    for path in (D.FAST, snap, Path("exp1.pt"), Path("exp2.pt")):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    seed = {"model": {"w": torch.ones(1)}, "rl": {"update": 60, "init": str(D.FAST),
            "optimizer": {"step": 60}, "rng": {"sentinel": 123}, "league": {
                "snapshots": [{"id": "snap_u0060", "update": 60, "path": "/workspace/wk_adapt/" + snap.as_posix()}],
                "external": ["exp1.pt"], "ratings": {"init": {"p": .8, "games": 40},
                "external:exp1.pt": {"p": .2, "games": 70}}}}}
    D.save_checkpoint(tmp_path / "seed.pt", seed)
    before = (tmp_path / "seed.pt").read_bytes()
    saved, anchor, start, pool = D.continuation_seed(Path("seed.pt"), ["exp1.pt", "exp2.pt", "exp2.pt"])
    assert (anchor, start, pool) == (str(D.FAST), 60, ["exp1.pt", "exp2.pt"])
    assert saved["rl"]["optimizer"] == seed["rl"]["optimizer"] and saved["rl"]["rng"] == seed["rl"]["rng"]
    league = saved["rl"]["league"]
    assert league["snapshots"][0]["path"] == snap.as_posix()
    for key, rating in seed["rl"]["league"]["ratings"].items():
        assert league["ratings"][key] == rating
    assert league["ratings"]["external:exp2.pt"] == {"p": .5, "games": 0}
    c = D.config_for(cfg(), "main", D.cycle_plan()[0], "decks.json", pool)
    assert len(A.opponent_pool(league["snapshots"], c, league)) == 4
    assert (tmp_path / "seed.pt").read_bytes() == before
    assert "restored league and PFSP ratings at update 60" in capsys.readouterr().out
    (tmp_path / snap).unlink()
    with pytest.raises(FileNotFoundError):
        D.continuation_seed(Path("seed.pt"), [])


@pytest.mark.parametrize("rl", [None, {"update": 60}])
def test_adapt2_seed_without_league_is_fresh(tmp_path, monkeypatch, capsys, rl):
    monkeypatch.setattr(D, "REPO", tmp_path)
    seed = {"model": {"w": torch.ones(1)}}
    if rl is not None:
        seed["rl"] = rl
    D.save_checkpoint(tmp_path / "seed.pt", seed)
    assert D.continuation_seed(Path("seed.pt"), ["exp.pt"]) == (None, "seed.pt", 0, ["exp.pt"])
    assert "fresh league and PFSP ratings" in capsys.readouterr().out


def test_adapt2_shell_wait_locks_failure_and_eval_reuse():
    shell = (Path(D.__file__).parent / "run_adapt2.sh").read_text()
    assert "ETA:" in shell and "OUT=/workspace/results/wk/ADAPT2" in shell
    assert 'WAIT_FOR=${WAIT_FOR:-/workspace/results/wk/ADAPT/DONE}' in shell
    assert shell.index("trap finish EXIT") < shell.index('while [ ! -f "$WAIT_FOR" ]') < shell.index("flock /workspace/gpu.lock")
    assert 'flock /workspace/gpu.lock flock /workspace/cpu.lock "$PY"' in shell
    assert 'touch "$OUT/DONE"' in shell and '> "$OUT/SUMMARY.txt"' in shell
    assert "trap 'exit 130' INT" in shell and "trap 'exit 143' TERM" in shell
    assert '--cycles 3 --tag adapt2' in shell and "wk_adapt_main_latest.pt" in shell
    for i in (1, 2, 3):
        assert f"wk_adapt_exp{i}_u0015.pt" in shell
    assert "--smoke" not in shell
    c = D.config_for(cfg(), "main", D.cycle_plan()[0], "decks.json", [])
    assert c["n_actors"] == 20 and c["actor_threads"] == 1 and not c["branch_gate"]

"""Plan A S1c: memory v2 = v1 + match_memory.S1C_FIELDS (model_gen ``memory: v2``; artifacts by L74/memory/s1c/fit_s1c.py).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_v2.py -q

Covers: v1 unchanged (tables + features byte for byte vs the pre-S1c commit's match_memory, also on real pro tables; the rl
config hash vs its rl_royale; the v1 encoder's state dict vs its model_gen); v2 causality randomised; incremental == offline
== features_at == rows_features (any batch); hand-made S1c values (revealed priors, plays since / need, cycle elixir, the
opponent elixir = opp_elixir_count.OppElixirCounter's, counter ready, king activation, margin + trends); the prior fit is
deterministic and the committed artifact = a refit; the lock head reloads to the same scores; v2 zero-init identity EXACT on
CPU (a tiny fv5 model on real pro rows, and CLXIII where it exists) + the loader paths."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import match_memory as M                                    # noqa: E402
from pipeline.tests.test_match_memory import DECK, GID, rand_match, rich_match, samples   # noqa: E402

PRE = "8e5fd6f"                       # the last commit before S1c: the v1 reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
MEM = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz"
DATA = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
CKPT = REPO / "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"
FIT = REPO / "scratchpad/gauntlet/L74/memory/s1c/fit_s1c.py"
V2 = "v2"
SC = {k: M.S + i for i, k in enumerate(M.S1C_FIELDS)}


def _pre(rel: str, name: str):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"git unavailable: {exc}")
    if src.returncode:
        pytest.skip(f"git show {PRE}:{rel} failed (not a git tree?)")
    mod = types.ModuleType(name)
    mod.__file__ = str(REPO / rel)
    mod.__package__ = "pipeline"
    sys.modules[name] = mod
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def _fit():
    if not FIT.is_file():
        pytest.skip("fit_s1c.py not in this tree")
    spec = importlib.util.spec_from_file_location("fit_s1c_ref", FIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def same(a, b, keys=M.MEM_KEYS):
    return all(np.asarray(a[k]).dtype == np.asarray(b[k]).dtype and np.asarray(a[k]).tobytes() == np.asarray(b[k]).tobytes()
               for k in keys)


# ------------------------------------------------------------------------------------------------------ v1 unchanged
def test_v1_tables_and_features_byte_identical_to_pre():
    P = _pre("pipeline/match_memory.py", "pipeline._mm_pre_s1c")
    deck = [GID.get(M.card_key(c), 0) for c in DECK]
    for seed in range(4):
        side, sm, plays = rich_match(500 + seed)
        new, old = M.build(side, sm, plays), P.build(side, sm, plays)
        tn, to = new.table(GID), old.table(GID)
        assert sorted(tn) == sorted(to) and same(tn, to, list(to))
        ticks = [s["tick"] for s in sm[::3]] + [10 ** 6]
        for t in ticks:
            assert same(new.features(t, GID, DECK), old.features(t, GID, DECK)), (seed, t)
            v2 = new.features(t, GID, DECK, V2)                        # v2 = v1 + appended fields, the rest identical
            assert same(v2, old.features(t, GID, DECK), [k for k in M.MEM_KEYS if k != "mem_summary"])
            assert v2["mem_summary"][:M.S].tobytes() == old.features(t, GID, DECK)["mem_summary"].tobytes()
        assert same(M.features_at(tn, ticks, deck), P.features_at(to, ticks, deck))
    assert M.empty_rows(3)["mem_summary"].shape == P.empty_rows(3)["mem_summary"].shape == (3, 54)
    if not (MEM.exists() and DATA.exists()):
        return
    from pipeline.dataset_gen import load_memory_tables
    packed, row_tab, _ = load_memory_tables(MEM)
    d = np.load(DATA)
    tick, deckc = d["tick"], d["deck_card"]
    ids = np.sort(np.random.default_rng(0).choice(len(row_tab), 3000, replace=False))
    assert same(M.rows_features(packed, row_tab, tick, deckc, ids), P.rows_features(packed, row_tab, tick, deckc, ids))


def test_v1_config_hash_and_encoder_unchanged(monkeypatch):
    import torch
    from pipeline import model_gen as MG
    from pipeline import rl_royale as RL
    PR = _pre("pipeline/rl_royale.py", "rl_royale_pre_s1c")
    for ov in ([], ["memory=v1"]):
        assert RL.config_sha(RL.load_config(YAML, ov, False)) == PR.config_sha(PR.load_config(YAML, ov, False)), ov
    v1, v2 = RL.load_config(YAML, ["memory=v1"], False), RL.load_config(YAML, ["memory=v2"], False)
    assert v2["memory"] == "v2" and RL.config_sha(v2) != RL.config_sha(v1)
    h = RL.config_sha(v2)
    monkeypatch.setattr(M, "v2_meta", lambda: {"priors_sha256": "x", "lock_head_sha256": "y"})
    assert RL.config_sha(v2) != h                            # the v2 hash carries the artifacts' bytes
    PM = _pre("pipeline/model_gen.py", "pipeline._mg_pre_s1c")
    nets = []
    for mod in (PM, MG):
        torch.manual_seed(0)
        net = mod.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=30, feature_version=5)
        net.add_memory()
        nets.append(net.state_dict())
    assert list(nets[0]) == list(nets[1]) and all(torch.equal(nets[0][k], nets[1][k]) for k in nets[0])


# ------------------------------------------------------------------------------------------------------ v2 properties
def test_v2_causality_randomised():
    """Altering or inserting any HP read, body, elixir or play at tick >= t never changes the v2 features(t)."""
    for seed in range(6):
        side, sm, plays = (rich_match if seed % 2 else rand_match)(700 + seed)
        rng = np.random.default_rng(seed)
        _, sm2, plays2 = rich_match(800 + seed)
        full = M.build(side, sm, plays)
        for t in rng.integers(50, 4200, 10):
            t = int(t)
            alt = M.build(side, [s for s in sm if s["tick"] < t] + [s for s in sm2 if s["tick"] >= t],
                          [p for p in plays if p["tick"] < t] + [p for p in plays2 if p["tick"] >= t])
            assert same(full.features(t, GID, DECK, V2), alt.features(t, GID, DECK, V2)), (seed, t)


def test_v2_incremental_equals_offline_and_rows():
    deck = np.array([GID.get(M.card_key(c), 0) for c in DECK])
    mms, n = [], 0
    for seed in range(3):
        side, sm, plays = rich_match(900 + seed)
        # v1 quirk (kept: v1 is frozen): two reports of ONE play (same tick / side / card / xy) with different ``seen`` --
        # rich_match draws such presses -- are deduplicated by build in LIST order but incrementally by arrival; listing them
        # by seen makes both keep the earliest report (seed 901 has one: tick 217, seen 254 and 228)
        plays = sorted(plays, key=lambda p: p.get("seen", p["tick"]))
        inc = M.MatchMemory(side)
        off = M.build(side, sm, plays)
        ticks = [s["tick"] for s in sm]
        got = {}
        for s in sm:
            inc.observe(**s, plays=[p for p in plays if p["tick"] <= s["tick"] and p.get("seen", p["tick"]) <= s["tick"]])
            got[s["tick"]] = inc.features(s["tick"], GID, deck, V2)
        fa = M.features_at(off.table(GID), ticks, deck, V2, GID)
        for i, t in enumerate(ticks):
            ref = off.features(t, GID, deck, V2)
            assert same(got[t], ref), (seed, t)
            assert same({k: fa[k][i] for k in M.MEM_KEYS}, ref), (seed, t)
            n += 1
        s1c = fa["mem_summary"][:, M.S:]
        assert s1c[:, M.S1C_FIELDS.index("opp_revealed_8")].max() > 0 and s1c[:, M.S1C_FIELDS.index("xb_lock_p")].min() > 0
        mms.append(off)
    assert n > 500
    packed = M.pack([m.table(GID) for m in mms])
    rng = np.random.default_rng(1)
    row_tab, row_t = rng.integers(-1, 3, 80), rng.integers(0, 4500, 80)
    ids = rng.permutation(80)[:50]
    rows = M.rows_features(packed, row_tab, row_t, np.tile(deck, (80, 1)), ids, V2, GID)
    for i, r in enumerate(ids):                                 # any batch / order / padding: the row's own match
        if row_tab[r] < 0:
            ref = M.features_at(M.MatchMemory(0).table(GID), [int(row_t[r])], deck, V2, GID)
            ref = {k: v[0] for k, v in ref.items()}
        else:
            ref = mms[row_tab[r]].features(int(row_t[r]), GID, deck, V2)
        assert same({k: rows[k][i] for k in M.MEM_KEYS}, ref), r
    assert M.empty_rows(2, V2)["mem_summary"].shape == (2, M.S_V2)


def _hand_match():
    """Side 0 = us. Theirs: Knight 100, HogRider 300, Fireball 500, Skeletons 700, Goblins 900. Our L princess -10 % at 400,
    their king -5 % at 600, our R princess falls at 800."""
    def tw(t):
        return (1.0, 1.0 if t < 400 else 0.9, 1.0 if t < 800 else 0.0, 0.95 if t >= 600 else 1.0, 1.0, 1.0)
    sm = samples(range(0, 2000, 10), towers=tw, alive=lambda t: (True, True, t < 800, True, True, True))
    plays = [dict(tick=t, side=1, card=c, form=0, x=9000, y=20000)
             for t, c in ((100, "Knight"), (300, "HogRider"), (500, "Fireball"), (700, "Skeletons"), (900, "Goblins"))]
    return M.build(0, sm, plays), plays


PRI = {"cards": {"knight": {"deck": {"lift": -0.03}, "answer": {"lift": -0.20}},
                 "hog-rider": {"deck": {"lift": 0.02}, "answer": {"lift": -0.15}},
                 "fireball": {"deck": {"lift": -0.01}, "answer": {"lift": 0.05}},
                 "skeletons": {"deck": {"lift": 0.04}, "answer": {"lift": -0.05}},
                 "goblins": {"deck": {"lift": 0.0}, "answer": {"lift": 0.0}}}}


def _s1c(m, ticks):
    tab = m.table(GID)
    E = {k: np.broadcast_to(tab[k], (len(ticks),) + tab[k].shape) for k in M.TABLE_KEYS}
    return {k: M._s1c(E, ticks, np.zeros((len(ticks), 14)), M.v2_lut(GID, PRI), None)[:, i]
            for i, k in enumerate(M.S1C_FIELDS)}


def test_v2_hand_made_values():
    from pipeline.opp_elixir_count import OppElixirCounter
    from pipeline.habit_terms import play_cost
    m, plays = _hand_match()
    f = _s1c(m, [801, 1000, 1700])
    assert f["opp_revealed_8"].tolist() == [4 / 8, 5 / 8, 5 / 8]
    assert f["deck_lift_min"][1] == pytest.approx(-0.03) and f["deck_lift_neg_sum"][1] == pytest.approx(-0.04)
    assert f["ans_lift_min"][1] == pytest.approx(-0.20) and f["ctr_known"].tolist() == [1, 1, 1]
    # 801: Knight played 3 plays ago -> 1 more play; the cheapest other slot = Skeletons (1)
    assert f["ctr_plays_4"][0] == pytest.approx(1 / 4) and f["ctr_cycle_el_10"][0] == pytest.approx(0.1)
    # 1000: Knight 4 plays ago = back in hand (elixir to cycle 0); slots by answer lift: Knight, Hog, Skeletons, Goblins, Fireball
    assert f["ctr_plays_4"][1] == 0 and f["ctr_cycle_el_10"][1] == 0
    assert [f[f"slot{i}_ans_lift"][1] for i in range(6)] == pytest.approx([-0.2, -0.15, -0.05, 0.0, 0.05, 0.0])
    assert [f[f"slot{i}_need_4"][1] for i in range(5)] == pytest.approx([0, 1 / 4, 3 / 4, 1, 2 / 4])
    assert [f[f"slot{i}_on"][1] for i in range(6)] == [1, 1, 1, 1, 1, 0]
    est = []
    for t in (801, 1000, 1700):                                # the public counter's rule on the plays before t
        c = OppElixirCounter()
        for p in plays:
            if p["tick"] < t:
                c.play(p["tick"], p["card"], play_cost(M.card_key(p["card"])))
        est.append(c.at(t))
    assert (f["opp_el_10"] * 10).tolist() == pytest.approx(est, abs=1e-9)
    assert f["ctr_ready"].tolist() == [0, float(est[1] >= 3), float(est[2] >= 3)]
    # kings: their king hit at 600 (activated), mine via the R princess falling at 800 (a princess hit alone does not)
    assert f["opp_king_on"].tolist() == [1, 1, 1] and f["opp_king_since_60"][1] == pytest.approx(400 * 0.05 / 60)
    assert f["own_king_on"].tolist() == [1, 1, 1] and f["own_king_since_60"][1] == pytest.approx(200 * 0.05 / 60)
    assert _s1c(m, [700])["own_king_on"][0] == 0 and _s1c(m, [599])["opp_king_on"][0] == 0
    # margin: theirs lost king 0.05; mine L 0.1 + R fell (1) -> princesses (0 - 1.1) / 2, kings +0.05; trends
    assert f["margin_p_2"][1] == pytest.approx(-0.55) and f["margin_k"][1] == pytest.approx(0.05)
    assert f["margin_p_d30_2"][1] == pytest.approx(-0.55) and f["margin_k_d30"][1] == pytest.approx(0.05)
    assert f["margin_p_d30_2"][2] == 0 and f["margin_p_d60_2"][2] == pytest.approx(-0.5)   # 1700: cut 500 sees L only
    assert f["margin_p_d60_2"][1] == pytest.approx(-0.55)
    g = _s1c(m, [1300])                                        # cut 700: L -0.1 and their king -0.05 before it
    assert g["margin_p_d30_2"][0] == pytest.approx(-0.5) and g["margin_k_d30"][0] == pytest.approx(0.0)
    e0 = _s1c(M.build(0, samples(range(0, 300, 10))), [250])           # no events: start 6 + regen, nothing else
    assert e0["opp_el_10"][0] * 10 == pytest.approx(min(10.0, 6.0 + 250 * 0.0178))
    assert e0["ctr_plays_4"][0] == 1 and all(v[0] == 0 for k, v in e0.items() if k not in ("opp_el_10", "ctr_plays_4"))


# ------------------------------------------------------------------------------------------------------ artifacts
def test_prior_fit_deterministic_and_artifact():
    fit = _fit()
    rng = np.random.default_rng(0)
    n, vocab = 600, ["<pad>"] + [f"c{i}" for i in range(1, 20)]
    S = dict(y=rng.integers(0, 2, n), ans=np.where(rng.random(n) < .6, rng.integers(1, 20, n), 0),
             deck=[sorted(set(rng.integers(1, 20, rng.integers(0, 8)).tolist())) for _ in range(n)])
    idx = np.arange(n)
    a = json.dumps(fit.fit_priors(S, idx, vocab), sort_keys=True, allow_nan=False)
    assert a == json.dumps(fit.fit_priors(S, rng.permutation(idx), vocab), sort_keys=True)
    few = fit.fit_priors(S, idx[:40], vocab)                       # no card reaches MIN_N: a fixed strength, still finite
    assert few["strength"] == {"deck": float(fit.MIN_N), "answer": float(fit.MIN_N)} and json.dumps(few, allow_nan=False)
    text = M.PRIORS.read_text(encoding="utf-8")
    art = json.loads(text)
    assert text == json.dumps(art, indent=1, sort_keys=True) + "\n"            # canonical: re-serialising is byte-identical
    assert all(len(s["sha256"]) == 64 for s in art["meta"]["sources"].values())
    for v in art["cards"].values():
        for view in ("deck", "answer"):
            assert v[view]["lift"] == pytest.approx(v[view]["rate"] - art["meta"]["base"], abs=2e-6)
    if not (MEM.exists() and DATA.exists()):
        return
    pp, voc, PT = fit.pro_tables()                                  # the committed artifact = a refit on the pro train X-Bows
    Sx = fit.samples(pp, PT)
    re = fit.fit_priors(Sx, np.flatnonzero(Sx["split"] == 0), voc)
    assert re["cards"] == art["cards"] and re["base"] == art["meta"]["base"]


def test_lock_head_reload_same_scores():
    h = json.loads(M.LOCK_HEAD.read_text(encoding="utf-8"))
    head = M.lock_head()
    x = np.asarray(h["check_x"])
    assert np.allclose(M.lock_p(head, x), h["check_p"], rtol=0, atol=1e-12)
    again = M.parse_lock_head(json.loads(json.dumps(h)))
    X = np.random.default_rng(0).random((64, len(M.LOCK_INPUTS)))
    assert np.array_equal(M.lock_p(head, X), M.lock_p(again, X))
    assert np.array_equal(M.lock_p(head, X[:5]), M.lock_p(head, X)[:5])            # a row's score is batch-free
    with pytest.raises(ValueError):
        M.parse_lock_head(dict(h, inputs=h["inputs"][::-1]))
    assert h["meta"]["sources"]["counter_priors_sha256"] == M.v2_meta()["priors_sha256"]


# ------------------------------------------------------------------------------------------------------ model
def _rows(n=200):
    if not DATA.exists():
        pytest.skip("the fv5 pro set is not on this host")
    from pipeline import train_memory as TM
    from pipeline.eval_gen import GenRows
    import torch
    arrs, meta = TM.npz_head(DATA, n)
    return GenRows(arrs, np.arange(len(arrs["y_gate"])), torch.device("cpu")), meta


def _random_v2(n, n_cards, rng):
    m = M.empty_rows(n, V2)
    m["mem_ev"][:] = rng.random(m["mem_ev"].shape, dtype=np.float32)
    k = rng.integers(0, M.E_MAX + 1, n)
    k[::7] = 0
    m["mem_mask"][:] = np.arange(M.E_MAX)[None] < k[:, None]
    m["mem_card"][:] = rng.integers(0, n_cards, m["mem_card"].shape)
    m["mem_form"][:] = rng.integers(0, 4, m["mem_form"].shape)
    m["mem_summary"][:] = rng.random(m["mem_summary"].shape, dtype=np.float32)
    m["mem_answer"][:] = rng.integers(0, n_cards, n)
    return m


def _outs(net, b):
    o = net(b, card=b["hand_card"][:, 0], form=b["hand_form"][:, 0])
    return {k: o[k] for k in ("gate", "card", "cell", "value")}


def test_v2_zero_init_identity_exact_cpu(tmp_path):
    import torch
    from pipeline import model_gen as MG
    rows, meta = _rows()
    nc = len(meta["card_vocab"])
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    base = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=nc, feature_version=5).eval()
    mem = copy.deepcopy(base)
    mem.add_memory(version=V2)
    assert mem.mem.version == V2 and mem.mem.summary[0].in_features == M.S_V2 + 8
    nets = [(base, mem)]
    if CKPT.exists():                                         # G-mem-0 style: CLXIII vs CLXIII + memory v2
        nets.append((MG.load_model(CKPT, torch.device("cpu"))[0].eval(),
                     MG.load_model(CKPT, torch.device("cpu"), memory=V2)[0].eval()))
    with torch.no_grad():
        for b0, b1 in nets:
            assert b1.mem.version == V2
            for s in range(0, len(rows.idx), 100):
                b = rows.batch(rows.idx[s:s + 100])
                bm = dict(b, **{k: torch.from_numpy(v) for k, v in _random_v2(len(b["gate"]), nc, rng).items()})
                r, g = _outs(b0, b), _outs(b1, bm)
                assert all(torch.equal(r[k], g[k]) for k in r)
            with torch.no_grad():                             # liveness: a nonzero output layer moves the outputs
                live = copy.deepcopy(b1)
                live.mem.out.weight.normal_(0, 0.05)
                assert float((_outs(live, bm)["gate"] - _outs(b0, b)["gate"]).abs().max()) > 1e-4
    # loader paths: weights build v2 by content (S_V2 in mem.cfg); a v1 request on v2 weights fails loudly; the artifacts
    # recorded in a v2 checkpoint must still be the current ones
    p = tmp_path / "v2.pt"
    torch.save({"gen": True, "args": {"d": 16, "layers": 1, "feature_version": 5}, "d_c": 8, "card_vocab": meta["card_vocab"],
                "memory": V2, "memory_v2": M.v2_meta(), "model": mem.state_dict()}, p)
    got = MG.load_model(p, torch.device("cpu"))[0]
    assert got.mem.version == V2 and got.mem.gid["x-bow"] == meta["card_vocab"].index("x-bow")
    with pytest.raises(RuntimeError):
        MG.load_model(p, torch.device("cpu"), memory="v1")
    st = torch.load(p, weights_only=False)
    torch.save(dict(st, memory_v2={"priors_sha256": "0" * 64, "lock_head_sha256": "0" * 64}), p)
    with pytest.raises(ValueError):
        MG.load_model(p, torch.device("cpu"))
    plain = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=nc, feature_version=5)
    plain.load_state_dict(mem.state_dict())
    assert MG.mem_version(plain) == V2 and MG.mem_version(base) is None


def test_genrows_v2_rows():
    """eval_gen.GenRows (train_memory's path) with memory_version v2 = rows_features(..., v2, gid); 'empty' = v2 zeros."""
    import torch
    rows, meta = _rows(120)
    from pipeline.dataset_gen import checkpoint_gid
    gid = checkpoint_gid(meta["card_vocab"])
    side, sm, plays = rich_match(3)
    packed = M.pack([M.build(side, sm, plays).table(gid)])
    row_tab, row_t = np.zeros(len(rows.idx), np.int64), np.asarray(rows.a["tick"])
    rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, row_t), V2, gid
    b = rows.batch(rows.idx[:40])
    ref = M.rows_features(packed, row_tab, row_t, rows.a["deck_card"], rows.idx[:40], V2, gid)
    assert all(torch.equal(b[k], torch.from_numpy(ref[k])) for k in M.MEM_KEYS) and b["mem_summary"].shape[1] == M.S_V2
    rows.memory = "empty"
    assert float(rows.batch(rows.idx[:4])["mem_summary"].abs().sum()) == 0
    assert rows.batch(rows.idx[:4])["mem_summary"].shape[1] == M.S_V2

"""W9 (10-20) exact identities (scratchpad/gauntlet/L74/identities/IDENTITIES.md): unit-vocab classes are APPENDED,
never renumbered; a checkpoint of the old 232-class vocab grows on load with byte-identical old rows and IDENTICAL
outputs; the extended live catalog names every card / form id and round-trips; a live deck with Minion Giant maps to
its own class."""
import contextlib
import copy
import hashlib
import json
import zipfile

import numpy as np
import pytest
import torch

from pipeline import vocab
from pipeline.obs_contract import REPO

CATALOG = REPO / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"
CKPT = REPO / "icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt"  # live 10-20
CKPT_RL = CKPT.with_name("rlarm_stepd_ctrl_nos2_u0130.pt")       # the same update as the RL run saved it (optimizer)
DATA = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"      # that checkpoint's IL rows
OLD_232_SHA = "8676eeffed0a838ee6f04d1ef6ff0222dbe9eda4f486857f73a3475df2e803de"   # names of ids 0..231 (commit 17cb3f3)
BALLOON = vocab.unit_id("balloon")


@contextlib.contextmanager
def old_vocab():
    """The model code as it was with the 232-class vocab (S1Model reads vocab.N_VOCAB at build AND forward time)."""
    n = vocab.N_VOCAB
    vocab.N_VOCAB = vocab.N_BASE
    try:
        yield
    finally:
        vocab.N_VOCAB = n


def test_ids_are_append_only():
    assert vocab.N_BASE == 232 and vocab.N_VOCAB == vocab.N_BASE + len(vocab.APPENDED_CLASSES)
    assert hashlib.sha256("\n".join(vocab.UNIT_VOCAB[:232]).encode()).hexdigest() == OLD_232_SHA
    assert vocab.UNIT_VOCAB[232:] == [n for n, _ in vocab.APPENDED_CLASSES]
    assert len(set(vocab.UNIT_VOCAB)) == vocab.N_VOCAB


def test_minion_giant_is_its_own_class():
    mg = vocab.unit_id("minion_giant")
    assert mg == 232 and vocab.engine_key("MinionGiant") == "minion_giant" and vocab.engine_unit_id("MinionGiant") == mg
    assert vocab.engine_unit_id("Balloon") == BALLOON != mg and vocab.kind_of(mg) == "troop"
    from pipeline import body_identity as BI
    assert BI.EXT_CLASS == {}
    with BI.extension():                          # a host whose catalog does not name 26000107 yet
        got = BI.resolve_board([(1, "26000107", 1817.0, 0, False)], {0: 1.0, 1: 1.0})
    assert vocab.UNIT_VOCAB[got[0].cls] == "minion_giant"


def test_grown_rows_map_and_refusals():
    assert vocab.grown_rows(232) == list(range(232)) + [BALLOON, 232]
    assert vocab.grown_rows(vocab.N_VOCAB) == list(range(vocab.N_VOCAB + 1))
    for bad in (0, 231, vocab.N_VOCAB + 1):
        with pytest.raises(ValueError):
            vocab.grown_rows(bad)


def _toy_batch(seed, n=6, u=12):
    from pipeline.dataset import PAST_K
    from pipeline.obs_contract import F, S
    g = torch.Generator().manual_seed(seed)
    tok = torch.rand(n, u, F, generator=g)
    tok[..., 0] = torch.randint(0, vocab.N_BASE, (n, u), generator=g).float()
    mask = torch.rand(n, u, generator=g) < 0.7
    past = torch.full((n, PAST_K, 4), -1.0)
    return tok, mask, torch.rand(n, S, generator=g), past


def test_old_s1_checkpoint_grows_identically():
    from pipeline.model_v3 import S1Model
    with old_vocab():
        torch.manual_seed(0)
        old = S1Model(d=32, layers=1).eval()
        sd = copy.deepcopy(old.state_dict())
    new = S1Model(d=32, layers=1).eval()
    new.load_state_dict(sd)
    assert sd["cls_emb.weight"].shape[0] == 233                      # the caller's dict is not modified
    w, w0 = new.cls_emb.weight.detach(), sd["cls_emb.weight"]
    assert torch.equal(w[:232], w0[:232]) and torch.equal(w[232], w0[BALLOON]) and torch.equal(w[233], w0[232])
    for k, v in sd.items():
        if k != "cls_emb.weight":
            assert torch.equal(new.state_dict()[k], v), k
    tok, mask, sc, past = _toy_batch(1)
    slot = torch.zeros(len(tok), dtype=torch.long)
    with torch.no_grad():
        with old_vocab():
            a = old(tok, mask, sc, past, card_slot=slot)
        b = new(tok, mask, sc, past, card_slot=slot)
        tok_mg = tok.clone()                                          # a balloon token in the old model ==
        tok_mg[:, 0, 0], tok[:, 0, 0] = 232.0, float(BALLOON)         # a minion_giant token in the grown one
        mask[:, 0] = True
        with old_vocab():
            c = old(tok, mask, sc, past, card_slot=slot)
        d = new(tok_mg, mask, sc, past, card_slot=slot)
    for k in a:
        assert torch.equal(a[k], b[k]) and torch.equal(c[k], d[k]), k


def test_other_shape_mismatch_is_refused():
    from pipeline.model_v3 import S1Model
    sd = S1Model(d=32, layers=1).state_dict()
    sd["cls_emb.weight"] = sd["cls_emb.weight"][:200]
    with pytest.raises(ValueError):
        S1Model(d=32, layers=1).load_state_dict(sd)
    sd = S1Model(d=32, layers=1).state_dict()
    sd["cls_emb.weight"] = torch.zeros(233, 16)                       # wrong width: torch's own size check
    with pytest.raises(RuntimeError):
        S1Model(d=32, layers=1).load_state_dict(sd)


def test_optimizer_state_grows_with_the_rows():
    from pipeline.model_v3 import S1Model, grow_optimizer_state
    with old_vocab():
        old = S1Model(d=32, layers=1)
        opt = torch.optim.Adam(old.parameters(), lr=1e-3)
        tok, mask, sc, past = _toy_batch(2)
        old(tok, mask, sc, past)["gate"].sum().backward()
        opt.step()
        osd, msd = copy.deepcopy(opt.state_dict()), copy.deepcopy(old.state_dict())
    new = S1Model(d=32, layers=1)
    new.load_state_dict(msd)
    opt2 = torch.optim.Adam(new.parameters(), lr=1e-3)
    opt2.load_state_dict(osd)
    grow_optimizer_state(opt2, new)
    st, st0 = opt2.state[new.cls_emb.weight], opt.state[old.cls_emb.weight]
    for k in ("exp_avg", "exp_avg_sq"):
        assert st[k].shape == new.cls_emb.weight.shape
        assert torch.equal(st[k][:232], st0[k][:232]) and torch.equal(st[k][233], st0[k][232])
    new(tok, mask, sc, past)["gate"].sum().backward()
    opt2.step()                                                       # runs (a 233-row exp_avg would raise here)
    grow_optimizer_state(opt2, new)                                   # matching shapes: no-op


def _head(npz, k):
    """First k rows of a dataset_gen npz, decompressing only each member's prefix (the file is ~470 MB)."""
    z = zipfile.ZipFile(npz)

    def read(name, n=None):
        with z.open(name + ".npy") as f:
            ver = np.lib.format.read_magic(f)
            shape, _, dt = (np.lib.format.read_array_header_1_0 if ver == (1, 0) else np.lib.format.read_array_header_2_0)(f)
            n = shape[0] if n is None else n
            per = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
            return np.frombuffer(f.read(n * per), dt).reshape((n, *shape[1:])).copy()
    off = read("off", k + 1)
    out = {"off": off, "tok": read("tok", int(off[-1])), "unit_form": read("unit_form", int(off[-1]))}
    for name in ("sc", "past", "y_xy", "y_hand_pos", "y_gate", "y_wait_card", "y_crowns", "hand_card", "hand_form",
                 "next_card", "next_form", "deck_card", "deck_form", "y_card", "opp_past", "opp_cycle", "projectiles",
                 "effects", "own_ability"):
        out[name] = read(name, k)
    return out


@pytest.mark.skipif(not (CKPT.exists() and DATA.exists()), reason="the live checkpoint / its IL rows are not on this host")
def test_live_checkpoint_outputs_identical_on_real_rows():
    from pipeline.model_gen import CUE_N, load_model
    from pipeline.train_gen import GenRows
    dev = torch.device("cpu")
    with old_vocab():
        old, st = load_model(CKPT, dev)
    new, _ = load_model(CKPT, dev)
    old.eval(), new.eval()
    raw = st["model"]["cls_emb.weight"]
    assert raw.shape[0] == vocab.N_BASE + 1                            # an old-vocab checkpoint
    w = new.cls_emb.weight.detach()
    assert torch.equal(w[:232], raw[:232]) and torch.equal(w[232], raw[BALLOON]) and torch.equal(w[233], raw[232])
    nsd = new.state_dict()
    for k, v in old.state_dict().items():
        if k != "cls_emb.weight":
            assert torch.equal(nsd[k], v), k
    k = 3000
    arrs = _head(DATA, k)
    has_balloon = [i for i in range(k) if (arrs["tok"][arrs["off"][i]:arrs["off"][i + 1], 0] == BALLOON).any()]
    ids = np.array(sorted(set(range(16)) | set(has_balloon[:32])))
    assert len(has_balloon) >= 8, len(has_balloon)                     # the swap check below needs real balloon tokens
    b = GenRows(arrs, np.arange(k), dev).batch(ids)
    assert int(b["tok"][..., 0][b["mask"]].max()) < vocab.N_BASE       # real rows hold old tokens only
    if getattr(new, "cue_in", None) is not None:
        b["cue"] = torch.zeros(*b["mask"].shape, CUE_N)                 # cue unknown
    with torch.no_grad():
        with old_vocab():
            a = old(b, card=b["card"], form=b["form"])
        c = new(b, card=b["card"], form=b["form"])
        bal = b["tok"][..., 0] == BALLOON
        if bal.any():                                                  # a real balloon token == the same body as minion_giant
            t = b["tok"].clone()
            t[..., 0] = torch.where(bal, torch.full_like(t[..., 0], 232.0), t[..., 0])
            d = new(dict(b, tok=t), card=b["card"], form=b["form"])
    for key in a:
        assert torch.equal(a[key], c[key]), key
        if bal.any():
            assert torch.equal(a[key], d[key]), key


@pytest.mark.skipif(not CKPT_RL.exists(), reason="the live run's resumable checkpoint is not on this host")
def test_live_run_resume_optimizer_grows():
    from pipeline.model_gen import load_model
    from pipeline.model_v3 import grow_optimizer_state
    net, st = load_model(CKPT_RL, torch.device("cpu"))
    opt = torch.optim.Adam(net.parameters(), lr=1e-4)
    opt.load_state_dict(st["rl"]["optimizer"])                        # as rl_royale._restore
    saved = opt.state[net.cls_emb.weight]["exp_avg"].clone()
    assert saved.shape[0] == vocab.N_BASE + 1
    grow_optimizer_state(opt, net)
    got = opt.state[net.cls_emb.weight]["exp_avg"]
    assert got.shape == net.cls_emb.weight.shape and torch.equal(got[:232], saved[:232]) and torch.equal(got[233], saved[232])
    for p in net.parameters():
        p.grad = torch.zeros_like(p)
    opt.step()                                                        # an un-grown 233-row exp_avg raises here


def test_checkpoint_card_vocab_stand_in():
    from pipeline.dataset_gen import CARD_STANDINS, card_key, checkpoint_gid
    cv = ["<pad>", "archers", "balloon", "knight"]
    gid = checkpoint_gid(cv)
    assert card_key("MinionGiant") == "minion-giant" and gid["minion-giant"] == gid["balloon"] == 2
    assert {k: v for k, v in gid.items() if k not in CARD_STANDINS} == {k: i for i, k in enumerate(cv)}
    assert checkpoint_gid(cv + ["minion-giant"])["minion-giant"] == 4  # a vocab that has the card keeps its own row


@pytest.mark.skipif(not CATALOG.exists(), reason="catalog not on disk")
def test_catalog_names_round_trip():
    from pipeline.obs_contract import _catalog_names, catalog_card_form
    from pipeline.public_observation import _native_ids
    cards = json.loads(CATALOG.read_text(encoding="utf-8"))["cards"]
    ids = [c[f] for c in cards for f in ("card_id", "evolution_form_id", "hero_form_id") if c.get(f) is not None]
    assert len(ids) == len(set(ids))
    for c in cards:
        for f, key in enumerate(("card_id", "evolution_form_id", "hero_form_id")):
            if c.get(key) is not None:
                assert catalog_card_form(c[key]) == (c["display_name"], f)
                assert _catalog_names()[c[key]] == c["display_name"]
                if vocab.engine_key(c["display_name"]):
                    assert _native_ids()[(vocab.engine_key(c["display_name"]), f)] in ids
    by = {c["internal_name"]: c for c in cards}
    # the four ids the live reader reported that the libg catalog lacked (raw_id_census.json), + Minion Giant
    assert (by["AngryBarbarians"]["evolution_form_id"], by["ElectroGiant"]["evolution_form_id"],
            by["ElectroWizard"]["hero_form_id"], by["IceWizard"]["hero_form_id"], by["MinionGiant"]["card_id"]) == \
           (13000043, 13000075, 203000042, 203000023, 26000107)
    ladder = [c for c in cards if c["standard_1v1"]]
    cls = [vocab.engine_unit_id(c["display_name"]) for c in ladder]
    assert None not in cls and len(set(cls)) == len(cls)              # every ladder card has its OWN class


@pytest.mark.skipif(not CATALOG.exists(), reason="catalog not on disk")
def test_live_deck_with_minion_giant():
    from pipeline.live_mem import deck_of
    from pipeline.tests.test_live_mem import FRAME
    f = copy.deepcopy(FRAME)
    me = next(p for p in f["players"] if p["deck_card_ids"])
    me["deck_card_ids"][3] = 26000107
    deck, names = deck_of(f, int(me["side"]))
    assert names[3] == "MinionGiant" and deck.cards[3] == "minion_giant" and deck.card_ids[3] == 232

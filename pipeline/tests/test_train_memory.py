"""Plan A S3: pipeline/train_memory.py (memory adapter only, the init frozen).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_train_memory.py -q

On the laptop: CLXIII (the grafted live file, the only CLXIII here), the first 1,509 rows of the fv5 pro set (replays 0-5,
replay 5 = a val replay) read as a streamed prefix, memory tables built for those 6 replays. Covers: step-0 identity (the
memory model = CLXIII) and every frozen tensor bit-identical after 20 steps (both asserted inside the trainer, re-checked
here from the saved checkpoint); the loss on a fixed small row set goes down; the training rows' memory inputs (the tables
via rows_features at the npz ticks / decks) = MatchMemory.features of the same replays (3 replays); the probes run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import match_memory as MM                                  # noqa: E402
from pipeline import train_memory as TM                                  # noqa: E402

DATA = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
CKPT = REPO / "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"
HEAD = 1509                           # the rows of replays 0-5 (dataset order)
pytestmark = pytest.mark.skipif(not (DATA.exists() and CKPT.exists()), reason="the fv5 pro set / CLXIII not on this host")


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    from pipeline.dataset_gen import memory_tables
    out = tmp_path_factory.mktemp("mem") / "mem6.npz"
    memory_tables(DATA, out, workers=1, limit=6, log=None)
    return out


def _run(tmp, tables, *extra):
    torch.set_num_threads(2)
    out = tmp / "run"
    TM.main(["--init", str(CKPT), "--memory", "v1", "--memory-tables", str(tables), "--data", str(DATA),
             "--trainable", "memory", "--out-dir", str(out), "--head-rows", str(HEAD), "--device", "cpu",
             "--val-sample", "64", "--prefetch", "2", *extra])
    return out


def test_identity_and_frozen_after_20_steps(tmp_path, tables, monkeypatch):
    """The trainer asserts both (it exits otherwise); re-checked from the saved checkpoint: every non-memory tensor = the
    init's, the memory output layer moved off zero; the probes ran (deck monkeypatched to a deck present in these rows)."""
    arrs, meta = TM.npz_head(DATA, HEAD)
    from pipeline.dataset_gen import checkpoint_gid
    gid = checkpoint_gid(meta["card_vocab"])
    inv = {v: k for k, v in gid.items()}
    val = np.flatnonzero(arrs["split"] == 1)
    monkeypatch.setattr(TM, "ICEBOW", tuple(inv[int(c)] for c in arrs["deck_card"][val[0]]))
    out = _run(tmp_path, tables, "--steps", "20", "--bs", "16", "--val-every", "20", "--ckpt-every", "1000")
    log = [json.loads(x) for x in (out / "s3_log.jsonl").read_text().splitlines()]
    assert log[0]["identity_max_diff"] == 0.0
    fin = json.loads((out / "s3_final.json").read_text())
    assert fin["steps"] == 20 and fin["frozen_tensors_unchanged"] > 100
    init = torch.load(CKPT, map_location="cpu", weights_only=False)["model"]
    got = torch.load(out / "mem_latest.pt", map_location="cpu", weights_only=False)
    assert got["memory"] == "v1" and got["s3"]["trainable"] == "memory"
    assert all(torch.equal(got["model"][k], v) for k, v in init.items())
    assert float(got["model"]["mem.out.weight"].abs().sum()) > 0
    pr = fin["probes"]
    assert pr["rows_icebow"] > 0 and "xbow_fails_0" in pr and pr["repeat_after_bad"]
    v = fin["hist"][-1]
    assert set(v) == {"step", "memory", "zeroed", "init"} and v["init"]["loss"] > 0


def test_loss_decreases_on_a_small_set(tmp_path, tables):
    """60 steps on 32 fixed train rows (no mirror, lr 3e-3): their gate + card + cell loss with memory goes down."""
    out = _run(tmp_path, tables, "--steps", "60", "--bs", "32", "--limit-rows", "32", "--lr", "3e-3", "--warmup", "1",
               "--no-mirror", "--val-every", "1000", "--ckpt-every", "1000")
    arrs, meta = TM.npz_head(DATA, HEAD)
    from pipeline.dataset_gen import load_memory_tables
    packed, row_tab, _ = load_memory_tables(tables)
    rng = np.random.default_rng(0)                       # the trainer's seeded --limit-rows draw
    tr = np.sort(rng.choice(np.flatnonzero(arrs["split"] == 0), size=32, replace=False))
    rows = TM.GenRows(arrs, tr, torch.device("cpu"))
    rows.memory, rows.grid = (packed, row_tab[:HEAD], arrs["tick"]), "lattice"
    before = TM.val_loss(TM.load_model(CKPT, torch.device("cpu"), memory="v1")[0].eval(), rows)["loss"]
    after = TM.val_loss(TM.load_model(out / "mem_latest.pt", torch.device("cpu"))[0].eval(), rows)["loss"]
    assert after < before - 0.01, (before, after)


def test_table_rows_equal_match_memory(tables):
    """The memory inputs the trainer feeds (tables -> rows_features at the npz row ticks / decks) = MatchMemory.features of
    the same replay, rebuilt from the replay file (dataset_gen.replay_memories), on every row of 3 replays."""
    from pipeline.dataset_gen import checkpoint_gid, load_memory_tables, replay_memories
    arrs, meta = TM.npz_head(DATA, HEAD)
    packed, row_tab, _ = load_memory_tables(tables)
    gid = checkpoint_gid(meta["card_vocab"])
    tags = np.load(DATA)["tags"]
    corpora = [REPO / c for c in meta["corpora"]]
    n = 0
    for r in range(3):
        path = next(p for c in corpora for p in c.glob(f"j*/replay_{tags[r]}.json"))
        tag, mems, _ = replay_memories(str(path))
        assert tag == str(tags[r])
        ids = np.flatnonzero(arrs["rep"] == r)
        got = MM.rows_features(packed, row_tab, arrs["tick"], arrs["deck_card"], ids)
        for i, row in enumerate(ids):
            ref = mems[int(arrs["side"][row])].features(int(arrs["tick"][row]), gid, arrs["deck_card"][row])
            for k in MM.MEM_KEYS:
                assert np.array_equal(got[k][i], ref[k]), (r, int(row), k)
            n += 1
    assert n > 500 and got["mem_mask"].any()

"""Contract tests for capture; root runs the frozen suite once.

The checkpoint-free fake exercises the real GenPilot decision implementation.
No test creates an optimizer, loads a checkpoint, or accesses a device reader.
"""
import copy
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline.live_gen import GenPilot
from pipeline.obs_contract import F, S

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("tested_decision_capture", HERE / "capture.py")
C = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = C
SPEC.loader.exec_module(C)

INPUT_KEYS = {
    "tok", "mask", "sc", "past", "hand_card", "hand_form", "next_card",
    "next_form", "deck_card", "deck_form", "unit_form", "opp_past",
    "own_ability", "opp_cycle", "projectiles", "effects",
}
SECRET = "PRIVATE_AND_FUTURE_SENTINEL_6f97988a"


def public_frame(tick=200):
    return {
        "game_tick": tick,
        "sample_monotonic_us": 1000000 + tick * 50000,
        "battle_active": True,
        "coherent": True,
        "players": [
            {"side": 0, "elixir_raw": SECRET, "deck_card_ids": [SECRET],
             "hand_deck_indices": [-1] * 4, "next_deck_index": SECRET},
            {"side": 1, "elixir_raw": 100000, "hand_deck_indices": [0, 1, 2, 3],
             "deck_card_ids": list(range(8)), "next_deck_index": 4},
        ],
        "entities": [dict(side=0, x=4000, y=6000, card_id=26000000,
                          hp=1000, max_hp=1000, kind=15, address="0xabc",
                          category=5000001, private_target=SECRET)],
        "projectiles": [dict(side=0, x=4500, y=6500, card_id=28000004,
                             target_x=3500, target_y=25500, time_to_impact_ms=300,
                             hidden_target=SECRET)],
        "effects": [],
        "future_actions": [SECRET],
        "secret": SECRET,
        "chain": {"battle": "0x123", "private": SECRET},
    }


def make_batch():
    out = {
        "tok": torch.zeros((1, 64, F), dtype=torch.float32),
        "mask": torch.zeros((1, 64), dtype=torch.bool),
        "sc": torch.zeros((1, S), dtype=torch.float32),
        "past": torch.zeros((1, 3, 5), dtype=torch.float32),
        "hand_card": torch.tensor([[1, 2, 3, 0]], dtype=torch.long),
        "hand_form": torch.tensor([[0, 2, 0, 3]], dtype=torch.long),
        "next_card": torch.tensor([4], dtype=torch.long),
        "next_form": torch.tensor([0], dtype=torch.long),
        "deck_card": torch.tensor([[1, 2, 3, 4, 5, 6, 7, 0]], dtype=torch.long),
        "deck_form": torch.tensor([[0, 2, 0, 0, 0, 0, 0, 3]], dtype=torch.long),
        "unit_form": torch.zeros((1, 64), dtype=torch.long),
        "opp_past": torch.zeros((1, 3, 5), dtype=torch.float32),
        "own_ability": torch.zeros((1, 8, 7), dtype=torch.float32),
        "opp_cycle": torch.zeros((1, 8, 4), dtype=torch.float32),
        "projectiles": torch.zeros((1, 64, 8), dtype=torch.float32),
        "effects": torch.zeros((1, 32, 6), dtype=torch.float32),
    }
    out["mask"][0, 0] = True
    out["tok"][0, 0, 0] = 1
    out["sc"][0, 0] = -0.0
    assert set(out) == INPUT_KEYS
    return out


class PolicyFailure(RuntimeError):
    pass


class FakeModel(torch.nn.Module):
    def __init__(self, gate=2.0, fail_call=None):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.tensor(0.25, dtype=torch.float32))
        self.gate = gate
        self.calls = 0
        self.fail_call = fail_call
        self.outputs = []

    def forward(self, batch, card=None, form=None):
        self.calls += 1
        if self.calls == self.fail_call:
            raise PolicyFailure("original policy failure")
        out = {
            "gate": torch.tensor([self.gate], dtype=torch.float32),
            "value": self.anchor.reshape(1, 1) + 1,
            "card": torch.tensor([[0.5, 3.0, 2.0, -float("inf")]], dtype=torch.float32),
            "wait": torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, -float("inf")]], dtype=torch.float32),
            "g": torch.arange(8, dtype=torch.float32).reshape(1, 8),
        }
        if card is not None:
            assert form is not None
            out["cell"] = torch.zeros((1, 2304), dtype=torch.float32)
            out["cell"][0, 37] = 5.0
        self.outputs.append(out)
        return out


class FakePilot(GenPilot):
    def __init__(self, gate=2.0, elixir=10, fail_call=None, row_failure=False):
        self.model = FakeModel(gate, fail_call).eval()
        self.dev = torch.device("cpu")
        self.feature_version = 4
        self.grid, self.gate_tau = "lattice", 0.35
        self.gid = {"<pad>": 0, **{f"card_{i}": i for i in range(1, 8)}}
        self.ext_h, self.use_counter = 26, True
        self.match_index, self.match_seed = 0, 123
        self.batch = make_batch()
        self.elixir = elixir
        self.row_calls = 0
        self.decide_calls = 0
        self.row_failure = row_failure
        self.bs = SimpleNamespace(t_sec=11.3, my_elixir=float(elixir), opp_elixir=5.25)

    def row(self, frame):
        self.row_calls += 1
        if self.row_failure:
            raise PolicyFailure("original row failure")
        return self.batch, {
            "bs": self.bs,
            "hand": [(1, 0), (2, 2), (3, 0), (0, 3)],
            "hand_deck_indices": [0, 1, 2, -1],
            "names": [f"Card{i}" for i in range(1, 9)],
            "costs": [2.0, 3.0, 4.0, 0.0],
            "el_int": self.elixir,
            "hidden_row_field": SECRET,
        }

    def decide(self, frame):
        self.decide_calls += 1
        return super().decide(frame)


@pytest.fixture
def manifest():
    # Keep this explicit: unrecognized nested manifest fields must never leak.
    return {
        "schema": 1,
        "checkpoint_path": "fixtures/checkpoint.pt",
        "checkpoint_sha256": "1" * 64,
        "sources": {"fixture.py": "2" * 64},
        "settings": {"feature_version": 4, "model_eval": True},
        "environment": {"device": "cpu"},
        "capture_id": "capture-fixture-20261006",
    }


def store(tmp_path, manifest, **limits):
    return C.CaptureStore(tmp_path / "capture", manifest, **limits)


def records(tmp_path):
    return sorted((tmp_path / "capture").glob("*.npz"))


def saved(tmp_path, manifest, index=0):
    return C.load_record(records(tmp_path)[index], manifest)


def assert_bytes(actual, expected):
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert actual.tobytes(order="C") == expected.tobytes(order="C")


def assert_restored(pilot, original_row, original_hooks, instance_row=None):
    assert pilot.row == original_row
    if instance_row is None:
        assert "row" not in pilot.__dict__
    else:
        assert pilot.__dict__["row"] is instance_row
    assert dict(pilot.model._forward_hooks) == original_hooks
    assert not pilot.model._forward_pre_hooks


@pytest.mark.parametrize("gate,elixir,nforwards,playing", [(2.0, 10, 2, True), (-4.0, 10, 2, False), (2.0, 0, 1, False)])
def test_real_decision_forward_contract(tmp_path, manifest, gate, elixir, nforwards, playing):
    reference = FakePilot(gate, elixir)
    expected = reference.decide(public_frame())
    pilot = FakePilot(gate, elixir)
    hooks, original_row = dict(pilot.model._forward_hooks), pilot.row
    weights = {k: v.detach().clone() for k, v in pilot.model.state_dict().items()}
    before = {k: v.clone() for k, v in pilot.batch.items()}
    rng = torch.random.get_rng_state().clone()
    capture = store(tmp_path, manifest)
    actual = capture.decide(pilot, public_frame())
    assert actual == expected and actual["play"] is playing
    assert pilot.decide_calls == pilot.row_calls == 1
    assert pilot.model.calls == nforwards
    assert capture.count == 1 and not capture.disabled_reason
    assert_restored(pilot, original_row, hooks)
    assert torch.equal(torch.random.get_rng_state(), rng)
    assert all(torch.equal(pilot.batch[k], v) for k, v in before.items())
    assert all(torch.equal(pilot.model.state_dict()[k], v) for k, v in weights.items())
    assert all(p.grad is None for p in pilot.model.parameters())
    meta, arrays = saved(tmp_path, manifest)
    assert len(meta["forwards"]) == nforwards
    for invocation in range(nforwards):
        for key, tensor in pilot.batch.items():
            value = arrays[f"f{invocation}__input__{key}"]
            assert_bytes(value, tensor.numpy())
        for key, tensor in pilot.model.outputs[invocation].items():
            assert_bytes(arrays[f"f{invocation}__output__{key}"], tensor.detach().numpy())
    assert np.isneginf(arrays["f0__output__card"][0, 3])
    assert np.isneginf(arrays["f0__output__wait"][0, 7])
    assert np.signbit(arrays["f0__input__sc"][0, 0])
    assert "f0__kwarg__card" not in arrays
    if nforwards == 2:
        assert_bytes(arrays["f1__kwarg__card"], np.asarray([actual["card"]], dtype=np.int64))
        assert_bytes(arrays["f1__kwarg__form"], np.asarray([actual["form"]], dtype=np.int64))
        assert "xy" in actual
    else:
        assert actual["no_affordable"] and "xy" not in actual


def test_copies_do_not_alias_live_storage(tmp_path, manifest):
    pilot = FakePilot()
    capture = store(tmp_path, manifest)
    capture.decide(pilot, public_frame())
    _, expected = saved(tmp_path, manifest)
    with torch.no_grad():
        for tensor in pilot.batch.values():
            tensor.fill_(0)
        for output in pilot.model.outputs:
            for tensor in output.values():
                tensor.fill_(99)
    _, after = saved(tmp_path, manifest)
    for key, value in expected.items():
        assert_bytes(after[key], value)


def test_first_forward_snapshot_survives_second_forward_buffer_reuse(tmp_path, manifest):
    class ReusingModel(FakeModel):
        def __init__(self):
            super().__init__()
            self.shared_gate = torch.empty(1, dtype=torch.float32)

        def forward(self, *args, **kwargs):
            result = super().forward(*args, **kwargs)
            self.shared_gate.fill_(float(self.calls + 1))
            result["gate"] = self.shared_gate
            return result

    pilot = FakePilot()
    pilot.model = ReusingModel().eval()
    capture = store(tmp_path, manifest)
    actual = capture.decide(pilot, public_frame())
    assert actual["p_play"] == float(torch.sigmoid(torch.tensor(2.0, dtype=torch.float32)))
    _, arrays = saved(tmp_path, manifest)
    assert_bytes(arrays["f0__output__gate"], np.array([2.0], dtype=np.float32))
    assert_bytes(arrays["f1__output__gate"], np.array([3.0], dtype=np.float32))


def test_only_wrapped_decisions_are_captured_and_existing_hooks_survive(tmp_path, manifest):
    pilot = FakePilot()
    observed = []
    prehandle = pilot.model.register_forward_pre_hook(lambda module, args: observed.append(("pre", module.calls + 1)))
    handle = pilot.model.register_forward_hook(lambda module, args, output: observed.append(("post", module.calls)))
    try:
        original_prehooks = dict(pilot.model._forward_pre_hooks)
        original_hooks = dict(pilot.model._forward_hooks)
        pilot.decide(public_frame(180))
        pilot.decide(public_frame(190))
        capture = store(tmp_path, manifest)
        capture.decide(pilot, public_frame(200))
        assert capture.count == 1 and len(records(tmp_path)) == 1
        pilot.decide(public_frame(210))
        assert observed == [(kind, call) for call in range(1, 9) for kind in ("pre", "post")]
        assert dict(pilot.model._forward_pre_hooks) == original_prehooks
        assert dict(pilot.model._forward_hooks) == original_hooks
        assert capture.count == 1 and len(records(tmp_path)) == 1
    finally:
        handle.remove()
        prehandle.remove()


def test_existing_instance_row_shadow_restored_exactly(tmp_path, manifest):
    pilot = FakePilot()
    class_row = pilot.row
    shadow = lambda frame: class_row(frame)
    pilot.row = shadow
    hooks = dict(pilot.model._forward_hooks)
    capture = store(tmp_path, manifest)
    capture.decide(pilot, public_frame())
    assert capture.count == 1
    assert_restored(pilot, shadow, hooks, instance_row=shadow)


@pytest.mark.parametrize("row_failure,fail_call", [(True, None), (False, 1), (False, 2)])
def test_original_exceptions_propagate_and_cleanup(tmp_path, manifest, row_failure, fail_call):
    pilot = FakePilot(row_failure=row_failure, fail_call=fail_call)
    hooks, original_row = dict(pilot.model._forward_hooks), pilot.row
    capture = store(tmp_path, manifest)
    with pytest.raises(PolicyFailure, match="original"):
        capture.decide(pilot, public_frame())
    assert_restored(pilot, original_row, hooks)
    assert capture.count == 0 and records(tmp_path) == []


def test_io_failure_disables_capture_and_preserves_policy(tmp_path, manifest, monkeypatch):
    capture = store(tmp_path, manifest)
    pilot = FakePilot()
    expected = FakePilot().decide(public_frame())
    commits = []
    def fail(*args, **kwargs):
        commits.append(1)
        raise OSError("synthetic storage failure " + SECRET)
    monkeypatch.setattr(capture, "_commit", fail)
    original_row, hooks = pilot.row, dict(pilot.model._forward_hooks)
    assert capture.decide(pilot, public_frame()) == expected
    assert capture.disabled_reason and capture.count == 0
    assert SECRET not in capture.disabled_reason
    assert capture.decide(pilot, public_frame(210)) == expected
    assert pilot.decide_calls == 2 and pilot.model.calls == 4 and commits == [1]
    assert_restored(pilot, original_row, hooks)
    for path in (tmp_path / "capture").iterdir():
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes()


def test_index_commit_failure_keeps_record_uncommitted(tmp_path, manifest, monkeypatch):
    capture = store(tmp_path, manifest)
    pilot = FakePilot()
    original_replace = C.os.replace
    def fail_index(source, destination):
        if Path(destination).name == "index.json":
            raise OSError("synthetic index failure " + SECRET)
        return original_replace(source, destination)
    monkeypatch.setattr(C.os, "replace", fail_index)
    assert capture.decide(pilot, public_frame()) == FakePilot().decide(public_frame())
    assert capture.count == 0 and capture.disabled_reason
    incomplete = records(tmp_path)
    assert len(incomplete) <= 1
    for record in incomplete:
        with pytest.raises(C.CaptureError):
            C.load_record(record, manifest)
    assert json.loads((tmp_path / "capture" / "index.json").read_text())["records"] == []
    assert not list((tmp_path / "capture").glob("*.tmp"))
    capture.decide(pilot, public_frame(210))
    assert pilot.model.calls == 4 and records(tmp_path) == incomplete
    assert SECRET not in capture.disabled_reason


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_incomplete_or_unrecognized_model_input_disables_only_capture(tmp_path, manifest, mutation):
    pilot = FakePilot()
    if mutation == "missing":
        del pilot.batch["effects"]
    else:
        pilot.batch["opponent_hidden_hand"] = torch.ones(1, 4)
    expected = FakePilot().decide(public_frame())
    capture = store(tmp_path, manifest)
    assert capture.decide(pilot, public_frame()) == expected
    assert capture.disabled_reason and capture.count == 0 and records(tmp_path) == []
    assert pilot.model.calls == 2 and pilot.decide_calls == 1


@pytest.mark.parametrize("mutation", ["missing_unused_head", "extra_head"])
def test_unqualified_output_schema_disables_only_capture(tmp_path, manifest, monkeypatch, mutation):
    pilot = FakePilot()
    original_forward = pilot.model.forward
    def altered(*args, **kwargs):
        result = original_forward(*args, **kwargs)
        if mutation == "missing_unused_head":
            del result["wait"]
        else:
            result["hidden_future_head"] = torch.ones(1)
        return result
    monkeypatch.setattr(pilot.model, "forward", altered)
    capture = store(tmp_path, manifest)
    assert capture.decide(pilot, public_frame()) == FakePilot().decide(public_frame())
    assert capture.disabled_reason and capture.count == 0 and records(tmp_path) == []
    assert pilot.model.calls == 2 and pilot.decide_calls == 1


def test_private_and_future_values_never_serialized(tmp_path, manifest):
    capture = store(tmp_path, manifest)
    capture.decide(FakePilot(), public_frame())
    meta, arrays = saved(tmp_path, manifest)
    assert SECRET not in json.dumps(meta)
    assert all(a.dtype.kind not in "OUS" for a in arrays.values())
    for path in (tmp_path / "capture").iterdir():
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes()


def test_record_cap_spans_matches(tmp_path, manifest):
    capture = store(tmp_path, manifest, max_records=2)
    pilot = FakePilot()
    for match_index in range(5):
        pilot.match_index = match_index
        capture.decide(pilot, public_frame(200 + match_index))
    assert pilot.decide_calls == 5 and pilot.model.calls == 10
    assert capture.count == 2 and len(records(tmp_path)) == 2


def test_byte_cap_cannot_commit_an_oversized_record(tmp_path, manifest):
    capture = store(tmp_path, manifest, max_bytes=1024)
    pilot = FakePilot()
    capture.decide(pilot, public_frame())
    assert pilot.model.calls == 2 and pilot.decide_calls == 1
    assert capture.count == 0 and records(tmp_path) == []
    assert capture.disabled_reason


def test_directory_is_exclusive(tmp_path, manifest):
    capture = store(tmp_path, manifest)
    capture.decide(FakePilot(), public_frame())
    before = {p.name: p.read_bytes() for p in (tmp_path / "capture").iterdir() if p.is_file()}
    with pytest.raises((FileExistsError, C.CaptureError)):
        store(tmp_path, manifest)
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "capture").iterdir() if p.is_file()}


@pytest.mark.parametrize("kind", ["checkpoint", "source", "schema", "settings", "environment"])
def test_loader_rejects_wrong_expected_binding(tmp_path, manifest, kind):
    capture = store(tmp_path, manifest)
    capture.decide(FakePilot(), public_frame())
    wrong = copy.deepcopy(manifest)
    if kind == "checkpoint":
        wrong["checkpoint_sha256"] = "f" * 64
    elif kind == "source":
        wrong["sources"]["fixture.py"] = "f" * 64
    elif kind == "schema":
        wrong["schema"] = 99
    else:
        wrong[kind]["unexpected"] = "altered"
    with pytest.raises(C.CaptureError):
        C.load_record(records(tmp_path)[0], wrong)


@pytest.mark.parametrize("kind", ["truncate", "byte", "uncommitted"])
def test_loader_rejects_damaged_or_uncommitted_record(tmp_path, manifest, kind):
    capture = store(tmp_path, manifest)
    capture.decide(FakePilot(), public_frame())
    path = records(tmp_path)[0]
    data = path.read_bytes()
    if kind == "truncate":
        path.write_bytes(data[:len(data) // 2])
    elif kind == "byte":
        altered = bytearray(data)
        altered[len(altered) // 2] ^= 1
        path.write_bytes(altered)
    else:
        path = path.with_name("uncommitted.npz")
        path.write_bytes(data)
    with pytest.raises(C.CaptureError):
        C.load_record(path, manifest)


def rewrite_with_consistent_checksums(path, meta, arrays):
    """Reach semantic validation without an earlier digest failure masking it."""
    def encoded(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode()
    meta["arrays"] = {
        key: {"dtype": value.dtype.str, "shape": list(value.shape),
              "sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest()}
        for key, value in arrays.items()
    }
    stream = io.BytesIO()
    np.savez(stream, **arrays, __metadata__=np.frombuffer(encoded(meta), dtype=np.uint8))
    payload = stream.getvalue()
    path.write_bytes(payload)
    index_path = path.parent / "index.json"
    index = json.loads(index_path.read_text())
    entry = next(item for item in index["records"] if item["file"] == path.name)
    entry["bytes"] = len(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    index_path.write_bytes(encoded(index))


@pytest.mark.parametrize("kind", [
    "nested_row_name", "extra_row_private", "short_hand", "nested_tick",
    "missing_tick", "extra_frame_private", "input_shape", "input_dtype",
    "conditioning_dtype", "gate_shape", "card_shape", "nonpadding_negative_inf",
])
def test_loader_semantics_reject_corruption_with_consistent_hashes(tmp_path, manifest, kind):
    capture = store(tmp_path, manifest)
    capture.decide(FakePilot(), public_frame())
    path = records(tmp_path)[0]
    meta, arrays = C.load_record(path, manifest)
    if kind == "nested_row_name":
        meta["row"]["names"][0] = {"private": SECRET}
    elif kind == "extra_row_private":
        meta["row"]["private"] = SECRET
    elif kind == "short_hand":
        meta["row"]["hand"] = meta["row"]["hand"][:3]
    elif kind == "nested_tick":
        meta["frame"]["raw_tick"] = {"private": SECRET}
    elif kind == "missing_tick":
        del meta["frame"]["raw_tick"]
    elif kind == "extra_frame_private":
        meta["frame"]["private"] = SECRET
    elif kind == "input_shape":
        arrays["f0__input__hand_card"] = arrays["f0__input__hand_card"].reshape(4)
    elif kind == "input_dtype":
        arrays["f0__input__sc"] = arrays["f0__input__sc"].astype(np.float64)
    elif kind == "conditioning_dtype":
        arrays["f1__kwarg__card"] = arrays["f1__kwarg__card"].astype(np.int32)
    elif kind == "gate_shape":
        arrays["f0__output__gate"] = arrays["f0__output__gate"].reshape(1, 1)
    elif kind == "card_shape":
        arrays["f0__output__card"] = np.zeros((1, 5), dtype=np.float32)
    else:
        arrays["f0__output__card"][0, 0] = -np.inf
    rewrite_with_consistent_checksums(path, meta, arrays)
    with pytest.raises(C.CaptureError):
        C.load_record(path, manifest)

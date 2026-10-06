"""New bounded-writer tests only; frozen synchronous tests are not collected.

All inference exercised here uses the original checkpoint-free FakePilot. Root
registers and runs this file after source review. Writer races use Events.
"""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
import threading

import pytest
import torch

HERE = Path(__file__).resolve().parent


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


F = import_file("frozen_capture_fake_fixtures", HERE.parent / "decision_capture" / "test_capture.py")
A = import_file("tested_async_capture", HERE / "async_capture.py")


@pytest.fixture
def manifest():
    return {
        "schema": 1,
        "checkpoint_path": "fixtures/checkpoint.pt",
        "checkpoint_sha256": "1" * 64,
        "sources": {"fixture.py": "2" * 64},
        "settings": {"feature_version": 4, "model_eval": True},
        "environment": {"device": "cpu"},
        "capture_id": "async-fixture-20261006",
    }


def make_store(tmp_path, manifest, **limits):
    return A.AsyncCaptureStore(tmp_path / "capture", manifest, **limits)


def records(tmp_path):
    return sorted((tmp_path / "capture").glob("*.npz"))


def load_all(tmp_path, manifest):
    return [F.C.load_record(path, manifest) for path in records(tmp_path)]


@contextmanager
def blocked_writer(capture, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = capture._write_record
    def blocked(meta, arrays):
        entered.set()
        if not release.wait(10):
            raise RuntimeError("test writer release guard expired")
        return original(meta, arrays)
    monkeypatch.setattr(capture, "_write_record", blocked)
    try:
        yield entered, release
    finally:
        release.set()
        capture.close(timeout=5)


def assert_committed(capture, tmp_path, manifest, expected_count):
    status = capture.flush(timeout=5)
    assert status["complete"] and status["pending"] == 0
    assert status["submitted"] == expected_count
    assert status["committed"] == expected_count
    assert capture.count == capture.committed_count == expected_count
    loaded = load_all(tmp_path, manifest)
    assert len(loaded) == expected_count
    assert [meta["record_id"] for meta, _ in loaded] == list(range(expected_count))
    return loaded


@pytest.mark.parametrize("gate,elixir,nforwards", [(2.0, 10, 2), (-4.0, 10, 2), (2.0, 0, 1)])
def test_async_submission_preserves_actual_decision_and_forward_calls(tmp_path, manifest, gate, elixir, nforwards):
    expected = F.FakePilot(gate, elixir).decide(F.public_frame())
    pilot = F.FakePilot(gate, elixir)
    capture = make_store(tmp_path, manifest)
    try:
        actual = capture.decide(pilot, F.public_frame())
        assert actual == expected
        assert pilot.decide_calls == pilot.row_calls == 1
        assert pilot.model.calls == nforwards
        [(meta, arrays)] = assert_committed(capture, tmp_path, manifest, 1)
        assert len(meta["forwards"]) == nforwards
        for index, heads in enumerate(pilot.model.outputs):
            for key, tensor in heads.items():
                F.assert_bytes(arrays[f"f{index}__output__{key}"], tensor.detach().numpy())
        assert not pilot.model._forward_hooks and not pilot.model._forward_pre_hooks
        assert "row" not in pilot.__dict__
    finally:
        result = capture.close(timeout=5)
        assert not result["writer_alive"]


def test_queue_is_two_waiting_plus_one_writer_and_overflow_preserves_policy(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    with blocked_writer(capture, monkeypatch) as (entered, release):
        capture.decide(pilot, F.public_frame(200))
        assert entered.wait(5)
        assert capture.count == 1 and capture.committed_count == 0
        capture.decide(pilot, F.public_frame(210))
        capture.decide(pilot, F.public_frame(220))
        assert capture.count == 3 and capture.committed_count == 0
        expected = F.FakePilot().decide(F.public_frame(230))
        assert capture.decide(pilot, F.public_frame(230)) == expected
        assert capture.disabled_reason and capture.count == 3
        assert pilot.decide_calls == 4 and pilot.model.calls == 8
        assert capture.flush(timeout=0)["pending"] == 3
        release.set()
        loaded = assert_committed(capture, tmp_path, manifest, 3)
        assert [meta["frame"]["raw_tick"] for meta, _ in loaded] == [200, 210, 220]


def test_snapshots_remain_immutable_while_waiting_for_writer(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    frame = F.public_frame()
    _, info = pilot.row(frame)
    row = lambda value: (pilot.batch, info)
    pilot.row = row
    initial_batch = {key: tensor.numpy().copy() for key, tensor in pilot.batch.items()}
    with blocked_writer(capture, monkeypatch) as (entered, release):
        capture.decide(pilot, frame)
        assert entered.wait(5)
        initial_heads = [{key: tensor.detach().numpy().copy() for key, tensor in heads.items()}
                         for heads in pilot.model.outputs]
        with torch.no_grad():
            for tensor in pilot.batch.values():
                tensor.fill_(0)
            for heads in pilot.model.outputs:
                for tensor in heads.values():
                    tensor.fill_(89)
        info["costs"][0] = 999
        info["names"][0] = F.SECRET
        info["bs"].my_elixir = 99
        frame["game_tick"] = 99999
        frame["entities"][0]["hp"] = 1
        release.set()
        [(meta, arrays)] = assert_committed(capture, tmp_path, manifest, 1)
        assert pilot.__dict__["row"] is row
        assert meta["row"]["costs"][0] == 2.0 and meta["row"]["my_elixir"] == 10.0
        assert meta["frame"]["raw_tick"] == 200 and meta["frame"]["raw_bodies"][0]["hp"] == 1000
        assert F.SECRET not in json.dumps(meta)
        for index, heads in enumerate(initial_heads):
            for key, value in initial_batch.items():
                F.assert_bytes(arrays[f"f{index}__input__{key}"], value)
            for key, value in heads.items():
                F.assert_bytes(arrays[f"f{index}__output__{key}"], value)


def test_ids_monotonic_across_matches_and_fast_writer(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    original_write = capture._write_record
    writer_threads = []
    def observe_writer(meta, arrays):
        writer_threads.append(threading.current_thread())
        return original_write(meta, arrays)
    monkeypatch.setattr(capture, "_write_record", observe_writer)
    try:
        for index in range(8):
            pilot.match_index = index // 2
            capture.decide(pilot, F.public_frame(200 + index))
            # Controlled draining tests fast completion without queue-overflow noise.
            assert capture.flush(timeout=5)["ok"]
        loaded = assert_committed(capture, tmp_path, manifest, 8)
        assert [meta["frame"]["match_index"] for meta, _ in loaded] == [i // 2 for i in range(8)]
        assert pilot.decide_calls == 8 and pilot.model.calls == 16
        assert len(writer_threads) == 8 and len(set(writer_threads)) == 1
        assert writer_threads[0] is not threading.current_thread() and writer_threads[0].daemon
    finally:
        assert not capture.close(timeout=5)["writer_alive"]
    assert not writer_threads[0].is_alive()


def test_record_cap_reserves_unwritten_records(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest, max_records=2)
    pilot = F.FakePilot()
    with blocked_writer(capture, monkeypatch) as (entered, release):
        capture.decide(pilot, F.public_frame(200))
        assert entered.wait(5)
        capture.decide(pilot, F.public_frame(210))
        assert capture.count == 2 and capture.committed_count == 0
        pilot.match_index = 1
        capture.decide(pilot, F.public_frame(220))
        assert capture.count == 2 and capture.disabled_reason
        assert pilot.decide_calls == 3 and pilot.model.calls == 6
        release.set()
        assert_committed(capture, tmp_path, manifest, 2)


def test_byte_reservations_include_pending_record(tmp_path, manifest, monkeypatch):
    # Registered estimate includes 1MiB metadata, archive overhead and index.
    # This admits one small fake record while two concurrent reservations exceed it.
    cap = 2 * 1024 * 1024
    capture = make_store(tmp_path, manifest, max_bytes=cap)
    pilot = F.FakePilot()
    with blocked_writer(capture, monkeypatch) as (entered, release):
        capture.decide(pilot, F.public_frame(200))
        assert entered.wait(5)
        assert capture.count == 1 and capture.committed_count == 0
        reserved = capture.reserved_bytes
        assert 1024 * 1024 < reserved <= cap
        capture.decide(pilot, F.public_frame(210))
        assert capture.count == 1 and capture.reserved_bytes == reserved
        assert capture.disabled_reason and pilot.model.calls == 4
        release.set()
        assert_committed(capture, tmp_path, manifest, 1)
        assert sum(path.stat().st_size for path in (tmp_path / "capture").iterdir() if path.is_file()) <= cap


def test_writer_error_preserves_committed_prefix_and_future_policy(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    entered, release = threading.Event(), threading.Event()
    try:
        capture.decide(pilot, F.public_frame(200))
        assert capture.flush(timeout=5)["ok"]
        original_bytes = records(tmp_path)[0].read_bytes()
        writes = []
        def fail(meta, arrays):
            writes.append(meta["record_id"])
            entered.set()
            if not release.wait(10):
                raise RuntimeError("test writer release guard expired")
            raise OSError("writer failed " + F.SECRET)
        monkeypatch.setattr(capture, "_write_record", fail)
        capture.decide(pilot, F.public_frame(210))
        assert entered.wait(5)
        capture.decide(pilot, F.public_frame(220))
        assert capture.count == 3 and capture.committed_count == 1
        release.set()
        state = capture.flush(timeout=5)
        assert state["complete"] and not state["ok"] and state["writer_failed"]
        assert state["submitted"] == 3 and state["committed"] == 1 and state["pending"] == 0
        assert state["excluded_ids"] == [1, 2]
        assert capture.disabled_reason and F.SECRET not in capture.disabled_reason
        expected = F.FakePilot().decide(F.public_frame(230))
        assert capture.decide(pilot, F.public_frame(230)) == expected
        assert capture.count == 3 and writes == [1]
        assert pilot.decide_calls == 4 and pilot.model.calls == 8
        assert records(tmp_path)[0].read_bytes() == original_bytes
        [(meta, arrays)] = load_all(tmp_path, manifest)
        assert meta["record_id"] == 0
        for path in (tmp_path / "capture").iterdir():
            if path.is_file():
                assert F.SECRET.encode() not in path.read_bytes()
    finally:
        release.set()
        assert not capture.close(timeout=5)["writer_alive"]


def test_writer_partial_index_failure_leaves_no_false_committed_record(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    try:
        capture.decide(pilot, F.public_frame(200))
        assert capture.flush(timeout=5)["ok"]
        first = records(tmp_path)[0]
        first_bytes = first.read_bytes()
        original_replace = A._BASE.os.replace
        def fail_index(source, destination):
            if Path(destination).name == "index.json":
                raise OSError("writer index failure " + F.SECRET)
            return original_replace(source, destination)
        monkeypatch.setattr(A._BASE.os, "replace", fail_index)
        capture.decide(pilot, F.public_frame(210))
        state = capture.flush(timeout=5)
        assert state["complete"] and state["writer_failed"] and not state["ok"]
        assert state["submitted"] == 2 and state["committed"] == 1 and state["excluded_ids"] == [1]
        assert first.read_bytes() == first_bytes
        assert A.load_record(first, manifest)[0]["record_id"] == 0
        index = json.loads((tmp_path / "capture" / "index.json").read_text())
        assert [entry["record_id"] for entry in index["records"]] == [0]
        for path in records(tmp_path):
            if path != first:
                with pytest.raises(A.CaptureError):
                    A.load_record(path, manifest)
        assert not list((tmp_path / "capture").glob("*.tmp"))
        previous = records(tmp_path)
        capture.decide(pilot, F.public_frame(220))
        assert pilot.decide_calls == 3 and pilot.model.calls == 6
        assert capture.count == 2 and records(tmp_path) == previous
    finally:
        assert not capture.close(timeout=5)["writer_alive"]


def test_flush_timeout_and_close_while_full_are_bounded_and_idempotent(tmp_path, manifest, monkeypatch):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot()
    with blocked_writer(capture, monkeypatch) as (entered, release):
        capture.decide(pilot, F.public_frame(200))
        assert entered.wait(5)
        capture.decide(pilot, F.public_frame(210))
        capture.decide(pilot, F.public_frame(220))
        state = capture.flush(timeout=0)
        assert not state["complete"] and state["pending"] == 3
        closing = capture.close(timeout=0)
        assert closing["writer_alive"] and not closing["complete"]
        # A close request permanently stops admission, even while the worker drains.
        assert capture.decide(pilot, F.public_frame(230)) == F.FakePilot().decide(F.public_frame(230))
        assert capture.count == 3 and pilot.decide_calls == 4
        release.set()
        closed = capture.close(timeout=5)
        assert closed["complete"] and closed["closed"] and not closed["writer_alive"]
        assert closed["submitted"] == closed["committed"] == 3
        again = capture.close(timeout=0)
        assert again["complete"] and again["closed"] and not again["writer_alive"]
        assert again["submitted"] == again["committed"] == 3
        assert len(load_all(tmp_path, manifest)) == 3


def test_policy_failure_does_not_enqueue_partial_record_or_hide_exception(tmp_path, manifest):
    capture = make_store(tmp_path, manifest)
    pilot = F.FakePilot(fail_call=2)
    try:
        with pytest.raises(F.PolicyFailure, match="original"):
            capture.decide(pilot, F.public_frame())
        state = capture.flush(timeout=5)
        assert state["pending"] == 0 and state["submitted"] == state["committed"] == 0
        assert not records(tmp_path)
        assert not pilot.model._forward_hooks and not pilot.model._forward_pre_hooks
        assert "row" not in pilot.__dict__
    finally:
        assert not capture.close(timeout=5)["writer_alive"]

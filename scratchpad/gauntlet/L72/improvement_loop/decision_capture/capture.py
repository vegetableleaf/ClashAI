"""Bounded capture around the actual public CPU feature4 decision.

Numeric NPZ arrays are named ``f0__input__tok`` (all INPUT_KEYS),
``f0__kwarg__card`` / ``f0__kwarg__form`` when supplied, and
``f0__output__gate`` (every returned head). Later forwards use f1, etc.
``__metadata__`` is a uint8 UTF-8 canonical JSON array. The metadata's
``forwards`` entries list input/kwarg/output keys and null kwargs; its ``arrays``
table binds dtype, shape and SHA256 of contiguous value bytes. load_record
returns (metadata, numeric_arrays), excluding __metadata__.

The caller computes source/checkpoint hashes once when constructing manifest.
This module binds that immutable manifest; it never rereads a checkpoint during
a decision. No unrestricted frame, BoardState, decision or public_audit is saved.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import zipfile

import numpy as np
import torch

SCHEMA = 1
INPUT_KEYS = ("tok", "mask", "sc", "past", "hand_card", "hand_form",
              "next_card", "next_form", "deck_card", "deck_form", "unit_form",
              "opp_past", "own_ability", "opp_cycle", "projectiles", "effects")
OUTPUT_KEYS = ("gate", "value", "card", "wait", "g", "cell")
_BASE_HEADS = set(OUTPUT_KEYS) - {"cell"}
_MAX_BYTES = 67108864
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_KEYS = {"schema", "checkpoint_path", "checkpoint_sha256", "sources",
                  "settings", "environment", "capture_id"}
_SETTING_KEYS = {"feature_version", "model_eval", "grid", "gate_tau", "use_counter",
                 "extrapolate_ticks", "decision_options", "decision_seed", "public_audit",
                 "card_vocab", "anti_leak", "hand_reader", "pilot_class",
                 "character_identity_enabled"}
_ENV_KEYS = {"torch_version", "numpy_version", "python_version", "torch_threads",
             "torch_interop_threads", "device", "platform", "machine", "processor",
             "deterministic", "mkldnn_enabled"}
_BODY_FIELDS = {"side", "x", "y", "card_id", "hp", "max_hp", "kind", "address",
                "category", "level", "native_name", "native_name_status",
                "attached_owner", "attached_owner_read_ok"}
_PROJECTILE_FIELDS = {"side", "x", "y", "card_id", "target_x", "target_y",
                      "time_to_impact_ms", "address", "generation_key", "remaining_ms"}
_DECISION_FIELDS = {"play", "no_affordable", "p_play", "hand_pos", "deck_index",
                    "card", "form", "name", "el_int", "xy"}
_INPUT_SHAPES = {"tok": (1, 64, 14), "mask": (1, 64), "sc": (1, 70),
                 "past": (1, 3, 5), "hand_card": (1, 4), "hand_form": (1, 4),
                 "next_card": (1,), "next_form": (1,), "deck_card": (1, 8),
                 "deck_form": (1, 8), "unit_form": (1, 64), "opp_past": (1, 3, 5),
                 "own_ability": (1, 8, 7), "opp_cycle": (1, 8, 4),
                 "projectiles": (1, 64, 8), "effects": (1, 32, 6)}
_LONG_INPUTS = {"hand_card", "hand_form", "next_card", "next_form", "deck_card",
                "deck_form", "unit_form"}
_ROW_FIELDS = {"hand", "hand_deck_indices", "names", "costs", "el_int", "t_sec",
               "model_tick", "my_elixir", "opp_elixir", "allowed"}
_FRAME_FIELDS = {"raw_tick", "match_index", "observer_side", "raw_bodies", "raw_projectiles",
                 "sequence", "sample_monotonic_us", "character_identity"}


class CaptureError(ValueError):
    """The capture contract or a stored record is invalid."""


def _require(condition, message):
    if not condition:
        raise CaptureError(message)


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _scalar(value):
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        _require(math.isfinite(float(value)), "nonfinite metadata scalar")
        return float(value)
    if type(value) is str:
        _require(len(value) <= 1024 and all(ord(c) >= 32 for c in value),
                 "invalid metadata string")
        return value
    raise CaptureError("metadata scalar type")


def _scalars(values, limit=2048):
    _require(type(values) in (list, tuple) and len(values) <= limit, "metadata sequence")
    return [_scalar(value) for value in values]


def _manifest(value):
    _require(type(value) is dict and set(value) == _MANIFEST_KEYS, "manifest fields")
    _require(value["schema"] == SCHEMA, "manifest schema")
    for key in ("checkpoint_path", "capture_id"):
        _require(type(value[key]) is str and 0 < len(value[key]) <= 1024,
                 "manifest identifier")
    _require(type(value["checkpoint_sha256"]) is str and
             _HEX.fullmatch(value["checkpoint_sha256"]), "checkpoint digest")
    _require(type(value["sources"]) is dict and len(value["sources"]) <= 256,
             "source map")
    for path, digest in value["sources"].items():
        _require(type(path) is str and 0 < len(path) <= 1024 and
                 type(digest) is str and _HEX.fullmatch(digest), "source binding")
    settings = value["settings"]
    _require(type(settings) is dict and set(settings) <= _SETTING_KEYS and
             settings.get("feature_version") == 4 and settings.get("model_eval") is True,
             "settings schema")
    for key, item in settings.items():
        if key == "decision_options":
            _require(type(item) is dict and set(item) ==
                     {"card_choice", "card_ratio", "card_T", "spell_aim"}, "options schema")
            _require(item["card_choice"] in ("argmax", "filtered") and
                     item["spell_aim"] in ("argmax", "rocket_area"), "options choices")
            _require(0 < float(item["card_ratio"]) <= 1 and
                     math.isfinite(float(item["card_T"])) and float(item["card_T"]) > 0,
                     "options numbers")
            for part in item.values():
                _scalar(part)
        elif key == "card_vocab":
            _require(type(item) is dict and len(item) <= 4096, "card vocabulary")
            for name, index in item.items():
                _require(type(name) is str and len(name) <= 128 and type(index) is int,
                         "card vocabulary entry")
        else:
            _scalar(item)
    environment = value["environment"]
    _require(type(environment) is dict and set(environment) <= _ENV_KEYS,
             "environment schema")
    for item in environment.values():
        _scalar(item)
    if "device" in environment:
        _require(environment["device"] == "cpu", "capture CPU environment")
    return json.loads(_json_bytes(value))


def _public_objects(values, fields):
    _require(type(values) in (tuple, list) and len(values) <= 2048, "public object count")
    result = []
    for value in values:
        _require(type(value) is dict, "public object mapping")
        result.append({key: _scalar(value[key]) for key in fields if key in value})
    return result


def _frame_view(frame, pilot):
    from pipeline.live_mem import my_side_of
    _require(type(frame) is dict, "frame mapping")
    result = {"raw_tick": _scalar(frame["game_tick"]),
              "match_index": _scalar(getattr(pilot, "match_index", -1)),
              "observer_side": my_side_of(frame),
              "raw_bodies": _public_objects(frame.get("entities", []), _BODY_FIELDS),
              "raw_projectiles": _public_objects(frame.get("projectiles", []), _PROJECTILE_FIELDS)}
    for key in ("sample_monotonic_us", "sequence"):
        if key in frame:
            result[key] = _scalar(frame[key])
    if "character_identity" in frame:
        identity = frame["character_identity"]
        _require(type(identity) is dict, "character identity mapping")
        result["character_identity"] = {key: _scalar(identity[key])
                                        for key in ("schema", "build") if key in identity}
    _validate_frame(result)
    return result


def _validate_frame(value):
    _require(type(value) is dict and set(value) <= _FRAME_FIELDS and
             {"raw_tick", "match_index", "observer_side", "raw_bodies", "raw_projectiles"}
             <= set(value), "frame schema")
    for key in ("raw_tick", "match_index", "observer_side", "sequence", "sample_monotonic_us"):
        if key in value:
            _require(type(value[key]) is int, "frame integer")
    _require(value["observer_side"] in (0, 1), "frame orientation")
    for key, fields in (("raw_bodies", _BODY_FIELDS), ("raw_projectiles", _PROJECTILE_FIELDS)):
        _require(_public_objects(value[key], fields) == value[key], "frame object schema")
    if "character_identity" in value:
        identity = value["character_identity"]
        _require(type(identity) is dict and set(identity) <= {"schema", "build"} and
                 all(type(v) is int for v in identity.values()), "identity metadata")


def _row_view(info):
    _require(type(info) is dict, "row info mapping")
    bs = info["bs"]
    hand = info["hand"]
    _require(type(hand) in (tuple, list) and len(hand) == 4, "hand length")
    result = {"hand": [_scalars(pair, 2) for pair in hand],
              "hand_deck_indices": _scalars(info["hand_deck_indices"], 4),
              "names": _scalars(info["names"], 8), "costs": _scalars(info["costs"], 4),
              "el_int": _scalar(info["el_int"]), "t_sec": _scalar(bs.t_sec),
              "model_tick": round(float(bs.t_sec) / .05),
              "my_elixir": _scalar(bs.my_elixir), "opp_elixir": _scalar(bs.opp_elixir)}
    _require(all(len(pair) == 2 for pair in result["hand"]) and
             len(result["hand_deck_indices"]) == 4 and len(result["costs"]) == 4,
             "row sequence dimensions")
    result["allowed"] = [card > 0 and float(cost) <= float(result["el_int"]) + 1e-6
                          for (card, _), cost in zip(result["hand"], result["costs"])]
    _validate_row(result)
    return result


def _validate_row(value):
    _require(type(value) is dict and set(value) == _ROW_FIELDS, "row fields")
    hand = value["hand"]
    _require(type(hand) is list and len(hand) == 4 and all(type(pair) is list and
             len(pair) == 2 and all(type(v) is int for v in pair) for pair in hand), "row hand")
    _require(type(value["hand_deck_indices"]) is list and len(value["hand_deck_indices"]) == 4 and
             all(type(v) is int and -1 <= v < 8 for v in value["hand_deck_indices"]), "row deck slots")
    _require(type(value["names"]) is list and len(value["names"]) == 8 and
             all(type(v) is str and len(v) <= 128 for v in value["names"]), "row card names")
    _require(type(value["costs"]) is list and len(value["costs"]) == 4 and
             all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 10
                 for v in value["costs"]), "row costs")
    _require(type(value["el_int"]) is int and type(value["model_tick"]) is int, "row integers")
    for key in ("t_sec", "my_elixir", "opp_elixir"):
        item = value[key]
        _require((key == "opp_elixir" and item is None) or
                 (type(item) in (int, float) and math.isfinite(item)), "row public scalar")
    _require(value["model_tick"] == round(value["t_sec"] / .05), "row clock")
    allowed = [card > 0 and float(cost) <= float(value["el_int"]) + 1e-6
               for (card, _), cost in zip(hand, value["costs"])]
    _require(type(value["allowed"]) is list and all(type(v) is bool for v in value["allowed"])
             and value["allowed"] == allowed, "row affordability")


def _decision_view(decision):
    _require(type(decision) is dict, "decision mapping")
    result = {key: (_scalars(decision[key], 2) if key == "xy" else _scalar(decision[key]))
              for key in _DECISION_FIELDS if key in decision}
    _require({"play", "no_affordable", "p_play", "hand_pos", "deck_index", "card", "form"}
             <= set(result), "decision fields")
    for key in ("play", "no_affordable"):
        _require(type(result[key]) is bool, "decision boolean")
    for key in ("hand_pos", "deck_index", "card", "form", "el_int"):
        if key in result:
            _require(type(result[key]) is int, "decision integer")
    _require(type(result["p_play"]) in (float, int) and 0 <= result["p_play"] <= 1,
             "decision probability")
    if "name" in result:
        _require(result["name"] is None or type(result["name"]) is str, "decision name")
    if "xy" in result:
        _require(len(result["xy"]) == 2 and all(type(v) in (float, int) and math.isfinite(v)
                 for v in result["xy"]), "decision coordinates")
    return result


def _array_info(array):
    return {"dtype": array.dtype.str, "shape": list(array.shape),
            "sha256": _sha(memoryview(array).cast("B"))}


def _copy_tensor(tensor, *, head=None):
    _require(isinstance(tensor, torch.Tensor) and tensor.device.type == "cpu" and
             tensor.layout == torch.strided and tensor.is_contiguous(),
             "CPU contiguous tensor required")
    _require(tensor.ndim <= 5 and tensor.numel() * tensor.element_size() <= _MAX_BYTES,
             "tensor copy budget")
    array = tensor.detach().numpy().copy(order="C")
    _require(array.dtype.kind in "biuf" and array.nbytes <= _MAX_BYTES and array.ndim <= 5,
             "tensor numeric shape or budget")
    if array.dtype.kind == "f":
        valid = ~np.isnan(array) & ~np.isposinf(array) if head in ("card", "wait") else np.isfinite(array)
        _require(bool(valid.all()), "nonfinite tensor")
    return array


def _validate_array_schema(arrays, forwards):
    for i, forward in enumerate(forwards):
        prefix = f"f{i}__"
        for key in INPUT_KEYS:
            array = arrays[prefix + "input__" + key]
            dtype = np.dtype("bool" if key == "mask" else "int64" if key in _LONG_INPUTS else "float32")
            _require(array.shape == _INPUT_SHAPES[key] and array.dtype == dtype, "feature4 tensor schema")
        for key in forward["kwargs"]:
            array = arrays[prefix + "kwarg__" + key]
            _require(array.shape == (1,) and array.dtype == np.int64, "conditioning tensor schema")
        for key in forward.get("outputs", []):
            array = arrays[prefix + "output__" + key]
            shape = {"gate": (1,), "card": (1, 4), "wait": (1, 8), "cell": (1, 2304)}.get(key)
            _require(array.dtype == np.float32 and
                     (array.shape == shape if shape else array.ndim == 2 and array.shape[0] == 1 and
                      1 <= array.shape[1] <= 4096), "output tensor schema")
            if key in ("card", "wait"):
                ids = arrays[prefix + "input__" + ("hand_card" if key == "card" else "deck_card")]
                _require(np.array_equal(np.isneginf(array), ids == 0), "masked logit positions")


class CaptureStore:
    def __init__(self, directory, manifest, max_records=128, max_bytes=_MAX_BYTES):
        _require(type(max_records) is int and 1 <= max_records <= 128, "record cap")
        _require(type(max_bytes) is int and 1 <= max_bytes <= _MAX_BYTES, "byte cap")
        self._manifest = _manifest(manifest)
        self._manifest_bytes = _json_bytes(self._manifest)
        self.manifest_sha256 = _sha(self._manifest_bytes)
        self.directory = Path(directory)
        self.max_records, self.max_bytes = max_records, max_bytes
        self.count = 0
        self.disabled_reason = None
        self.timings = []
        self._records = []
        self._index_bytes = self._index([])
        self._bytes_used = len(self._manifest_bytes) + len(self._index_bytes)
        _require(self._bytes_used <= max_bytes, "manifest exceeds byte cap")
        self.directory.mkdir(parents=True, exist_ok=False)
        (self.directory / "manifest.json").write_bytes(self._manifest_bytes)
        (self.directory / "index.json").write_bytes(self._index_bytes)

    @property
    def manifest(self):
        return json.loads(self._manifest_bytes)

    def _index(self, records):
        return _json_bytes({"schema": SCHEMA, "manifest_sha256": self.manifest_sha256,
                            "records": records})

    def _disable(self, reason):
        if self.disabled_reason is None:
            self.disabled_reason = reason
            status = _json_bytes({"event": "decision_capture_disabled", "reason": reason,
                                  "record_count": self.count})
            try:
                print(status.decode("ascii"), file=sys.stderr, flush=True)
            except Exception:
                pass
            # Best effort only. A full/broken store cannot interfere with play.
            if self._bytes_used + len(status) <= self.max_bytes:
                try:
                    with (self.directory / "status.json").open("xb") as stream:
                        stream.write(status)
                    self._bytes_used += len(status)
                except OSError:
                    pass

    def _pilot_binding(self, pilot):
        settings = self._manifest["settings"]
        _require(getattr(pilot, "feature_version", None) == 4 and
                 pilot.model.training is False, "feature4 eval model required")
        actual = {"grid": getattr(pilot, "grid", None),
                  "gate_tau": getattr(pilot, "gate_tau", None),
                  "use_counter": getattr(pilot, "use_counter", None),
                  "extrapolate_ticks": getattr(pilot, "ext_h", None),
                  "card_vocab": getattr(pilot, "gid", None),
                  "decision_seed": getattr(pilot, "decision_seed", None),
                  "public_audit": getattr(pilot, "public_audit", None),
                  "pilot_class": type(pilot).__module__ + "." + type(pilot).__name__}
        for key, value in actual.items():
            if key in settings:
                _require(value == settings[key], "pilot settings changed")
        if "decision_options" in settings:
            options = getattr(pilot, "decision_options", None)
            _require(options is not None and all(getattr(options, key, None) == value
                     for key, value in settings["decision_options"].items()), "pilot options changed")
        _require(str(getattr(pilot, "dev", "cpu")) == "cpu", "pilot CPU device required")
        environment = self._manifest["environment"]
        runtime = {"torch_threads": torch.get_num_threads(),
                   "torch_interop_threads": torch.get_num_interop_threads(),
                   "deterministic": torch.are_deterministic_algorithms_enabled(),
                   "mkldnn_enabled": torch.backends.mkldnn.enabled}
        _require(all(key not in environment or environment[key] == value
                     for key, value in runtime.items()), "runtime environment changed")

    def _commit(self, meta, arrays):
        meta["arrays"] = {key: _array_info(value) for key, value in arrays.items()}
        meta_bytes = _json_bytes(meta)
        _require(len(meta_bytes) <= 1048576, "record metadata budget")
        with io.BytesIO() as buffer:
            np.savez(buffer, **arrays, __metadata__=np.frombuffer(meta_bytes, dtype=np.uint8))
            payload = buffer.getvalue()
        filename = f"record_{self.count:06d}.npz"
        item = {"record_id": self.count, "file": filename,
                "bytes": len(payload), "sha256": _sha(payload)}
        records = [*self._records, item]
        index_bytes = self._index(records)
        # Includes simultaneous old index, new index temp, and new record temp.
        _require(self._bytes_used + len(payload) + len(index_bytes) <= self.max_bytes,
                 "capture byte cap")
        record_tmp = self.directory / (filename + ".tmp")
        index_tmp = self.directory / "index.json.tmp"
        try:
            with record_tmp.open("xb") as stream:
                stream.write(payload)
            os.replace(record_tmp, self.directory / filename)
            with index_tmp.open("xb") as stream:
                stream.write(index_bytes)
            os.replace(index_tmp, self.directory / "index.json")
        finally:
            for temporary in (record_tmp, index_tmp):
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        self._bytes_used += len(payload) + len(index_bytes) - len(self._index_bytes)
        self._index_bytes, self._records = index_bytes, records
        self.count += 1

    def decide(self, pilot, frame):
        if self.disabled_reason is not None:
            return pilot.decide(frame)
        if self.count >= self.max_records:
            self._disable("record_limit")
            return pilot.decide(frame)
        began = time.perf_counter()
        copy_seconds = 0.0
        inside_seconds = 0.0
        serialize_seconds = 0.0
        call_seconds = 0.0
        arrays, forwards, row = {}, [], None
        handles = []
        row_saved = "row" in pilot.__dict__
        row_value = pilot.__dict__.get("row")
        original_row = pilot.row
        installed_row = False
        failed_decision = False

        def capture_work(fn):
            nonlocal copy_seconds, inside_seconds
            if self.disabled_reason is not None:
                return
            start = time.perf_counter()
            try:
                fn()
            except Exception as error:
                self._disable("capture_" + type(error).__name__)
            finally:
                elapsed = time.perf_counter() - start
                copy_seconds += elapsed
                inside_seconds += elapsed

        def wrapped_row(*args, **kwargs):
            # Policy exceptions originate outside the capture-only handler.
            batch, info = original_row(*args, **kwargs)
            def save_row():
                nonlocal row
                _require(row is None, "multiple rows in one decision")
                row = _row_view(info)
            capture_work(save_row)
            return batch, info

        def before_forward(module, args, kwargs):
            def save_inputs():
                _require(len(args) == 1 and type(args[0]) is dict and
                         set(args[0]) == set(INPUT_KEYS), "input schema")
                _require(set(kwargs) <= {"card", "form"}, "conditioning schema")
                _require(len(forwards) < 2 and
                         (not forwards or "outputs" in forwards[-1]), "forward order")
                index = len(forwards)
                entry = {"inputs": list(INPUT_KEYS), "kwargs": [], "null_kwargs": []}
                for key in INPUT_KEYS:
                    _require(tuple(args[0][key].shape) == _INPUT_SHAPES[key], "input tensor shape")
                    arrays[f"f{index}__input__{key}"] = _copy_tensor(args[0][key])
                for key in sorted(kwargs):
                    if kwargs[key] is None:
                        entry["null_kwargs"].append(key)
                    else:
                        arrays[f"f{index}__kwarg__{key}"] = _copy_tensor(kwargs[key])
                        entry["kwargs"].append(key)
                _require(sum(a.nbytes for a in arrays.values()) <= self.max_bytes,
                         "array capture budget")
                forwards.append(entry)
            capture_work(save_inputs)
            return None

        def after_forward(module, args, kwargs, output):
            def save_outputs():
                _require(type(output) is dict and _BASE_HEADS <= set(output) <= set(OUTPUT_KEYS),
                         "output schema")
                _require(forwards and "outputs" not in forwards[-1], "forward output order")
                index = len(forwards) - 1
                forwards[-1]["outputs"] = sorted(output)
                for key in sorted(output):
                    arrays[f"f{index}__output__{key}"] = _copy_tensor(output[key], head=key)
                    _require(sum(a.nbytes for a in arrays.values()) <= self.max_bytes,
                             "array capture budget")
                _require(sum(a.nbytes for a in arrays.values()) <= self.max_bytes,
                         "array capture budget")
            capture_work(save_outputs)
            return None

        try:
            try:
                self._pilot_binding(pilot)
                frame_meta = _frame_view(frame, pilot)
                pilot.row = wrapped_row
                installed_row = True
                handles.append(pilot.model.register_forward_pre_hook(before_forward, with_kwargs=True))
                handles.append(pilot.model.register_forward_hook(after_forward, with_kwargs=True))
            except Exception as error:
                self._disable("setup_" + type(error).__name__)
            start = time.perf_counter()
            try:
                decision = pilot.decide(frame)
            except BaseException:
                failed_decision = True
                raise
            finally:
                call_seconds = time.perf_counter() - start
        finally:
            for handle in reversed(handles):
                try:
                    handle.remove()
                except Exception:
                    self._disable("hook_cleanup_error")
            if installed_row:
                try:
                    if row_saved:
                        pilot.row = row_value
                    else:
                        del pilot.row
                except Exception:
                    self._disable("row_cleanup_error")
            if failed_decision:
                self._disable("decision_exception")

        if self.disabled_reason is None:
            start = time.perf_counter()
            try:
                _require(row is not None and 1 <= len(forwards) <= 2 and
                         all("outputs" in item for item in forwards), "incomplete decision")
                _validate_array_schema(arrays, forwards)
                meta = {"schema": SCHEMA, "manifest_sha256": self.manifest_sha256,
                        "record_id": self.count, "frame": frame_meta, "row": row,
                        "decision": _decision_view(decision), "forwards": forwards,
                        "model_eval": True}
                self._commit(meta, arrays)
            except Exception as error:
                self._disable("storage_" + type(error).__name__)
            finally:
                serialize_seconds = time.perf_counter() - start
        total_ms = (time.perf_counter() - began - call_seconds + inside_seconds) * 1000
        self.timings.append({"copy_ms": copy_seconds * 1000,
                             "serialize_ms": serialize_seconds * 1000, "total_ms": total_ms})
        if total_ms > 20.0:
            self._disable("capture_time_limit")
        return decision


def _read_json(path, limit):
    _require(path.stat().st_size <= limit, "JSON size budget")
    raw = path.read_bytes()
    value = json.loads(raw)
    _require(_json_bytes(value) == raw, "noncanonical JSON")
    return value, raw


def load_record(path, expected_manifest):
    """Load only an indexed, hash-bound, strict-schema numeric record."""
    try:
        path = Path(path)
        expected = _manifest(expected_manifest)
        manifest, raw_manifest = _read_json(path.parent / "manifest.json", 1048576)
        _require(_manifest(manifest) == expected, "manifest mismatch")
        manifest_digest = _sha(raw_manifest)
        index, _ = _read_json(path.parent / "index.json", 1048576)
        _require(type(index) is dict and set(index) == {"schema", "manifest_sha256", "records"}
                 and index["schema"] == SCHEMA and index["manifest_sha256"] == manifest_digest,
                 "index schema")
        _require(type(index["records"]) is list and len(index["records"]) <= 128, "index records")
        entries = []
        for number, item in enumerate(index["records"]):
            _require(type(item) is dict and set(item) == {"record_id", "file", "bytes", "sha256"}
                     and item["record_id"] == number and item["file"] == f"record_{number:06d}.npz"
                     and type(item["bytes"]) is int and 0 < item["bytes"] <= _MAX_BYTES
                     and type(item["sha256"]) is str and _HEX.fullmatch(item["sha256"]),
                     "index entry")
            if item["file"] == path.name:
                entries.append(item)
        _require(len(entries) == 1, "record is uncommitted")
        item = entries[0]
        _require(path.stat().st_size == item["bytes"], "record length")
        payload = path.read_bytes()
        _require(_sha(payload) == item["sha256"], "record digest")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = archive.infolist()
            _require(len(files) <= 65 and len({f.filename for f in files}) == len(files) and
                     all(f.compress_type == zipfile.ZIP_STORED and f.file_size <= _MAX_BYTES for f in files)
                     and sum(f.file_size for f in files) <= _MAX_BYTES, "NPZ archive bounds")
            # Inspect shape and numeric dtype before NumPy can allocate arrays
            # from an untrusted NPY header. Every member body must fit exactly.
            for file in files:
                _require(file.filename.endswith(".npy") and "/" not in file.filename and
                         "\\" not in file.filename, "NPZ member name")
                with archive.open(file) as member:
                    version = np.lib.format.read_magic(member)
                    _require(version in ((1, 0), (2, 0)), "NPY version")
                    read_header = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                                   else np.lib.format.read_array_header_2_0)
                    shape, fortran, dtype = read_header(member, max_header_size=10000)
                    _require(type(shape) is tuple and len(shape) <= 5 and
                             all(type(v) is int and v >= 0 for v in shape) and
                             not fortran and dtype.kind in "biuf" and not dtype.hasobject,
                             "NPY header schema")
                    size = math.prod(shape) * dtype.itemsize
                    _require(size <= _MAX_BYTES and member.tell() + size == file.file_size,
                             "NPY header byte count")
        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            _require("__metadata__" in archive.files, "missing metadata")
            raw = archive["__metadata__"]
            _require(raw.dtype == np.uint8 and raw.ndim == 1 and raw.size <= 1048576,
                     "metadata array")
            meta_bytes = raw.tobytes()
            meta = json.loads(meta_bytes)
            _require(_json_bytes(meta) == meta_bytes, "metadata encoding")
            _require(type(meta) is dict and set(meta) == {"schema", "manifest_sha256", "record_id",
                     "frame", "row", "decision", "forwards", "arrays", "model_eval"} and
                     meta["schema"] == SCHEMA and meta["manifest_sha256"] == manifest_digest and
                     meta["record_id"] == item["record_id"] and meta["model_eval"] is True,
                     "record metadata schema")
            _require(type(meta["forwards"]) is list and 1 <= len(meta["forwards"]) <= 2,
                     "forward metadata")
            names = set()
            for number, forward in enumerate(meta["forwards"]):
                _require(type(forward) is dict and set(forward) ==
                         {"inputs", "kwargs", "null_kwargs", "outputs"} and
                         forward["inputs"] == list(INPUT_KEYS), "forward fields")
                for group, allowed in (("kwargs", {"card", "form"}),
                                       ("null_kwargs", {"card", "form"}), ("outputs", set(OUTPUT_KEYS))):
                    values = forward[group]
                    _require(type(values) is list and len(values) == len(set(values)) and
                             set(values) <= allowed, "forward key list")
                _require(not set(forward["kwargs"]) & set(forward["null_kwargs"]) and
                         _BASE_HEADS <= set(forward["outputs"]), "forward heads")
                for group, label in (("inputs", "input"), ("kwargs", "kwarg"), ("outputs", "output")):
                    names.update(f"f{number}__{label}__{key}" for key in forward[group])
            _require(set(archive.files) == names | {"__metadata__"} and
                     type(meta["arrays"]) is dict and set(meta["arrays"]) == names, "array keys")
            arrays = {}
            for key in names:
                array = archive[key]
                _require(array.dtype.kind in "biuf" and array.ndim <= 5 and
                         array.flags.c_contiguous, "stored array type")
                _require(_array_info(array) == meta["arrays"][key], "array checksum or shape")
                if array.dtype.kind == "f":
                    permit = key.endswith("__output__card") or key.endswith("__output__wait")
                    valid = ~np.isnan(array) & ~np.isposinf(array) if permit else np.isfinite(array)
                    _require(bool(valid.all()), "stored nonfinite tensor")
                arrays[key] = array.copy()
            _validate_array_schema(arrays, meta["forwards"])
            _validate_frame(meta["frame"])
            _validate_row(meta["row"])
            _require(_decision_view(meta["decision"]) == meta["decision"], "stored decision fields")
        return meta, arrays
    except CaptureError:
        raise
    except Exception as error:
        raise CaptureError("invalid capture record") from error

"""JSON contracts, stable spawn alignment, streaming first-divergence comparison."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from itertools import zip_longest
import json
import math
from typing import Protocol

HZ = 20
MISSING = {"missing": True}


class Unsupported(RuntimeError):
    """Requested semantics are unavailable; never turn this into an exact case."""


class Engine(Protocol):
    def reset(self, scenario: dict) -> None: ...
    def step(self, n: int) -> None: ...
    def deploy(self, side: int, card: str, form: int, x: int, y: int, tick: int) -> dict: ...
    def ability(self, side: int, card: str, tick: int, **kwargs) -> dict: ...
    def state(self) -> dict: ...
    def can_deploy(self, side: int, card: str, form: int, x: int, y: int) -> bool: ...
    def close(self) -> None: ...


def validate(s):
    if s.get("schema_version") != 1:
        raise ValueError("scenario schema_version must be 1")
    if len(s["decks"]) != 2 or s["side"] not in (0, 1):
        raise ValueError("two positional sides required")
    if not isinstance(s["seed"], int) or not 0 <= s["seed"] < 2**64:
        raise ValueError("seed must be uint64")
    if not isinstance(s["duration_ticks"], int) or s["duration_ticks"] < 0:
        raise ValueError("duration_ticks must be nonnegative")
    for deck in s["decks"]:
        if len({c["card"] for c in deck}) != len(deck):
            raise ValueError("duplicate deck card")
        for c in deck:
            if c["form"] not in (0, 1, 2) or not 1 <= c["level"] <= 16:
                raise ValueError("invalid form or level")
    last = -1
    used = set()
    for p in s["plays"]:
        if p["tick"] < last or not 0 <= p["tick"] <= s["duration_ticks"] or p["side"] not in (0, 1):
            raise ValueError("invalid action ordering/tick/side")
        last = p["tick"]
        key = (p["tick"], p["side"])
        if key in used:
            raise ValueError("at most one action per side per tick")
        used.add(key)
        if p["type"] not in ("deploy", "ability"):
            raise ValueError("unknown action")
    return s


class Aligner:
    """Lifetime map: deaths never renumber survivors; forms may change in place.

    An adapter supplies a stable id and monotone spawn_order. Keys use birth
    card + side + ordinal within that group, not raw IDs or current list order.
    """
    def __init__(self):
        self.ids = {}
        self.counts = Counter()

    def state(self, state):
        out = deepcopy(state)
        bodies = out["units"] + out["towers"]
        if len({str(e["id"]) for e in bodies}) != len(bodies):
            raise ValueError("duplicate entity id")
        for e in sorted(bodies, key=lambda e: (e["spawn_order"], str(e["id"]))):
            raw = str(e["id"])
            if raw not in self.ids:
                group = (e["side"], e["card"])
                k = self.counts[group]
                self.counts[group] += 1
                self.ids[raw] = f"{group[0]}:{group[1]}:{k}"
        for group in ("units", "towers"):
            normalized = {}
            for e in out[group]:
                key = self.ids[str(e.pop("id"))]
                e.pop("spawn_order")
                for field in ("target", "mount"):
                    if field in e and e[field] is not None:
                        raw = str(e[field])
                        if raw not in self.ids:
                            raise ValueError(f"unresolved {field}: {raw}")
                        e[field] = self.ids[raw]
                normalized[key] = e
            out[group] = normalized
        # Projectiles retain target identity too.
        for p in out.get("projectiles", []):
            if p.get("target") is not None:
                p["target"] = self.ids[str(p["target"])]
        return out


@dataclass(frozen=True)
class Divergence:
    tick: int
    field: str
    left: object
    right: object
    cards: tuple[str, ...]
    event_type: str

    def json(self):
        return {**asdict(self), "seconds": self.tick / HZ}


def differences(a, b, path="", tolerances=None):
    """Deterministic leaf order; tolerances are absolute and path-glob keyed."""
    tolerances = tolerances or {}
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(a.keys() | b.keys()):
            p = f"{path}.{k}" if path else k
            if k not in a or k not in b:
                yield p, a.get(k, MISSING), b.get(k, MISSING)
            else:
                yield from differences(a[k], b[k], p, tolerances)
    elif isinstance(a, list) and isinstance(b, list):
        for i, (x, y) in enumerate(zip_longest(a, b, fillvalue=MISSING)):
            yield from differences(x, y, f"{path}[{i}]", tolerances)
    elif type(a) in (int, float) and type(b) in (int, float):
        tol = max((v for k, v in tolerances.items() if fnmatchcase(path, k)), default=0)
        if tol < 0 or not math.isfinite(tol):
            raise ValueError("tolerances must be finite and nonnegative")
        # Hex comparison distinguishes signed zero; integers remain lossless.
        exact = (type(a) is type(b) and a == b and not
                 (isinstance(a, float) and isinstance(b, float) and a.hex() != b.hex()))
        if not math.isfinite(a) or not math.isfinite(b) or (not exact and (tol == 0 or abs(a-b) > tol)):
            yield path, a, b
    elif type(a) != type(b) or a != b:
        yield path, a, b


def make_divergence(tick, diff, left, right):
    field, a, b = diff
    cards = set()
    for state in (left, right):
        for group in ("units", "towers"):
            for key, e in state.get(group, {}).items():
                if field.startswith(f"{group}.{key}"):
                    cards.add(e["card"])
                    target = e.get("target")
                    for other in ("units", "towers"):
                        if target in state.get(other, {}):
                            cards.add(state[other][target]["card"])
        for action in state.get("actions", []):
            if action.get("card"):
                cards.add(action["card"])
    event = "state"
    if field.startswith("actions"):
        event = "command"
    elif a == MISSING or b == MISSING:
        event = "spawn_or_despawn"
    elif any(x in field for x in ("hp", "shield")):
        event = "damage_or_heal"
    elif "status" in field:
        event = "status"
    elif "target" in field:
        event = "target"
    return Divergence(tick, field, a, b, tuple(sorted(cards)), event)


def compare_traces(left, right, tolerances=None):
    """Iterables may be JSONL streams. Never zip away missing tail frames."""
    aligns = Aligner(), Aligner()
    prev = [-1, -1]
    for a, b in zip_longest(left, right):
        if a is None or b is None:
            return Divergence((a or b)["tick"], "trace.length", a, b, (), "timeline")
        for i, s in enumerate((a, b)):
            if s["tick"] <= prev[i] or (prev[i] >= 0 and s["tick"] != prev[i] + 1):
                raise ValueError("trace must contain every tick, once, in order")
            prev[i] = s["tick"]
        x, y = aligns[0].state(a), aligns[1].state(b)
        d = next(differences(x, y, tolerances=tolerances), None)
        if d:
            return make_divergence(min(a["tick"], b["tick"]), d, x, y)
    return None


def json_dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

"""Per-term reward accounting -- WHICH shaping term is actually driving the policy.

WHY THIS EXISTS
---------------
Three shaping terms have already been deleted from this project after measurement contradicted
intuition -- `cycle_plan` fired 110 times for 0 positives, `threat_response`'s quiet-board branch
257 times for 0 positives -- and BOTH collapses reached the same end state: the policy stopped
playing. The only symptom either produced was "plays per match fell off a cliff", and nothing
recorded WHICH term did it, so each diagnosis cost a full training run to isolate.

This records, per term and per match: how often it fired, how those fires split positive/negative,
and the running totals. A term that fires often and is never positive is an ACTION TAX -- the shape
that has collapsed every run so far -- and this makes that visible in one match instead of ten hours.

It is deliberately dumb: :meth:`RewardTerms.add` returns its input UNCHANGED, so instrumenting a
reward assembly is a pure wrapper and can never alter the number that reaches the agent.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional


class _Term:
    """Counters for one named reward term."""

    __slots__ = ("fires", "pos", "neg", "total", "pos_total", "neg_total")

    def __init__(self) -> None:
        self.fires = 0
        self.pos = 0
        self.neg = 0
        self.total = 0.0
        self.pos_total = 0.0
        self.neg_total = 0.0

    def record(self, v: float) -> None:
        self.fires += 1
        self.total += v
        if v > 0.0:
            self.pos += 1
            self.pos_total += v
        else:
            self.neg += 1
            self.neg_total += v

    def as_dict(self) -> dict:
        return {"fires": self.fires, "pos": self.pos, "neg": self.neg,
                "total": round(self.total, 4),
                "pos_total": round(self.pos_total, 4),
                "neg_total": round(self.neg_total, 4)}


class RewardTerms:
    """Per-term reward statistics for the CURRENT match plus a running total over the session.

    ``add(name, value)`` is the only call site needed; a zero contribution is not counted as a fire,
    so "fires" means "this term actually said something about this step".
    """

    def __init__(self, eps: float = 1e-9) -> None:
        self.eps = float(eps)
        self.match: Dict[str, _Term] = {}
        self.run: Dict[str, _Term] = {}
        self.matches = 0
        self.match_steps = 0
        self.match_plays = 0

    # -- recording -------------------------------------------------------
    def add(self, name: str, value: float) -> float:
        """Record ``value`` under ``name``; returns it UNCHANGED so this can wrap any reward term."""
        v = float(value)
        if abs(v) > self.eps:
            for table in (self.match, self.run):
                t = table.get(name)
                if t is None:
                    t = table[name] = _Term()
                t.record(v)
        return v

    def step(self, played: bool) -> None:
        """Count one agent decision (and whether it was a PLAY) for the per-match rates."""
        self.match_steps += 1
        self.match_plays += 1 if played else 0

    def new_match(self) -> None:
        self.match = {}
        self.match_steps = 0
        self.match_plays = 0

    # -- reporting -------------------------------------------------------
    def _summary(self, table: Dict[str, _Term]) -> dict:
        return {k: t.as_dict() for k, t in sorted(table.items(), key=lambda kv: kv[1].total)}

    def match_summary(self) -> dict:
        return {"steps": self.match_steps, "plays": self.match_plays,
                "terms": self._summary(self.match)}

    def run_summary(self) -> dict:
        return {"matches": self.matches, "terms": self._summary(self.run)}

    def format_match(self, label: str = "") -> str:
        """One-line-per-term view, most NEGATIVE first -- the action taxes surface at the top."""
        rows = sorted(self.match.items(), key=lambda kv: kv[1].total)
        if not rows:
            return f"[reward-terms]{(' ' + label) if label else ''} no terms fired"
        head = (f"[reward-terms]{(' ' + label) if label else ''} "
                f"{self.match_steps} step(s), {self.match_plays} play(s)")
        out = [head]
        for name, t in rows:
            out.append(f"    {name:<22} total {t.total:+8.2f}   fires {t.fires:>4}  "
                       f"(+{t.pos} / -{t.neg})   pos {t.pos_total:+7.2f}  neg {t.neg_total:+7.2f}")
        return "\n".join(out)

    def zero_positive_terms(self) -> list:
        """Terms that fired but NEVER paid positive over the run -- the action-tax signature."""
        return [k for k, t in self.run.items() if t.fires > 0 and t.pos == 0]

    # -- persistence -----------------------------------------------------
    def dump_match(self, path: Path, extra: Optional[dict] = None) -> None:
        """Append this match's summary to a JSONL file (created on first write)."""
        rec = {"t": time.time(), "match": self.matches, **(extra or {}), **self.match_summary()}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass          # measurement must never take the training loop down

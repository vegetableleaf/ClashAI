"""Single-engine execution and isolated, persistent wheel workers (local pipes)."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
import threading

from .core import compare_traces, validate
from .generators import LegalPolicy


def projection(state, profile):
    if profile == "public":
        return state
    if profile != "common":
        raise ValueError("unknown comparison profile")
    # Native adapter is unqualified. This explicitly narrower profile must never
    # be described as full-state parity. Preserve exact coordinates and elixir.
    s = deepcopy(state)
    s.pop("extra", None)
    s.pop("projectiles", None)
    s["clock"] = {"tick_ms": s["clock"]["tick_ms"]}
    for e in s["units"] + s["towers"]:
        for k in ("extra", "unit_type", "mount"):
            e.pop(k, None)
        e["status"] = {"buffs": e["status"]["buffs"]}
    return s


def execute(engine, scenario, emit, profile="public", emit_full=None):
    """One state per tick, after that tick's commands and before step(1).

    Includes reset tick 0 and the terminal frame. No whole-match trace in RAM.
    """
    s = deepcopy(validate(scenario))
    engine.reset(s)
    policy = LegalPolicy(s.pop("policy")) if s.get("policy") else None
    if policy and s["plays"]:
        raise ValueError("policy scenarios must have no pre-existing plays")
    by_tick = {}
    for p in s["plays"]:
        by_tick.setdefault(p["tick"], []).append(p)
    frozen = []
    seen_forms = set()
    ability_cards = set()
    rejects = 0
    frames = 0
    previous = -1
    trace_hash = hashlib.sha256()
    state = engine.state()
    while True:
        tick = state["tick"]
        if tick != previous + 1:
            raise ValueError(f"missing/nonadvancing tick: expected {previous+1}, got {tick}")
        previous = tick
        actions = []
        proposals = [] if state["result"]["terminal"] else (policy.choose(engine, s, tick) if policy else by_tick.get(tick, []))
        for p in sorted(proposals, key=lambda p: p["side"]):
            args = {k: v for k, v in p.items() if k != "type"}
            outcome = getattr(engine, p["type"])(**args)
            if not outcome["accepted"]:
                rejects += 1
                if policy:
                    continue
            frozen.append(p)
            actions.append({"type": p["type"], "side": p["side"], "card": p["card"], **outcome})
            if p["type"] == "ability" and outcome["accepted"]:
                ability_cards.add(p["card"])
        if proposals:
            state = engine.state()
        for e in state["units"]:
            seen_forms.add((e["card"], e["form"]))
        state["actions"] = actions
        if emit_full:
            emit_full(state)
        state = projection(state, profile)
        trace_hash.update(json.dumps(state, sort_keys=True, allow_nan=False).encode())
        emit(state)
        frames += 1
        if state["result"]["terminal"] or tick >= s["duration_ticks"]:
            break
        engine.step(1)
        state = engine.state()
    s["plays"] = frozen if policy else s["plays"]
    required = s.get("coverage_required")
    coverage = not required or ((required["card"], required["form"]) in seen_forms
               and (not required["ability"] or required["card"] in ability_cards))
    return dict(scenario=s, final=state, frames=frames, trace_sha256=trace_hash.hexdigest(),
                rejected_attempts=rejects, fixed_rejections=rejects if not policy else 0,
                unexecuted_plays=sum(p["tick"] > state["tick"] for p in s["plays"]),
                coverage_ok=coverage, seen_forms=sorted(seen_forms), ability_cards=sorted(ability_cards),
                provenance=engine.provenance)


def trace(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


class Worker:
    """Each interpreter loads exactly one wheel. No runtime switching or TCP."""
    def __init__(self, python, engine, directory, runtime=None, native_manifest=None, native_template=None,
                 native_port=37031, timeout=600, expected_version=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.counter = 0
        cmd = [str(python), "-m", "scratchpad.gauntlet.L74.diffsim.worker", "--engine", engine]
        for flag, value in (("--runtime", runtime), ("--native-manifest", native_manifest),
                            ("--native-template", native_template), ("--native-port", native_port)):
            if value is not None:
                cmd.extend([flag, str(value)])
        if expected_version:
            cmd.extend(["--expected-version", expected_version])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1")
        self.stderr = (self.directory / "worker.stderr.log").open("w", encoding="utf-8")
        self.proc = subprocess.Popen(cmd, cwd=Path(__file__).resolve().parents[4], env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                                     text=True, encoding="utf-8", bufsize=1)
        self.responses = Queue()
        def read():
            for line in self.proc.stdout:
                self.responses.put(line)
            self.responses.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def run(self, s, profile="public"):
        self.counter += 1
        out = self.directory / f"trace-{self.counter:07d}.jsonl.gz"
        self.proc.stdin.write(json.dumps(dict(scenario=s, trace=str(out), profile=profile)) + "\n")
        self.proc.stdin.flush()
        try:
            response = self.responses.get(timeout=self.timeout)
        except Empty as exc:
            self.close()
            raise TimeoutError("owned engine worker timed out") from exc
        if response is None:
            raise RuntimeError("engine worker exited; see " + str(self.directory / "worker.stderr.log"))
        data = json.loads(response)
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data, out

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        self.stderr.close()
        self.proc.stdout.close()


def paired(candidate, oracle, s, profile="public", tolerances=None):
    # Oracle materializes once; the candidate receives the exact frozen actions.
    right, rp = oracle.run(s, profile)
    left, lp = candidate.run(right["scenario"], profile)
    exact_diff = compare_traces(trace(lp), trace(rp))
    tolerant_diff = compare_traces(trace(lp), trace(rp), tolerances) if tolerances else exact_diff
    completed = left["final"]["result"]["terminal"] and right["final"]["result"]["terminal"]
    valid = right["coverage_ok"] and right["fixed_rejections"] == 0 and right["unexecuted_plays"] == 0
    if s["suite"] == "full":
        valid = valid and completed
    row = dict(id=s["id"], suite=s["suite"], status="ok" if valid else "coverage_incomplete",
               exact=valid and exact_diff is None, within_tolerance=valid and tolerant_diff is None,
               completed=completed, result_match=completed and left["final"]["result"] == right["final"]["result"],
               divergence=exact_diff.json() if exact_diff else None,
               tolerance_divergence=tolerant_diff.json() if tolerant_diff else None,
               traces={"candidate": str(lp), "oracle": str(rp)},
               hashes={"candidate": left["trace_sha256"], "oracle": right["trace_sha256"]},
               frames={"candidate": left["frames"], "oracle": right["frames"]},
               coverage={"oracle_forms": right["seen_forms"], "oracle_abilities": right["ability_cards"],
                         "oracle_fixed_rejections": right["fixed_rejections"],
                         "oracle_unexecuted_plays": right["unexecuted_plays"], "required_met": right["coverage_ok"]},
               full_diagnostic_traces={"candidate": left.get("full_trace"), "oracle": right.get("full_trace")},
               provenance={"candidate": left["provenance"], "oracle": right["provenance"]})
    return row, right["scenario"]

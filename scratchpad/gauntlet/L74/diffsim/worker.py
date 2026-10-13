"""Private harness subprocess entry point; stdout is JSON-line replies only."""
import argparse
from contextlib import redirect_stdout, ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

from .adapters import FakeEngine, ForkEngine, NativeEngine
from .core import compare_traces
from .runner import execute, trace
from .resources import bind_worker_to_parent


def main():
    bind_worker_to_parent()
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=["fork", "wheel", "native", "fake", "fake-bug"], required=True)
    p.add_argument("--runtime")
    p.add_argument("--expected-version")
    p.add_argument("--native-manifest")
    p.add_argument("--native-template")
    p.add_argument("--native-port", type=int, default=37031)
    a = p.parse_args()
    engine = None
    try:
        with redirect_stdout(sys.stderr):
            if a.engine in ("fake", "fake-bug"):
                engine = FakeEngine(bug=a.engine == "fake-bug")
            elif a.engine == "native":
                engine = NativeEngine(manifest=a.native_manifest, template=a.native_template, port=a.native_port)
            else:
                stamp = None
                if a.engine == "fork" or a.runtime:
                    os.environ["ROYALE_RUNTIME"] = a.runtime or "fork"
                    from pipeline.royale_runtime import activate
                    stamp = activate()
                engine = ForkEngine(options={"calibration_overrides": {"cards.CARD_TABLE": json.dumps("client160402017_20261006")}})
                if a.expected_version and engine.provenance["version"] != a.expected_version:
                    raise RuntimeError("wheel version must be " + a.expected_version)
                engine.provenance["runtime_stamp"] = stamp
                from importlib.metadata import distribution
                package = distribution("royalesim")
                engine.provenance["installed_binary_sha256"] = {
                    str(p): hashlib.sha256(Path(package.locate_file(p)).read_bytes()).hexdigest()
                    for p in package.files or [] if str(p).endswith((".pyd", ".so", ".dll"))}
                engine.provenance["card_table"] = engine.battle.card_table()
        for line in sys.stdin:
            try:
                request = json.loads(line)
                path = Path(request["trace"])
                with redirect_stdout(sys.stderr), ExitStack() as stack:
                    f = stack.enter_context(gzip.open(path, "wt", encoding="utf-8"))
                    full_path = path.with_suffix(".full.jsonl.gz") if request["profile"] == "common" else None
                    full = stack.enter_context(gzip.open(full_path, "wt", encoding="utf-8")) if full_path else None
                    result = execute(engine, request["scenario"],
                        lambda state: f.write(json.dumps(state, sort_keys=True, allow_nan=False) + "\n"), request["profile"],
                        (lambda state: full.write(json.dumps(state, sort_keys=True, allow_nan=False) + "\n")) if full else None)
                    result["full_trace"] = str(full_path) if full_path else None
                if request.get("reference_trace"):
                    reference = request["reference_trace"]
                    exact = compare_traces(trace(path), trace(reference))
                    tolerant = (compare_traces(trace(path), trace(reference), request["tolerances"])
                                if request.get("tolerances") else exact)
                    result["comparison"] = dict(exact=exact.json() if exact else None,
                                                tolerant=tolerant.json() if tolerant else None)
                # Do not send a large final board through the response pipe.
                result["final"] = {"tick": result["final"]["tick"], "result": result["final"]["result"]}
                print(json.dumps(result, allow_nan=False), flush=True)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                print(json.dumps({"error": f"{type(e).__name__}: {e}"}), flush=True)
    finally:
        if engine:
            engine.close()


if __name__ == "__main__":
    main()

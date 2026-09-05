"""L61 Task D: throughput of the real engine as a recorder.  One converted replay, driven with an observe every
K ticks (compact), timed; raw observe latency; qemu working set; optional second slot for contention.
    python throughput.py --port 37031 --tag <tag> --every 10 --every 2 --reps 2 [--label x]
"""
import argparse, json, sys, time, statistics, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "research" / "ext" / "cr-native-sandbox"))
import replay_drive_rec as RD  # noqa: E402


def qemu_ws_mb():
    try:
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
                                       "(Get-Process qemu-system-x86_64-headless | Measure-Object WorkingSet64 -Sum).Sum/1MB"], text=True)
        return round(float(out.strip()), 0)
    except Exception as e:
        return str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--tag", default="000YLY0JCPGL")
    ap.add_argument("--every", type=int, action="append", default=None)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--no-latency", action="store_true")
    a = ap.parse_args()
    every = a.every or [0, 10, 2]
    res = {"port": a.port, "tag": a.tag, "label": a.label, "runs": [], "qemu_ws_mb_before": qemu_ws_mb()}
    for k in every:
        for r in range(a.reps):
            t0 = time.perf_counter()
            out = RD.drive(a.tag, port=a.port, seed=424242, level=11, elixir_slack=40, tail_cap=7200,
                           run_label=f"tp_{k}_{r}", verbose=False, record_every=k, record_full=False, record_plays=False)
            dt = time.perf_counter() - t0
            fin = out["final"]["tick"]
            n_obs = len(out.get("frames", [])) + len(out["log"])
            res["runs"].append({"every": k, "rep": r, "wall_s": round(dt, 3), "final_tick": fin, "n_frames": len(out.get("frames", [])),
                                "n_plays": len(out["log"]), "n_observe_calls_approx": n_obs, "state_hash": out["final"].get("state_hash"),
                                "qemu_ws_mb": qemu_ws_mb()})
            print(json.dumps(res["runs"][-1]), flush=True)
    # raw observe / step latency on a live match (compact + full), 200 calls each
    if not a.no_latency:
        from native_core.env import NativeRoyaleEnv
        battle, plays = RD.load_battle(a.tag)
        decks = {side: RD.deck_for_side(battle, side) for side in (0, 1)}
        template = json.loads((RD.SANDBOX / "examples" / "full-card-bootstrap.json").read_text(encoding="utf-8-sig"))
        env = NativeRoyaleEnv(port=a.port, timeout=120)
        env.reset(RD.build_replay(template, RD.deck_spec(decks[0], 11), RD.deck_spec(decks[1], 11), seed=424242), warmup_steps=0)
        env.step(600)
        lat = {}
        for name, fn in (("observe_compact", env.observe_compact), ("observe_full", env.observe),
                         ("step1", lambda: env.step(1)), ("step10", lambda: env.step(10)), ("step20", lambda: env.step(20))):
            ts = []
            for _ in range(100):
                t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
            lat[name] = {"ms_median": round(statistics.median(ts), 2), "ms_mean": round(statistics.mean(ts), 2), "ms_p90": round(sorted(ts)[89], 2)}
            print(name, lat[name], flush=True)
        res["latency_ms"] = lat
        env.close()
    res["qemu_ws_mb_after"] = qemu_ws_mb()
    (Path(a.out) if a.out else HERE / f"throughput_{a.label or 'p' + str(a.port)}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

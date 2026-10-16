"""Synthetic check of validate_stream.py: a 600-frame stream and a probe capture of the same ticks PASS S1-S4, S7, S8;
one-row-in-1800 noise still passes the 99.9% identity, three rows fail it; a cue difference fails S4; a slow stream fails
S2; degraded frames are not invalid; mismatched hashes fail S1; a reader left running fails S8.

    icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/parity/reader_val/test_validate_stream.py
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_stream as vs  # noqa: E402

BODIES = [  # side, x, y, card_id, hp, max_hp, kind, address, behavior, category
    (0, 9000, 3000, -1, 4000, 4000, 12, "0xa1", 0, 5000000), (1, 9000, 29000, -1, 4000, 4000, 12, "0xa2", 0, 5000001),
    (0, 9000, 14000, 26000000, 1400, 1400, 15, "0xa3", 2, 5000007)]


def blocks(tick):
    p2 = {"valid": True, "own_side": 0, "units": [
        {"generation": b[9], "side": b[0], "name": "Knight" if b[3] > 0 else "KingTower", "buffs": [
            {"type_id": 1, "name": "Slow", "remaining_ms_raw": 1000 - tick, "duration_ms_raw": 2000,
             "source_side_cached": 1}] if b[3] > 0 else []} for b in BODIES]}
    p3 = {"valid": True, "unlisted_targets": 0, "defs": [], "bodies": [
        {"generation": b[9], "definition_id": 7, "attack": {"target_gen": 5000001, "progress_raw": 35 * tick,
                                                             "load_raw": 0}} for b in BODIES]}
    return p2, p3


def stream(n=600, read_us=450, degraded=()):
    log, probe = [{"event": "start"}, {"event": "cues_defs", "tick": 140, "defs": []}], []
    for k in range(n):
        t = 150 + 2 * k
        p2, p3 = blocks(t)
        fr = {"event": "frame", "tick": t, "my_side": 0, "elixir": 5.0, "backlog": 0,
              "ents": [list(b[:8]) for b in BODIES], "ents_state": [[b[8], 0, 11, b[9]] for b in BODIES],
              "proj": [], "fx": [], "read_us": read_us, "cues_degraded": t in degraded}
        if t not in degraded:
            fr.update(phase2=p2, phase3=p3)
        log.append(fr)
        probe.append({"battle_active": True, "coherent": True, "game_tick": t, "players": [], "phase2": p2,
                      "phase3": p3, "entities": [dict(side=b[0], x=b[1], y=b[2], card_id=b[3], hp=b[4], max_hp=b[5],
                                                      behavior_state_raw=b[8], category=b[9]) for b in BODIES]})
    log.append({"event": "end"})
    return log, probe


def run(tmp_path, log, probe, monkeypatch, extra=(), left=""):
    (tmp_path / "log.jsonl").write_text("\n".join(json.dumps(e) for e in log))
    (tmp_path / "probe.jsonl").write_text("\n".join(json.dumps(e) for e in probe))
    (tmp_path / "pgrep.txt").write_text(left)
    import validate_p3
    monkeypatch.setattr(validate_p3, "run", lambda frames, n, *a, **k: [f"{v} PASS synthetic" for v in vs.S5_REQUIRED])
    out = vs.main([str(tmp_path / "log.jsonl"), "--probe", str(tmp_path / "probe.jsonl"), "--sha-receipt", "ab",
                   "--sha-device", "ab", "--build-checked", "--pgrep-after", str(tmp_path / "pgrep.txt"),
                   "--s7-frames", "20", *extra])
    return {ln.split()[0]: ln for ln in out if ln[:1] == "S"}


def test_clean_stream_passes(tmp_path, monkeypatch):
    log, probe = stream(degraded=(400, 402))
    r = run(tmp_path, log, probe, monkeypatch)
    for s in ("S1", "S2", "S3", "S4", "S5", "S7", "S8"):
        assert r[s].split()[1] == "PASS", r[s]
    assert "invalid cue frames 0" in r["S2"] and "degraded frames 2" in r["S2"]
    assert r["S6"].split()[1] == "SKIP" and "1800/1800" in r["S3"]


def test_identity_threshold_and_cue_difference(tmp_path, monkeypatch):
    log, probe = stream()
    probe[10]["entities"][2]["hp"] = 1
    assert run(tmp_path, log, probe, monkeypatch)["S3"].split()[1] == "PASS"      # 1799/1800 >= 0.999
    for k in (20, 30):
        probe[k]["entities"][2]["x"] += 1
    assert run(tmp_path, log, probe, monkeypatch)["S3"].split()[1] == "FAIL"      # 1797/1800 < 0.999
    log, probe = stream()
    for k in range(3):
        probe[k] = copy.deepcopy(probe[k])
        probe[k]["phase3"]["bodies"][2]["attack"]["progress_raw"] += 50
    r = run(tmp_path, log, probe, monkeypatch)
    assert r["S4"].split()[1] == "FAIL" and r["S3"].split()[1] == "PASS"


def test_budget_hashes_and_leftover_reader(tmp_path, monkeypatch):
    log, probe = stream(read_us=700)
    r = run(tmp_path, log, probe, monkeypatch, extra=("--sha-device", "cd"), left="1234\n")
    assert r["S2"].split()[1] == "FAIL" and r["S1"].split()[1] == "FAIL" and r["S8"].split()[1] == "FAIL"
    log, probe = stream()
    del log[100]["phase3"]                                                     # a non-degraded frame without its block
    assert "invalid cue frames 1" in run(tmp_path, log, probe, monkeypatch)["S2"]


def test_s5_reports_a_required_fail(tmp_path, monkeypatch):
    log, probe = stream()
    (tmp_path / "log.jsonl").write_text("\n".join(json.dumps(e) for e in log))
    import validate_p3
    monkeypatch.setattr(validate_p3, "run", lambda frames, n, *a, **k: ["V1 PASS x", "V2 FAIL y", "V3 SKIP z"])
    out = vs.s5([e for e in log if e["event"] == "frame"], [])
    assert out[0].split()[1] == "FAIL" and "['V2']" in out[0] and "V3" in out[0]

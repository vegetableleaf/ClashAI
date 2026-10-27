"""Offline tests for rc_parse / rc_crawl (ticket D2b). No network, no browser. Run: python -I test_rc.py
Fixtures: the IL_Replay sample (icebow/data/ildata_samples/hf_il_replay) and the 614 payloads saved by the 10-05 crawl
(icebow/data/royaleapi/crawl2/payloads + plays_ext_i1.csv). Tests that need a fixture print SKIP if it is missing."""
import argparse
import csv
import json
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc_crawl as C  # noqa: E402
import rc_parse as P  # noqa: E402

REPO = C.REPO
SAMPLE = REPO / "icebow/data/ildata_samples/hf_il_replay"
CRAWL2 = REPO / "icebow/data/royaleapi/crawl2"


def _sample_replays(n):
    rep = pq.read_table(SAMPLE / "replays-part-000051.parquet", columns=["replay_tag", "payload_json"]).slice(0, n).to_pylist()
    return {r["replay_tag"]: json.loads(r["payload_json"]) for r in rep}


def test_schema_matches_sample():
    if not SAMPLE.exists():
        return print("SKIP schema (no sample)")
    for name, ours in (("replays", P.REPLAYS_SCHEMA), ("actions", P.ACTIONS_SCHEMA)):
        theirs = pq.read_schema(SAMPLE / f"{name}-part-000051.parquet")
        assert [(f.name, str(f.type)) for f in theirs] == [(f.name, str(f.type)) for f in ours], name


def test_events_roundtrip_against_sample():
    """Rebuild each sample replay's plays from its own source_fields, run build_events, compare every event dict."""
    if not SAMPLE.exists():
        return print("SKIP roundtrip (no sample)")
    n_ev = bad = 0
    first_bad = None
    for tag, p in _sample_replays(400).items():
        decks = {s: [c["card_key"] for c in p["battle"][s]["players"][0]["deck"]] for s in ("team", "opponent")}
        plays = []
        for e in p["events"]:
            sf = e["source_fields"]
            ab = e["kind"] != "play_card"
            plays.append({"play_index": e["source_index"], "tick": sf["data_t"], "attr_s": "blue" if sf["data_s"] == "t" else "red",
                          "attr_card": sf["timeline_card_key"], "attr_ability": "1" if ab else "0",
                          "x_units": "" if sf["data_x"] is None else str(sf["data_x"]),
                          "y_units": "" if sf["data_y"] is None else str(sf["data_y"])})
        seat = p["events"][0]["source_fields"]["data_i"]
        got, warn = P.build_events(plays, decks, seat)
        assert len(got) == len(p["events"]), tag
        for g, w in zip(got, p["events"]):
            n_ev += 1
            if g != w:
                bad += 1
                first_bad = first_bad or (tag, {k: (g[k], w[k]) for k in w if g.get(k) != w[k]})
    assert bad == 0, f"{bad}/{n_ev} events differ, first: {first_bad}"
    print(f"  roundtrip: {n_ev} sample events reproduced exactly")


def test_parse_saved_payloads_vs_old_csv():
    pdir = CRAWL2 / "payloads"
    if not pdir.exists():
        return print("SKIP payloads (not local)")
    old = defaultdict(list)
    with (CRAWL2 / "plays_ext_i1.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            old[r["replay_tag"]].append((int(r["tick"]), r["attr_card"], r["x_units"], r["y_units"], r["attr_s"]))
    files = sorted(pdir.glob("*.html"))
    ok = stubs = 0
    for fp in files:
        rep = P.parse_replay(fp.read_text(encoding="utf-8"))
        mine = [(p["tick"], p.get("attr_card", ""), p.get("x_units", ""), p.get("y_units", ""), p.get("attr_s", "")) for p in rep["plays"]]
        assert mine == old[rep["tag"]], fp.name
        if not rep["plays"]:                 # 2 of the 614 saved payloads are 265-byte stubs: build_record must refuse them
            stubs += 1
            try:
                P.build_record({"team_deck": "", "opponent_deck": "", "result": "win", "battle_type": "PvP", "replay_tag": "x",
                                "team_crowns": "0", "opponent_crowns": "0", "battle_time": "", "battle_timestamp": 0,
                                "team_tags": "", "opponent_tags": ""}, fp.read_text(encoding="utf-8"), "")
                raise AssertionError("stub accepted")
            except ValueError:
                continue
        assert rep["stats"]["team"]["total"][0] > 0
        ok += 1
    assert ok >= 100, ok
    print(f"  parsed {ok} saved payloads (+{stubs} empty stubs refused), play lists identical to plays_ext_i1.csv")


def test_end_to_end_writer_on_saved_payloads():
    """history row (from battles.csv) + saved payload -> build_record -> Writer parquet -> read back."""
    pdir = CRAWL2 / "payloads"
    if not pdir.exists():
        return print("SKIP writer (no payloads)")
    battles = {}
    with (CRAWL2 / "battles.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            battles[r["replay_tag"]] = r
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        out = Path(td)
        store = C.Store(out / "s.db")
        w = C.Writer(out, store)
        n = acts = 0
        for fp in sorted(pdir.glob("*.html"))[:60]:
            b = battles.get(fp.stem)
            if not b or not b["team_deck"]:
                continue
            row = {**b, "battle_timestamp": int(b["battle_timestamp"]), "row_html": ""}
            rrow, arows = P.build_record(row, fp.read_text(encoding="utf-8"), b["player_tag"])
            store.add_battles([row], b["player_tag"])
            w.add(row["replay_tag"], rrow, arows, "x")
            n += 1
            acts += len(arows)
        assert n > 20
        assert w.flush() == n
        rt = pq.read_table(out / "replays/part-000000.parquet")
        at = pq.read_table(out / "actions/part-000000.parquet")
        assert rt.schema == P.REPLAYS_SCHEMA and at.schema == P.ACTIONS_SCHEMA
        assert rt.num_rows == n and at.num_rows == acts
        assert sum(rt["event_count"].to_pylist()) == acts
        assert store.n("battles", "done") == n
        assert (out / "raw/raw-000000.jsonl.gz").exists()
        w.add("again", rrow, arows, "x")        # second flush -> next part number
        w.flush()
        assert (out / "replays/part-000001.parquet").exists()
    print(f"  wrote {n} real replays ({acts} actions), schema equals the HF sample's")


# ------------------------------------------------------------------------------ state machine
def _args(**kw):
    a = argparse.Namespace(floor="2026-10-19", types="pathOfLegend,PvP", max_pages=3, max_replays=0, seed_url=["/players"],
                           seed_tags=[], seed_csv=[], no_pair_dedupe=False, no_raw=True, min_free_gb=0.001,
                           no_local_seed=True)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class Env:
    """Fake clock/sleep + a fetcher that records (time, url) of every request."""

    def __init__(self, td, faults=None, n_players=12, owner=None, **kw):
        self.t = 0.0
        self.calls = []                      # (clock, url)
        self.sleeps = []
        self.out = Path(td)
        self.f = C.FakeFetcher(n_players=n_players, faults=faults)
        real_get = self.f.get
        def get(url, manual=False):
            self.calls.append((self.t, url))
            return real_get(url, manual)
        self.f.get = get
        self.alerts = []
        self.owner = owner                   # callable(env, sleep_count) run on every sleep while paused
        self.c = C.Crawler(self.out, self.f, _args(**kw), clock=lambda: self.t, sleep=self.sleep, rng=random.Random(3),
                           alert=self.alerts.append)

    def sleep(self, s):
        self.t += s
        self.sleeps.append(s)
        if self.owner:
            self.owner(self)


def fixing_owner(env):
    """Owner who fixes everything 20 fake seconds after the pause started."""
    if (env.out / "PAUSED.json").exists() and not (env.out / "RESUME").exists():
        env._since = getattr(env, "_since", None) or env.t
        if env.t - env._since >= 20:
            env.f.logged_out = False
            (env.out / "RESUME").write_text("x")
            env._since = None


def test_pacing_never_faster_than_1_per_second():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Env(td, owner=fixing_owner)
        e.c.run()
        gaps = [b[0] - a[0] for a, b in zip(e.calls, e.calls[1:])]
        assert len(gaps) > 50 and min(gaps) >= 1.0 - 1e-9, min(gaps)
        assert max(g for g in gaps if g < 30) <= C.MIN_INTERVAL + C.JITTER + 1e-9
    print(f"  {len(e.calls)} requests, min gap {min(gaps):.3f}s, jitter up to {C.JITTER}s")


def test_each_fault_pauses_and_sends_nothing_until_resume():
    for kind, label in (("429", "rate"), ("challenge", "challenge"), ("login", "login")):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e = Env(td, faults={30: kind}, owner=fixing_owner, max_replays=40)
            e.c.run()
            assert e.c.cnt["pauses"] == 1, (kind, e.c.cnt)
            assert any(f"({label})" in a for a in e.alerts), e.alerts
            # find the request that hit the fault and the next one: the gap must cover the owner's delay
            k = 29 if kind != "login" else next(i for i, (_, u) in enumerate(e.calls) if "/me" in u)   # login: the /me check that found it
            if kind == "429":
                assert e.calls[k + 1][0] - e.calls[k][0] >= 300, "Retry-After / cooldown not honoured"
            else:
                assert e.calls[k + 1][0] - e.calls[k][0] >= 20, "request sent while paused"
            assert not (e.out / "PAUSED.json").exists()
    print("  429 / challenge / login loss: paused, alerted, silent until RESUME, 429 cooldown >= 300 s")


def test_stop_file_and_resume_without_duplicates():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e1 = Env(td, max_replays=60)
        e1.c.run()
        done1 = e1.c.store.n("battles", "done")
        assert done1 == 60, done1
        (Path(td) / "STOP").write_text("x")
        e2 = Env(td)                         # new process, same state dir
        e2.c.run()
        assert len(e2.calls) == 0, "request sent although STOP existed"
        (Path(td) / "STOP").unlink()
        e3 = Env(td)
        e3.c.run()
        tags = []
        for p in sorted((Path(td) / "replays").glob("part-*.parquet")):
            tags += pq.read_table(p, columns=["replay_tag"])["replay_tag"].to_pylist()
        assert len(tags) == len(set(tags)), "duplicate replays across runs"
        # 12 players x 12 battles each, every battle seen from both sides -> 72 unique battles
        assert len(tags) == 72, len(tags)
        assert e1.c.cnt["paired_dupes"] + e3.c.cnt["paired_dupes"] > 0
    print("  STOP honoured, resume continued from state: 72 unique replays, 0 duplicates, pair-dedupe active")


def test_no_pair_dedupe_doubles_work():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Env(td, no_pair_dedupe=True)
        e.c.run()
        assert e.c.store.n("battles", "done") == 144


def test_floor_and_types_filter():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Env(td, floor="2026-11-30")      # every fake battle is older -> nothing queued
        e.c.run()
        assert e.c.store.n("battles", "done") == 0 and e.c.cnt["replays"] == 0


def test_real_mode_refuses_without_owner_go():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        assert C.main(["crawl", "--out", td]) == 2
        assert C.main(["probe", "--out", td]) == 2
        (Path(td) / "OWNER_GO").write_text("x")
        (Path(td) / "STOP").write_text("x")
        assert C.main(["crawl", "--out", td]) == 2      # STOP still blocks a restart


def test_dry_run_cli():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        assert C.main(["crawl", "--dry-run", "--out", td]) == 0
        assert list((Path(td) / "replays").glob("*.parquet"))


def test_leaderboard_and_history_parsers():
    html = '<a href="/player/ABC123">x</a><a href="/player/ABC123/">dup</a><a href="/clan/XYZ">c</a><a href="/player/ABC123/battles">no</a><a href="/player/Q9">y</a>'
    assert P.leaderboard_tags(html) == ["ABC123", "Q9"]
    f = C.FakeFetcher(6)
    rows, n, nxt = P.history_page(f._history("FAKE0001", 0))
    assert len(rows) == n == 10 and nxt and "before=" in nxt
    assert P.pair_key({"team_tags": "A", "opponent_tags": "B", "battle_timestamp": 5}) == \
           P.pair_key({"team_tags": "B", "opponent_tags": "A", "battle_timestamp": 5})


CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cdp_attach_to_local_chrome_full_stack():
    """Real Chrome (headless, throwaway profile) attached over CDP to a LOCAL stand-in server (BASE patched); the whole
    Crawler runs through CdpFetcher. royaleapi.com is never contacted."""
    if not CHROME.exists():
        return print("SKIP cdp (no Chrome)")
    fake = C.FakeFetcher(n_players=12, faults={12: "429"})
    port, dport = _free_port(), _free_port()
    base = f"http://127.0.0.1:{port}"
    seen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            seen.append(self.path)
            if self.path == "/":
                body, code, hdr = b"<html><body>stand-in</body></html>", 200, {}
            else:
                r = fake.get(base + self.path)
                body, code = r.text.encode(), r.status
                hdr = {"Retry-After": str(int(r.retry_after))} if r.retry_after else {}
                if code == 302:
                    hdr["Location"] = "/login"
            self.send_response(code)
            for k, v in hdr.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    td = tempfile.mkdtemp()
    proc = subprocess.Popen([str(CHROME), "--headless=new", f"--remote-debugging-port={dport}", f"--user-data-dir={td}/prof",
                             "--no-first-run", "--no-default-browser-check", base + "/"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    old = (C.BASE, C.MIN_INTERVAL, C.JITTER, C.POLL, C.RATE_COOLDOWN)
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", dport), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.2)
        time.sleep(1.0)
        C.BASE, C.MIN_INTERVAL, C.JITTER, C.POLL, C.RATE_COOLDOWN = base, 0.02, 0.01, 0.05, 0.0
        out = Path(td) / "out"
        out.mkdir()
        f = C.CdpFetcher(f"http://127.0.0.1:{dport}")
        a = _args(max_replays=20)
        resumed = []
        def alert(msg):                    # the owner: sees the 429 alert and creates RESUME
            resumed.append(msg)
            (out / "RESUME").write_text("x")
        c = C.Crawler(out, f, a, alert=alert)
        c.run()
        c.store.close()
        f.close()
        assert c.cnt["replays"] == 20 and c.cnt["rate"] == 1 and c.cnt["pauses"] == 1, c.cnt
        assert len(resumed) == 1 and "429" in resumed[0]
        assert any(p.startswith("/data/replay?tag=") for p in seen)
        n = sum(pq.read_table(p).num_rows for p in (out / "replays").glob("*.parquet"))
        assert n == 20, n
        time.sleep(1.0)
        assert proc.poll() is None, f"Chrome exited (code {proc.poll()}) after the crawler detached"
        socket.create_connection(("127.0.0.1", dport), timeout=2).close()     # the owner's Chrome is still listening
        print(f"  CDP full stack: {len(seen)} requests through Chrome, 429 -> pause -> RESUME -> 20 replays written, Chrome still open")
    finally:
        C.BASE, C.MIN_INTERVAL, C.JITTER, C.POLL, C.RATE_COOLDOWN = old
        srv.shutdown()
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(t.__name__)
        t()
    print(f"ALL {len(tests)} TESTS PASSED")

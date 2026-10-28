"""Offline tests for rc_parse / rc_crawl (ticket D2b). No network, no browser. Run: python -I test_rc.py
Fixtures: the IL_Replay sample (icebow/data/ildata_samples/hf_il_replay) and the 614 payloads saved by the 10-05 crawl
(icebow/data/royaleapi/crawl2/payloads + plays_ext_i1.csv). Tests that need a fixture print SKIP if it is missing."""
import argparse
import functools
import csv
import json
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
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

    def __init__(self, td, faults=None, n_players=12, owner=None, t0=0.0, **kw):
        self.t = t0
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
    if list(env.out.glob("PAUSED*.json")) and not (env.out / "RESUME").exists():
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
            assert not list(e.out.glob("PAUSED*.json"))
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


# ------------------------------------------------------------------------------ D2c: several lanes (one per exit IP)
class VClock:
    """Virtual time shared by lane threads: it advances only when every live lane is asleep (discrete-event), so real
    threads, the real lock and the real limiter run, but a 300 s cooldown costs no wall time."""

    def __init__(self, n, t0=0.0):
        self.t, self.active, self.wakes = t0, n, []
        self.cv = threading.Condition()

    def now(self):
        return self.t

    def sleep(self, d):
        with self.cv:
            w = self.t + max(d, 0.0)
            self.wakes.append(w)
            self.active -= 1
            self._advance()
            while self.t < w:
                assert self.cv.wait(60), "virtual clock deadlock"
            self.wakes.remove(w)
            self.active += 1

    def done(self):
        with self.cv:
            self.active -= 1
            self._advance()

    def _advance(self):
        if self.active == 0 and self.wakes:
            self.t = max(self.t, min(self.wakes))
            self.cv.notify_all()


class Lanes:
    """n lanes, each with its own FakeFetcher (same fake world = one site), sharing one Shared, on one VClock.
    calls = [(virtual time, lane, url)]. owner(env) runs after every sleep of any lane."""

    def __init__(self, td, n=3, faults=None, n_players=12, owner=None, t0=0.0, **kw):
        self.out, self.vc, self.calls, self.alerts, self.owner = Path(td), VClock(n, t0), [], [], owner
        self.olock = threading.Lock()
        a = _args(**{"min_gap": 1.0, **kw})
        self.sh = C.Shared(self.out, a)
        self.fs, self.lanes = [], []
        for i in range(n):
            f = C.FakeFetcher(n_players=n_players, faults=(faults or {}).get(i))
            real = f.get
            def get(url, manual=False, real=real, i=i):
                self.calls.append((self.vc.t, i, url))
                return real(url, manual)
            f.get = get
            c = C.Crawler(self.out, f, a, clock=self.vc.now, sleep=self.sleep, rng=random.Random(i),
                          alert=self.alerts.append, shared=self.sh, name=f"lane{i}")
            inner = c.lane_main
            def lane_main(first, inner=inner):
                try:
                    inner(first)
                finally:
                    self.vc.done()
            c.lane_main = lane_main
            self.fs.append(f)
            self.lanes.append(c)

    def sleep(self, s):
        self.vc.sleep(s)
        if self.owner:
            with self.olock:
                self.owner(self)

    def run(self):
        r = C.run_lanes(self.lanes)
        self.sh.store.close()
        return r

    def times(self, lane=None):
        return sorted(t for t, i, _ in self.calls if lane is None or i == lane)


def _max_in_window(ts, w):
    ts, j, best = sorted(ts), 0, 0
    for i in range(len(ts)):
        while ts[i] - ts[j] >= w - 1e-6:   # half-open window [ts[j], ts[j] + w)
            j += 1
        best = max(best, i - j + 1)
    return best


def _replay_tags(out):
    tags = []
    for p in sorted((Path(out) / "replays").glob("part-*.parquet")):
        tags += pq.read_table(p, columns=["replay_tag"])["replay_tag"].to_pylist()
    return tags


def test_lanes_global_rate_windows_and_no_duplicates():
    """4 lanes asking for 4 x 0.8 req/s: the global limiter must hold every 1 s window to <= 2 starts and every 60 s
    window to <= 96 (= 1.6/s), across a stop + restart; and no replay may be fetched twice by two lanes."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e1 = Lanes(td, n=4, n_players=40, max_replays=60)
        assert e1.run() == "max-replays"
        e2 = Lanes(td, n=4, n_players=40, t0=e1.vc.t)  # restart at once: wall time goes on, the persisted slot schedule too
        assert e2.run() == "frontier empty"
        ts = e1.times() + e2.times()
        assert len(ts) > 300, len(ts)
        w1, w60 = _max_in_window(ts, 1.0), _max_in_window(ts, 60.0)
        assert w1 <= 2 and w60 <= 96, (w1, w60)
        span = e2.times()[-1] - e2.times()[0]
        rate = len(e2.calls) / span
        assert 1.45 <= rate <= 1.6, rate                    # the limiter, not the lanes, sets the pace
        for e in (e1, e2):
            for i in range(4):
                lt = e.times(i)
                assert lt and min(b - a for a, b in zip(lt, lt[1:])) >= 1.0 - 1e-6     # per-lane --min-gap
        tags = _replay_tags(td)
        assert len(tags) == len(set(tags)) == 40 * 6, (len(tags), len(set(tags)))
        per_lane = {i: sum(1 for _, j, u in e2.calls if j == i and "/data/replay" in u) for i in range(4)}
        assert all(per_lane.values()), per_lane
    print(f"  4 lanes: {len(ts)} requests, max {w1} per 1 s window, {w60} per 60 s window, {rate:.3f} req/s; "
          f"{len(tags)} unique replays over a restart, 0 duplicates")


def test_late_wake_takes_a_new_slot():
    """A lane whose sleep overshoots its slot by more than LATE must not fire on that slot."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Env(td, max_replays=30, min_gap=0.0)
        slots, fires = [], []
        real_reserve = e.c.store.reserve
        def reserve(now, gap, cap):
            s = real_reserve(now, gap, cap)
            slots.append(s)
            return s
        e.c.store.reserve = reserve
        rng = random.Random(5)
        real_sleep = e.c.sleep
        e.c.sleep = lambda s: real_sleep(s + (0.3 if rng.random() < 0.3 else 0.0))
        g = e.f.get
        def get(url, manual=False):
            fires.append((e.t, slots[-1]))
            return g(url, manual)
        e.f.get = get
        e.c.run()
        assert e.c.cnt["late"] > 0
        assert all(0 <= t - s <= C.LATE + 1e-9 for t, s in fires), max(t - s for t, s in fires)
    print(f"  {e.c.cnt['late']} late wakes re-reserved; every request fired within {C.LATE}s of its slot")


def test_daily_cap_persists_across_restart():
    old = C.DAILY_CAP
    C.DAILY_CAP = 30
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e1 = Env(td)
            assert e1.c.run() == "daily cap"
            assert len(e1.calls) == 30
            e2 = Env(td, t0=3600.0)                     # restart, same UTC day
            assert e2.c.run() == "daily cap" and len(e2.calls) == 0
            assert e2.c.store.today("1970-01-01") == 30
            e3 = Env(td, t0=86_400.0 + 10)              # next UTC day: a fresh budget
            e3.c.run()
            assert 0 < len(e3.calls) <= 30
    finally:
        C.DAILY_CAP = old
    print(f"  daily cap: 30 requests then stop; restart same UTC day sends 0; next day sends {len(e3.calls)}")


def test_429_cools_only_that_lane_and_honours_retry_after():
    old = C.RATE_COOLDOWN
    C.RATE_COOLDOWN = 5                                # Retry-After (30 s from the fake) must win over the 5 s floor
    try:
        for scope in ("ip", "all"):
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                e = Lanes(td, n=3, faults={0: {10: "429"}}, auto_resume_rate=True, rate_scope=scope)
                e.run()
                lt = e.times(0)
                t429 = lt[9]
                assert lt[10] - t429 >= 30 - 1e-6, lt[10] - t429
                others = [t for t, i, _ in e.calls if i != 0 and t429 < t < t429 + 30 - 1e-6]
                assert (len(others) > 5) if scope == "ip" else not others, (scope, len(others))
                assert not e.alerts and not list(e.out.glob("PAUSED*.json"))
                assert [c.cnt["pauses"] for c in e.lanes] == [1, 0, 0]
                assert len(set(_replay_tags(td))) == 72
    finally:
        C.RATE_COOLDOWN = old
    print("  429 on lane0: lane0 silent for Retry-After 30 s while lanes 1-2 kept going (--rate-scope all: nobody did)")


def _fixing_owner_lanes(env):
    """Owner: 20 fake s after a pause file appears, fixes Chrome and creates the matching RESUME (per lane or global)."""
    env.since = getattr(env, "since", {})
    env.seen_pauses = getattr(env, "seen_pauses", {})
    for p in env.out.glob("PAUSED*.json"):
        rid = p.stem.removeprefix("PAUSED").lstrip("_")
        res = env.out / (f"RESUME_{rid}" if rid else "RESUME")
        if res.exists():
            continue
        if p.name not in env.since:
            env.since[p.name] = env.vc.t
            env.seen_pauses.setdefault(p.name, []).append(json.loads(p.read_text()))
        if env.vc.t - env.since[p.name] >= 20:
            for f in env.fs:
                f.logged_out = False
            res.write_text("x")
            del env.since[p.name]


def test_challenge_or_login_pauses_only_that_lane():
    """10-28 rule: a challenge / login loss / first 403 on one IP pauses ONLY that lane (alert names it) until its own
    RESUME_<port>; the other lanes keep collecting; the trigger path is recorded."""
    for kind, label in (("challenge", "challenge"), ("403", "blocked"), ("login", "login")):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e = Lanes(td, n=3, faults={2: {8: kind}}, owner=_fixing_owner_lanes)
            assert e.run() == "frontier empty"
            mine = [(t, u) for t, i, u in e.calls if i == 2]
            tc = next(t for t, u in mine if "/me" in u) if kind == "login" else mine[7][0]
            assert not [t for t, _ in mine if tc < t < tc + 20 - 1e-6], kind          # lane2 silent until its RESUME
            others = [t for t, i, _ in e.calls if i != 2 and tc < t < tc + 20 - 1e-6]
            assert len(others) >= 10, (kind, len(others))                              # lanes 0-1 kept going
            al = [a for a in e.alerts if f"({label})" in a]
            assert len(al) == 1 and "lane2" in al[0] and "RESUME_lane2" in al[0] and "other lanes keep" in al[0], al
            info = e.seen_pauses["PAUSED_lane2.json"][0]
            assert info["lane"] == "lane2" and not (e.out / "PAUSED.json").exists()
            if kind != "login":                        # the request that was blocked: path + status, nothing else
                trig = info["trigger"]
                assert trig["path"].startswith("/") and "?" not in trig["path"] and trig["status"] == 403, trig
                assert set(trig) == {"path", "status", "cf_mitigated", "title", "manual"}
                st = C.Store(e.out / "state.db")
                assert st.meta("blocks")[-1]["path"] == trig["path"] and st.meta("blocks")[-1]["port"] == "lane2"
                st.close()
            assert not list(e.out.glob("PAUSED*.json")) and not (e.out / "STOP").exists()
            assert len(set(_replay_tags(td))) == 72
    print("  challenge / first 403 / login loss on lane2: only lane2 paused until RESUME_lane2, lanes 0-1 went on, "
          "one alert naming it, trigger path recorded")


def test_still_blocked_after_resume_is_a_ban_and_stops_all():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Lanes(td, n=3, faults={2: {8: "403", 9: "403"}}, owner=_fixing_owner_lanes)
        assert e.run().startswith("BANNED")
        mine = e.times(2)
        tban = mine[8]                                  # first request after RESUME_lane2: 403 again
        assert mine[8] - mine[7] >= 20 - 1e-6
        assert max(e.times()) <= tban + 1e-9, "a lane sent after the ban"
        assert (e.out / "STOP").exists() and json.loads((e.out / "BANNED.json").read_text())["lane"] == "lane2"
        assert sum("STOPPED ALL" in a for a in e.alerts) == 1
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:   # single lane, plain RESUME: same rule
        e = Env(td, faults={30: "403", 31: "403"}, owner=fixing_owner)
        assert e.c.run().startswith("BANNED") and len(e.calls) == 31 and (e.out / "STOP").exists()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:   # 403 once, fine after RESUME: goes on
        e = Env(td, faults={30: "403"}, owner=fixing_owner)
        assert e.c.run() == "frontier empty" and not (e.out / "STOP").exists()
        assert e.calls[30][0] - e.calls[29][0] >= 20
    print("  403 again on the first request after RESUME: BANNED, STOP file, all lanes stopped, one alert; "
          "a single 403 cleared by the owner just pauses")


def test_repeated_5xx_halts_all_lanes():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        e = Lanes(td, n=3, faults={1: {k: "500" for k in (6, 7, 8, 9)}}, owner=_fixing_owner_lanes)
        assert e.run() == "frontier empty"
        th = e.times(1)[8]                              # 4th consecutive 500: service disruption
        assert not [t for t in e.times() if th < t < th + 20 - 1e-6]
        assert e.seen_pauses["PAUSED.json"][0]["kind"] == "server"
        assert len(set(_replay_tags(td))) == 72
    print("  4 x HTTP 500 on lane1: ALL lanes paused until RESUME")


def test_single_lane_challenge_pauses_and_names_the_port():
    """Today's one-IP crawl: a challenge pauses the lane (PAUSED_<port>.json), alert names the port, plain RESUME or
    RESUME_<port> resumes; the global PAUSED.json is not used."""
    for resume in ("RESUME", "RESUME_9222"):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e = Env(td, faults={30: "challenge"}, max_replays=40)
            e.c.rid, e.c.pfile, e.c.rfile = "9222", e.out / "PAUSED_9222.json", e.out / "RESUME_9222"
            def owner(env, resume=resume):
                if (env.out / "PAUSED_9222.json").exists() and not (env.out / resume).exists():
                    env._s = getattr(env, "_s", None) or env.t
                    if env.t - env._s >= 20:
                        (env.out / resume).write_text("x")
            e.owner = owner
            e.c.run()
            assert e.calls[30][0] - e.calls[29][0] >= 20 and e.c.cnt["replays"] == 40
            assert len(e.alerts) == 1 and "port 9222" in e.alerts[0] and "(challenge)" in e.alerts[0]
            assert not list(e.out.glob("PAUSED*.json")) and not list(e.out.glob("RESUME*"))
    print("  single lane: challenge -> PAUSED_9222.json, alert names port 9222, RESUME or RESUME_9222 resumes")


def test_stop_file_stops_all_lanes():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        def owner(env):
            if env.vc.t >= 50 and not (env.out / "STOP").exists():
                (env.out / "STOP").write_text("x")
                env.t_stop = env.vc.t
        e = Lanes(td, n=3, owner=owner)
        assert e.run() == "STOP file"
        assert max(e.times()) <= e.t_stop + 1e-9, (max(e.times()), e.t_stop)
    print(f"  STOP at t={e.t_stop:.1f}: no lane sent anything after it")


def test_instance_lock():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        p = Path(td) / "x.lock"
        a = C.instance_lock(p)
        assert a is not None and C.instance_lock(p) is None
        a.close()
        b = C.instance_lock(p)
        assert b is not None
        b.close()


def test_lanes_json_commands():
    ls = C.lane_commands(json.loads(C.LANES_JSON.read_text()))
    assert len({ln["cdp_port"] for ln in ls}) == len(ls)
    pod = [ln for ln in ls if ln["tunnel"]]
    assert pod and all("-D" in ln["tunnel"] and "--proxy-server=" in ln["chrome"] for ln in pod)
    assert all(ln["tunnel"][ln["tunnel"].index("-D") + 1] == f"127.0.0.1:{ln['socks_port']}" for ln in pod)


def test_cdp_two_chromes_two_lanes_real_time():
    """Two real headless Chromes = two lanes in threads (each builds its own Playwright), real clock, the real
    GLOBAL_GAP, against a LOCAL stand-in. Arrival times at the server: never 3 within 1 s. The exit-IP check sees the
    same IP for both and is refused. royaleapi.com is never contacted."""
    if not CHROME.exists():
        return print("SKIP cdp2 (no Chrome)")
    fake = C.FakeFetcher(n_players=12)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    seen, flock = [], threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/favicon.ico":            # Chrome's own tab-load request, not the crawler's
                body, code = b"", 404
            elif self.path == "/ip":
                body, code = b"127.0.0.1", 200
            elif self.path == "/":
                body, code = b"<html><body>stand-in</body></html>", 200
            else:
                with flock:
                    seen.append((time.monotonic(), self.path))
                    r = fake.get(base + self.path)
                body, code = r.text.encode(), r.status
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)     # a single-threaded server queues requests behind an idle
    srv.daemon_threads = True                              # Chrome preconnect socket and logs them in bursts
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    td = tempfile.mkdtemp()
    procs, dports = [], [_free_port(), _free_port()]
    for k, dp in enumerate(dports):
        procs.append(subprocess.Popen([str(CHROME), "--headless=new", f"--remote-debugging-port={dp}",
                                       f"--user-data-dir={td}/prof{k}", "--no-first-run", "--no-default-browser-check",
                                       base + "/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    old = (C.BASE, C.MIN_INTERVAL, C.JITTER, C.IPECHO)
    try:
        for dp in dports:
            for _ in range(100):
                try:
                    socket.create_connection(("127.0.0.1", dp), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.2)
        time.sleep(1.0)
        C.BASE, C.MIN_INTERVAL, C.JITTER, C.IPECHO = base, 0.05, 0.01, base + "/ip"
        cdps = [f"http://127.0.0.1:{dp}" for dp in dports]
        ips, problem = C.check_ips(cdps)
        assert ips == ["127.0.0.1", "127.0.0.1"] and problem.startswith("two lanes share an exit IP"), (ips, problem)
        out = Path(td) / "out"
        out.mkdir()
        a = _args(max_replays=12)
        sh = C.Shared(out, a)
        lanes = [C.Crawler(out, functools.partial(C.CdpFetcher, u), a, shared=sh, name=f"lane{i}")
                 for i, u in enumerate(cdps)]
        t0 = time.monotonic()
        assert C.run_lanes(lanes) == "max-replays"
        wall = time.monotonic() - t0
        sh.store.close()
        assert all(c.cnt["req"] > 3 for c in lanes), [c.cnt["req"] for c in lanes]
        ts = [t for t, _ in seen]
        gaps3 = [b - a for a, b in zip(ts, ts[2:])]
        k = min(range(len(gaps3)), key=gaps3.__getitem__)
        assert min(gaps3) >= 1.0, (min(gaps3), [(round(t - ts[0], 3), u[:40]) for t, u in seen[k:k + 3]])
        assert min(b - a for a, b in zip(ts, ts[1:])) >= C.GLOBAL_GAP - C.LATE - 0.05, seen[:6]
        assert len(set(_replay_tags(out))) >= 12
        assert all(p.poll() is None for p in procs), "a Chrome exited after the lanes detached"
        print(f"  2 Chromes / 2 lanes: {len(ts)} requests in {wall:.1f}s = {len(ts) / wall:.2f}/s; any 3 arrivals span "
              f">= {min(gaps3):.3f}s; min gap {min(b - a for a, b in zip(ts, ts[1:])):.3f}s; same-IP lanes refused")
    finally:
        C.BASE, C.MIN_INTERVAL, C.JITTER, C.IPECHO = old
        srv.shutdown()
        for p in procs:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(t.__name__)
        t()
    print(f"ALL {len(tests)} TESTS PASSED")

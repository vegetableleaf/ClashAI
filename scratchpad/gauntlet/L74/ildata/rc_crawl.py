"""Resumable RoyaleAPI replay crawler for the LAPTOP (ticket D2b, plan1026 Pillar 4e). Read CRAWL.md first.

Transport: attaches over CDP to a Chrome the OWNER started, cleared (Cloudflare) and logged into. Every request is an
in-page fetch() of that Chrome: no cookie, clearance or session value is read, copied or saved. <= 1 request/s with
jitter, one in flight. On a challenge page / 429 / 403 / login loss it PAUSES, alerts Discord and waits for the owner
(RESUME file); it never retries a blocked request by itself and never touches Cloudflare.

  python rc_crawl.py crawl --dry-run          # state machine against a fake fetcher, no browser, no network
  python rc_crawl.py probe                    # (needs OWNER_GO) <= 5 requests, saves raw pages for a selector check
  python rc_crawl.py crawl [--max-replays N]  # (needs OWNER_GO)
  python rc_crawl.py crawl --cdp URL1 --cdp URL2 ...   # D2c: one lane per Chrome (= per exit IP), see CRAWL.md
  python rc_crawl.py lanes [--start-tunnels] | ips --cdp URL ...   # setup helpers (no royaleapi.com request)
  python rc_crawl.py status | stop | resume

Control files live in --out (default icebow/data/crawl, untracked): OWNER_GO (must exist for any real request),
STOP (finish cleanly; remove it before restarting), RESUME (owner touches it after fixing Chrome), PAUSED.json (why).

D2c limits (RoyaleAPI's written conditions, accepted by the owner): every request of every lane takes a slot from ONE
limiter persisted in state.db (GLOBAL_GAP between starts, <= 1.6/s; DAILY_CAP per UTC day); each lane also keeps its
own --min-gap. A 429 cools only that lane (--auto-resume-rate). A challenge / login loss / first 403 on a lane
writes PAUSED_<port>.json: only that lane waits for RESUME_<port> (10-28); still blocked right after RESUME = ban = STOP all.
Repeated 5xx halts all (PAUSED.json). Only one real instance runs at a time (LOCK).
"""
from __future__ import annotations

import argparse
import csv
import functools
import gzip
import json
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc_parse as P  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
OUT_DEFAULT = REPO / "icebow" / "data" / "crawl"
POST = REPO / "scratchpad" / "gauntlet" / "L69" / "discord" / "post.py"
BASE = "https://royaleapi.com"   # test_rc.py points this at a local server; nothing else changes it
MIN_INTERVAL = 8.0          # per-lane (= per-IP) seconds between request starts; jitter is ADDED (--min-gap)
JITTER = 0.5
# Global limiter, all lanes + restarts (RoyaleAPI: 2/s and 150k/day combined; ours below both). A lane fires within
# LATE of its slot or takes a new one, so starts are >= GLOBAL_GAP - LATE = 0.53 s apart, any 3 starts span >= 1.16 s
# (<= 2 per 1 s window) and any 60 s window holds <= ceil(60.1 / 0.63) = 96 starts (= 1.6/s).
GLOBAL_GAP = 0.63
LATE = 0.1
DAILY_CAP = 140_000         # requests per UTC day (1.6/s for 24 h is 138,240, so this is a backstop)
LOCK = REPO / "icebow" / "data" / "crawl_instance.lock"    # one real crawler process on this laptop at a time
IPECHO = "https://api.ipify.org"                           # exit-IP check page (not royaleapi.com)
LANES_JSON = Path(__file__).resolve().parent / "lanes.json"
LOW_WATER = 50              # fetch a history page when fewer than this many replays are queued
FLUSH_ROWS, FLUSH_SECS = 500, 300
POLL = 5.0                  # seconds between STOP/RESUME checks while paused
RATE_COOLDOWN = 300         # first 429 pause floor in seconds; doubles per consecutive pause, max 3600
REMIND = 1800               # Discord reminder while still paused
SEED_CSVS = [REPO / "icebow/data/royaleapi/battles.csv", REPO / "icebow/data/royaleapi/crawl2/battles.csv"]


class Stop(Exception):
    """STOP file seen, disk low, or max-replays reached: finish cleanly."""


class FetchError(Exception):
    """Transport-level failure (network, tab gone)."""


@dataclass
class Resp:
    status: int
    text: str = ""
    retry_after: float | None = None
    cf: str = ""
    redirected: bool = False    # fetch followed a redirect: one more request reached the site


def is_challenge(r: Resp) -> bool:
    return r.cf == "challenge" or "<title>Just a moment" in r.text[:4000]


# ------------------------------------------------------------------------------------------ transports
_FETCH_JS = """async ([url, manual, timeout]) => {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeout);
    try {
        const r = await fetch(url, {credentials: 'same-origin', signal: ctl.signal,
                                    redirect: manual ? 'manual' : 'follow'});
        return {status: r.type === 'opaqueredirect' ? 302 : r.status,
                cf: r.headers.get('cf-mitigated') || '', ra: r.headers.get('retry-after') || '',
                rd: r.redirected, text: manual ? '' : await r.text()};
    } finally { clearTimeout(timer); }
}"""


class CdpFetcher:
    """In-page fetch() through the owner's Chrome (started with --remote-debugging-port). Never creates a tab,
    never navigates, never reads cookies."""

    def __init__(self, cdp_url: str):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            self._pw.stop()
            raise FetchError(f"cannot attach to Chrome at {cdp_url}: {e.__class__.__name__}") from e
        self.page = None

    def _page(self):
        if self.page is not None and not self.page.is_closed() and self.page.url.startswith(BASE):
            return self.page
        for ctx in self._browser.contexts:
            for pg in ctx.pages:
                if not pg.is_closed() and pg.url.startswith(BASE):
                    self.page = pg
                    return pg
        raise FetchError("no royaleapi.com tab open in the attached Chrome")

    def get(self, url: str, manual: bool = False) -> Resp:
        from playwright.sync_api import Error as PwError
        try:
            r = self._page().evaluate(_FETCH_JS, [url, manual, 45_000])
        except PwError as e:
            raise FetchError(e.__class__.__name__) from e
        ra = float(r["ra"]) if re.fullmatch(r"\d+(\.\d+)?", r.get("ra") or "") else None
        return Resp(r["status"], r["text"], ra, r["cf"], bool(r.get("rd")))

    def exit_ip(self) -> str:
        """This Chrome's exit IP: a NEW tab loads IPECHO and is closed again (the royaleapi.com tab is not touched;
        a proxied Chrome sends it through its SOCKS tunnel, unlike a request made by Playwright itself)."""
        from playwright.sync_api import Error as PwError
        try:
            pg = self._browser.contexts[0].new_page()
            try:
                pg.goto(IPECHO, timeout=30_000)
                ip = pg.inner_text("body").strip()
            finally:
                pg.close()
        except PwError as e:
            raise FetchError(f"exit-IP check failed: {e.__class__.__name__}") from e
        if not re.fullmatch(r"[0-9A-Fa-f:.]{3,45}", ip):
            raise FetchError(f"exit-IP check page did not return an IP: {ip[:80]!r}")
        return ip

    def close(self) -> None:
        self._pw.stop()         # drops the CDP connection; Chrome and its tabs stay open


class FakeFetcher:
    """Dry-run world: `n_players` fake players, 12 battles each; every battle appears in both players' histories
    (different replay tags) so pair-dedupe is exercised. `faults` = {request ordinal: kind}."""

    def __init__(self, n_players: int = 40, faults: dict | None = None):
        self.n, self.faults, self.calls = n_players, dict(faults or {}), 0
        self.log: list[str] = []
        self.logged_out = self.pending_login = False

    def _tag(self, i): return f"FAKE{i % self.n:04d}"

    def _battles(self, tag):
        """12 battles per player against the 6 players after and 6 before it; a pair has ONE timestamp, so both
        players' histories show the same battle (pair-dedupe must collapse them)."""
        me, out = int(tag[4:]), []
        for d in range(1, 7):
            for other, lo in (((me + d) % self.n, me), ((me - d) % self.n, (me - d) % self.n)):
                out.append((1_793_000_000 - (lo * 6 + d) * 60, other))
        return sorted(out, reverse=True)

    def _history(self, tag, before):
        rows = []
        for ts, opp in self._battles(tag):
            if before and ts * 1000 >= before:
                continue
            rt = f"{tag}x{ts}"
            rows.append(
                f'<div class="battle_list_battle battletype-pathOfLegend {"blue" if ts % 2 else "red"}" data-timestamp="{ts}.0">'
                f'<div class="battle-timestamp-popup" data-content="t{ts}"></div>'
                f'<button class="replay_button" data-replay="{rt}" data-team-tags="{tag}" data-opponent-tags="{self._tag(opp)}"'
                f' data-team-crowns="{ts % 3}" data-opponent-crowns="{(ts + 1) % 3}"></button>'
                f'<button class="matchup_button" data-team-deck="knight,the-log,x-bow,rocket,tesla-ev1,skeletons,tornado,ice-wizard"'
                f' data-opponent-deck="hog-rider,musketeer,fireball,zap,cannon,ice-spirit,skeletons,the-log"></button></div>')
            if len(rows) == 10:
                nxt = f'<a href="/player/{tag}/battles/history?before={ts * 1000}"><i class="right icon"></i></a>'
                return "<html>" + "".join(rows) + nxt + "</html>"
        return "<html>" + "".join(rows) + "</html>"

    def _replay(self, tag):
        cards = "".join(
            f'<img class="replay_card" data-card="{c}" data-s="{s}" data-t="{t}" data-ability="0" src=""/>'
            for c, s, t in (("knight", "blue", 200), ("hog-rider", "red", 260), ("the-log", "blue", 400)))
        marks = "".join(
            f'<div class="{"blue" if s == "t" else "red"} marker" data-x="{x}" data-y="14500" data-c="{c}" data-t="{t}" data-i="{self.calls % 2}" data-s="{s}"></div>'
            for c, s, t, x in (("knight", "t", 200, 9500), ("hog-rider", "o", 260, 8500), ("the-log", "t", 400, 9000)))
        tbl = ('<table class="replay_elixir_table"><tr><td>Total</td><td>3</td><td>9</td></tr>'
               '<tr><td>Leaked</td><td colspan="2">0.5</td></tr></table>')
        return f'<div class="battle_replay" data-tag="{tag}"><div class="replay_timeline">{cards}</div>{marks}{tbl}{tbl}</div>'

    def get(self, url: str, manual: bool = False) -> Resp:
        self.calls += 1
        self.log.append(url)
        fault = self.faults.pop(self.calls, None)
        if fault == "net":
            raise FetchError("fake network error")
        if fault == "challenge":
            return Resp(403, "<html><title>Just a moment...</title></html>", cf="challenge")
        if fault == "429":
            return Resp(429, "", retry_after=30.0)
        if fault == "500":
            return Resp(500, "<html>Server error</html>")
        if fault == "403":
            return Resp(403, "<html>Forbidden</html>")
        self.pending_login |= fault == "login"
        path = url.removeprefix(BASE)
        if self.pending_login and path.startswith("/data/replay"):
            self.logged_out, self.pending_login = True, False
        if path.startswith("/me"):
            return Resp(302 if self.logged_out else 200)
        if path.startswith("/players"):
            return Resp(200, "<html>" + "".join(f'<a href="/player/{self._tag(i)}">p</a>' for i in range(3)) + "</html>")
        m = re.match(r"/player/(\w+)/battles/history(?:\?before=(\d+))?", path)
        if m:
            return Resp(200, self._history(m.group(1), int(m.group(2) or 0)))
        if path.startswith("/data/replay"):
            if self.logged_out:
                return Resp(200, json.dumps({"success": False}))
            tag = re.search(r"tag=([^&]+)", path).group(1)
            return Resp(200, json.dumps({"success": True, "html": self._replay(tag)}))
        return Resp(404)


# ------------------------------------------------------------------------------------------ state
def _locked(fn):
    @functools.wraps(fn)
    def w(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    return w


class Store:
    """sqlite: players frontier, battles queue (dedupe by replay tag and by battle pair), counters, and the global
    request limiter (next slot + per-UTC-day count). One connection shared by the lane threads under one lock."""

    def __init__(self, path: Path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS players(tag TEXT PRIMARY KEY, status TEXT, next_path TEXT, pages INT DEFAULT 0,
                prio INT, added INT, source TEXT);
            CREATE INDEX IF NOT EXISTS players_q ON players(status, prio, added);
            CREATE TABLE IF NOT EXISTS battles(replay_tag TEXT PRIMARY KEY, pair_key TEXT UNIQUE, status TEXT, ts INT,
                player_tag TEXT, tries INT DEFAULT 0, row_json TEXT, row_html BLOB);
            CREATE INDEX IF NOT EXISTS battles_q ON battles(status, ts);
            CREATE TABLE IF NOT EXISTS daily(day TEXT PRIMARY KEY, n INT);
        """)

    @_locked
    def reserve(self, now: float, gap: float, cap: int) -> float | None:
        """Take the next global request slot: >= now and >= gap after the previous slot of ANY lane (also across a
        restart: the schedule is persisted). Counts it in today's UTC total; None once the total has reached cap."""
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        n = self.today(day)
        if n >= cap:
            return None
        nxt = self.meta("next_slot", 0.0)
        slot = now if nxt > now + 60 else max(now, nxt)     # a clock stepped back must not stall the crawl
        self.db.execute("INSERT OR REPLACE INTO daily VALUES(?,?)", (day, n + 1))
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('next_slot',?)", (json.dumps(slot + gap),))
        self.db.commit()
        return slot

    @_locked
    def today(self, day: str) -> int:
        r = self.db.execute("SELECT n FROM daily WHERE day=?", (day,)).fetchone()
        return r[0] if r else 0

    @_locked
    def recover(self) -> None:
        """Crash recovery: replays fetched but not flushed, and players whose page was in flight, go back to the queue."""
        self.db.execute("UPDATE battles SET status='todo' WHERE status='buf'")
        self.db.execute("UPDATE players SET status=CASE WHEN next_path IS NULL THEN 'todo' ELSE 'active' END "
                        "WHERE status='busy'")
        self.db.commit()

    @_locked
    def claim_player(self):
        r = self.next_player()
        if r:
            self.db.execute("UPDATE players SET status='busy' WHERE tag=?", (r[0],))
            self.db.commit()
        return r

    @_locked
    def claim_battle(self):
        r = self.next_battle()
        if r:
            self.set_battle(r[0], "buf")                    # no other lane picks it; reset to todo on a restart
        return r

    @_locked
    def meta(self, k, default=None):
        r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    @_locked
    def set_meta(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))
        self.db.commit()

    @_locked
    def add_players(self, tags, source: str, prio: int, cap: int = 500_000) -> int:
        if self.db.execute("SELECT COUNT(*) FROM players WHERE status IN ('todo','active')").fetchone()[0] >= cap:
            return 0
        now = int(time.time())
        n = self.db.total_changes
        self.db.executemany("INSERT OR IGNORE INTO players(tag,status,prio,added,source) VALUES(?,?,?,?,?)",
                            [(t, "todo", prio, now, source) for t in tags])
        self.db.commit()
        return self.db.total_changes - n

    @_locked
    def next_player(self):
        return self.db.execute("SELECT tag,next_path,pages FROM players WHERE status IN ('todo','active') "
                               "ORDER BY (status='active') DESC, prio, added LIMIT 1").fetchone()

    @_locked
    def update_player(self, tag, status, next_path=None, pages=0):
        self.db.execute("UPDATE players SET status=?, next_path=?, pages=? WHERE tag=?", (status, next_path, pages, tag))
        self.db.commit()

    @_locked
    def add_battles(self, rows, player_tag, pair_dedupe=True) -> int:
        n = self.db.total_changes
        for r in rows:
            light = {k: v for k, v in r.items() if k != "row_html"}
            self.db.execute("INSERT OR IGNORE INTO battles(replay_tag,pair_key,status,ts,player_tag,row_json,row_html) "
                            "VALUES(?,?,?,?,?,?,?)",
                            (r["replay_tag"], P.pair_key(r) if pair_dedupe else r["replay_tag"], "todo", r["battle_timestamp"],
                             player_tag, json.dumps(light), _z(r["row_html"])))
        self.db.commit()
        return self.db.total_changes - n

    @_locked
    def next_battle(self):
        return self.db.execute("SELECT replay_tag,player_tag,row_json,tries FROM battles WHERE status='todo' "
                               "ORDER BY ts DESC LIMIT 1").fetchone()

    @_locked
    def set_battle(self, tag, status, tries=None):
        self.db.execute("UPDATE battles SET status=?, tries=COALESCE(?, tries) WHERE replay_tag=?", (status, tries, tag))
        self.db.commit()

    @_locked
    def done(self, tags):
        self.db.executemany("UPDATE battles SET status='done' WHERE replay_tag=?", [(t,) for t in tags])
        self.db.commit()

    @_locked
    def counts(self) -> dict:
        c = {f"battles_{s}": n for s, n in self.db.execute("SELECT status, COUNT(*) FROM battles GROUP BY status")}
        c.update({f"players_{s}": n for s, n in self.db.execute("SELECT status, COUNT(*) FROM players GROUP BY status")})
        return c

    @_locked
    def n(self, table, status) -> int:
        return self.db.execute(f"SELECT COUNT(*) FROM {table} WHERE status=?", (status,)).fetchone()[0]

    @_locked
    def close(self) -> None:
        self.db.close()

    @_locked
    def has_player_work(self) -> bool:
        return self.next_player() is not None


def _z(s: str) -> bytes:
    import zlib
    return zlib.compress(s.encode("utf-8"), 6)


class Writer:
    """Buffers parsed replays and writes numbered parquet parts (replays/, actions/) + a raw gz shard. The sqlite
    'done' mark follows the file write, so a crash can duplicate one buffer on resume (dedupe on replay_tag at read
    time) but never lose one. ponytail: no atomic two-phase commit; upgrade if duplicates ever matter."""

    def __init__(self, out: Path, store: Store, keep_raw: bool = True):
        self.out, self.store, self.keep_raw = out, store, keep_raw
        self.lock = store.lock
        for d in ("replays", "actions", "raw"):
            (out / d).mkdir(parents=True, exist_ok=True)
        self.r, self.a, self.raw, self.tags = [], [], [], []
        self.last = time.monotonic()

    @_locked
    def add(self, tag, rrow, arows, html):
        self.r.append(rrow)
        self.a.extend(arows)
        self.tags.append(tag)
        if self.keep_raw:
            self.raw.append({"tag": tag, "html": html})

    @_locked
    def due(self) -> bool:
        return len(self.tags) >= FLUSH_ROWS or (self.tags and time.monotonic() - self.last >= FLUSH_SECS)

    @_locked
    def flush(self) -> int:
        if not self.tags:
            return 0
        n = 1 + max([int(p.stem.split("-")[1]) for p in (self.out / "replays").glob("part-*.parquet")] or [-1])
        rt, at = P.to_tables(self.r, self.a)
        for name, tbl in (("replays", rt), ("actions", at)):
            tmp = self.out / name / f"part-{n:06d}.tmp"
            pq.write_table(tbl, tmp, compression="zstd")
            tmp.replace(self.out / name / f"part-{n:06d}.parquet")
        if self.raw:
            with gzip.open(self.out / "raw" / f"raw-{n:06d}.jsonl.gz", "wt", encoding="utf-8", compresslevel=6) as f:
                f.writelines(json.dumps(x) + "\n" for x in self.raw)
        self.store.done(self.tags)
        k = len(self.tags)
        self.r, self.a, self.raw, self.tags = [], [], [], []
        self.last = time.monotonic()
        return k


# ------------------------------------------------------------------------------------------ crawler
class Shared:
    """What the lanes of one process share: the sqlite store and the parquet writer (both under store.lock), the first
    stop reason (every lane stops on it), and the cool-all / reminder clocks."""

    def __init__(self, out: Path, args):
        self.store = Store(out / "state.db")
        self.writer = Writer(out, self.store, keep_raw=not args.no_raw)
        self.lock = self.store.lock
        self.stop = None
        self.seeded = False
        self.busy = 0                       # lanes with a claimed player / battle in flight
        self.replays = 0
        self.cool_all = self.last_alert = float("-inf")


class Crawler:
    """One lane = one fetcher = one Chrome = one exit IP. Several lanes share one Shared and run under run_lanes()."""

    def __init__(self, out: Path, fetcher, args, clock=time.time, sleep=time.sleep, rng=None, alert=None,
                 shared: Shared | None = None, name: str = "lane0", rid: str | None = None, ip: str | None = None):
        self.out, self.f, self.a, self.name = out, fetcher, args, name
        # per-IP pause (10-28 RoyaleAPI reply): PAUSED_<rid>.json holds only this lane until the owner creates
        # RESUME_<rid> (rid = the Chrome's debug port); a sole lane also accepts the plain RESUME
        self.rid, self.ip = rid or name, ip
        self.pfile, self.rfile = out / f"PAUSED_{self.rid}.json", out / f"RESUME_{self.rid}"
        self.sole = True                            # run_lanes sets it
        self.after_resume = False                   # the next response is the first after an owner RESUME
        self.lane_alert = float("-inf")
        self.clock, self.sleep, self.rng = clock, sleep, rng or random.Random()
        self.alert_fn = alert or (lambda msg: None)
        self.sh = shared or Shared(out, args)
        self.store, self.writer = self.sh.store, self.sh.writer
        self.last = self.cool_until = float("-inf")
        self.consec = 0
        self.cnt = {k: 0 for k in ("req", "ok", "rate", "challenge", "blocked", "server", "neterr", "login", "pauses",
                                   "replays", "refused", "history_pages", "paired_dupes", "late")}
        self.floor = int(datetime.fromisoformat(args.floor).replace(tzinfo=timezone.utc).timestamp())
        self.types = set(args.types.split(","))
        self.t0 = self.clock()

    # ---- control
    def _stop(self) -> None:
        if self.sh.stop:
            raise Stop(self.sh.stop)
        if (self.out / "STOP").exists():
            raise Stop("STOP file")

    def _alert(self, msg: str) -> None:
        try:
            self.alert_fn(msg)
        except Exception:
            pass                                    # never let an alert failure kill the crawl

    def _nap(self, s: float) -> None:
        """Sleep s seconds in POLL chunks so STOP is seen promptly."""
        end = self.clock() + s
        while (left := end - self.clock()) > 1e-6:
            self._stop()
            self.sleep(min(left, POLL))

    def _gate(self) -> None:
        """This lane's own gap (per IP), then a slot from the global limiter shared by every lane."""
        self._nap(self.last + getattr(self.a, "min_gap", MIN_INTERVAL) + self.rng.uniform(0, JITTER) - self.clock())
        while True:
            slot = self.store.reserve(self.clock(), GLOBAL_GAP, DAILY_CAP)
            if slot is None:
                raise Stop("daily cap")
            self._nap(slot - self.clock())
            if self.clock() - slot <= LATE:
                break
            self.cnt["late"] += 1                   # woke too late: firing now could crowd the next lane's slot
        self.last = self.clock()

    def _halted(self) -> bool:
        return ((self.out / "PAUSED.json").exists() or self.pfile.exists()
                or self.clock() < max(self.cool_until, self.sh.cool_all))

    def _who(self) -> str:
        return f"{self.name} (port {self.rid}, exit IP {self.ip or 'not checked'})"

    def _hold(self) -> None:
        """Before every request: STOP; this lane's (or all lanes') 429 cooldown; a global halt (PAUSED.json: repeated
        5xx = service disruption, or a file left by an older run) until RESUME; then this lane's own pause
        (PAUSED_<rid>.json: challenge / login loss / first 403 / network) until RESUME_<rid>. Never before not_before."""
        p, res = self.out / "PAUSED.json", self.out / "RESUME"
        while True:
            self._stop()
            cool = max(self.cool_until, self.sh.cool_all) - self.clock()
            if cool > 0:
                self._nap(cool)
                continue
            with self.sh.lock:
                if p.exists():
                    f, rf, scope = p, res, "ALL lanes wait"
                elif self.pfile.exists():
                    rf = self.rfile if self.rfile.exists() or not self.sole else res
                    f, scope = self.pfile, f"only {self._who()} waits; other lanes go on"
                else:
                    return
                try:
                    info = json.loads(f.read_text())
                except (OSError, ValueError):
                    info = {}
                if rf.exists() and self.clock() >= info.get("not_before", 0):
                    rf.unlink(missing_ok=True)
                    f.unlink(missing_ok=True)
                    if f is self.pfile:
                        self.after_resume = True    # a 403 on the next response = permanent ban
                    continue
                last = self.sh.last_alert if f is p else self.lane_alert
                remind = self.clock() - last >= REMIND
                if remind:
                    if f is p:
                        self.sh.last_alert = self.clock()
                    else:
                        self.lane_alert = self.clock()
            if remind:
                self._alert(f"RoyaleAPI crawl still PAUSED ({info.get('kind', '?')}, {info.get('lane', '?')}): "
                            f"{info.get('why', '')} {scope}. Fix that Chrome window by hand, then create {rf}.")
            self.sleep(POLL)

    def _record(self, kind: str, trigger: dict | None) -> None:
        if trigger:
            with self.sh.lock:
                self.store.set_meta("blocks", (self.store.meta("blocks", []) or [])[-199:] + [
                    {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lane": self.name, "port": self.rid,
                     "ip": self.ip, "kind": kind, **trigger}])

    def _pause(self, kind: str, why: str, retry_after: float | None = None, trigger: dict | None = None) -> None:
        """trigger: the request that caused it (URL path without the query, HTTP status, cf-mitigated header,
        page title) -> PAUSED*.json and state.db meta 'blocks', so the owner can tell RoyaleAPI which endpoint
        answered what. No cookie, no other header, no body is recorded."""
        self.consec += 1
        self.cnt["pauses"] += 1
        cool = max(retry_after or 0, min(3600, RATE_COOLDOWN * 2 ** (self.consec - 1))) if kind == "rate" else 0
        # owner 10-27: --auto-resume-rate continues after a 429 cooldown by itself, on this lane only (or on all lanes
        # with --rate-scope all)
        if kind == "rate" and getattr(self.a, "auto_resume_rate", False):
            until = self.clock() + cool
            scope = getattr(self.a, "rate_scope", "ip")
            if scope == "all":
                with self.sh.lock:
                    self.sh.cool_all = max(self.sh.cool_all, until)
            else:
                self.cool_until = until
            print(f"[crawl] {self.name} 429: cooling {'ALL lanes' if scope == 'all' else 'this lane'} {int(cool)}s, "
                  f"then continuing (consecutive {self.consec})", flush=True)
            return
        self.writer.flush()
        self._record(kind, trigger)
        where = f" [{trigger['path']} -> HTTP {trigger['status']}]" if trigger else ""
        everyone = kind == "server"                 # repeated 5xx = service disruption: every lane pauses
        p = self.out / "PAUSED.json" if everyone else self.pfile
        rf = self.out / "RESUME" if everyone else self.rfile
        msg = (f"RoyaleAPI crawl PAUSED ({kind}) on {self._who()}{where}: {why.rstrip('.')}. "
               + ("ALL lanes stopped. " if everyone else "Only this IP is paused; other lanes keep collecting. ")
               + f"Nothing is retried on it until you fix that Chrome window by hand (clear the check / log in / wait) "
                 f"and create {rf.name} (`rc_crawl.py resume" + ("" if everyone else f" --lane {self.rid}") + "`). "
               f"Cooldown {int(cool)}s. Done so far: {self.sh.replays} replays this run.")
        with self.sh.lock:
            first = not p.exists()                  # already halted: one alert is enough
            if first:
                info = {"kind": kind, "why": why, "lane": self.name, "port": self.rid, "ip": self.ip,
                        "since": datetime.now(timezone.utc).isoformat(), "cooldown_s": cool,
                        "not_before": self.clock() + cool, "consecutive": self.consec,
                        "to_resume": f"create {rf} after fixing Chrome", "trigger": trigger}
                p.write_text(json.dumps(info, indent=1))
                if everyone:
                    self.sh.last_alert = self.clock()
                else:
                    self.lane_alert = self.clock()
        if first:
            self._alert(msg)
        self._hold()

    def _ban(self, trigger: dict) -> None:
        """Still blocked (HTTP 401/403, not a challenge) on the first request after the owner's RESUME for this IP =
        treated as a permanent ban: STOP every lane and every later start (STOP file), BANNED.json, one alert."""
        self.cnt["blocked"] += 1
        self._record("ban", trigger)
        why = (f"RoyaleAPI crawl STOPPED ALL: {self._who()} is still blocked (HTTP {trigger['status']} on "
               f"{trigger['path']}) on the first request after RESUME = treated as a permanent ban. Every lane stopped; "
               f"STOP file written. Do not restart without the owner.")
        with self.sh.lock:
            (self.out / "BANNED.json").write_text(json.dumps({"lane": self.name, "port": self.rid, "ip": self.ip,
                                                              "t": datetime.now(timezone.utc).isoformat(),
                                                              "trigger": trigger}, indent=1))
            (self.out / "STOP").write_text("permanent ban, see BANNED.json")
            self.sh.stop = self.sh.stop or f"BANNED: {self.name}"
        self.writer.flush()
        self._alert(why)
        raise Stop(f"BANNED: {self.name}")

    # ---- one request, with every stop condition
    def request(self, path: str, params: dict | None = None, manual: bool = False) -> Resp:
        url = path if path.startswith("http") else BASE + path
        if params:
            url += "?" + urlencode(params)
        net = 0
        while True:
            self._hold()
            self._gate()
            self._stop()
            if self._halted():
                continue                            # this lane paused, or another lane halted / cooled all, meanwhile
            self.cnt["req"] += 1
            try:
                r = self.f.get(url, manual)
            except FetchError as e:
                self.cnt["neterr"] += 1
                net += 1
                if net > 3:
                    net = 0
                    self._pause("network", f"{e} (3 automatic retries failed). Is Chrome open on a royaleapi.com tab? "
                                           f"Is its tunnel up?")
                else:
                    self._nap(30 * 2 ** (net - 1))
                continue
            if r.redirected:                        # the followed hop was one more request: count it and its slot
                self.store.reserve(self.clock(), GLOBAL_GAP, DAILY_CAP)
            trig = {"path": path.split("?")[0].removeprefix(BASE), "status": r.status, "cf_mitigated": r.cf,
                    "title": (re.search(r"<title>([^<]{0,80})", r.text[:4000]) or [None, ""])[1], "manual": manual}
            first_after, self.after_resume = self.after_resume, False
            if is_challenge(r):
                self.cnt["challenge"] += 1
                self._pause("challenge", "Cloudflare check page. Clear it in that Chrome window yourself.", trigger=trig)
            elif r.status == 429:
                self.cnt["rate"] += 1
                self._pause("rate", "HTTP 429 too many requests", r.retry_after, trigger=trig)
            elif r.status in (401, 403) and first_after:
                self._ban(trig)
            elif r.status in (401, 403):
                self.cnt["blocked"] += 1
                self._pause("blocked", f"HTTP {r.status} on {path}. Look at that Chrome window (check or login?). "
                                       f"If it is still blocked on the first request after RESUME, ALL lanes stop.",
                            trigger=trig)
            elif r.status >= 500:
                self.cnt["server"] += 1
                net += 1
                if net > 3:
                    net = 0
                    self._pause("server", f"HTTP {r.status} on {path} (3 automatic retries failed)")
                else:
                    self._nap(30 * 2 ** (net - 1))
            else:
                self.consec = 0
                self.cnt["ok"] += 1
                return r

    def logged_in(self) -> bool:
        return self.request("/me", manual=True).status == 200

    # ---- steps
    def seed(self) -> None:
        if self.store.meta("seeded"):
            return
        tags = set()
        for p in [*([] if self.a.no_local_seed else SEED_CSVS), *map(Path, self.a.seed_csv)]:
            if p.exists():
                with p.open(encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        for k in ("player_tag", "team_tags", "opponent_tags"):
                            tags.update(t for t in (row.get(k) or "").split(",") if t)
        for p in map(Path, self.a.seed_tags):
            tags.update(t.strip() for t in p.read_text().split() if t.strip())
        n = self.store.add_players(sorted(tags), "local", 0)
        for path in self.a.seed_url:
            r = self.request(path)
            if r.status == 200:
                n += self.store.add_players(P.leaderboard_tags(r.text), path, 0)
            else:
                print(f"[seed] {path} answered {r.status}: skipped", flush=True)
        self.store.set_meta("seeded", {"players": n})
        print(f"[seed] {n} players queued", flush=True)

    def history_step(self, claimed) -> None:
        tag, nxt, pages = claimed
        r = self.request(nxt or f"/player/{tag}/battles/history")
        self.cnt["history_pages"] += 1
        if r.status != 200:
            self.store.update_player(tag, "skip", None, pages)      # 404 etc: a removed or hidden player
            return
        rows, n_rows, nxt = P.history_page(r.text)
        pages += 1
        others = {t for row in rows for t in (row["team_tags"] + "," + row["opponent_tags"]).split(",") if t and t != tag}
        self.store.add_players(sorted(others), "snowball", 1)
        keep = [x for x in rows if x["battle_type"] in self.types and x["battle_timestamp"] >= self.floor]
        added = self.store.add_battles(keep, tag, not self.a.no_pair_dedupe)
        self.cnt["paired_dupes"] += len(keep) - added
        stamps = [x["battle_timestamp"] for x in rows if x["battle_timestamp"] > 0]
        end = n_rows == 0 or not nxt or pages >= self.a.max_pages or (stamps and min(stamps) < self.floor)
        self.store.update_player(tag, "done" if end else "active", None if end else nxt, pages)

    def replay_step(self, claimed) -> None:
        tag, ptag, row_json, tries = claimed                        # claim_battle set it to 'buf'
        row = json.loads(row_json)
        params = {"tag": tag, "team_tags": row["team_tags"], "opponent_tags": row["opponent_tags"],
                  "team_crowns": row["team_crowns"], "opponent_crowns": row["opponent_crowns"],
                  "referrer_path": f"{BASE}/player/{row['team_tags'].split(',')[0]}/battles"}
        r = self.request("/data/replay", params)
        try:
            data = json.loads(r.text)
        except ValueError:
            data = {}
        if not data.get("success"):
            if self.logged_in():                                    # refused while logged in: that battle is bad
                self.cnt["refused"] += 1
                self.store.set_battle(tag, "todo" if tries < 2 else "fail", tries + 1)
            else:
                self.cnt["login"] += 1
                while True:
                    self._pause("login", "RoyaleAPI session lost. Log in again in the Chrome window.")
                    if self.logged_in():
                        break
                self.store.set_battle(tag, "todo")
            return
        try:
            rrow, arows = P.build_record(row, data["html"], ptag)
        except (ValueError, KeyError) as e:
            print(f"[replay] {tag}: unparseable ({e.__class__.__name__}: {e}); marked fail", flush=True)
            self.store.set_battle(tag, "fail", tries + 1)
            return
        self.writer.add(tag, rrow, arows, data["html"])
        self.cnt["replays"] += 1
        with self.sh.lock:
            self.sh.replays += 1
            total = self.sh.replays
        if self.cnt["replays"] % 50 == 0:
            self.progress()
        if self.a.max_replays and total >= self.a.max_replays:
            raise Stop("max-replays")

    def progress(self) -> None:
        with self.sh.lock:
            line = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lane": self.name,
                    "elapsed_s": round(self.clock() - self.t0), **self.cnt, **self.store.counts()}
            with (self.out / "progress.jsonl").open("a") as f:
                f.write(json.dumps(line) + "\n")

    def loop(self) -> None:
        sh = self.sh
        while True:
            self._stop()
            with sh.lock:                                           # claim atomically: no two lanes take one job
                p = self.store.claim_player() if self.store.n("battles", "todo") < LOW_WATER else None
                b = None if p else self.store.claim_battle()
                if not (p or b) and not sh.busy:
                    return                                          # frontier empty and no lane is fetching
                sh.busy += bool(p or b)
            if not (p or b):
                self.sleep(POLL)                                    # another lane's page may add work
                continue
            try:
                self.history_step(p) if p else self.replay_step(b)
            finally:
                with sh.lock:
                    sh.busy -= 1
            with sh.lock:
                if self.writer.due():
                    self.writer.flush()
                    if shutil.disk_usage(self.out).free < self.a.min_free_gb * 2**30:
                        raise Stop("disk low")

    def lane_main(self, first: bool) -> None:
        own = not hasattr(self.f, "get")            # a factory: build the fetcher in this thread (Playwright is per thread)
        try:
            if own:
                self.f = self.f()
            if first:
                self.seed()
                self.sh.seeded = True
            while not self.sh.seeded:
                self._stop()
                self.sleep(POLL)
            self.loop()
        except Stop as e:
            self.sh.stop = self.sh.stop or str(e)
        except BaseException as e:
            self.sh.stop = self.sh.stop or f"{self.name} crashed ({e.__class__.__name__}: {e})"
            raise
        finally:
            if own and hasattr(self.f, "close"):
                self.f.close()
                self.f = None                       # closed in its own thread; main must not close it again

    def run(self) -> str:
        return run_lanes([self])


def run_lanes(lanes: list[Crawler]) -> str:
    """Run the lanes until the frontier is empty or any lane stops (STOP, max-replays, daily cap, disk, crash): one
    lane in the calling thread, several in threads. Returns the stop reason."""
    sh = lanes[0].sh
    sh.store.recover()
    for c in lanes:
        c.sole = len(lanes) == 1
        c.progress()
    try:
        if len(lanes) == 1:
            lanes[0].lane_main(True)
        else:
            ts = [threading.Thread(target=c.lane_main, args=(i == 0,), name=c.name, daemon=True)
                  for i, c in enumerate(lanes)]
            for t in ts:
                t.start()
            try:
                while any(t.is_alive() for t in ts):
                    ts[0].join(0.2)
                    for t in ts:
                        t.join(0.01)
            except KeyboardInterrupt:
                sh.stop = sh.stop or "Ctrl+C"
                for t in ts:
                    t.join()
    finally:
        sh.writer.flush()
        for c in lanes:
            c.progress()
        reason = sh.stop or "frontier empty"
        sh.store.set_meta("last_run", {"end": reason, "lanes": {c.name: c.cnt for c in lanes}})
    print(f"[crawl] stopped: {reason}; " + "; ".join(f"{c.name} {c.cnt}" for c in lanes), flush=True)
    if reason in ("disk low", "daily cap") or "crashed" in reason:            # a ban alerted already
        lanes[0]._alert(f"RoyaleAPI crawl stopped: {reason}.")
    return reason


# ------------------------------------------------------------------------------------------ cli
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_ALERT_LOCK = threading.Lock()


def discord_alert(out: Path):
    def send(msg: str) -> None:
        with _ALERT_LOCK:                           # lanes share alert.txt
            f = out / "alert.txt"
            f.write_text(msg, encoding="utf-8")
            subprocess.run([sys.executable, str(POST), str(f)], timeout=30, capture_output=True)   # output may hold the URL
    return send


def lower_priority() -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL
    except Exception:
        pass


def instance_lock(path: Path):
    """Exclusive sqlite lock held for the life of the process (the OS drops it on any exit): a second real crawler on
    this laptop refuses to start, so two processes can never split the global limits. None = held by another."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=0, isolation_level=None, check_same_thread=False)
    try:
        db.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError:
        db.close()
        return None
    return db


def check_ips(cdps: list[str]) -> tuple[list[str], str | None]:
    """Exit IP of each Chrome. problem is set when a check failed or two lanes share an IP (two lanes on one IP would
    double that IP's request rate)."""
    ips = []
    for u in cdps:
        try:
            f = CdpFetcher(u)
            try:
                ips.append(f.exit_ip())
            finally:
                f.close()
        except FetchError as e:
            ips.append(f"ERROR {e}")
    if any(i.startswith("ERROR") for i in ips):
        return ips, "exit-IP check failed"
    # compare networks, not addresses: RunPod pods leave through a NAT pool (measured 10-27: 185.226.156.3 and .5 per
    # connection, shared by pods 32657 / 33308), so one exit can show different addresses of one /24
    nets = [".".join(i.split(".")[:3]) if "." in i else ":".join(i.split(":")[:4]) for i in ips]
    return ips, ("two lanes share an exit IP network (/24 or /64)" if len(set(nets)) < len(nets) else None)


def lane_commands(cfg: dict) -> list[dict]:
    """lanes.json -> per lane: the ssh -D tunnel argv (pod lanes), the owner's Chrome line (PowerShell), the CDP URL."""
    key = Path(cfg["ssh_key"]).expanduser()
    out = []
    for ln in cfg["lanes"]:
        chrome = (f'& "{CHROME_EXE}" --remote-debugging-port={ln["cdp_port"]} '
                  f'--user-data-dir="{Path.home() / ln["profile"]}"')
        tunnel = None
        if ln.get("socks_port"):
            chrome += f' --proxy-server="socks5://127.0.0.1:{ln["socks_port"]}"'
            tunnel = ["ssh", "-i", str(key), "-N", "-D", f"127.0.0.1:{ln['socks_port']}", "-p", str(ln["ssh_port"]),
                      "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                      "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", ln["ssh_host"]]
        out.append({**ln, "chrome": chrome, "tunnel": tunnel, "cdp": f"http://127.0.0.1:{ln['cdp_port']}"})
    return out


def lanes_mode(start_tunnels: bool) -> int:
    ls = lane_commands(json.loads(LANES_JSON.read_text()))
    me = f"python -I {Path(__file__).resolve()}"
    for ln in ls:
        print(f"\n[{ln['name']}] {ln.get('note', '')}")
        if ln["tunnel"]:
            print("  tunnel (keep it running; stop it by its PID):", subprocess.list2cmdline(ln["tunnel"]))
            if start_tunnels:
                p = subprocess.Popen(ln["tunnel"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                time.sleep(4)
                print(f"  started: PID {p.pid}, " + ("running" if p.poll() is None else f"EXITED with {p.returncode}"))
        print("  Chrome (PowerShell; then clear the check and log in to RoyaleAPI by hand, leave a royaleapi.com tab open):")
        print("   ", ln["chrome"])
    cdps = " ".join(f"--cdp {ln['cdp']}" for ln in ls)
    print(f"\nverify the exit IPs (they must all differ; opens and closes one tab per Chrome on {IPECHO}):\n  {me} ips {cdps}")
    print(f"crawl (only after the lead's go):\n  {me} crawl --min-gap 8 --auto-resume-rate {cdps}")
    return 0


def status(out: Path) -> None:
    if not (out / "state.db").exists():
        print("no state yet")
        return
    s = Store(out / "state.db")
    print(json.dumps(s.counts()), "\nlast_run:", s.meta("last_run"))
    day = time.strftime("%Y-%m-%d", time.gmtime())
    n = s.today(day)
    print(f"requests today (UTC {day}): {n:,} of {DAILY_CAP:,}; remaining {DAILY_CAP - n:,}; "
          f"global cap {1 / GLOBAL_GAP:.3f}/s over all lanes")
    for ln in s.meta("lanes", None) or []:
        print(f"lane {ln['lane']}: {ln['cdp']} exit IP {ln['ip']}")
    for f in sorted(out.glob("PAUSED*.json")) + sorted(out.glob("BANNED.json")):
        print(f"{f.name}:", f.read_text())
    prog = [json.loads(x) for x in (out / "progress.jsonl").read_text().splitlines()] if (out / "progress.jsonl").exists() else []
    if len(prog) >= 2:
        a, b = prog[0], prog[-1]
        h = (datetime.fromisoformat(b["t"]) - datetime.fromisoformat(a["t"])).total_seconds() / 3600
        d = b.get("battles_done", 0) - a.get("battles_done", 0)
        print(f"progress.jsonl: {d} replays in {h:.2f} h wall = {d / h if h else 0:.0f}/h (includes pauses)")
    last = {}
    for r in prog:
        last[r.get("lane", "lane0")] = r
    for name, r in sorted(last.items()):
        el = r.get("elapsed_s") or 0
        print(f"{name} (row {r['t']}): req {r['req']} in {el} s = {r['req'] / el if el else 0:.3f}/s, 429 {r['rate']}, "
              f"challenge {r['challenge']}, 403 {r['blocked']}, pauses {r['pauses']}, late {r.get('late', 0)}")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"disk: {size / 2**20:.1f} MiB under {out}")


def probe(out: Path, c: Crawler) -> None:
    """<= 5 requests: login check, one seed page, one history page, one replay. Raw bodies saved for review."""
    d = out / "probe"
    d.mkdir(exist_ok=True)
    print("logged in:", c.logged_in())
    seed = c.request(c.a.seed_url[0])
    (d / "seed.html").write_text(seed.text, encoding="utf-8")
    tags = P.leaderboard_tags(seed.text)
    print(f"seed {c.a.seed_url[0]}: HTTP {seed.status}, {len(tags)} player links, first {tags[:3]}")
    if not tags:
        return
    h = c.request(f"/player/{tags[0]}/battles/history")
    (d / "history.html").write_text(h.text, encoding="utf-8")
    rows, n_rows, nxt = P.history_page(h.text)
    print(f"history: HTTP {h.status}, {n_rows} battle rows, {len(rows)} with replay, next={nxt}")
    attrs = sorted({k for r in rows[:1] for k in re.findall(r'\s([\w-]*level[\w-]*)=', r["row_html"])})
    print("attributes mentioning 'level' in the first row:", attrs or "none")
    if rows:
        row = rows[0]
        r = c.request("/data/replay", {"tag": row["replay_tag"], "team_tags": row["team_tags"],
                                       "opponent_tags": row["opponent_tags"], "team_crowns": row["team_crowns"],
                                       "opponent_crowns": row["opponent_crowns"],
                                       "referrer_path": f"{BASE}/player/{row['team_tags'].split(',')[0]}/battles"})
        (d / "replay.json").write_text(r.text, encoding="utf-8")
        rec, acts = P.build_record(row, json.loads(r.text)["html"], tags[0])
        print(f"replay {row['replay_tag']}: {rec['event_count']} events, {rec['warning_count']} warnings")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["crawl", "probe", "status", "stop", "resume", "lanes", "ips"])
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--dry-run", action="store_true", help="fake fetcher + fake clock: no browser, no network")
    ap.add_argument("--cdp", action="append", default=None,
                    help="Chrome debug URL, repeatable: one lane (= one exit IP) each; default http://127.0.0.1:9222")
    ap.add_argument("--rate-scope", choices=["ip", "all"], default="ip",
                    help="with --auto-resume-rate: a 429 cools only its lane (ip) or every lane (all)")
    ap.add_argument("--start-tunnels", action="store_true", help="lanes: also start the ssh -D tunnels")
    ap.add_argument("--lane", default=None, help="resume: the paused lane's Chrome debug port (writes RESUME_<port>)")
    ap.add_argument("--floor", default="2026-10-19", help="oldest battle kept, UTC date (balance patch 10-19)")
    ap.add_argument("--types", default="pathOfLegend,PvP")
    ap.add_argument("--max-pages", type=int, default=3, help="history pages (10 battles each) per player")
    ap.add_argument("--max-replays", type=int, default=0, help="stop after N replays this run (0 = no limit)")
    ap.add_argument("--seed-url", action="append", default=None, help="leaderboard/clan page path, repeatable")
    ap.add_argument("--seed-tags", action="append", default=[], help="file with player tags")
    ap.add_argument("--seed-csv", action="append", default=[], help="old battles.csv to take tags from")
    ap.add_argument("--no-pair-dedupe", action="store_true")
    ap.add_argument("--no-local-seed", action="store_true", help="do not seed from the old crawls' battles.csv")
    ap.add_argument("--no-raw", action="store_true", help="do not keep the raw replay HTML (gz shards)")
    ap.add_argument("--min-free-gb", type=float, default=10.0)
    ap.add_argument("--min-gap", type=float, default=MIN_INTERVAL,
                    help="seconds between request starts (jitter added); raise it if the site answers 429")
    ap.add_argument("--auto-resume-rate", action="store_true",
                    help="after a 429 cooldown (doubling per consecutive 429, max 1 h) continue without RESUME")
    a = ap.parse_args(argv)
    a.seed_url = a.seed_url if a.seed_url is not None else ["/players"]
    a.cdp = a.cdp or ["http://127.0.0.1:9222"]
    if a.mode == "lanes":
        return lanes_mode(a.start_tunnels)
    if a.mode == "ips":
        ips, problem = check_ips(a.cdp)
        for u, ip in zip(a.cdp, ips):
            print(f"{u}  {ip}")
        print(f"PROBLEM: {problem}" if problem else f"OK: {len(ips)} lanes, {len(ips)} distinct exit IPs")
        return 2 if problem else 0
    out = Path(a.out)
    if a.dry_run and not argv_has(argv, "--out"):
        out = out.parent / "crawl_dryrun"
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "status":
        return status(out) or 0
    if a.mode in ("stop", "resume"):
        f = out / (f"RESUME_{a.lane}" if a.mode == "resume" and a.lane else a.mode.upper())
        f.write_text(datetime.now(timezone.utc).isoformat())
        print(f"created {f}")
        return 0
    if a.dry_run:
        a.no_local_seed = True
        fake_t = [0.0]
        def sleep(s): fake_t[0] += s
        fetcher = FakeFetcher(faults={40: "429", 90: "challenge", 140: "login", 170: "net"})
        def alert(msg):
            print("[ALERT dry-run]", msg, flush=True)
            fetcher.logged_out = False
            (out / "RESUME").write_text("auto")
        lanes = [Crawler(out, fetcher, a, clock=lambda: fake_t[0], sleep=sleep, rng=random.Random(1), alert=alert)]
    else:
        if not (out / "OWNER_GO").exists():
            print(f"REFUSED: no real request is allowed until the owner says go. Create {out / 'OWNER_GO'} then.")
            return 2
        if (out / "STOP").exists():
            print(f"REFUSED: {out / 'STOP'} exists; remove it to restart.")
            return 2
        lock = instance_lock(LOCK)          # held until this process exits
        if lock is None:
            print(f"REFUSED: another crawler process holds {LOCK}; only one instance may run (shared limits).")
            return 2
        cdps = a.cdp if a.mode == "crawl" else a.cdp[:1]
        ips = [None] * len(cdps)
        if len(cdps) > 1:
            ips, problem = check_ips(cdps)
            if problem:
                print(f"REFUSED: {problem}: " + ", ".join(f"{u} {ip}" for u, ip in zip(cdps, ips)))
                return 2
        lower_priority()
        sh = Shared(out, a)
        alert = discord_alert(out)
        # one lane runs in this thread (fetcher built here); several run in threads that build their own fetcher
        fs = [CdpFetcher(cdps[0])] if len(cdps) == 1 else [functools.partial(CdpFetcher, u) for u in cdps]
        lanes = [Crawler(out, f, a, alert=alert, shared=sh, name=f"lane{i}", rid=str(urlparse(u).port), ip=ip)
                 for i, (f, u, ip) in enumerate(zip(fs, cdps, ips))]
        sh.store.set_meta("lanes", [{"lane": c.name, "cdp": u, "ip": ip} for c, u, ip in zip(lanes, cdps, ips)])
    sh = lanes[0].sh
    try:
        probe(out, lanes[0]) if a.mode == "probe" else run_lanes(lanes)
    except Stop as e:
        print(f"stopped: {e}")
    finally:
        sh.writer.flush()
        sh.store.close()
        for c in lanes:
            if hasattr(c.f, "get") and hasattr(c.f, "close"):
                c.f.close()
    return 0


def argv_has(argv, flag) -> bool:
    return flag in (sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())

"""Resumable RoyaleAPI replay crawler for the LAPTOP (ticket D2b, plan1026 Pillar 4e). Read CRAWL.md first.

Transport: attaches over CDP to a Chrome the OWNER started, cleared (Cloudflare) and logged into. Every request is an
in-page fetch() of that Chrome: no cookie, clearance or session value is read, copied or saved. <= 1 request/s with
jitter, one in flight. On a challenge page / 429 / 403 / login loss it PAUSES, alerts Discord and waits for the owner
(RESUME file); it never retries a blocked request by itself and never touches Cloudflare.

  python rc_crawl.py crawl --dry-run          # state machine against a fake fetcher, no browser, no network
  python rc_crawl.py probe                    # (needs OWNER_GO) <= 5 requests, saves raw pages for a selector check
  python rc_crawl.py crawl [--max-replays N]  # (needs OWNER_GO)
  python rc_crawl.py status | stop | resume

Control files live in --out (default icebow/data/crawl, untracked): OWNER_GO (must exist for any real request),
STOP (finish cleanly; remove it before restarting), RESUME (owner touches it after fixing Chrome), PAUSED.json (why).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rc_parse as P  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
OUT_DEFAULT = REPO / "icebow" / "data" / "crawl"
POST = REPO / "scratchpad" / "gauntlet" / "L69" / "discord" / "post.py"
BASE = "https://royaleapi.com"   # test_rc.py points this at a local server; nothing else changes it
MIN_INTERVAL = 1.0          # seconds between request starts; jitter is ADDED, so the rate never exceeds 1/s
JITTER = 0.5
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
                text: manual ? '' : await r.text()};
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
        return Resp(r["status"], r["text"], ra, r["cf"])

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
class Store:
    """sqlite: players frontier, battles queue (dedupe by replay tag and by battle pair), counters."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS players(tag TEXT PRIMARY KEY, status TEXT, next_path TEXT, pages INT DEFAULT 0,
                prio INT, added INT, source TEXT);
            CREATE INDEX IF NOT EXISTS players_q ON players(status, prio, added);
            CREATE TABLE IF NOT EXISTS battles(replay_tag TEXT PRIMARY KEY, pair_key TEXT UNIQUE, status TEXT, ts INT,
                player_tag TEXT, tries INT DEFAULT 0, row_json TEXT, row_html BLOB);
            CREATE INDEX IF NOT EXISTS battles_q ON battles(status, ts);
        """)

    def meta(self, k, default=None):
        r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_meta(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))
        self.db.commit()

    def add_players(self, tags, source: str, prio: int, cap: int = 500_000) -> int:
        if self.db.execute("SELECT COUNT(*) FROM players WHERE status IN ('todo','active')").fetchone()[0] >= cap:
            return 0
        now = int(time.time())
        n = self.db.total_changes
        self.db.executemany("INSERT OR IGNORE INTO players(tag,status,prio,added,source) VALUES(?,?,?,?,?)",
                            [(t, "todo", prio, now, source) for t in tags])
        self.db.commit()
        return self.db.total_changes - n

    def next_player(self):
        return self.db.execute("SELECT tag,next_path,pages FROM players WHERE status IN ('todo','active') "
                               "ORDER BY (status='active') DESC, prio, added LIMIT 1").fetchone()

    def update_player(self, tag, status, next_path=None, pages=0):
        self.db.execute("UPDATE players SET status=?, next_path=?, pages=? WHERE tag=?", (status, next_path, pages, tag))
        self.db.commit()

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

    def next_battle(self):
        return self.db.execute("SELECT replay_tag,player_tag,row_json,tries FROM battles WHERE status='todo' "
                               "ORDER BY ts DESC LIMIT 1").fetchone()

    def set_battle(self, tag, status, tries=None):
        self.db.execute("UPDATE battles SET status=?, tries=COALESCE(?, tries) WHERE replay_tag=?", (status, tries, tag))
        self.db.commit()

    def done(self, tags):
        self.db.executemany("UPDATE battles SET status='done' WHERE replay_tag=?", [(t,) for t in tags])
        self.db.commit()

    def counts(self) -> dict:
        c = {f"battles_{s}": n for s, n in self.db.execute("SELECT status, COUNT(*) FROM battles GROUP BY status")}
        c.update({f"players_{s}": n for s, n in self.db.execute("SELECT status, COUNT(*) FROM players GROUP BY status")})
        return c

    def n(self, table, status) -> int:
        return self.db.execute(f"SELECT COUNT(*) FROM {table} WHERE status=?", (status,)).fetchone()[0]

    def close(self) -> None:
        self.db.close()

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
        for d in ("replays", "actions", "raw"):
            (out / d).mkdir(parents=True, exist_ok=True)
        self.r, self.a, self.raw, self.tags = [], [], [], []
        self.last = time.monotonic()

    def add(self, tag, rrow, arows, html):
        self.r.append(rrow)
        self.a.extend(arows)
        self.tags.append(tag)
        if self.keep_raw:
            self.raw.append({"tag": tag, "html": html})

    def due(self) -> bool:
        return len(self.tags) >= FLUSH_ROWS or (self.tags and time.monotonic() - self.last >= FLUSH_SECS)

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
class Crawler:
    def __init__(self, out: Path, fetcher, args, clock=time.monotonic, sleep=time.sleep, rng=None, alert=None):
        self.out, self.f, self.a = out, fetcher, args
        self.clock, self.sleep, self.rng = clock, sleep, rng or random.Random()
        self.alert_fn = alert or (lambda msg: None)
        self.store = Store(out / "state.db")
        self.writer = Writer(out, self.store, keep_raw=not args.no_raw)
        self.last = float("-inf")
        self.consec = 0
        self.cnt = {k: 0 for k in ("req", "ok", "rate", "challenge", "blocked", "server", "neterr", "login", "pauses",
                                   "replays", "refused", "history_pages", "paired_dupes")}
        self.floor = int(datetime.fromisoformat(args.floor).replace(tzinfo=timezone.utc).timestamp())
        self.types = set(args.types.split(","))
        self.t0 = self.clock()

    # ---- control files
    def _stop(self) -> None:
        if (self.out / "STOP").exists():
            raise Stop("STOP file")

    def _alert(self, msg: str) -> None:
        try:
            self.alert_fn(msg)
        except Exception:
            pass                                    # never let an alert failure kill the crawl

    def _gate(self) -> None:
        wait = self.last + MIN_INTERVAL + self.rng.uniform(0, JITTER) - self.clock()
        if wait > 0:
            self.sleep(wait)
        self.last = self.clock()

    def _pause(self, kind: str, why: str, retry_after: float | None = None) -> None:
        self.consec += 1
        self.cnt["pauses"] += 1
        cool = max(retry_after or 0, min(3600, RATE_COOLDOWN * 2 ** (self.consec - 1))) if kind == "rate" else 0
        self.writer.flush()
        info = {"kind": kind, "why": why, "since": datetime.now(timezone.utc).isoformat(), "cooldown_s": cool,
                "consecutive": self.consec, "to_resume": f"create {self.out / 'RESUME'} after fixing Chrome"}
        (self.out / "PAUSED.json").write_text(json.dumps(info, indent=1))
        msg = (f"RoyaleAPI crawl PAUSED ({kind}): {why.rstrip('.')}. Nothing is retried until you fix the Chrome window "
               f"(clear the check / log in / wait) and create the RESUME file. Cooldown {int(cool)}s. "
               f"Done so far: {self.cnt['replays']} replays this run.")
        self._alert(msg)
        t0 = last_alert = self.clock()
        while True:
            self._stop()
            if (self.out / "RESUME").exists() and self.clock() - t0 >= cool:
                (self.out / "RESUME").unlink()
                (self.out / "PAUSED.json").unlink(missing_ok=True)
                return
            if self.clock() - last_alert >= REMIND:
                last_alert = self.clock()
                self._alert("Still paused: " + msg)
            self.sleep(POLL)

    # ---- one request, with every stop condition
    def request(self, path: str, params: dict | None = None, manual: bool = False) -> Resp:
        url = path if path.startswith("http") else BASE + path
        if params:
            url += "?" + urlencode(params)
        net = 0
        while True:
            self._stop()
            self._gate()
            self.cnt["req"] += 1
            try:
                r = self.f.get(url, manual)
            except FetchError as e:
                self.cnt["neterr"] += 1
                net += 1
                if net > 3:
                    net = 0
                    self._pause("network", f"{e} (3 automatic retries failed). Is Chrome open on a royaleapi.com tab?")
                else:
                    self.sleep(30 * 2 ** (net - 1))
                continue
            if is_challenge(r):
                self.cnt["challenge"] += 1
                self._pause("challenge", "Cloudflare check page. Clear it in the Chrome window yourself.")
            elif r.status == 429:
                self.cnt["rate"] += 1
                self._pause("rate", "HTTP 429 too many requests", r.retry_after)
            elif r.status == 403:
                self.cnt["blocked"] += 1
                self._pause("blocked", f"HTTP 403 on {path}. Look at the Chrome window (check or login?).")
            elif r.status >= 500:
                self.cnt["server"] += 1
                net += 1
                if net > 3:
                    net = 0
                    self._pause("server", f"HTTP {r.status} on {path} (3 automatic retries failed)")
                else:
                    self.sleep(30 * 2 ** (net - 1))
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

    def history_step(self) -> None:
        tag, nxt, pages = self.store.next_player()
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

    def replay_step(self) -> None:
        tag, ptag, row_json, tries = self.store.next_battle()
        row = json.loads(row_json)
        self.store.set_battle(tag, "buf")                           # not picked again; reset to todo on a restart
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
        if self.cnt["replays"] % 50 == 0:
            self.progress()
        if self.a.max_replays and self.cnt["replays"] >= self.a.max_replays:
            raise Stop("max-replays")

    def progress(self) -> None:
        line = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "elapsed_s": round(self.clock() - self.t0),
                **self.cnt, **self.store.counts()}
        with (self.out / "progress.jsonl").open("a") as f:
            f.write(json.dumps(line) + "\n")

    def run(self) -> None:
        self.store.db.execute("UPDATE battles SET status='todo' WHERE status='buf'")     # crash recovery
        self.store.db.commit()
        reason = "frontier empty"
        self.progress()
        try:
            self.seed()
            while True:
                self._stop()
                todo = self.store.n("battles", "todo")
                if self.store.has_player_work() and (todo < LOW_WATER or not todo):
                    self.history_step()
                elif todo:
                    self.replay_step()
                else:
                    break
                if self.writer.due():
                    self.writer.flush()
                    if shutil.disk_usage(self.out).free < self.a.min_free_gb * 2**30:
                        raise Stop("disk low")
        except Stop as e:
            reason = str(e)
        finally:
            self.writer.flush()
            self.progress()
            self.store.set_meta("last_run", {"end": reason, **self.cnt})
        print(f"[crawl] stopped: {reason}; {self.cnt}", flush=True)
        if reason in ("disk low",):
            self._alert(f"RoyaleAPI crawl stopped: {reason}.")


# ------------------------------------------------------------------------------------------ cli
def discord_alert(out: Path):
    def send(msg: str) -> None:
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


def status(out: Path) -> None:
    if not (out / "state.db").exists():
        print("no state yet")
        return
    s = Store(out / "state.db")
    print(json.dumps(s.counts()), "\nlast_run:", s.meta("last_run"))
    if (out / "PAUSED.json").exists():
        print("PAUSED:", (out / "PAUSED.json").read_text())
    prog = [json.loads(x) for x in (out / "progress.jsonl").read_text().splitlines()] if (out / "progress.jsonl").exists() else []
    if len(prog) >= 2:
        a, b = prog[0], prog[-1]
        h = (datetime.fromisoformat(b["t"]) - datetime.fromisoformat(a["t"])).total_seconds() / 3600
        d = b.get("battles_done", 0) - a.get("battles_done", 0)
        print(f"progress.jsonl: {d} replays in {h:.2f} h wall = {d / h if h else 0:.0f}/h (includes pauses); last run: req {b['req']}, 429 {b['rate']}, "
              f"challenge {b['challenge']}, 403 {b['blocked']}, pauses {b['pauses']}")
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
    ap.add_argument("mode", choices=["crawl", "probe", "status", "stop", "resume"])
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--dry-run", action="store_true", help="fake fetcher + fake clock: no browser, no network")
    ap.add_argument("--cdp", default="http://127.0.0.1:9222")
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
    a = ap.parse_args(argv)
    a.seed_url = a.seed_url if a.seed_url is not None else ["/players"]
    out = Path(a.out)
    if a.dry_run and not argv_has(argv, "--out"):
        out = out.parent / "crawl_dryrun"
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "status":
        return status(out) or 0
    if a.mode in ("stop", "resume"):
        (out / a.mode.upper()).write_text(datetime.now(timezone.utc).isoformat())
        print(f"created {out / a.mode.upper()}")
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
        c = Crawler(out, fetcher, a, clock=lambda: fake_t[0], sleep=sleep, rng=random.Random(1), alert=alert)
    else:
        if not (out / "OWNER_GO").exists():
            print(f"REFUSED: no real request is allowed until the owner says go. Create {out / 'OWNER_GO'} then.")
            return 2
        if (out / "STOP").exists():
            print(f"REFUSED: {out / 'STOP'} exists; remove it to restart.")
            return 2
        lower_priority()
        c = Crawler(out, CdpFetcher(a.cdp), a, alert=discord_alert(out))
    try:
        probe(out, c) if a.mode == "probe" else c.run()
    except Stop as e:
        print(f"stopped: {e}")
    finally:
        c.writer.flush()
        c.store.close()
        if hasattr(c.f, "close"):
            c.f.close()
    return 0


def argv_has(argv, flag) -> bool:
    return flag in (sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())

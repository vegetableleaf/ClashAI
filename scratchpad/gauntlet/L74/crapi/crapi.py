"""Official Clash Royale API crawler (stdlib only). Runs unattended on the ClashBot VM.

  python3 crapi.py selftest            # one GET /v1/cards, prints counts only
  python3 crapi.py crawl [--max-players N]
                                       # cards + rankings seeds + battlelogs -> data/ (append-only, resumable)

KEY: read at runtime from ~/.cr_api/key (override path: CR_API_KEY_FILE, used by tests). The key is only ever placed
in the Authorization header of requests to api.clashroyale.com; it is never printed, logged or written anywhere.
No card placements: the official API has none.
"""
import argparse, datetime as dt, hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.clashroyale.com/v1"
HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CR_API_DATA", HERE / "data"))
KEY_PATH = Path(os.environ.get("CR_API_KEY_FILE", Path.home() / ".cr_api" / "key"))
VM_IP = "34.148.91.90"
MIN_INTERVAL_S = 0.5          # 2 requests/s, single process: far under the per-key throttle
RECRAWL_H = 6                 # a player's 25-battle log is re-read at most this often
MAX_PLAYERS = 5000            # cap on the known-player pool (seeds + Path of Legends opponents)


class KeyMissing(SystemExit):
    pass


class AuthError(Exception):
    pass


def read_key():
    if not KEY_PATH.is_file():
        raise KeyMissing(
            f"No API key at {KEY_PATH}.\n"
            f"Create one at https://developer.clashroyale.com (My Account -> Create New Key, allowed IP {VM_IP}),\n"
            f"then on the VM: mkdir -p ~/.cr_api && chmod 700 ~/.cr_api && nano ~/.cr_api/key && chmod 600 ~/.cr_api/key")
    key = KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise KeyMissing(f"{KEY_PATH} is empty; paste the API key (the long token) into it.")
    if os.name == "posix" and KEY_PATH.stat().st_mode & 0o077:
        log(f"WARNING: {KEY_PATH} is readable by group/other; run: chmod 600 {KEY_PATH}")
    return key


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "crawl.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def http_get(url, key):
    """-> (status or None on network error, body bytes, headers). Replaced by a fake in tests."""
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", dict(e.headers or {})
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None, b"", {}


class Api:
    def __init__(self, key, min_interval=MIN_INTERVAL_S, sleep=time.sleep, clock=time.monotonic):
        self._key, self.min_interval, self.sleep, self.clock = key, min_interval, sleep, clock
        self._last = -1e9
        self.calls = 0

    def get(self, path, tries=6):
        """Parsed JSON, or None on 404/400. Backs off on 429 / 5xx / network errors; AuthError on 403."""
        for attempt in range(tries):
            gap = self._last + self.min_interval - self.clock()
            if gap > 0:
                self.sleep(gap)
            self._last = self.clock()
            st, body, hdr = http_get(API + path, self._key)
            self.calls += 1
            if st == 200:
                return json.loads(body)
            if st in (400, 404):
                return None
            if st == 403:
                raise AuthError(f"403 on {path}: {_reason(body)} (key valid? allowed IP {VM_IP}?)")
            ra = hdr.get("Retry-After") or hdr.get("retry-after")
            wait = max(float(ra) if ra and str(ra).replace(".", "", 1).isdigit() else 0.0, 2.0 * 2 ** attempt)
            log(f"{st or 'network error'} on {path}; backing off {wait:.0f}s (attempt {attempt + 1}/{tries})")
            self.sleep(wait)
        raise RuntimeError(f"giving up on {path} after {tries} tries")


def _reason(body):
    try:
        j = json.loads(body)
        return f"{j.get('reason')}: {j.get('message')}"
    except Exception:
        return "(no body)"


def q(tag):
    return urllib.parse.quote(tag if tag.startswith("#") else "#" + tag, safe="")


def battle_key(b):
    tags = sorted(p.get("tag", "") for s in ("team", "opponent") for p in b.get(s, []))
    return b.get("battleTime", "") + "|" + ",".join(tags)


def load_seen(path):
    seen = set()
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(battle_key(json.loads(line)["battle"]))
                except (ValueError, KeyError):
                    pass             # a line torn by a crash mid-write; skipped, never rewritten
    return seen


def append_jsonl(path, rows):
    if not rows:
        return
    with open(path, "a+b") as f:
        f.seek(0, 2)
        if f.tell():
            f.seek(-1, 2)
            if f.read(1) != b"\n":   # previous run died mid-line: start on a fresh line
                f.write(b"\n")
        f.write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows).encode("utf-8"))


def load_state():
    p = DATA / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"players": {}}


def save_state(state):
    p = DATA / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, p)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_cards(api):
    cards = api.get("/cards")
    if cards is None:
        raise RuntimeError("/cards returned nothing")
    raw = json.dumps(cards, sort_keys=True).encode()
    (DATA / "cards_latest.json").write_bytes(raw)
    hist = DATA / "cards_history"
    hist.mkdir(exist_ok=True)
    h = hashlib.sha256(raw).hexdigest()[:12]
    if not any(p.name.endswith(f"_{h}.json") for p in hist.iterdir()):
        (hist / f"cards_{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M}_{h}.json").write_bytes(raw)
        log(f"card list changed/new: {len(cards.get('items', []))} items, sha {h}")
    return cards


def seed_tags(api):
    """Top players from every rankings endpoint that answers; which ones did is logged."""
    out = {}
    seasons = api.get("/locations/global/seasons") or {}
    ids = [s.get("id") for s in seasons.get("items", []) if s.get("id")]
    this_month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    cands = [f"/locations/global/pathoflegend/{s}/rankings/players?limit=1000"
             for s in dict.fromkeys([this_month] + ids[::-1][:2])]
    cands += ["/locations/global/pathoflegend/rankings/players?limit=1000",
              "/locations/57000006/pathoflegend/rankings/players?limit=1000",
              "/locations/global/rankings/players?limit=1000"]
    for path in cands:
        j = api.get(path)
        n = 0
        for it in (j or {}).get("items", []):
            if it.get("tag"):
                out.setdefault(it["tag"], path.split("?")[0])
                n += 1
        log(f"seed {path.split('?')[0]}: {n} players")
    extra = DATA.parent / "seeds.txt"           # optional owner-supplied tags, one per line
    if extra.is_file():
        for t in extra.read_text(encoding="utf-8").split():
            out.setdefault(t if t.startswith("#") else "#" + t, "seeds.txt")
    return out


def crawl(api, max_players=400):
    DATA.mkdir(parents=True, exist_ok=True)
    state = load_state()
    players = state["players"]
    fetch_cards(api)
    for tag, src in seed_tags(api).items():
        if tag not in players and len(players) < MAX_PLAYERS:
            players[tag] = {"src": src, "last": None}
    save_state(state)
    bpath = DATA / "battles.jsonl"
    seen = load_seen(bpath)
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=RECRAWL_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
    due = sorted((t for t, p in players.items() if not p["last"] or p["last"] < cutoff),
                 key=lambda t: (players[t]["last"] is not None, players[t]["last"] or ""))
    new_total = i = 0
    while i < min(len(due), max_players):       # `due` grows as ranked opponents are discovered
        tag = due[i]
        i += 1
        log_ = api.get(f"/players/{q(tag)}/battlelog")
        fetched = now_iso()
        rows = []
        for b in log_ or []:
            k = battle_key(b)
            if k in seen:
                continue
            seen.add(k)
            rows.append({"fetched": fetched, "src": tag, "battle": b})
            if b.get("type") == "pathOfLegend":     # ranked opponents are top players: grow the pool
                for p in b.get("opponent", []):
                    t = p.get("tag")
                    if t and t not in players and len(players) < MAX_PLAYERS:
                        players[t] = {"src": "opponent", "last": None}
                        due.append(t)                 # read new top players in this same run
        append_jsonl(bpath, rows)                     # battles first, then the state that says we read them
        players[tag]["last"] = fetched
        save_state(state)
        new_total += len(rows)
        if i % 50 == 0:
            log(f"  {i} players read (queue {len(due)}), +{new_total} battles")
    log(f"crawl done: {i} players read, +{new_total} new battles, "
        f"{len(seen)} total, pool {len(players)}, {api.calls} requests")
    return new_total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["selftest", "crawl"])
    ap.add_argument("--max-players", type=int, default=400)
    a = ap.parse_args(argv)
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass
    try:
        api = Api(read_key())
        if a.cmd == "selftest":
            j = api.get("/cards") or {}
            items = j.get("items", [])
            keys = sorted({k for c in items for k in c})
            icons = sorted({k for c in items for k in (c.get("iconUrls") or {})})
            print(f"SELFTEST OK: /v1/cards -> {len(items)} cards, {len(j.get('supportItems', []))} support items; "
                  f"card fields {keys}; icon kinds {icons}")
            return 0
        crawl(api, a.max_players)
        return 0
    except KeyMissing as e:
        print(e.code if isinstance(e.code, str) else "API key missing", file=sys.stderr)
        return 2
    except AuthError as e:
        log(f"AUTH FAILED: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())

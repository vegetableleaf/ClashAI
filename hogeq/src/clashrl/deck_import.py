"""Import the current top meta decks from the OFFICIAL Clash Royale API into config/meta_decks.yaml,
so the sim's opponents reflect what's actually played right now.

Data source (sanctioned, no scraping): the official API (https://developer.clashroyale.com) -- the
top PATH OF LEGENDS players -> their recent BATTLE LOGS -> the 8-card decks both sides used ->
tallied by frequency -> the top N. (The legacy global TROPHY leaderboard now returns an empty list,
so Path of Legends is the live top-ladder source; see :func:`_top_player_tags`.) Needs a FREE API
token (IP-locked to where you run this): create one at developer.clashroyale.com, then either write
it into the git-ignored file `sim.api_token_file` (default data/cr_api_token.txt) or set the env var
named by `sim.api_token_env` (default CLASHRL_CR_API_TOKEN). Without a token this prints
instructions and leaves the curated config/meta_decks.yaml in place.

A battle log covers EVERY mode, including limited-time events, so it offers decks holding cards that
do not exist in trophy ladder. Those cards were purged from the KB, so they no longer resolve and the
decks holding them are dropped (and counted) -- the sim only ever trains against ladder-legal decks.

Per deck it also records the TOWER TROOP that stood behind it (`supportCards` on the team entry) as
`support:`, plus a derived `evo_candidates:` -- the deck's cards that really have an evolution.

It deliberately does NOT write an `evo:` slot. `evolutionLevel` on a card entry looks like "this
card was in an evolution slot" and is not: MEASURED, it reports the player's OWNED evolution level,
yielding THREE evolutions for 153/233 decks against a game that allows at most two (one Evolution +
one Hero + one Wild, wiki 16/3/2026) and a level for `berserker`, which has no evolution at all.
233 declarations built from it were stripped again in 84e144a. No accessible source names the
slotted card (RoyaleAPI / Deck Shop / StatsRoyale are all 403), so the sim draws uniformly from the
LEGAL set instead of guessing one -- guessing is what produced phantom evolutions in the first
place (research/sim_parity/conflicts.md, R4/I3).

Best-effort: the rankings endpoint/season can change; on an error the message says so and the curated
fallback keeps working. Card names are mapped to KB keys (evolutions fold to their base).
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


def _name_to_key(name: str) -> str:
    k = name.lower().replace(".", "").replace("'", "")
    return re.sub(r"[ \-]+", "_", k).strip("_")


def _modal(counter: Counter) -> tuple:
    """The most-sighted loadout in a tally, ties broken lexicographically so re-runs agree."""
    if not counter:
        return ()
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _get(url: str, token: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_token(cfg) -> str:
    """The CR API token from the env var (preferred) or the git-ignored file, or "".

    Same two-source pattern as :func:`clashrl.monitor._load_webhook`. The FILE matters more here
    than it looks: setting the env var means pasting a long-lived credential on a command line,
    where it lands in shell history -- and on PowerShell `set NAME value` is `Set-Variable`, which
    makes a shell variable that ``os.environ`` never sees, so it silently looks like it worked.
    """
    env_name = cfg.get("sim", "api_token_env", default="CLASHRL_CR_API_TOKEN")
    tok = os.environ.get(env_name, "") if env_name else ""
    if tok.strip():
        return tok.strip()
    fpath = cfg.get("sim", "api_token_file", default="data/cr_api_token.txt")
    p = Path(cfg.path(fpath))
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return ""


def _diagnose_403(token: str) -> str:
    """Explain a 403 by naming the IP the key allows vs the IP this machine actually has.

    The key is IP-LOCKED by Supercell and residential IPs rotate, so "403" is nearly always
    "your IP changed" -- but the raw error can't say that, and finding your public IP is a
    manual lookup. The JWT's PAYLOAD carries the allowlist in plain base64url (read-only, no
    signature check, nothing secret printed), so the exact mismatch can be reported instead.
    """
    bits = []
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)                 # base64url is unpadded
        cidrs = []
        for lim in json.loads(base64.urlsafe_b64decode(payload)).get("limits", []):
            cidrs += lim.get("cidrs", []) or []
        if cidrs:
            bits.append(f"key allows {', '.join(cidrs)}")
    except Exception:  # noqa: BLE001 -- diagnosis is best-effort; never mask the original error
        return ""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
            mine = r.read().decode().strip()
        bits.append(f"this machine is {mine}")
        if cidrs and not any(mine == c.split("/")[0] for c in cidrs):
            bits.append(f"MISMATCH -> add {mine} to the key (or make a new one) at "
                        "developer.clashroyale.com")
    except Exception:  # noqa: BLE001
        pass
    return "; ".join(bits)


def _top_player_tags(base: str, token: str, players: int) -> "tuple[list[str], str]":
    """Player tags of the current top ladder, via PATH OF LEGENDS.

    The legacy `/locations/global/rankings/players` trophy leaderboard still answers HTTP 200 but
    returns an EMPTY item list (measured 2026-08-07) -- Path of Legends replaced trophy ladder at
    the top end, so that endpoint is dead weight and its emptiness looked like "no players" rather
    than "wrong endpoint". Path of Legends rankings are SEASON-SCOPED and the CURRENT season 404s
    until it has been ranked, so this walks the season list newest-first and takes the first season
    that actually has players. The legacy board is still tried last in case Supercell revives it.
    """
    seasons: list = []
    try:
        got = _get(f"{base}/locations/global/seasons", token).get("items", [])
        seasons = sorted({s["id"] for s in got if s.get("id")}, reverse=True)
    except Exception:  # noqa: BLE001 -- fall through to the legacy board
        seasons = []
    for sid in seasons[:6]:
        try:
            d = _get(f"{base}/locations/global/pathoflegend/{sid}/rankings/players"
                     f"?limit={players}", token)
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # season listed but never ranked
                continue
            raise
        items = d.get("items", [])
        if items:
            return [p["tag"] for p in items][:players], f"path-of-legends {sid}"
    d = _get(f"{base}/locations/global/rankings/players?limit={players}", token)
    return [p["tag"] for p in d.get("items", [])][:players], "global trophy rankings"


def import_decks(cfg, limit: int = 1000, players: int = 120) -> None:
    from .cards import CardDB
    db = CardDB(cfg)
    token_env = cfg.get("sim", "api_token_env", default="CLASHRL_CR_API_TOKEN")
    token = _load_token(cfg)
    out_path = Path(cfg.path(cfg.get("sim", "meta_decks_file", default="config/meta_decks.yaml")))
    if not token:
        tf = cfg.get("sim", "api_token_file", default="data/cr_api_token.txt")
        print(f"[decks-import] no API token. Get a FREE one at https://developer.clashroyale.com "
              f"(create a key locked to THIS machine's public IP), then EITHER write it into the "
              f"git-ignored file {tf} (one line, keeps it out of shell history) OR set env {token_env} "
              f"-- in PowerShell that is `$env:{token_env} = \"...\"`, NOT `set {token_env} ...`, "
              f"which only makes a shell variable.\n"
              f"  Until then the curated {out_path.name} is used as-is.")
        return
    base = cfg.get("sim", "api_base", default="https://api.clashroyale.com/v1")

    # 1) top global players
    try:
        tags, source = _top_player_tags(base, token, players)
    except urllib.error.HTTPError as e:
        why = _diagnose_403(token) if e.code == 403 else ""
        print(f"[decks-import] rankings fetch failed (HTTP {e.code}). A 403 = bad token / wrong IP; "
              "a 404 = the endpoint/season moved. Curated decks kept."
              + (f"\n  {why}" if why else ""))
        return
    except Exception as e:  # noqa: BLE001
        print(f"[decks-import] rankings fetch failed: {e!r}. Curated decks kept.")
        return
    if not tags:
        print("[decks-import] no players returned by ANY ranking endpoint; curated decks kept.")
        return
    print(f"[decks-import] {len(tags)} top players from {source}")

    # 2) their battle logs -> tally 8-card decks (both sides)
    tally: Counter = Counter()
    # WHICH tower troop stood behind each 8-card set. The MODAL one per deck wins: one deck list
    # gets piloted with different towers, and the common one is the honest single answer.
    #
    # NOT tallied: `evolutionLevel`. It is the one field that looks like an evolution SLOT and is
    # not (module docstring), and a tally of it is how 233 wrong `evo:` declarations got shipped.
    sup_tally: dict = defaultdict(Counter)
    seen = 0
    n_event = 0
    for i, tag in enumerate(tags):
        enc = urllib.parse.quote(tag, safe="")
        try:
            battles = _get(f"{base}/players/{enc}/battlelog", token)
        except Exception:  # noqa: BLE001 -- skip a player we can't read
            continue
        for b in battles:
            for side in ("team", "opponent"):
                for entry in b.get(side, []):
                    raw = entry.get("cards", [])
                    keys = []
                    for c in raw:
                        k = _name_to_key(c.get("name", ""))
                        base_k = k[:-4] if k.endswith("_evo") else k
                        if db.get(base_k):
                            keys.append(base_k)
                    # A battle log covers EVERY mode, including limited-time events, so decks
                    # holding party_*/super_*/Heal/etc. show up here. Those cards were purged from
                    # the KB, so they no longer resolve -- which means a deck containing one is
                    # short of 8 and is dropped by the check below. Counted separately so the
                    # filtering is visible rather than silently shrinking the sample.
                    if len(raw) == 8 and len(keys) < 8:
                        n_event += 1
                    if len(keys) == 8:
                        ck = tuple(sorted(keys))
                        tally[ck] += 1
                        # The tower troop is NOT a deck card and has no KB row, so it is recorded
                        # by name-key with no `db.get` filter -- filtering would drop all of them.
                        sup_tally[ck][tuple(_name_to_key(s.get("name", ""))
                                            for s in (entry.get("supportCards") or []))] += 1
                        seen += 1
        if (i + 1) % 20 == 0:
            print(f"[decks-import] scanned {i + 1}/{len(tags)} players, {seen} decks so far...")
        time.sleep(0.12)                                     # be gentle on the API

    if not tally:
        print("[decks-import] no valid decks parsed; curated decks kept.")
        return
    if n_event:
        print(f"[decks-import] dropped {n_event} deck-sightings containing event-only/unknown cards "
              f"({100 * n_event / (seen + n_event):.1f}% of sightings) -- ladder-legal decks only.")

    top_decks = tally.most_common(limit)
    lines = ["# Imported from the official Clash Royale API (top-player battle logs).",
             f"# {time.strftime('%Y-%m-%d %H:%M')} -- {len(top_decks)} decks from {len(tags)} "
             f"players ({source}), {seen} deck-sightings. Regenerate with `run.py decks-import`.",
             "# LADDER-LEGAL ONLY: a battle log covers every mode, so decks holding event-only cards"
             f" are dropped ({n_event} sightings this run). `weight` = raw sighting count.",
             "# `support` = the deck's MODAL tower troop (battlelog `supportCards`), measured.",
             "# `evo_candidates` = the deck's cards that really HAVE an evolution (the KB's `_evo`"
             " rows, == the 42 wiki-verified evolutions in ledger/r1a_evolutions.json). DERIVED, not"
             " observed:",
             "# no source says which card a player slotted -- `evolutionLevel` reports OWNED level,"
             " not the slot -- so the sim draws ONE candidate uniformly per match instead of"
             " guessing a fixed one.",
             "decks:"]
    for n, (cards, count) in enumerate(top_decks, 1):
        # DERIVED from the KB, never from `evolutionLevel` (see the module docstring for why that
        # field cannot identify a slot). `sim.meta_decks` re-derives this if the key is absent, so
        # writing it is for inspectability -- a reader can see what each deck may field.
        cands = [k for k in cards if db.get(k + "_evo")
                 or isinstance((db.get(k) or {}).get("evolution"), dict)]
        sup = _modal(sup_tally[cards])
        bits = [f"name: meta_{n:03d}", f"weight: {count}", f"cards: [{', '.join(cards)}]",
                f"evo_candidates: [{', '.join(cands)}]"]
        if sup:
            bits.append(f"support: {sup[0]}")
        lines.append("  - {" + ", ".join(bits) + "}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[decks-import] wrote {len(top_decks)} decks -> {out_path} "
          f"(most common: {'/'.join(top_decks[0][0][:3])}... x{top_decks[0][1]})")

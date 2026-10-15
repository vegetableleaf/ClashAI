"""Live-mirrored opponent deck pool (owner plan 2026-10-15): each recent live opponent (only the cards we SAW) is completed to a
full 8-card deck from the IL_Replay library, and the pool is written in the decks_rl.json schema.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mix/live_pool.py            # build (needs polars; ~2 min cold, cached after)
    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mix/live_pool.py --check-loadable JOB.json   # pod/local

Stage 2 of the build re-runs this file in the Royale venv (--check-loadable) on every candidate deck; the same mode annotates any
{"decks":[{"engine":[...]}]} file in place with loadable / blocker / form_fallbacks, so a pool file can be re-checked on a Linux pod.

Matching: library decks keep their exact-form identity (sorted card keys incl. -evN/-hero) and are ranked by deck-sides. For an
opponent's `seen` set: exact = base card set contains every seen card (most frequent first); if no usable exact candidate among the
first 20, approximate = max overlap then max frequency. Candidates that do not convert to 8 engine names (census.deck) or do not
load in RoyaleSim are skipped (next candidate, up to 20). Pool rows: sides = n_live (eval) or n_live + n_lost (train).
"""
import argparse
import collections
import glob
import heapq
import itertools
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROYALE_PY = REPO / "research/ext/Royale/.venv/Scripts/python.exe"
LIVE_JSON = HERE / "live_cost_1001.json"
CARDS_JSON = REPO / "scratchpad/gauntlet/L68/generalist/royalesim_cards.json"
GHOST_POOL = REPO / "icebow/data/ghost_pool/pool_env_v1.jsonl"
PRO_CSV = REPO / "scratchpad/gauntlet/L74/pro2/output/battles.csv"
REPLAYS = REPO / "scratchpad/gauntlet/L67/hf/replays"
FORM = re.compile(r"-(ev\d+|hero)$")
HEAD_DECKS = 20          # rl_royale.HEAD_DECKS: "head" bucket = the first 20 decks (league_decks recomputes it from list order)
K = 20                   # candidates tried per opponent
# Explicit extra aliases, applied AFTER the census mapping (alnum-lowercase slug -> alnum-lowercase live canon). Filled by the unmapped
# report (see LIVE_POOL.md); the census mapping + archetypes.ALIAS already cover the known spelling splits (the-log/log, x-bow/xbow,
# elite-barbarians/angrybarbarians, mini-pekka, ice-spirit/icespirits, dart-goblin/blowdartgoblin, skeleton-army ...).
EXTRA = {}
# Live-side names with no library spelling: the engine's two Spirit Empress bodies are one card (slug spirit-empress -> MergeMaiden).
LIVE_ALIAS = {"mergemaidennormal": "mergemaiden", "mergemaidenmounted": "mergemaiden"}


def _imports():
    sys.path.insert(0, str(REPO))
    from scratchpad.gauntlet.L74.newsim import census
    from scratchpad.gauntlet.L74.weekend import archetypes
    return census, archetypes


# event / "Super" / chess variants of real cards: their vocab.engine_key collides with the real card ("SuperMiniPekka" -> mini_pekka), and
# census.aliases lets the last name win, so a slug would resolve to the variant. Dropped from the name list (never in a pool deck).
VARIANTS = {"SuperArcher", "SuperEliteArcher", "BarbarianLauncher", "GlobalClone", "WarmSpell", "GlobalLightning", "GoblinRocketSilo",
            "GoblinPartyHut", "GoblinPartyRocket", "SuperHogRider", "SuperHogRiderTerry", "SuperIceGolemite", "SuperKnight",
            "SuperLavaHound", "MergeMaiden_Normal", "MergeMaiden_Mounted", "SuperMiniPekka", "PrinceBuff", "RoyalRecruits_Chess",
            "SkeletonWarriors_SpookyChess", "SuperWitch", "TriWizards"}


def engine_names():
    names = {c["name"] for c in json.load(open(CARDS_JSON))}          # engine names only: display names ("The Log") would canon differently from live
    for line in open(GHOST_POOL):
        e = json.loads(line)
        names |= {it["name"] for it in e["icebow_deck"] + e["ghost_deck"]}
    return names - VARIANTS


def split_slug(card):
    m = FORM.search(card)
    return (card[:m.start()], m[1]) if m else (card, "")


def card_canon(card, mapping, canon):
    """RoyaleAPI card key (maybe with -evN/-hero) -> the live `seen` canon space (archetypes.canon of the engine name)."""
    base = split_slug(card)[0]
    name = mapping.get(re.sub(r"[^a-z0-9]", "", base))
    k = canon(name or base)
    return EXTRA.get(k, k)


def to_engine(card_keys, mapping, deck_fn):
    """Exact-form library deck (card keys) -> sorted engine tuple with @evolution/@hero, or None (not 8 distinct engine names)."""
    toks = []
    for c in card_keys:
        base, f = split_slug(c)
        toks.append(base + ("@hero" if f == "hero" else "@evolution" if f else ""))
    return deck_fn(toks, mapping)[0]


def candidates(seen, lib, k=K):
    """lib = [(canon frozenset, ident)] sorted by frequency desc, usable decks only. Yields (ident, overlap, exact), best first:
    up to k exact (contain every seen card), then, only if there were none, up to k by (-overlap, rank)."""
    seen = set(seen)
    ex = list(itertools.islice(((i, len(seen), True) for c, i in lib if seen <= c), k))
    if ex or not seen:
        return ex if seen else []
    top = heapq.nsmallest(k, ((-len(seen & c), r) for r, (c, _) in enumerate(lib)))
    return [(lib[r][1], -o, False) for o, r in top]


def pick(cs, usable):
    """First candidate of `cs` (= candidates(), in order over ALL decks) that passes `usable`. -> (ident, overlap, exact, skipped)."""
    for n, (ident, ov, exact) in enumerate(cs):
        if usable(ident):
            return ident, ov, exact, n
    return None, 0, False, len(cs)


def load_library(cache, pro=False):
    """-> Counter {sorted card-key tuple (exact forms): deck-sides}. Cached as JSON."""
    cache = Path(cache)
    if cache.exists():
        sides = collections.Counter({tuple(k): n for k, n in json.load(open(cache))})
    else:
        import polars as pl
        sides = collections.Counter()
        for f in sorted(glob.glob(str(REPLAYS / "*.parquet"))):
            for pj in pl.read_parquet(f, columns=["payload_json"])["payload_json"]:
                b = json.loads(pj)["battle"]
                for who in ("team", "opponent"):
                    for p in b[who]["players"]:
                        sides[tuple(sorted(c["card_key"] for c in p["deck"]))] += 1
        json.dump([[list(k), n] for k, n in sides.items()], open(cache, "w"))
    if pro:
        import csv
        for r in csv.DictReader(open(PRO_CSV, encoding="utf-8-sig")):
            for col in ("team_deck", "opponent_deck"):
                sides[tuple(sorted(r[col].split(",")))] += 1
    return sides


# ---------------------------------------------------------------------------------------------------------------- loadability
def check_loadable(job):
    """Royale venv / pod: annotate job["decks"][i] with loadable, blocker, form_fallbacks (RoyaleSelfPlayEnv forms_mode='deck')."""
    sys.path.insert(0, str(REPO))
    from pipeline.royale_env import RoyaleSelfPlayEnv, UnsupportedDeck
    from pipeline.e1_eval import ICEBOW_ENGINE_DECK
    d = json.load(open(job))
    env = RoyaleSelfPlayEnv(forms_mode="deck", hero_abilities=True, ability_policy="v2")
    t0 = time.perf_counter()
    for x in d["decks"]:
        env.form_fallbacks = []
        try:
            env.reset(ICEBOW_ENGINE_DECK, x["engine"], 0)
            x["loadable"], x["blocker"] = True, None
        except (UnsupportedDeck, KeyError) as e:
            x["loadable"], x["blocker"] = False, f"{type(e).__name__}: {e}"
        x["form_fallbacks"] = [list(f) for f in env.form_fallbacks]
    d["reset_seconds"] = round(time.perf_counter() - t0, 1)
    json.dump(d, open(job, "w"))


# ---------------------------------------------------------------------------------------------------------------------- build
def build(a):
    census, A = _imports()
    t0 = time.perf_counter()
    mapping = census.aliases(engine_names())
    sides = load_library(a.cache, a.pro)
    live = [[f, r, sorted({LIVE_ALIAS.get(c, c) for c in seen})] for f, r, seen in json.load(open(LIVE_JSON))]
    canon = A.canon

    # library: rank by sides, exact identity; engine conversion once per deck
    ranked = sorted(sides.items(), key=lambda x: (-x[1], x[0]))
    conv = {k: to_engine(k, mapping, census.deck) for k, _ in ranked}
    cset = {k: frozenset(card_canon(c, mapping, canon) for c in k) for k, _ in ranked}
    vocab = set().union(*cset.values())
    unmapped_slugs = collections.Counter()           # library cards with no engine spelling (decks holding them cannot convert)
    for k, n in ranked:
        for c in k:
            if re.sub(r"[^a-z0-9]", "", split_slug(c)[0]) not in mapping:
                unmapped_slugs[split_slug(c)[0]] += n
    live_names = collections.Counter(c for _, _, seen in live for c in seen)
    unknown_live = {c: n for c, n in live_names.items() if c not in vocab}

    lib_all = [(cset[k], k) for k, _ in ranked]                      # candidate order over ALL decks (conversion applied in pick)
    # stage 2 input: every convertible deck any opponent might try
    tried, cands = set(), {}
    for _, _, seen in live:
        known = tuple(c for c in seen if c in vocab)
        if known not in cands:
            cands[known] = candidates(known, lib_all, K)
            tried.update(i for i, _, _ in cands[known])
    engines = sorted({conv[k] for k in tried if conv[k]})
    loadable = {}
    if engines and not a.skip_load:
        job = Path(tempfile.gettempdir()) / "live_pool_load_job.json"
        json.dump({"decks": [{"engine": list(e)} for e in engines]}, open(job, "w"))
        subprocess.run([str(ROYALE_PY), __file__, "--check-loadable", str(job)], check=True)
        res = json.load(open(job))
        job.unlink()
        loadable = {tuple(x["engine"]): x for x in res["decks"]}
    blockers = collections.Counter(x["blocker"] for x in loadable.values() if not x["loadable"])
    usable = lambda k: conv[k] is not None and (a.skip_load or loadable[conv[k]]["loadable"])  # noqa: E731

    rows, per = [], collections.Counter()
    agg = collections.defaultdict(lambda: [0, 0, None])
    for log, res, seen in live:
        known = [c for c in seen if c in vocab]
        k, ov, exact, skipped = pick(cands[tuple(known)], usable)
        q = "none" if k is None else "exact" if exact and len(known) == len(seen) else "approx"
        per[q] += 1
        rows.append((log, res, seen, k, ov, q, skipped))
        if k is not None:
            r = agg[conv[k]]
            r[0] += 1
            r[1] += 1 - res
            r[2] = r[2] or k
    n_skipped = sum(1 for r in rows if r[6] and r[3] is not None)

    decks = sorted(agg.items(), key=lambda x: (-x[1][0], -x[1][1], x[0]))

    def pool(train):
        out = []
        for i, (eng, (nl, nlost, key)) in enumerate(decks):
            fb = loadable.get(eng, {}).get("form_fallbacks", [])
            out.append({"rank": i + 1, "name": f"live{i + 1}", "sides": nl + (nlost if train else 0), "n_live": nl, "n_lost": nlost,
                        "bucket": "head" if i < HEAD_DECKS else "tail", "engine": list(eng), "slugs": list(key),
                        "form_fallbacks": fb})
        return out

    meta = {"source": "live_pool.py", "live_opponents": len(live), "mapped": per["exact"] + per["approx"], "coverage": dict(per),
            "weights": "sides = n_live (eval) | n_live + n_lost (train)", "bucket": "head = first 20 by sides, as rl_royale.league_decks"}
    for name, train in (("decks_live_eval.json", False), ("decks_live_train.json", True)):
        json.dump(dict(meta, decks=pool(train)), open(HERE / name, "w"), indent=1)
    write_report(a, rows, decks, per, live, vocab, unknown_live, unmapped_slugs, blockers, n_skipped, canon, ranked, conv, time.perf_counter() - t0,
                 (len(loadable), sum(x['loadable'] for x in loadable.values()), sum(1 for d in decks if loadable.get(d[0], {}).get('form_fallbacks'))))


def share_table(decks, live, ref):
    cards = ["megaknight", "firecracker", "minipekka", "hogrider", "elixirgolem", "royalrecruits", "skeletonballoon", "golem",
             "angrybarbarians", "lavahound", "xbow", "mortar"]
    from scratchpad.gauntlet.L74.weekend import archetypes as A
    tot = sum(d[1][0] for d in decks)
    pool = {c: sum(d[1][0] for d in decks if c in {A.canon(x) for x in d[0]}) / tot for c in cards}
    lv = {c: sum(1 for _, _, s in live if c in s) / len(live) for c in cards}
    old = {}
    if ref:
        dd = json.load(open(ref))["decks"]
        t = sum(x["sides"] for x in dd)
        old = {c: sum(x["sides"] for x in dd if c in {A.canon(y) for y in x["engine"]}) / t for c in cards}
    L = ["| card | live seen % | pool (n_live-weighted) % | old training pool (sides-weighted) % |", "|---|---|---|---|"]
    L += [f"| {c} | {100 * lv[c]:.1f} | {100 * pool[c]:.1f} | {('%.1f' % (100 * old[c])) if old else 'n/a'} |" for c in cards]
    return L


def write_report(a, rows, decks, per, live, vocab, unknown_live, unmapped_slugs, blockers, n_skipped, canon, ranked, conv, secs, checks):
    n_checked, n_loadable, n_fb = checks
    n = len(live)
    ov = collections.Counter((len(r[2]), r[4]) for r in rows if r[5] == "approx")
    sizes = collections.Counter(len(r[2]) for r in rows)
    top = decks[0][1][0] / max(1, per["exact"] + per["approx"])
    L = ["# Live-mirrored deck pool", "",
         f"Built by `live_pool.py` ({secs:.0f}s). Library: {len(ranked)} distinct exact-form decks "
         f"({sum(n_ for _, n_ in ranked)} deck-sides){' + pro battles' if a.pro else ''}; {sum(1 for k, _ in ranked if conv[k])} convert to 8 engine names. "
         f"Loadability: {'SKIPPED' if a.skip_load else 'checked in the Royale venv (forms_mode=deck, ICEBOW_ENGINE_DECK on the other side)'}.", "",
         "## Coverage", "",
         f"- live opponents: {n}; mapped exactly (deck contains every seen card): **{per['exact']}**; approximately (max overlap, or a seen "
         f"card absent from the library): **{per['approx']}**; not at all: **{per['none']}** (|seen|=0 or no usable candidate in the first {K}).",
         f"- opponents whose first-choice deck was skipped (unconvertible / unloadable) and fell to a later candidate: {n_skipped}",
         f"- distinct decks in the pool: **{len(decks)}**; the top deck takes {100 * top:.1f}% of mapped opponents",
         f"- |seen| histogram: {dict(sorted(sizes.items()))}",
         f"- approx rows by (|seen|, overlap): {dict(sorted(ov.items()))}",
         f"- loadability: {n_checked} distinct candidate decks reset in RoyaleSim, {n_loadable} loadable; blockers: {dict(blockers) or 'none'}; "
         f"pool decks with a refused-form fallback (loaded as base): {n_fb}", "",
         "## Unmapped names", "",
         f"- live names never present in any library deck: {unknown_live or 'none'}",
         f"- library card keys with no engine spelling (decks with them cannot convert): {dict(unmapped_slugs.most_common(15)) or 'none'}", "",
         "## Top 30 decks", "", "| # | n_live | n_lost | engine |", "|---|---|---|---|"]
    L += [f"| {i + 1} | {d[1][0]} | {d[1][1]} | {', '.join(d[0])} |" for i, d in enumerate(decks[:30])]
    L += ["", "## Card shares: pool vs live", ""] + share_table(decks, [(r[0], r[1], r[2]) for r in rows], a.train_ref)
    L += ["", "Live seen % is a LOWER bound on true presence (only cards we saw played); pool % counts the full completed deck."]
    (HERE / "LIVE_POOL.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:22]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-loadable", metavar="JOB")
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "live_pool_lib_cache.json"))
    ap.add_argument("--pro", action="store_true", help="add the 1,064 pro battles (base slugs) to the library")
    ap.add_argument("--skip-load", action="store_true")
    ap.add_argument("--train-ref", help="current training deck file, for the old-pool column of the share table")
    a = ap.parse_args()
    check_loadable(a.check_loadable) if a.check_loadable else build(a)


if __name__ == "__main__":
    main()

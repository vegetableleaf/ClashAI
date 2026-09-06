"""L63e: promote L61's per-play recording into research/sandbox_tools/replay_drive.py and make the crawl
directory a parameter (--crawl <deck>|<path>) in both replay_drive.py and replay_batch.py.  Defaults keep the
old behaviour byte-for-byte (icebow crawl2, no recording, OUT=ext/batch)."""
import re, sys
from pathlib import Path
ROOT = Path(r"C:/Users/benpe/ClashBot")
d = ROOT / "research/sandbox_tools/replay_drive.py"
s = d.read_text(encoding="utf-8")
def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:60], s.count(old))
    s = s.replace(old, new)
rep('CRAWL = REPO / "icebow" / "data" / "royaleapi" / "crawl2"\n',
    'CRAWL = REPO / "icebow" / "data" / "royaleapi" / "crawl2"\n\n\n'
    'def set_crawl(deck_or_path: str) -> Path:\n'
    '    """L63e: point the loader at another deck\'s crawl (a deck name -> <deck>/data/royaleapi/crawl2, or a path)."""\n'
    '    global CRAWL\n'
    '    p = Path(deck_or_path)\n'
    '    CRAWL = p if p.exists() else REPO / deck_or_path / "data" / "royaleapi" / "crawl2"\n'
    '    if not (CRAWL / "battles.csv").exists():\n'
    '        raise SystemExit(f"no battles.csv under {CRAWL}")\n'
    '    return CRAWL\n')
rep('          run_label: str, verbose: bool, record_every: int = 0, record_full: bool = False) -> dict:',
    '          run_label: str, verbose: bool, record_every: int = 0, record_full: bool = False,\n'
    '          record_plays: bool = False) -> dict:')
rep('    record_full=True uses the full observation (adds entity kind, projectiles and spell effects)."""',
    '    record_full=True uses the full observation (adds entity kind, projectiles and spell effects).\n'
    '    record_plays=True (L63e, from L61\'s replay_drive_rec) stores a FULL observation immediately BEFORE every\n'
    '    driven play of both sides in out["play_frames"] (with play_index, side, card, x, y and both players\'\n'
    '    hand/cycle/next/elixir)."""')
rep('    def snapshot(state: dict) -> None:\n',
    '    play_frames: list[dict] = []\n\n'
    '    def snapshot(state: dict, full: bool = False, extra: dict | None = None, into: list | None = None) -> None:\n'
    '        record_full_ = record_full or full\n')
rep('int(e["max_hp"])] + ([int(e.get("kind", -1))] if record_full else [])',
    'int(e["max_hp"])] + ([int(e.get("kind", -1))] if record_full_ else [])')
rep('        if record_full:\n', '        if record_full_:\n')
rep('        frames.append(frame)\n',
    '        if extra:\n'
    '            frame.update(extra)\n'
    '            frame["players"] = [{"side": int(pl["side"]), "elixir": pl.get("elixir_exact", pl.get("elixir")),\n'
    '                                 "hand": [item["name"] for item in pl["hand"]],\n'
    '                                 "hand_pos": list(pl["hand_deck_indices"]), "cycle_pos": list(pl.get("cycle_deck_indices", [])),\n'
    '                                 "next": pl.get("next_deck_index")} for pl in state["players"]]\n'
    '        (frames if into is None else into).append(frame)\n')
rep('        before = player(env.observe_compact(), side)\n',
    '        if record_plays:\n'
    '            obs_before = env.observe()\n'
    '            snapshot(obs_before, full=True, extra={"play_index": row["play_index"], "side": side, "card": slug,\n'
    '                                                   "x": row["x"], "y": row["y"]}, into=play_frames)\n'
    '            before = player(obs_before, side)\n'
    '        else:\n'
    '            before = player(env.observe_compact(), side)\n')
rep('        out["record_full"] = record_full\n',
    '        out["record_full"] = record_full\n'
    '    if record_plays:\n'
    '        out["play_frames"] = play_frames\n')
rep('    parser.add_argument("--quiet", action="store_true")\n',
    '    parser.add_argument("--quiet", action="store_true")\n'
    '    parser.add_argument("--crawl", default="", help="deck name (icebow|hogeq) or crawl dir; default icebow crawl2")\n'
    '    parser.add_argument("--record-plays", action="store_true", help="full observation before every driven play (both sides)")\n')
rep('record_every=args.record_every, record_full=args.record_full)',
    'record_every=args.record_every, record_full=args.record_full,\n'
    '                       record_plays=args.record_plays)')
# set_crawl must run before load_battle: insert right after parse_args
m = re.search(r'    args = parser\.parse_args\(\)\n', s)
assert m, "parse_args not found"
s = s[:m.end()] + '    if args.crawl:\n        set_crawl(args.crawl)\n' + s[m.end():]
d.write_text(s, encoding="utf-8")

b = ROOT / "research/sandbox_tools/replay_batch.py"
s = b.read_text(encoding="utf-8")
rep('    ap.add_argument("--redo", action="store_true")\n',
    '    ap.add_argument("--redo", action="store_true")\n'
    '    ap.add_argument("--crawl", default="", help="L63e: deck name (icebow|hogeq) or crawl dir; default icebow crawl2")\n'
    '    ap.add_argument("--out", default="", help="L63e: output dir (default scratchpad/gauntlet/ext/batch)")\n'
    '    ap.add_argument("--record-every", type=int, default=0, help="L63e: compact frame every N ticks")\n'
    '    ap.add_argument("--record-plays", action="store_true", help="L63e: full observation before every driven play")\n')
rep('    tags = json.loads(Path(args.tags).read_text(encoding="utf-8"))\n',
    '    global OUT\n'
    '    if args.crawl:\n'
    '        replay_drive.set_crawl(args.crawl)\n'
    '    if args.out:\n'
    '        OUT = Path(args.out)\n'
    '    tags = json.loads(Path(args.tags).read_text(encoding="utf-8"))\n')
rep('tail_cap=args.tail_cap, run_label="batch", verbose=False)',
    'tail_cap=args.tail_cap, run_label="batch", verbose=False,\n'
    '                                         record_every=args.record_every, record_plays=args.record_plays)')
rep('(OUT / f"replay_{tag}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")',
    '(OUT / f"replay_{tag}.json").write_text(json.dumps(res, indent=None if args.record_plays else 1, default=str), encoding="utf-8")')
b.write_text(s, encoding="utf-8")
print("patched OK")

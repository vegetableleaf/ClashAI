r"""Runbook + driver: verify the v2 bridge (buffs + area_effects) against a live battle.

NOT RUN by the RE session (adb / emulator were off limits). Everything here is
what the owner (or a later session) runs once the emulator can be touched.

RUNBOOK
-------
Preconditions
  * The AVD is booted (emulator-5554) and `adb` works. The training workers on
    37031/37032 (direct 38031/38032, remote roots /data/local/tmp/cr-native-direct-{0,1})
    are NOT touched by this script: it uses its own remote root
    /data/local/tmp/cr-native-sandbox-probe and its own port (default 37041).
  * `research\ext\cr-native-sandbox\artifacts\libnative_core_probe.so` is still the
    v1 bridge (sha256 82887463...); the v2 build lives ONLY in
    scratchpad\gauntlet\ext\re\bridge_v2\libnative_core_probe.v2.so (sha256 9b63a7a0...).
    Do not copy v2 into artifacts/ while the training workers are alive: the worker
    pool's `_service_artifacts_current` check would redeploy + restart them on their
    next start_service().
  * Dot-source `research\ext\cr-native-sandbox\runtime.env.ps1` in the shell first
    (CR_SANDBOX_ADB / RUNTIME_DIR / BASE_APK / ASSET_PACK_APK / ASSETS / DATA).

Steps (PowerShell, from C:\Users\benpe\ClashBot):
  1. . .\research\ext\cr-native-sandbox\runtime.env.ps1
  2. python scratchpad\gauntlet\L62\re_verify_bridge.py deploy --bridge v2
        pushes jar/base.apk/assets (only if missing or hash-different) + the v2 bridge
        to /data/local/tmp/cr-native-sandbox-probe, forwards tcp:37041, launches
        `app_process ... serve-direct 37041`, waits for ping.
  3. python scratchpad\gauntlet\L62\re_verify_bridge.py drive --out scratchpad\gauntlet\ext\re\bridge_v2\obs_v2.jsonl
        drives ONE pool replay (default tag 092PPVPCRCPC: Poison, Tornado, Graveyard,
        Ice Spirit, Log, Barbarian Barrel are played by both sides), issuing every
        recorded command for BOTH sides at its tick, records a FULL observe every
        tick, and prints every distinct buff name / area-effect name seen with the
        tick range, remaining_ms trajectory and sanity checks. Use `--synthetic` to
        instead build a Freeze/Zap/Rage/Poison/Tornado/IceSpirit deck and script
        the plays (covers the buff types the pool does not contain).
  4. python scratchpad\gauntlet\L62\re_verify_bridge.py stop
        kills only the probe app_process (matched on the probe remote root) and
        removes the tcp:37041 forward.
  5. Regression vs v1 (same replay, same command schedule => same state_hash stream):
        python ... deploy --bridge v1
        python ... drive --out scratchpad\gauntlet\ext\re\bridge_v2\obs_v1.jsonl
        python ... stop
        python ... compare scratchpad\gauntlet\ext\re\bridge_v2\obs_v1.jsonl scratchpad\gauntlet\ext\re\bridge_v2\obs_v2.jsonl
     `compare` strips the v2-only keys and asserts byte-identical JSON for every
     tick (entities, effects, projectiles, players, state_hash, episode ...).

What "verified" means afterwards (update bridge_re.md + docs/API.md, drop the
`_unverified` suffix from bridge_ext in jni_bridge.cpp, rebuild, recommit):
  * area_effects: names are real record names ("Poison", "Tornado", "Graveyard" ...),
    side/x/y match the cast, remaining_ms decreases 50 per tick from life_ms and the
    object disappears at ~0; class_histogram[3] > 0 while a zone is alive and
    area_effect_vtable_histogram[3] == area_effect_count.
  * buffs: a troop inside Poison shows a buff named like "Poison..." with
    remaining_ms refreshing; a troop hit by Ice Spirit shows "Freeze"-like buff with
    hit_speed_multiplier == speed_multiplier == -100 (flags & 3 == 3) for ~1 s;
    flags never carry 0x40000000 / 0x80000000 (vtable / owner mismatch).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\benpe\ClashBot")
SANDBOX = ROOT / "research" / "ext" / "cr-native-sandbox"
BRIDGE_V2_DIR = ROOT / "scratchpad" / "gauntlet" / "ext" / "re" / "bridge_v2"
BRIDGES = {
    "v1": (BRIDGE_V2_DIR / "libnative_core_probe.v1_82887463.so",
           "82887463deee1f2c92acb70368dbb7d8f323433980a5c1b1abddd15241c81289"),
    "v2": (BRIDGE_V2_DIR / "libnative_core_probe.v2.so",
           "9b63a7a0bce2dcdc8e24608e8b6f161396a05bced4b68f23dab865632ee4ce3f"),
}
POOL = ROOT / "icebow" / "data" / "ghost_pool" / "pool_env_v0.jsonl"
TEMPLATE = SANDBOX / "examples" / "full-card-bootstrap.json"
REMOTE_ROOT = "/data/local/tmp/cr-native-sandbox-probe"
FORBIDDEN_PORTS = {37031, 37032, 38031, 38032}
V2_ENTITY_KEYS = {"buffs", "buff_manager_count", "buff_manager_vtable_rva"}
V2_TOP_KEYS = {"area_effects", "area_effect_count", "class_histogram",
               "area_effect_vtable_histogram", "bridge_ext"}

sys.path.insert(0, str(SANDBOX))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def adb_bin() -> str:
    value = os.environ.get("CR_SANDBOX_ADB")
    if not value:
        raise SystemExit("CR_SANDBOX_ADB missing: dot-source runtime.env.ps1 first")
    return value


def adb(*args: str, check: bool = True, timeout: float = 60.0) -> str:
    cmd = [adb_bin(), "-s", "emulator-5554", *args]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and res.returncode:
        raise SystemExit(f"adb {' '.join(args)} failed:\n{res.stdout}\n{res.stderr}")
    return res.stdout


def remote_sha(path: str) -> str:
    out = adb("shell", f"sha256sum '{path}' 2>/dev/null || true", check=False).strip()
    return out.split()[0].lower() if out else ""


def push_verified(local: Path, remote: str) -> None:
    if remote_sha(remote) == sha256(local):
        print(f"  up to date: {remote}")
        return
    adb("push", str(local), remote + ".upload")
    adb("shell", f"mv '{remote}.upload' '{remote}'")
    if remote_sha(remote) != sha256(local):
        raise SystemExit(f"push verification failed for {remote}")
    print(f"  pushed: {remote}")


def ping(port: int, timeout: float = 2.0) -> dict | None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.sendall((json.dumps({"op": "ping"}) + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode() or "null")
    except OSError:
        return None


def cmd_deploy(args: argparse.Namespace) -> int:
    if args.port in FORBIDDEN_PORTS:
        raise SystemExit("refusing to use a training-worker port")
    bridge, expected = BRIDGES[args.bridge]
    actual = sha256(bridge)
    if actual != expected:
        raise SystemExit(f"{bridge} sha256 {actual} != expected {expected}")
    env = os.environ
    runtime_dir = Path(env["CR_SANDBOX_RUNTIME_DIR"])
    base_apk = Path(env["CR_SANDBOX_BASE_APK"])
    jar = SANDBOX / "artifacts" / "lifecycle-probe.jar"
    assets_tar = SANDBOX / "artifacts" / "runtime-assets.tar"
    if not assets_tar.is_file():
        raise SystemExit(
            "artifacts/runtime-assets.tar missing; run scripts/start_direct_service.ps1 once "
            "(it extracts it) or build it the same way (see that script, lines 108-119)")
    print(f"deploying bridge {args.bridge} ({actual[:12]}) to {REMOTE_ROOT} port {args.port}")
    adb("shell", f"mkdir -p '{REMOTE_ROOT}'")
    for lib in sorted(runtime_dir.glob("*.so")):
        push_verified(lib, f"{REMOTE_ROOT}/{lib.name}")
    push_verified(jar, f"{REMOTE_ROOT}/lifecycle-probe.jar")
    push_verified(bridge, f"{REMOTE_ROOT}/libnative_host_bridge.so")
    push_verified(base_apk, f"{REMOTE_ROOT}/base.apk")
    push_verified(SANDBOX / "examples" / "eight-card-bootstrap.json",
                  f"{REMOTE_ROOT}/bootstrap-replay.json")
    push_verified(assets_tar, f"{REMOTE_ROOT}/runtime-assets.tar")
    adb("shell", f"mkdir -p '{REMOTE_ROOT}/assets' && tar -xf '{REMOTE_ROOT}/runtime-assets.tar' -C '{REMOTE_ROOT}/assets'")
    cmd_stop(args)
    adb("forward", f"tcp:{args.port}", f"tcp:{args.port}")
    classpath = f"{REMOTE_ROOT}/lifecycle-probe.jar:{REMOTE_ROOT}/base.apk"
    launch = (f"cd '{REMOTE_ROOT}' && exec env CLASSPATH='{classpath}' LD_LIBRARY_PATH='{REMOTE_ROOT}' "
              f"app_process /system/bin royale.nativehost.JniHost '{REMOTE_ROOT}' serve-direct '{args.port}'")
    adb("shell", f"nohup sh -c \"{launch}\" >'{REMOTE_ROOT}/service.log' 2>&1 </dev/null &")
    deadline = time.time() + args.ready_timeout
    while time.time() < deadline:
        reply = ping(args.port)
        if reply and reply.get("ok"):
            print("service ready:", json.dumps(reply)[:200])
            return 0
        time.sleep(2)
    print(adb("shell", f"tail -n 60 '{REMOTE_ROOT}/service.log'", check=False))
    raise SystemExit("probe service did not answer")


def cmd_stop(args: argparse.Namespace) -> int:
    listing = adb("shell", "ps -A -o PID,ARGS 2>/dev/null || ps -A", check=False)
    for line in listing.splitlines():
        if REMOTE_ROOT in line and "app_process" in line and "cr-native-direct" not in line:
            pid = line.split()[0]
            print("killing probe pid", pid)
            adb("shell", f"kill {pid}", check=False)
    adb("forward", "--remove", f"tcp:{args.port}", check=False)
    return 0


def load_entry(tag: str) -> dict:
    for line in POOL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["tag"] == tag:
            return r
    raise SystemExit(f"tag {tag} not in {POOL}")


def synthetic_plan() -> tuple[list[dict], list[dict], list[dict]]:
    """Decks + scripted plays that exercise Freeze / Zap / Rage / Poison / Tornado / Ice Spirit.
    Card ids are the Supercell scid values used throughout the pool (26M troops, 28M spells)."""
    deck0 = ["knight", "giant", "ice-spirit", "freeze", "zap", "rage", "poison", "tornado"]
    deck1 = ["knight", "musketeer", "ice-spirit", "freeze", "zap", "rage", "poison", "tornado"]
    # tick, side, card, x, y  (engine coords: x 0..18000, y 0..32000; side 0 at the bottom)
    plays = [
        (200, 0, "giant", 9500, 9500),
        (260, 1, "musketeer", 9500, 22500),
        (400, 0, "rage", 9500, 12500),
        (460, 1, "poison", 9500, 15000),
        (520, 0, "ice-spirit", 9500, 13500),
        (600, 1, "zap", 9500, 15500),
        (700, 1, "freeze", 9500, 16000),
        (760, 0, "tornado", 9500, 18000),
    ]
    return deck0, deck1, [dict(tick=t, side=s, card=c, x=x, y=y) for t, s, c, x, y in plays]


def summarize(observes: list[dict]) -> None:
    buffs: dict[str, dict] = {}
    areas: dict[str, dict] = {}
    bad_flags = 0
    hist_ticks = 0
    for st in observes:
        tick = st["tick"]
        for e in st.get("entities", []):
            for b in e.get("buffs", []):
                d = buffs.setdefault(b["name"], {"first": tick, "last": tick, "n": 0, "remaining": [], "flags": set()})
                d["last"] = tick
                d["n"] += 1
                d["flags"].add(b["flags"])
                if len(d["remaining"]) < 12:
                    d["remaining"].append(b["remaining_ms"])
                if b["flags"] & 0xC0000000:
                    bad_flags += 1
        for a in st.get("area_effects", []):
            d = areas.setdefault(a["name"], {"first": tick, "last": tick, "n": 0, "remaining": [], "sides": set(), "radius": set()})
            d["last"] = tick
            d["n"] += 1
            d["sides"].add(a["side"])
            d["radius"].add(a["current_radius"])
            if len(d["remaining"]) < 12:
                d["remaining"].append(a["remaining_ms"])
        h = st.get("class_histogram")
        if h and st.get("area_effect_count", 0) != (st.get("area_effect_vtable_histogram") or [0] * 4)[3]:
            hist_ticks += 1
    print("\n=== buffs seen ===")
    for name, d in sorted(buffs.items()):
        print(f"  {name!r}: ticks {d['first']}..{d['last']} rows {d['n']} flags {sorted(d['flags'])} remaining[:12] {d['remaining']}")
    print("=== area effects seen ===")
    for name, d in sorted(areas.items()):
        print(f"  {name!r}: ticks {d['first']}..{d['last']} rows {d['n']} sides {sorted(d['sides'])} radius {sorted(d['radius'])[:6]} remaining[:12] {d['remaining']}")
    print(f"buff rows with vtable/owner mismatch flags: {bad_flags}")
    print(f"ticks where area_effect_count != area_effect_vtable_histogram[3]: {hist_ticks}")
    last = observes[-1] if observes else {}
    print("last class_histogram:", last.get("class_histogram"), "bridge_ext:", last.get("bridge_ext"))


def cmd_drive(args: argparse.Namespace) -> int:
    if args.port in FORBIDDEN_PORTS:
        raise SystemExit("refusing to use a training-worker port")
    from native_core.env import NativeRoyaleEnv
    from native_core.decks import build_replay
    template = json.loads(TEMPLATE.read_text(encoding="utf-8-sig"))
    if args.synthetic:
        from native_core.decks import resolve_card
        d0, d1, plays = synthetic_plan()
        spec0 = [dict(card_id=int(resolve_card(c)), form="base", level=args.level) for c in d0]
        spec1 = [dict(card_id=int(resolve_card(c)), form="base", level=args.level) for c in d1]
        name_to_index = {0: {n: i for i, n in enumerate(d0)}, 1: {n: i for i, n in enumerate(d1)}}
        plays = [dict(p, deck_index=name_to_index[p["side"]][p["card"]]) for p in plays]
        max_tick = args.max_ticks or 1200
    else:
        entry = load_entry(args.tag)
        decks = {int(entry["icebow_side"]): entry["icebow_deck"], int(entry["ghost_side"]): entry["ghost_deck"]}
        spec0 = [dict(card_id=int(it["card_id"]), form=it["form"], level=args.level) for it in decks[0]]
        spec1 = [dict(card_id=int(it["card_id"]), form=it["form"], level=args.level) for it in decks[1]]
        plays = []
        for side in (0, 1):
            cmds = entry["icebow_commands"] if side == int(entry["icebow_side"]) else entry["ghost_commands"]
            idx = {int(it["card_id"]): i for i, it in enumerate(decks[side])}
            for c in cmds:
                if c.get("ability"):
                    continue
                plays.append(dict(tick=int(c["tick"]), side=side, card=c["card"], x=int(c["x"]), y=int(c["y"]),
                                  deck_index=idx[int(c["card_id"])]))
        max_tick = args.max_ticks or int(entry.get("duration_ticks") or 3600)
    plays.sort(key=lambda p: p["tick"])
    replay = build_replay(template, spec0, spec1, seed=args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    observes: list[dict] = []
    accepted = rejected = 0
    reasons: dict[str, int] = {}
    pending: list[dict] = []
    with NativeRoyaleEnv(host="127.0.0.1", port=args.port, timeout=args.timeout) as eng, out.open("w", encoding="utf-8") as fh:
        state = eng.reset(replay, warmup_steps=0)
        tick = int(state["tick"])
        pi = 0
        while tick < max_tick and not state.get("episode", {}).get("terminal"):
            # hand-index is engine-dealt, so play by deck_index and let the engine refuse
            due = pending + [p for p in plays[pi:] if p["tick"] <= tick]
            pi += len(due) - len(pending)
            pending = []
            for p in due:
                r = eng.act(side=p["side"], deck_index=p["deck_index"], x=p["x"], y=p["y"])
                code = int(r.get("result_code", -1))
                if r.get("accepted") or code == 0:
                    accepted += 1
                else:
                    name = str(r.get("result", code))
                    reasons[name] = reasons.get(name, 0) + 1
                    if code == 1050 and tick - p["tick"] < 40:   # not_enough_elixir: retry for 2 s
                        pending.append(p)
                    else:
                        rejected += 1
            state = eng.step(1)
            tick = int(state["tick"])
            full = eng.observe()
            observes.append(full)
            fh.write(json.dumps(full, separators=(",", ":")) + "\n")
    print(f"drove {len(observes)} ticks; plays accepted {accepted} rejected {rejected} reasons {reasons}")
    summarize(observes)
    return 0


def strip_v2(state: dict) -> dict:
    s = {k: v for k, v in state.items() if k not in V2_TOP_KEYS}
    s["entities"] = [{k: v for k, v in e.items() if k not in V2_ENTITY_KEYS} for e in state.get("entities", [])]
    return s


def cmd_compare(args: argparse.Namespace) -> int:
    a = [json.loads(l) for l in Path(args.a).read_text(encoding="utf-8").splitlines() if l.strip()]
    b = [json.loads(l) for l in Path(args.b).read_text(encoding="utf-8").splitlines() if l.strip()]
    n = min(len(a), len(b))
    print(f"{len(a)} vs {len(b)} observes; comparing first {n}")
    for i in range(n):
        sa, sb = strip_v2(a[i]), strip_v2(b[i])
        if json.dumps(sa, sort_keys=True) != json.dumps(sb, sort_keys=True):
            for k in sorted(set(sa) | set(sb)):
                if json.dumps(sa.get(k), sort_keys=True) != json.dumps(sb.get(k), sort_keys=True):
                    print(f"tick index {i}: key {k!r} differs")
            raise SystemExit("MISMATCH: pre-existing fields differ between the two bridges")
    print("OK: all pre-existing fields identical (state_hash included) over", n, "ticks")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("deploy")
    d.add_argument("--bridge", choices=sorted(BRIDGES), default="v2")
    d.add_argument("--port", type=int, default=37041)
    d.add_argument("--ready-timeout", type=float, default=300)
    d.set_defaults(fn=cmd_deploy)
    s = sub.add_parser("stop")
    s.add_argument("--port", type=int, default=37041)
    s.set_defaults(fn=cmd_stop)
    r = sub.add_parser("drive")
    r.add_argument("--port", type=int, default=37041)
    r.add_argument("--tag", default="092PPVPCRCPC")
    r.add_argument("--synthetic", action="store_true")
    r.add_argument("--seed", type=int, default=424242)
    r.add_argument("--level", type=int, default=11)
    r.add_argument("--max-ticks", type=int, default=0)
    r.add_argument("--timeout", type=float, default=30)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_drive)
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    c.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

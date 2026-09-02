"""Decisive experiment for the tick-0 stall (HANDOFF 5aw): launch probe-direct with the pre-step hold,
read GameMain's pending-action fields (+0x1b8..+0x1c3) and the stored message string (+0x1d0) from the
live process, optionally clear the pending action exactly as the engine's own processor (0x72d230)
would (qword +0x1bc = 0, word +0x1b8 = 0), release the hold, and report step.tick_after / state_hash.
usage: python hold_fix.py <out_dir> [--clear] [--jar <path>]   (pushes the jar if given)
"""
import json, os, re, subprocess, sys, time, struct
ADB = r"C:\Android\Sdk\platform-tools\adb.exe"
SER = ["-s", "emulator-5554"]
ROOT = "/data/local/tmp/cr-native-sandbox-probe"
out_dir = sys.argv[1]; os.makedirs(out_dir, exist_ok=True)
clear = "--clear" in sys.argv
if "--jar" in sys.argv:
    jar = sys.argv[sys.argv.index("--jar") + 1]
    subprocess.run([ADB, *SER, "push", jar, f"{ROOT}/lifecycle-probe.jar.upload"], check=True, capture_output=True)
    subprocess.run([ADB, *SER, "shell", f"mv -f {ROOT}/lifecycle-probe.jar.upload {ROOT}/lifecycle-probe.jar && chmod 0666 {ROOT}/lifecycle-probe.jar && sha256sum {ROOT}/lifecycle-probe.jar"], check=True)
def sh(cmd):
    return subprocess.run([ADB, *SER, "shell", cmd], capture_output=True, text=True).stdout
sh(f"rm -f {ROOT}/.hold_release")
launch = (f"cd '{ROOT}' && CR_PROBE_HOLD_PRE_MS=120000 CLASSPATH='{ROOT}/lifecycle-probe.jar:{ROOT}/base.apk' "
          f"LD_LIBRARY_PATH='{ROOT}' app_process /system/bin royale.nativehost.JniHost '{ROOT}' probe-direct '{ROOT}/input-replay.json'")
log_path = os.path.join(out_dir, "probe.log")
log = open(log_path, "wb")
proc = subprocess.Popen([ADB, *SER, "shell", launch], stdout=log, stderr=subprocess.STDOUT)
def read_log():
    with open(log_path, "rb") as f:
        return f.read().decode("utf-8", "replace")
pid = None; deadline = time.time() + 150
while time.time() < deadline and proc.poll() is None:
    time.sleep(0.5)
    m = re.search(r'"stage":"probe_hold_pre","pid":(\d+)', read_log())
    if m: pid = int(m.group(1)); break
if pid is None:
    print("no probe_hold_pre line; probe exited", proc.poll()); sys.exit(1)
text = read_log()
def jl(stage, event=None):
    for l in text.splitlines():
        if f'"stage":"{stage}"' in l and (event is None or f'"event":"{event}"' in l):
            return json.loads(l[l.index("{"):])
    return None
game = int(jl("prerequisite_probe", "after_direct_resources")["value"]["game_singleton"], 16)
print("held pid", pid, "GameMain", hex(game))
def rd(addr, n, name):
    remote = f"/data/local/tmp/dump/{name}.bin"
    sh(f"mkdir -p /data/local/tmp/dump; /data/local/tmp/memdump {pid} {addr:x} {n:x} {remote}")
    local = os.path.join(out_dir, f"{name}.bin")
    subprocess.run([ADB, *SER, "pull", remote, local], capture_output=True)
    return open(local, "rb").read()
g = rd(game + 0x1b0, 0x40, "gm_1b0_before")
b8, b9, code, param = g[8], g[9], struct.unpack("<I", g[0xc:0x10])[0], struct.unpack("<I", g[0x10:0x14])[0]
slen, sptr = struct.unpack("<I", g[0x24:0x28])[0], struct.unpack("<Q", g[0x28:0x30])[0]
print(f"before: +0x1b8={b8} +0x1b9={b9} +0x1bc(code)={code} +0x1c0(param)={param} str len={slen} ptr={sptr:#x}")
msg = rd(sptr, slen, "gm_msg").decode("utf-8", "replace") if slen and sptr else ""
print("stored message:", repr(msg))
result = {"pid": pid, "game": hex(game), "before": {"b8": b8, "b9": b9, "code": code, "param": param, "msg": msg}, "clear": clear}
if clear:
    print("memwrite +0x1bc:", sh(f"/data/local/tmp/memwrite {pid} {game+0x1bc:x} 0000000000000000").strip())
    print("memwrite +0x1b8:", sh(f"/data/local/tmp/memwrite {pid} {game+0x1b8:x} 0000").strip())
    g2 = rd(game + 0x1b0, 0x40, "gm_1b0_after")
    print("after :", g2[8:0x14].hex())
sh(f"touch {ROOT}/.hold_release")
try:
    proc.wait(timeout=180)
except subprocess.TimeoutExpired:
    sh(f"kill -9 {pid}"); proc.wait(timeout=30)
text = read_log()
res = jl("probe_result")
if res:
    v = res["value"]
    result["step"] = {k: v["step"].get(k) for k in ("tick_before", "tick_after", "stepped")}
    result["state_hash"] = v["state"].get("state_hash"); result["rng_state"] = v["state"].get("rng_state")
    result["crown_hp"] = [t["hp"] for t in v["state"]["episode"]["crown_towers"]]
    result["elapsed_ms"] = v.get("elapsed_ms")
    print("STEP", result["step"], "hash", result["state_hash"], "rng", result["rng_state"], "hp", result["crown_hp"])
else:
    print("no probe_result; exit", proc.poll())
json.dump(result, open(os.path.join(out_dir, "result.json"), "w"), indent=1)
print("exit", proc.poll())

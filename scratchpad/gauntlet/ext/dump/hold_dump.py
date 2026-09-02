"""Launch the (patched) probe-direct with CR_PROBE_HOLD_MS, wait for the probe_hold line, then dump
live libg state through memdump (/proc/<pid>/mem) while the stalled battle is still alive.
Assumes run_probe.ps1 has already pushed the current jar/bridge/libg to /data/local/tmp/cr-native-sandbox-probe.
usage: python hold_dump.py <out_dir> [extra "name=hexaddr:hexlen" ...]
"""
import json, os, re, subprocess, sys, time
ADB = r"C:\Android\Sdk\platform-tools\adb.exe"
SER = ["-s", "emulator-5554"]
ROOT = "/data/local/tmp/cr-native-sandbox-probe"
out_dir = sys.argv[1]; os.makedirs(out_dir, exist_ok=True)
extra = sys.argv[2:]
launch = (f"cd '{ROOT}' && CR_PROBE_HOLD_MS=90000 CLASSPATH='{ROOT}/lifecycle-probe.jar:{ROOT}/base.apk' "
          f"LD_LIBRARY_PATH='{ROOT}' app_process /system/bin royale.nativehost.JniHost '{ROOT}' probe-direct '{ROOT}/input-replay.json'")
log_path = os.path.join(out_dir, "probe_hold.log")
log = open(log_path, "wb")
proc = subprocess.Popen([ADB, *SER, "shell", launch], stdout=log, stderr=subprocess.STDOUT)
pid = None; lines = []
deadline = time.time() + 120
while time.time() < deadline and proc.poll() is None:
    time.sleep(0.5)
    with open(log_path, "rb") as f:
        text = f.read().decode("utf-8", "replace")
    m = re.search(r'"stage":"probe_hold","pid":(\d+)', text)
    if m:
        pid = int(m.group(1)); lines = text.splitlines(); break
if pid is None:
    print("no probe_hold line; probe exited", proc.poll()); sys.exit(1)
print("held pid", pid)
def jl(stage, event=None):
    for l in lines:
        if f'"stage":"{stage}"' in l and (event is None or f'"event":"{event}"' in l):
            return json.loads(l[l.index("{"):])
    return None
res = jl("probe_result")["value"]
pre = jl("prerequisite_probe", "after_direct_resources")["value"]
dt = jl("direct_data_tables")["value"]
maps = subprocess.run([ADB, *SER, "shell", f"cat /proc/{pid}/maps"], capture_output=True, text=True).stdout
open(os.path.join(out_dir, "maps.txt"), "w").write(maps)
base = None
for l in maps.splitlines():
    if "libg.so" in l:
        base = int(l.split("-")[0], 16); break
info = {"pid": pid, "libg_base": hex(base), "step": res["step"], "ready_tick": res["ready"]["tick"],
        "state": res["step"]["state"], "battle": res["step"]["battle"], "game_singleton": pre.get("game_singleton"),
        "runtime_clock": pre.get("runtime_clock"), "manager": pre.get("manager"), "loading_state": dt.get("loading_state"),
        "logic_battle": res["pump"].get("logic_battle"), "replay": res["pump"].get("replay")}
print(json.dumps({k: v for k, v in info.items() if k != "step"}))
regions = {
    "state": (int(info["state"], 16), 0x800),
    "battle": (int(info["battle"], 16), 0x800),
    "game_singleton": (int(info["game_singleton"], 16), 0x800),
    "runtime_clock": (int(info["runtime_clock"], 16), 0x200),
    "loading_state": (int(info["loading_state"], 16), 0x200),
    "logic_battle": (int(info["logic_battle"], 16), 0x800),
    "libg_data_rw": (base + 0x19af000, 0xaa000),   # rw-p mapping (file off 0x19af000)
    "libg_bss_tail": (base + 0x1afc000, 0x4000),
}
for e in extra:
    name, spec = e.split("="); a, n = spec.split(":"); regions[name] = (int(a, 16), int(n, 16))
for name, (addr, n) in regions.items():
    remote = f"/data/local/tmp/dump/{name}.bin"
    r = subprocess.run([ADB, *SER, "shell", f"mkdir -p /data/local/tmp/dump; /data/local/tmp/memdump {pid} {addr:x} {n:x} {remote}"], capture_output=True, text=True)
    print(name, hex(addr), hex(n), r.stdout.strip(), r.stderr.strip())
    subprocess.run([ADB, *SER, "pull", remote, os.path.join(out_dir, f"{name}.bin")], capture_output=True)
json.dump(info, open(os.path.join(out_dir, "info.json"), "w"), indent=1)
subprocess.run([ADB, *SER, "shell", f"kill -9 {pid}"], capture_output=True)
proc.wait(timeout=30)
print("done")

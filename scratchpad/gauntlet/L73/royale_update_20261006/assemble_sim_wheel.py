"""Assemble the royalesim wheel by hand from `cargo build --release --no-default-features` output.

Why: maturin.exe is blocked on this machine by Windows Application Control (OS error 4551) as of 2026-10-06,
although the same binary built the 20261005 wheel on 2026-10-05. Nothing is renamed, copied or unblocked; cargo built the
cdylib, and this script lays out the same wheel structure maturin 1.15 wrote for the 0.1.13 wheel (royalesim/*.py, data,
royalesim.pyd, dist-info with METADATA/WHEEL/LICENSE/RECORD; maturin's CycloneDX SBOM is not reproduced).
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SIM = ROOT / "research/ext/Royale-20261006/RoyaleSim"
OLD = ROOT / "research/ext/Royale-20261005/wheels/royalesim-0.1.13-cp310-abi3-win_amd64.whl"
OUT = ROOT / "research/ext/Royale-20261006/wheels"
VERSION = re.search(r'^version = "(.+?)"', (SIM / "crates/royalesim/Cargo.toml").read_text(), re.M).group(1)
dll = SIM / "crates/royalesim/target/release/royalesim.dll"
dist = f"royalesim-{VERSION}.dist-info"

with zipfile.ZipFile(OLD) as z:
    old_meta = z.read("royalesim-0.1.13.dist-info/METADATA").decode("utf-8")
header = old_meta.split("\n\n", 1)[0].replace("Version: 0.1.13", f"Version: {VERSION}")
meta = header + "\n\n" + (SIM / "README.md").read_text(encoding="utf-8")
files = {}
pkg = SIM / "python/royalesim"
for p in sorted(pkg.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
        files["royalesim/" + p.relative_to(pkg).as_posix()] = p.read_bytes()
files["royalesim/royalesim.pyd"] = dll.read_bytes()
files[f"{dist}/METADATA"] = meta.encode("utf-8")
files[f"{dist}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: manual-cargo-assembly (maturin.exe blocked, OS4551)\nRoot-Is-Purelib: false\nTag: cp310-abi3-win_amd64\n"
files[f"{dist}/licenses/LICENSE"] = (SIM / "LICENSE").read_bytes()
rec = []
for name, data in files.items():
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    rec.append(f"{name},sha256={digest},{len(data)}")
rec.append(f"{dist}/RECORD,,")
files[f"{dist}/RECORD"] = ("\n".join(rec) + "\n").encode()
OUT.mkdir(exist_ok=True)
wheel = OUT / f"royalesim-{VERSION}-cp310-abi3-win_amd64.whl"
if wheel.exists():
    raise SystemExit("wheel exists; refusing to overwrite")
with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(zipfile.ZipInfo(name, (2026, 10, 6, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
print(wheel, wheel.stat().st_size)

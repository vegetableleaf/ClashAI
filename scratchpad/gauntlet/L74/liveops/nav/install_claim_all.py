"""Install the Claim All template into a navigator template dir: copy claim_all.png + merge manifest_fragment.json into manifest.json
(idempotent; backs up manifest.json once as manifest.json.pre_claim_all). Inert until ladder_nav.py has the patch too (and the other
way round): either half alone changes nothing. Default dest = the LIVE templates, so run it only when the lead says so.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/nav/install_claim_all.py [--dest DIR]"""
import argparse
import json
import shutil
from pathlib import Path

H = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--dest", default=str(H.parents[2] / "L70" / "ladder_nav" / "templates"))
dest = Path(ap.parse_args().dest)
man = json.loads((dest / "manifest.json").read_text())
frag = json.loads((H / "manifest_fragment.json").read_text())
if man["templates"].get("claim_all") == frag["claim_all"] and (dest / "claim_all.png").exists():
    print("already installed:", dest)
else:
    bak = dest / "manifest.json.pre_claim_all"
    if not bak.exists():
        shutil.copy(dest / "manifest.json", bak)
    shutil.copy(H / "templates" / "claim_all.png", dest / "claim_all.png")
    man["templates"].update(frag)
    (dest / "manifest.json").write_text(json.dumps(man, indent=1))
    print("installed claim_all into", dest, "(backup", bak.name + ")")

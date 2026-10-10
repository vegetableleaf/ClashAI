"""Offline syntax/import and legacy-preservation checks; never starts a simulator.

With --shell, also require bash -n (pod/hosts where Bash can start).
"""
import ast
import importlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
BASE = "9489fb0e99dc7eacb640259241b1fe731af9b7a6"
WK = "scratchpad/gauntlet/L74/weekend/"
MF = "scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py"


def original(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT).decode("utf-8")


def functions(src):
    return {n.name: n for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def same(a, b):
    return ast.dump(a, include_attributes=False) == ast.dump(b, include_attributes=False)


def verify():
    old = functions(original(WK + "drill_arms.py"))
    new = functions((ROOT / WK / "drill_arms.py").read_text())
    for name, node in old.items():
        current = new[name]
        if name == "build_arms":
            # Only the new variant/new-drill guards precede the original body.
            current.body = current.body[:1] + current.body[3:]
        assert same(node, current), f"legacy arm changed: {name}"
    old_m = functions(original(MF))
    new_m = functions((ROOT / MF).read_text())
    assert same(old_m["rocket_tower_choice"], new["rocket_tower_choice"]), "shared Rocket mechanic drift"
    for name, node in old_m.items():
        if name == "rocket_tower_choice":
            continue
        if name == "mech_fork":
            class StripMetadata(ast.NodeTransformer):
                def visit_If(self, n):
                    if ast.unparse(n.test) == "moment is not None and moment.get('variant')":
                        return None
                    return self.generic_visit(n)
            current = StripMetadata().visit(new_m[name])
        else:
            current = new_m[name]
        assert same(node, current), f"legacy fork changed: {name}"
    script = (ROOT / WK / "wk_driver.sh").read_text()
    extra = script.index("# ---------------------------------------------------------------------------------------------------- S9XL2 / S10XL2")
    main = script.index("# ---------------------------------------------------------------------------------------------------- main", extra)
    stripped = (script[:extra] + script[main:]).replace('TRAIN=" S5 S6 S10 S10XL S10XL2 "', 'TRAIN=" S5 S6 S10 S10XL "')
    assert stripped == original(WK + "wk_driver.sh"), "legacy driver drift"
    for path in ("scratchpad/gauntlet/L74/drills/drills.py", WK + "moments_from_dump.py", WK + "train_drills.py",
                 WK + "run_wk.sh", WK + "wk_xl_stats.py"):
        assert (ROOT / path).read_text() == original(path), path
    for name in ("pro_when", "xl2_selectors", "drill_arms", "variant_search", "xl2_stage", "xl2_fork"):
        sys.path[:0] = [str(ROOT), str(ROOT / WK), str(ROOT / "scratchpad/gauntlet/L74/drills")]
        module = importlib.import_module(name)
        compile(Path(module.__file__).read_text(), module.__file__, "exec")
    compile((ROOT / MF).read_text(), MF, "exec")
    if "--shell" in sys.argv:
        for path in (WK + "wk_driver.sh", WK + "run_xl2.sh"):
            subprocess.run(["bash", "-n", str(ROOT / path)], check=True)
    if "--tests" in sys.argv:
        subprocess.run([sys.executable, "-m", "pytest", str(ROOT / WK / "tests"), "-q", "-p", "no:cacheprovider"], cwd=ROOT, check=True)
        print("XL2 unit checks passed")
    print("XL2 static checks passed" + ("; bash -n passed" if "--shell" in sys.argv else "; shell syntax requires separate bash -n"))


if __name__ == "__main__":
    verify()

"""Model checkpoint registry -- owner rule 2026-10-17: every model is named "[DECK] Mark [Roman numeral]: [WORD]".

registry.json (next to this file) is the source of truth; REGISTRY.md is generated from it. Original checkpoint files are
never moved or renamed: each Mark gets NTFS hard links (same volume, zero extra space) under icebow/data/models/<DECK>/
named <DECK>_Mark_<ROMAN>_<WORD>.pt (+ _grafted.pt for a grafted twin), and every link is sha256-verified.

  register_ckpt.py PATH [GRAFTED_PATH] --deck ICEBOW|Bait --change WORD --parent "ICEBOW Mark N"|none
                   [--run RUNID] [--note TEXT] [--eval TEXT]      append the next Mark of DECK, link, render
  register_ckpt.py --name PATH       print PATH's Mark name (by sha256), or "unregistered"
  register_ckpt.py --render          regenerate REGISTRY.md from registry.json
  register_ckpt.py --relink          create missing links and verify every link against its original
  register_ckpt.py --selftest        assert-based self-check in a temp dir (touches nothing real)

N in --parent may be Roman (XII) or arabic (12). WORD = one uppercase word [A-Z0-9]+ naming the change vs the parent.
"""
import argparse, datetime, hashlib, json, os, re, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # scratchpad/gauntlet/L74/models -> repo root
DECKS = ("ICEBOW", "Bait")
WORD_RE = re.compile(r"^[A-Z0-9]+$")
NAME_RE = re.compile(r"^(ICEBOW|Bait) Mark ([IVXLCDM]+|\d+)$")
_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
          (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n: int) -> str:
    assert n > 0
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out, n = out + s, n - v
    return out


def unroman(s: str) -> int:
    if s.isdigit():
        return int(s)
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    n = sum(-vals[a] if vals[a] < vals[b] else vals[a] for a, b in zip(s, s[1:])) + vals[s[-1]]
    if roman(n) != s:
        raise ValueError(f"not a canonical Roman numeral: {s}")
    return n


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(path: str, root: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / p


def rel(p: Path, root: Path) -> str:
    p = p.resolve()
    try:
        return p.relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def display(m: dict) -> str:
    return f"{m['deck']} Mark {roman(m['n'])}: {m['word']}"


def link_path(deck: str, n: int, word: str, role: str) -> str:
    return f"icebow/data/models/{deck}/{deck}_Mark_{roman(n)}_{word}{'_grafted' if role == 'grafted' else ''}.pt"


class Registry:
    def __init__(self, path: Path, root: Path):
        self.path, self.root = path, root
        self.d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema": 1, "marks": [], "unmarked": []}

    def save(self):
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def find_mark(self, name: str) -> dict:
        m = NAME_RE.match(name.strip())
        if not m:
            raise ValueError(f'parent must look like "ICEBOW Mark XII" or "none", got {name!r}')
        deck, n = m.group(1), unroman(m.group(2))
        for mk in self.d["marks"]:
            if mk["deck"] == deck and mk["n"] == n:
                return mk
        raise ValueError(f"no such Mark: {name}")

    def lookup(self, sha: str) -> str:
        for mk in self.d["marks"]:
            for f in mk["files"]:
                if f["sha256"] == sha:
                    return display(mk) + (f" ({f['role']})" if f["role"] not in ("model", "grafted") else "")
        for u in self.d.get("unmarked", []):
            if u["sha256"] == sha:
                return "unregistered" + (f" -- {u['why']}" if u.get("why") else "")
        return "unregistered"

    def link_one(self, mk: dict, f: dict) -> str:
        """Create (if missing) and verify f's hard link. Returns 'created' / 'ok'; raises on any mismatch."""
        if not f.get("link"):
            return "nolink"
        src, dst = resolve(f["path"], self.root), resolve(f["link"], self.root)
        if not src.exists():
            raise FileNotFoundError(f"{display(mk)}: original missing: {src}")
        state = "ok"
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(src, dst)                       # same volume -> NTFS hard link, no copy
            state = "created"
        if not os.path.samefile(src, dst):
            raise RuntimeError(f"{dst} exists but is not a hard link of {src}")
        got = sha256(dst)
        if got != f["sha256"]:
            raise RuntimeError(f"{dst}: sha256 {got[:12]} != registered {f['sha256'][:12]}")
        return state

    def relink(self) -> dict:
        out = {"created": 0, "ok": 0, "nolink": 0}
        for mk in self.d["marks"]:
            for f in mk["files"]:
                out[self.link_one(mk, f)] += 1
        return out

    def register(self, paths, deck, word, parent, run=None, note=None, ev=None) -> dict:
        if deck not in DECKS:
            raise ValueError(f"deck must be one of {DECKS}")
        if not WORD_RE.match(word):
            raise ValueError(f"change word must be ONE uppercase word [A-Z0-9]+, got {word!r}")
        parent_name = None
        if parent and parent.lower() != "none":
            parent_name = display(self.find_mark(parent))
        files = []
        for i, p in enumerate(paths):
            p = resolve(p, self.root) if not Path(p).is_absolute() else Path(p)
            if not p.is_file():
                raise FileNotFoundError(p)
            sha = sha256(p)
            hit = self.lookup(sha)
            if not hit.startswith("unregistered"):
                raise ValueError(f"{p} is already registered as {hit}")
            files.append({"path": rel(p, self.root), "sha256": sha, "role": "grafted" if i == 1 else "model"})
        if len(files) == 2 and files[0]["sha256"] == files[1]["sha256"]:
            raise ValueError("the grafted twin is the same file as the model")
        n = 1 + max([m["n"] for m in self.d["marks"] if m["deck"] == deck], default=0)
        for f in files:
            f["link"] = link_path(deck, n, word, f["role"])
        mtime = datetime.datetime.fromtimestamp(resolve(files[0]["path"], self.root).stat().st_mtime)
        mk = {"deck": deck, "n": n, "word": word, "name": None, "run": run or "", "parent": parent_name,
              "change": note or "", "created": mtime.isoformat(timespec="minutes"), "eval": ev or "", "live": "",
              "files": files, "registered": datetime.datetime.now().isoformat(timespec="minutes")}
        mk["name"] = display(mk)
        self.d["marks"].append(mk)
        # drop any 'unmarked' record of these files (they are Marks now)
        shas = {f["sha256"] for f in files}
        self.d["unmarked"] = [u for u in self.d.get("unmarked", []) if u["sha256"] not in shas]
        for f in files:
            self.link_one(mk, f)
        self.save()
        return mk


def _cell(s) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def render(reg: Registry, out: Path) -> None:
    d = reg.d
    L = ["# Model checkpoint registry", "",
         "Owner rule 2026-10-17: every model checkpoint is named **\"[DECK] Mark [Roman numeral]: [One word that describes "
         "the change]\"**. Decks: **ICEBOW** (the icebow X-Bow deck) and **Bait** (the Log Bait deck). Generated from "
         "`registry.json` by `register_ckpt.py --render`; do not edit by hand.", "",
         d.get("rule", ""), ""] + [f"- {n}" for n in d.get("notes", [])] + ["",
         "Original files are never moved or renamed. Each Mark has NTFS hard links (zero extra space, sha256-verified) "
         "under `icebow/data/models/<DECK>/` named `<DECK>_Mark_<ROMAN>_<WORD>.pt` (`_grafted.pt` = the grafted twin "
         "that live play loads). `register_ckpt.py --name PATH` prints any file's Mark name.", ""]
    for deck in DECKS:
        marks = sorted((m for m in d["marks"] if m["deck"] == deck), key=lambda m: m["n"])
        L += [f"## {deck} ({len(marks)} Marks)", "",
              "| Mark | file(s) (path, sha256[:12]) | run id | parent Mark | change detail | created | key eval vs its baseline | live periods |",
              "|---|---|---|---|---|---|---|---|"]
        for m in marks:
            fl = "<br>".join(f"{_cell(f['role'])}: `{_cell(f['path'])}` {f['sha256'][:12]}"
                             + (" (pod backup only)" if f["path"].startswith("C:/Users/benpe/pod_backup_weekend/")
                                and not any(not c.startswith("C:/") for c in f.get("copies", [])) else "")
                             + (f" (+{len(f['copies'])} identical copies)" if f.get("copies") else "")
                             for f in m["files"]) or "(no local copy)"
            par = m["parent"] or (f"- (scratch; compared to {m['compared_to']})" if m.get("compared_to") else "-")
            L.append(f"| **{_cell(m['name'])}** | {fl} | {_cell(m['run'])} | {_cell(par)} | "
                     f"{_cell(m['change'])} | {_cell(m['created'])} | {_cell(m['eval'])} | {_cell(m['live'] or '-')} |")
        L.append("")
    L += ["## How to name a new checkpoint", "",
          "1. It needs a Mark only if it is a distinct model: evaluated as a candidate, deployed live, or used as the init "
          "of another run. Snapshots (u0005, u0010 ...) and seed replicates stay unmarked (listed below).",
          "2. Pick its PARENT Mark = the checkpoint it was initialised from (`rl.init` / `grafted_heads_from` inside the "
          ".pt). Scratch IL models have no parent; name the change vs the model they were measured against.",
          "3. Pick ONE uppercase word for the change vs the parent (e.g. CUES, EXPLOITERS, HEROIW, LONGER, POSTURE). If "
          "the run bundled several changes, name the dominant one and list all in --note. A repeated word is fine; the "
          "numeral disambiguates.",
          "4. Register it (the number is the deck's next Roman numeral):",
          "   `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/models/register_ckpt.py PATH [GRAFTED_PATH] "
          "--deck ICEBOW --change CUES --parent \"ICEBOW Mark CXXIV\" --run RUNID --note \"...\" --eval \"...\"`",
          "   It hashes the file(s), appends the Mark to registry.json, creates + verifies the hard link(s) and "
          "regenerates this file. Commit registry.json + REGISTRY.md (never icebow/data).",
          "5. When a Mark goes live, add its live period to its `live` field in registry.json and run `--render`.", ""]
    un = d.get("unmarked", [])
    if un:
        groups = {}
        for u in un:
            groups.setdefault(u.get("why", ""), []).append(u)
        L += [f"## Unmarked checkpoints ({len(un)} files)", "",
              "Files that exist but are not distinct models (snapshots, seed replicates, smokes, failed runs, test "
              "scaffolding, opponent/exploiter policies, eval controls). `--name` reports the relation below.", "",
              "| relation | files | examples |", "|---|---|---|"]
        for why, us in sorted(groups.items(), key=lambda kv: kv[0]):
            ex = "<br>".join(f"`{_cell(u['path'])}`" for u in us[:3]) + (f"<br>... (+{len(us) - 3})" if len(us) > 3 else "")
            L.append(f"| {_cell(why)} | {len(us)} | {ex} |")
        L.append("")
    out.write_text("\n".join(L), encoding="utf-8")


def selftest() -> None:
    assert [roman(i) for i in (1, 4, 9, 14, 40, 49, 90, 400, 1994)] == \
        ["I", "IV", "IX", "XIV", "XL", "XLIX", "XC", "CD", "MCMXCIV"]
    assert all(unroman(roman(i)) == i for i in range(1, 400)) and unroman("12") == 12
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "ck").mkdir()
        for name, data in (("a.pt", b"A" * 100), ("b.pt", b"B" * 50), ("b_grafted.pt", b"G" * 70), ("c.pt", b"C")):
            (root / "ck" / name).write_bytes(data)
        reg = Registry(root / "registry.json", root)
        reg.d["unmarked"].append({"path": "ck/c.pt", "sha256": sha256(root / "ck/c.pt"), "of": "ICEBOW Mark I",
                                  "why": "snapshot of ICEBOW Mark I: IMITATION"})
        m1 = reg.register(["ck/a.pt"], "ICEBOW", "IMITATION", "none", run="r0", note="scratch")
        assert m1["name"] == "ICEBOW Mark I: IMITATION" and m1["parent"] is None
        m2 = reg.register(["ck/b.pt", "ck/b_grafted.pt"], "ICEBOW", "CUES", "ICEBOW Mark I", run="r1")
        assert m2["name"] == "ICEBOW Mark II: CUES" and m2["parent"] == "ICEBOW Mark I: IMITATION"
        assert [f["role"] for f in m2["files"]] == ["model", "grafted"]
        lk = root / "icebow/data/models/ICEBOW/ICEBOW_Mark_II_CUES_grafted.pt"
        assert lk.exists() and os.path.samefile(lk, root / "ck/b_grafted.pt") and sha256(lk) == sha256(root / "ck/b_grafted.pt")
        m3 = reg.register(["ck/c.pt"], "Bait", "BAIT", "ICEBOW Mark 2")      # cross-deck parent, arabic numeral
        assert m3["name"] == "Bait Mark I: BAIT" and m3["parent"] == "ICEBOW Mark II: CUES"
        assert not reg.d["unmarked"]                                        # c.pt left the unmarked list
        for bad in (dict(deck="icebow", word="X", parent="none"), dict(deck="ICEBOW", word="cues", parent="none"),
                    dict(deck="ICEBOW", word="TWO WORDS", parent="none"), dict(deck="ICEBOW", word="X", parent="ICEBOW Mark IX")):
            try:
                reg.register(["ck/a.pt"], bad["deck"], bad["word"], bad["parent"])
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted {bad}")
        try:                                                                 # same file twice -> refused
            reg.register(["ck/a.pt"], "ICEBOW", "AGAIN", "none")
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate sha accepted")
        reg2 = Registry(root / "registry.json", root)                        # persisted
        assert len(reg2.d["marks"]) == 3
        assert reg2.lookup(sha256(root / "ck/b.pt")) == "ICEBOW Mark II: CUES"
        assert reg2.lookup(sha256(lk)) == "ICEBOW Mark II: CUES"            # the link resolves to the same Mark
        assert reg2.lookup(hashlib.sha256(b"nope").hexdigest()) == "unregistered"
        assert reg2.relink() == {"created": 0, "ok": 4, "nolink": 0}
        lk.unlink()
        assert reg2.relink()["created"] == 1 and lk.exists()
        (root / "ck/a.pt").write_bytes(b"tampered")                          # a changed original must fail verification
        try:
            reg2.relink()
        except RuntimeError:
            pass
        else:
            raise AssertionError("tampered original verified")
        render(reg2, root / "REGISTRY.md")
        md = (root / "REGISTRY.md").read_text(encoding="utf-8")
        assert "**ICEBOW Mark II: CUES**" in md and "**Bait Mark I: BAIT**" in md and "How to name" in md
    print("selftest PASS")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--deck", choices=DECKS)
    ap.add_argument("--change")
    ap.add_argument("--parent")
    ap.add_argument("--run")
    ap.add_argument("--note")
    ap.add_argument("--eval")
    ap.add_argument("--name", metavar="PATH")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--relink", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    reg = Registry(HERE / "registry.json", ROOT)
    if a.name:
        if not Path(a.name).is_file():
            print(f"no such file: {a.name}", file=sys.stderr)
            return 2
        print(reg.lookup(sha256(Path(a.name))))
        return 0
    if a.relink:
        print(json.dumps(reg.relink()))
        render(reg, HERE / "REGISTRY.md")
        return 0
    if a.render:
        render(reg, HERE / "REGISTRY.md")
        return 0
    if not (a.paths and a.deck and a.change and a.parent):
        ap.error("registering needs PATH [GRAFTED_PATH] --deck --change --parent")
    if len(a.paths) > 2:
        ap.error("at most two paths: the model and its grafted twin")
    mk = reg.register(a.paths, a.deck, a.change, a.parent, a.run, a.note, a.eval)
    render(reg, HERE / "REGISTRY.md")
    print(mk["name"])
    for f in mk["files"]:
        print(f"  {f['role']}: {f['link']} -> {f['path']} ({f['sha256'][:12]}, verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

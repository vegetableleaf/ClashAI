"""ClashBot course server (stdlib only). Serves the syllabus and lessons, runs exercise code, and stores progress.

Run:  icebow/.venv/Scripts/python.exe course/server.py [--port 8765]      Self-check:  ... course/server.py --selftest
Binds 127.0.0.1 only: it executes code you type, so it must never listen on the network.

Data (all under course/):
  syllabus.json                 parts -> lessons (id, title, hours, files, summary, project)
  lessons/<ID>.md               lesson text (Markdown)
  exercises/<ID>.json           [{id, title, lang: python|bash, prompt, starter, tests?, expect?, hint?, solution?}]
                                python: `tests` (asserts) run after your code in the same file; pass = exit code 0.
                                any lang: `expect` = a regex your program's stdout must match.
  progress.json                 written by the server: lessons {status, note, updated}, exercises {passed, attempts, ...}
"""
import json, os, re, shutil, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROGRESS = HERE / "progress.json"
LOCK = threading.Lock()
TIMEOUT_S = 30


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_progress():
    try:
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"lessons": {}, "exercises": {}}


def save_progress(p):
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps(p, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, PROGRESS)


def exercises(lid):
    f = HERE / "exercises" / f"{lid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def run_code(ex, code):
    """Run the learner's code (+ the exercise's tests) in a temp file, cwd = repo root. Returns (passed, output)."""
    lang = ex.get("lang", "python")
    with tempfile.TemporaryDirectory() as td:
        if lang == "bash":
            src = Path(td) / "answer.sh"
            src.write_text(code, encoding="utf-8", newline="\n")
            cmd = [shutil.which("bash") or "bash", str(src)]
        else:
            src = Path(td) / "answer.py"
            src.write_text(code + "\n\n# ---- checks ----\n" + ex.get("tests", ""), encoding="utf-8")
            cmd = [sys.executable, str(src)]
        try:
            r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=TIMEOUT_S,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"})
        except subprocess.TimeoutExpired:
            return False, f"Stopped: your program ran longer than {TIMEOUT_S} s (an endless loop?)."
    out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    ok = r.returncode == 0 and (not ex.get("expect") or re.search(ex["expect"], r.stdout or "", re.M) is not None)
    if r.returncode == 0 and not ok:
        out += f"\n[check] your output did not match what was expected (pattern: {ex['expect']})"
    return ok, out[-20000:]


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._send(200, (HERE / "static" / "index.html").read_bytes(), "text/html")
        if p.startswith("/lesson/"):
            return self._send(200, (HERE / "static" / "lesson.html").read_bytes(), "text/html")
        if p == "/api/syllabus":
            return self._send(200, json.loads((HERE / "syllabus.json").read_text(encoding="utf-8")))
        if p == "/api/progress":
            with LOCK:
                return self._send(200, load_progress())
        m = re.fullmatch(r"/api/lesson/([A-Z]\d\d)", p)
        if m:
            lid = m.group(1)
            md = HERE / "lessons" / f"{lid}.md"
            exs = [{k: v for k, v in e.items() if k != "solution"} | {"has_solution": bool(e.get("solution"))}
                   for e in exercises(lid)]
            return self._send(200, {"id": lid, "md": md.read_text(encoding="utf-8") if md.exists() else None, "exercises": exs})
        m = re.fullmatch(r"/api/solution/([A-Z]\d\d)/([\w-]+)", p)
        if m:
            ex = next((e for e in exercises(m.group(1)) if e["id"] == m.group(2)), None)
            if not ex:
                return self._send(404, {"error": "no such exercise"})
            with LOCK:
                pr = load_progress()
                pr["exercises"].setdefault(f"{m.group(1)}/{ex['id']}", {})["solution_viewed"] = now()
                save_progress(pr)
            return self._send(200, {"solution": ex.get("solution", "")})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        b = self._body()
        if p == "/api/progress":            # {lesson, status: not_started|in_progress|done, note?}
            with LOCK:
                pr = load_progress()
                e = pr["lessons"].setdefault(b["lesson"], {})
                if "status" in b:
                    e["status"] = b["status"]
                if "note" in b:
                    e["note"] = b["note"]
                e["updated"] = now()
                save_progress(pr)
            return self._send(200, {"ok": True})
        if p == "/api/run":                 # {lesson, ex, code}
            ex = next((e for e in exercises(b["lesson"]) if e["id"] == b["ex"]), None)
            if not ex:
                return self._send(404, {"error": "no such exercise"})
            ok, out = run_code(ex, b.get("code", ""))
            with LOCK:
                pr = load_progress()
                e = pr["exercises"].setdefault(f"{b['lesson']}/{ex['id']}", {})
                e["attempts"] = e.get("attempts", 0) + 1
                e["last_code"] = b.get("code", "")
                if ok and not e.get("passed"):
                    e["passed"] = now()
                e["last_run"] = now()
                l = pr["lessons"].setdefault(b["lesson"], {})
                if l.get("status") in (None, "not_started"):
                    l["status"], l["updated"] = "in_progress", now()
                save_progress(pr)
            return self._send(200, {"passed": ok, "output": out})
        self._send(404, {"error": "not found"})


def selftest():
    ok, _ = run_code({"tests": "assert add(2, 3) == 5"}, "def add(a, b):\n    return a + b")
    assert ok, "a correct answer must pass"
    ok, out = run_code({"tests": "assert add(2, 3) == 5"}, "def add(a, b):\n    return a - b")
    assert not ok and "AssertionError" in out, "a wrong answer must fail with its assertion"
    ok, _ = run_code({"expect": r"^elixir 7$"}, "print('elixir', 7)")
    assert ok, "expect regex must match stdout"
    ok, _ = run_code({"expect": r"^elixir 7$"}, "print('elixir', 6)")
    assert not ok, "expect regex mismatch must fail"
    syl = json.loads((HERE / "syllabus.json").read_text(encoding="utf-8"))
    ids = [l["id"] for part in syl["parts"] for l in part["lessons"]]
    assert len(ids) == len(set(ids)), "lesson ids must be unique"
    print(f"selftest ok: runner pass/fail/expect, {len(ids)} unique lesson ids")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    print(f"ClashBot course on http://127.0.0.1:{port}  (python for exercises: {sys.executable})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()

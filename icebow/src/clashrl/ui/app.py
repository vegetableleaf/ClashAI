"""Flask app for the local launcher UI (`run.py ui`).

Localhost only, no auth, no external calls: it binds 127.0.0.1 explicitly and every
endpoint works offline. It drives the EXISTING CLI through `procs.ProcManager` --
nothing here reimplements a command.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, Response, jsonify, render_template, request, send_file

from . import editor, jobs as jobcat
from .ckpt import list_checkpoints
from .metrics import MetricsStore, to_csv
from .procs import ProcManager

TOS_WARNING = (
    "Automatisiertes Spielen verstößt gegen die Supercell-Nutzungsbedingungen. "
    "Dieses Projekt ist ein Lern-/Forschungsprojekt -- der Einsatz auf einem echten "
    "Account kann zur Sperrung führen. Nutzung auf eigenes Risiko."
)


def _card_role(c: Dict[str, Any]) -> str:
    # order matters: a win condition stays a win condition even though X-Bow is
    # also a 'building' and Goblin Barrel also a 'spell'.
    flags = set(c.get("flags") or [])
    if c.get("win_condition"):
        return "Win Condition" + (" (Belagerung)" if "siege" in flags else "")
    if "siege" in flags:
        return "Belagerung"
    if c.get("kind") == "spell":
        return "Zauber"
    if c.get("kind") == "building":
        return "Gebäude"
    if "tank" in flags:
        return "Tank"
    if "mini_tank" in flags:
        return "Mini-Tank"
    if "swarm" in flags:
        return "Schwarm"
    if "ranged" in flags:
        return "Fernkampf"
    return "Truppe"


def create_app(cfg) -> Flask:
    root: Path = cfg.root                                     # icebow/
    metrics = MetricsStore(root / "data" / "metrics.jsonl")
    pm = ProcManager(root, metrics)
    backup_dir = root / "data" / "config_backups"
    cfg_path = root / "config" / "config.yaml"
    cards_path = root / "config" / "cards.yaml"

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    # -- helpers -----------------------------------------------------------
    def sessions() -> List[str]:
        d = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
        if not d.exists():
            return []
        return sorted((p.name for p in d.iterdir() if p.is_dir()), reverse=True)

    def card_db():
        from ..cards import CardDB
        return CardDB(cfg)

    # -- pages -------------------------------------------------------------
    @app.get("/")
    def index():
        return render_template("index.html", tos=TOS_WARNING)

    # -- catalog + state ---------------------------------------------------
    @app.get("/api/state")
    def state():
        return jsonify({
            "commands": jobcat.COMMANDS,
            "jobs": pm.list(),
            "gpu_busy": (pm.gpu_busy().id if pm.gpu_busy() else None),
            "sessions": sessions(),
            "root": str(root),
            "tos": TOS_WARNING,
            "now": time.time(),
        })

    @app.post("/api/jobs/start")
    def job_start():
        body = request.get_json(force=True, silent=True) or {}
        cmd = str(body.get("cmd", ""))
        try:
            job = pm.start(cmd, body.get("args") or {})
        except (jobcat.ArgError, RuntimeError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"error": f"Start fehlgeschlagen: {exc}"}), 500
        return jsonify(job.info())

    @app.post("/api/jobs/<jid>/stop")
    def job_stop(jid: str):
        try:
            return jsonify(pm.stop(jid))
        except KeyError:
            return jsonify({"error": "unbekannter Job"}), 404

    @app.get("/api/jobs/<jid>/log")
    def job_log(jid: str):
        job = pm.jobs.get(jid)
        if job is None:
            return jsonify({"error": "unbekannter Job"}), 404
        return jsonify({"info": job.info(), "lines": list(job.lines)})

    @app.get("/api/jobs/<jid>/stream")
    def job_stream(jid: str):
        job = pm.jobs.get(jid)
        if job is None:
            return jsonify({"error": "unbekannter Job"}), 404
        q = job.subscribe()
        backlog = list(job.lines)

        def gen():
            try:
                for line in backlog:
                    yield f"data: {json.dumps({'line': line})}\n\n"
                while True:
                    try:
                        line = q.get(timeout=15.0)
                        yield f"data: {json.dumps({'line': line})}\n\n"
                    except Exception:                          # noqa: BLE001 -- queue.Empty
                        if not job.running:
                            yield f"data: {json.dumps({'eof': True, 'rc': job.rc})}\n\n"
                            return
                        yield ": keepalive\n\n"
            finally:
                job.unsubscribe(q)

        return Response(gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # -- metrics -----------------------------------------------------------
    @app.get("/api/metrics/runs")
    def metric_runs():
        return jsonify(metrics.runs())

    @app.get("/api/metrics")
    def metric_series():
        run = request.args.get("run") or None
        recs = metrics.read(run=run)
        return jsonify({"run": run, "records": recs})

    @app.get("/api/metrics.csv")
    def metric_csv():
        run = request.args.get("run") or None
        csv = to_csv(metrics.read(run=run, limit=10 ** 9))
        name = f"metrics_{run or 'alle'}.csv"
        return Response(csv, mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # -- strategy ----------------------------------------------------------
    @app.get("/api/strategy")
    def strategy():
        p = root / "data" / "policy_stats.json"
        if not p.exists():
            return jsonify({"available": False})
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return jsonify({"available": False, "error": str(exc)})
        data["available"] = True
        data["mtime"] = p.stat().st_mtime
        return jsonify(data)

    # -- deck --------------------------------------------------------------
    @app.get("/api/deck")
    def deck_get():
        db = card_db()
        deck = editor.read_deck(cards_path)
        rows = []
        for entry in deck["cards"]:
            key = str(entry.get("card"))
            c = db.get(key) or {}
            rows.append({"card": key, "level": entry.get("level", 11),
                         "evolved": bool(entry.get("evolved")),
                         "display": c.get("display", key), "elixir": c.get("elixir"),
                         "role": _card_role(c),
                         "evo_available": bool((c.get("evolution") or {}).get("available"))
                         if isinstance(c.get("evolution"), dict) else False})
        catalog = sorted(
            ({"key": k, "display": v.get("display", k), "elixir": v.get("elixir"),
              "role": _card_role(v)}
             for k, v in db.cards.items()
             if not k.endswith("_evo") and v.get("elixir") is not None),
            key=lambda c: c["display"])
        costs = [r["elixir"] for r in rows if r["elixir"] is not None]
        return jsonify({
            "name": deck["name"], "cards": rows, "catalog": catalog,
            "avg_elixir": round(sum(costs) / len(costs), 2) if costs else None,
            "identities": db.deck_identities(),
            "stale": _stale_report(db),
        })

    def _stale_report(db) -> Dict[str, Any]:
        """What a deck change invalidates: templates, datasets, checkpoints."""
        ids = db.deck_identities()
        tdir = root / "templates" / "cards"
        have = set()
        if tdir.exists():
            for p in tdir.glob("*.png"):
                stem = p.stem
                have.add(stem.rsplit("_", 1)[0] if stem.rsplit("_", 1)[-1].isdigit() else stem)
        missing = [k for k in ids if k not in have and k.replace("_evo", "") not in have]
        stale_ck = []
        for c in list_checkpoints(root / "data"):
            ck_deck = c.get("deck")
            if isinstance(ck_deck, list) and list(ck_deck) != list(ids):
                stale_ck.append(c["name"])
        sess = root / "data" / "sessions"
        datasets = len(list(sess.glob("*/dataset.npz"))) if sess.exists() else 0
        return {"missing_templates": missing, "stale_checkpoints": stale_ck,
                "datasets": datasets}

    @app.post("/api/deck")
    def deck_set():
        body = request.get_json(force=True, silent=True) or {}
        db = card_db()
        try:
            res = editor.save_deck(cards_path, body.get("name") or "deck",
                                   body.get("cards") or [], backup_dir,
                                   valid_keys=set(db.cards.keys()))
        except editor.EditError as exc:
            return jsonify({"error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"error": f"Schreiben fehlgeschlagen: {exc}"}), 500
        return jsonify(res)

    # -- config ------------------------------------------------------------
    @app.get("/api/config")
    def config_get():
        return jsonify({"fields": editor.read_config_fields(cfg_path),
                        "path": str(cfg_path)})

    @app.post("/api/config")
    def config_set():
        body = request.get_json(force=True, silent=True) or {}
        try:
            res = editor.save_config_fields(cfg_path, body.get("changes") or {}, backup_dir)
        except editor.EditError as exc:
            return jsonify({"error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"error": f"Schreiben fehlgeschlagen: {exc}"}), 500
        return jsonify(res)

    # -- checkpoints -------------------------------------------------------
    @app.get("/api/checkpoints")
    def checkpoints():
        return jsonify(list_checkpoints(root / "data", metrics.runs()))

    @app.get("/api/logfile/<jid>")
    def logfile(jid: str):
        job = pm.jobs.get(jid)
        if job is None or not job.log_path.exists():
            return jsonify({"error": "kein Log"}), 404
        return send_file(job.log_path, as_attachment=True)

    app.proc_manager = pm                                     # type: ignore[attr-defined]
    return app


def serve(cfg, port: int = 8765, open_browser: bool = True) -> None:
    host = "127.0.0.1"                                        # localhost ONLY -- never 0.0.0.0
    app = create_app(cfg)
    url = f"http://{host}:{port}/"
    print(f"[ui] {TOS_WARNING}")
    print(f"[ui] Launcher läuft auf {url}  (nur lokal erreichbar; Strg+C beendet ihn)")
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        pm = getattr(app, "proc_manager", None)
        if pm is not None and pm.active():
            print(f"[ui] stoppe {len(pm.active())} laufende(n) Job(s) ...")
            pm.stop_all(grace=30.0)
            for _ in range(120):
                if not pm.active():
                    break
                time.sleep(0.5)
        print("[ui] beendet.")

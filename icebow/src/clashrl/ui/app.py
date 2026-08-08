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

from . import jobs as jobcat
from .. import config_edit as editor
from .ckpt import list_checkpoints
from ..hardware import probe, suggest
from .metrics import MetricsStore, to_csv
from .procs import ProcManager

TOS_WARNING = (
    "Automating play violates the Supercell terms of service. This is a learning and "
    "research project; using it on a real account can get that account banned. "
    "Use at your own risk."
)


def _card_role(c: Dict[str, Any]) -> str:
    # order matters: a win condition stays a win condition even though X-Bow is
    # also a 'building' and Goblin Barrel also a 'spell'.
    flags = set(c.get("flags") or [])
    if c.get("win_condition"):
        return "Win condition" + (" (siege)" if "siege" in flags else "")
    if "siege" in flags:
        return "Siege"
    if c.get("kind") == "spell":
        return "Spell"
    if c.get("kind") == "building":
        return "Building"
    if "tank" in flags:
        return "Tank"
    if "mini_tank" in flags:
        return "Mini tank"
    if "swarm" in flags:
        return "Swarm"
    if "ranged" in flags:
        return "Ranged"
    return "Troop"


def create_app(cfg) -> Flask:
    root: Path = cfg.root                                     # icebow/
    metrics = MetricsStore(root / "data" / "metrics.jsonl")
    pm = ProcManager(root, metrics)
    backup_dir = root / "data" / "config_backups"
    cfg_path = root / "config" / "config.yaml"
    cards_path = root / "config" / "cards.yaml"

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.json.sort_keys = False        # keep config/deck/tower order as it is in the YAML files

    @app.after_request
    def _no_store(resp):
        # Never let a browser keep the page, the scripts or an API answer: after an update
        # a cached app.js silently drives a UI that no longer matches the server.
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp

    # -- helpers -----------------------------------------------------------
    # The panel EDITS config.yaml, so a snapshot taken at startup goes stale the moment
    # something is saved (the first version kept proposing a setting it had just applied).
    # Re-read whenever the file's mtime moves -- also picks up edits made outside the UI.
    _cfg_state = {"cfg": cfg, "mtime": cfg_path.stat().st_mtime if cfg_path.exists() else 0.0}

    def C():
        """The current config, reloaded on change."""
        try:
            m = cfg_path.stat().st_mtime
        except OSError:
            return _cfg_state["cfg"]
        if m != _cfg_state["mtime"]:
            from ..config import Config
            try:
                _cfg_state["cfg"] = Config.load(cfg_path)
                _cfg_state["mtime"] = m
            except Exception:                      # noqa: BLE001 -- keep serving the last good one
                pass
        return _cfg_state["cfg"]

    def sessions() -> List[str]:
        c = C()
        d = c.path(c.get("record", "out_dir", default="data/sessions"))
        if not d.exists():
            return []
        return sorted((p.name for p in d.iterdir() if p.is_dir()), reverse=True)

    def card_db():
        from ..cards import CardDB
        return CardDB(C())

    # -- pages -------------------------------------------------------------
    @app.get("/")
    def index():
        return render_template("index.html", tos=TOS_WARNING)

    # -- catalog + state ---------------------------------------------------
    @app.get("/api/state")
    def state():
        return jsonify({
            "commands": jobcat.available(root),
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
            return jsonify({"error": f"could not start: {exc}"}), 500
        return jsonify(job.info())

    @app.post("/api/jobs/<jid>/stop")
    def job_stop(jid: str):
        try:
            return jsonify(pm.stop(jid))
        except KeyError:
            return jsonify({"error": "unknown job"}), 404

    @app.get("/api/jobs/<jid>/log")
    def job_log(jid: str):
        job = pm.jobs.get(jid)
        if job is None:
            return jsonify({"error": "unknown job"}), 404
        return jsonify({"info": job.info(), "lines": list(job.lines)})

    @app.get("/api/jobs/<jid>/stream")
    def job_stream(jid: str):
        job = pm.jobs.get(jid)
        if job is None:
            return jsonify({"error": "unknown job"}), 404
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
        name = f"metrics_{run or 'all'}.csv"
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

    @app.get("/api/deck-detect")
    def deck_detect():
        p = root / "data" / "deck_detect.json"
        if not p.exists():
            return jsonify({"available": False})
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return jsonify({"available": False, "error": str(exc)})
        data["available"] = True
        art = root / "templates" / "cardart"
        data["reference_bank"] = len(list(art.glob("*.png"))) if art.exists() else 0
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
            return jsonify({"error": f"could not write: {exc}"}), 500
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
            return jsonify({"error": f"could not write: {exc}"}), 500
        return jsonify(res)

    # -- checkpoints -------------------------------------------------------
    @app.get("/api/checkpoints")
    def checkpoints():
        return jsonify(list_checkpoints(root / "data", metrics.runs()))

    # -- live view ---------------------------------------------------------
    @app.get("/api/live")
    def live_view():
        from .live import snapshot
        try:
            return jsonify(snapshot(C(), width=int(request.args.get("width", 420))))
        except Exception as exc:                       # noqa: BLE001 -- must never break the panel
            return jsonify({"ok": False, "error": str(exc)})

    @app.post("/api/live/reset")
    def live_reset():
        from .live import reset
        reset()
        return jsonify({"ok": True})

    # -- hardware / speed --------------------------------------------------
    def _bench_file():
        p = root / "data" / "sim_bench.json"
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["mtime"] = p.stat().st_mtime
            return d
        except (OSError, json.JSONDecodeError):
            return None

    @app.get("/api/hardware")
    def hardware():
        info = probe()
        cur_envs = int(C().get("sim", "envs", default=8))
        sug = suggest(info, cur_envs)
        aw, ah = (C().get("observation", "arena_size", default=[64, 96]) + [0, 0])[:2]
        frame_bytes = int(aw) * int(ah) * 3
        replay = int(C().get("train", "replay_size", default=100000))
        bench = _bench_file()
        return jsonify({
            "hardware": info,
            "suggestion": sug,
            "current": {
                "envs": cur_envs,
                "batch_size": int(C().get("train", "batch_size", default=64)),
                "replay_size": replay,
                "eval_envs": int(C().get("sim", "eval_envs", default=8)),
                "device": C().get("train", "device", default="cuda"),
            },
            # one uint8 frame per stored step (obs and next-obs share the array between
            # consecutive transitions), so this is the dominant replay cost.
            "replay_ram_estimate": replay * frame_bytes,
            "frame_bytes": frame_bytes,
            "bench": bench,
        })

    @app.post("/api/hardware/apply")
    def hardware_apply():
        """Write the MEASURED best env count (and optionally the hardware guesses)."""
        body = request.get_json(force=True, silent=True) or {}
        changes: Dict[str, Any] = {}
        bench = _bench_file()
        if body.get("envs") is not None:
            changes["sim.envs"] = body["envs"]
        elif bench and bench.get("best_envs"):
            changes["sim.envs"] = bench["best_envs"]
        if body.get("with_suggestion"):
            sug = suggest(probe(), int(C().get("sim", "envs", default=8)))
            changes.setdefault("train.batch_size", sug["batch_size"])
            changes.setdefault("train.replay_size", sug["replay_size"])
            changes.setdefault("sim.eval_envs", min(int(changes.get("sim.envs", sug["envs"])),
                                                    sug["eval_envs"]))
        if not changes:
            return jsonify({"error": "Nothing to apply. Run the throughput benchmark first."}), 400
        try:
            res = editor.save_config_fields(cfg_path, changes, backup_dir)
        except editor.EditError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(res)

    # -- tower troops ------------------------------------------------------
    @app.get("/api/towers")
    def towers_get():
        t = editor.read_towers(cfg_path)
        t["defaults"] = {
            "princess": {"hp": 4424, "dps": 197, "hit_speed": 0.8},
        }
        return jsonify(t)

    @app.post("/api/towers")
    def towers_set():
        body = request.get_json(force=True, silent=True) or {}
        try:
            return jsonify(editor.save_towers(cfg_path, body, backup_dir))
        except editor.EditError as exc:
            return jsonify({"error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"error": f"could not write: {exc}"}), 500

    # -- overview ----------------------------------------------------------
    @app.get("/api/overview")
    def overview():
        """Plain status. No generic advice: what is worth doing next depends on the
        project, not on what a panel can infer from a few file names."""
        db = card_db()
        cks = list_checkpoints(root / "data", metrics.runs())
        return jsonify({
            "deck": {"name": db.deck_name(), "avg_elixir": db.deck_avg_elixir(),
                     "cards": db.deck_names(), "identities": db.deck_identities()},
            "checkpoints": cks[:6], "runs": metrics.runs()[:5], "bench": _bench_file(),
            "envs": int(C().get("sim", "envs", default=8)), "stale": _stale_report(db),
            "towers": {"mine": C().get("sim", "my_tower_troop", default="princess"),
                       "level": C().get("sim", "my_tower_level", default=15),
                       "opponents": list((C().get("sim", "opponent_tower_weights", default={}) or {}))},
        })

    @app.get("/api/logfile/<jid>")
    def logfile(jid: str):
        job = pm.jobs.get(jid)
        if job is None or not job.log_path.exists():
            return jsonify({"error": "no log"}), 404
        return send_file(job.log_path, as_attachment=True)

    app.proc_manager = pm                                     # type: ignore[attr-defined]
    return app


def _port_in_use(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def serve(cfg, port: int = 8765, open_browser: bool = True) -> None:
    host = "127.0.0.1"                                        # localhost ONLY -- never 0.0.0.0
    # Windows lets a second server bind a port that is already listening (SO_REUSEADDR is
    # not exclusive there), and requests then land on either process at random -- which
    # looks exactly like the UI ignoring your changes. Refuse instead.
    if _port_in_use(host, port):
        print(f"[ui] A panel is already running on {host}:{port}.")
        print(f"[ui] Either use that one: http://{host}:{port}/")
        print(f"[ui] or close it, or pick another port here: run.py ui --port {port + 1}")
        return
    app = create_app(cfg)
    url = f"http://{host}:{port}/"
    print(f"[ui] {TOS_WARNING}")
    print(f"[ui] panel running at {url}  (local only; Ctrl+C stops it)")
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
            print(f"[ui] stopping {len(pm.active())} running job(s) ...")
            pm.stop_all(grace=30.0)
            for _ in range(120):
                if not pm.active():
                    break
                time.sleep(0.5)
        print("[ui] stopped.")

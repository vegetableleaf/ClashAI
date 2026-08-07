# Launcher (`run.py ui`)

A localhost control panel for the existing CLI. It starts the same commands you would
type, streams their output, records the numbers, and edits the two config files. It does
not reimplement any command, and the CLI keeps working on its own.

Start it with `start_ui.bat` in the repo root, or:

```powershell
.\.venv\Scripts\python.exe run.py ui          # http://127.0.0.1:8765, localhost only
```

Flask is the only added dependency. No Node, no build step, no CDN: the panel works
offline.

---

## Layout

| Backend (`src/clashrl/ui/*.py`) | what it does |
|---|---|
| `app.py` | Flask routes. Holds no logic beyond assembling answers. |
| `procs.py` | Starts, streams and stops CLI subprocesses. Enforces one GPU job at a time. |
| `jobs.py` | Describes which commands and flags the panel may launch. Validates every value before spawning. |
| `metrics.py` | Scrapes the trainers' own stdout into `data/metrics.jsonl`. |
| `editor.py` | Surgical YAML editing of `config.yaml` / `cards.yaml`. |
| `ckpt.py` | Checkpoint inventory. |
| `hardware.py` | Reads CPU / RAM / GPU, proposes a starting point. |
| `bench.py` | `sim-bench`: measures simulator throughput. |
| `rollout.py` | `policy-stats`: measures what the policy plays. |
| `live.py` | One frame of the game window plus the bot's reading of it. |
| `child.py` | Maps the stop signal onto the ordinary Ctrl+C path. |

| Frontend (`src/clashrl/ui/`) | what it does |
|---|---|
| `templates/index.html` | The page: tabs, forms, the log bar, the tour scaffolding. |
| `static/app.js` | All behaviour. Plain JavaScript, no framework. |
| `static/style.css` | One stylesheet, dark, no external fonts. |

Backend and frontend only meet at the JSON API below, so either side can be reviewed on
its own.

---

## API

| Route | Purpose |
|---|---|
| `GET /api/state` | Command catalog, running jobs, recording list. |
| `POST /api/jobs/start` · `POST /api/jobs/<id>/stop` | Job lifecycle. |
| `GET /api/jobs/<id>/stream` | Server-sent events with the live output. |
| `GET /api/metrics` · `/api/metrics/runs` · `/api/metrics.csv` | Training numbers. |
| `GET /api/live` · `POST /api/live/reset` | Current frame plus the recognised state. |
| `GET /api/hardware` · `POST /api/hardware/apply` | Machine, proposal, measured optimum. |
| `GET/POST /api/deck` · `GET /api/deck-detect` | Deck, and the automatic proposal. |
| `GET/POST /api/towers` | Tower troops of the simulator. |
| `GET/POST /api/config` | The curated set of editable config fields. |
| `GET /api/checkpoints` · `GET /api/strategy` · `GET /api/overview` | Read-only views. |

---

## Design decisions worth knowing

**Stopping is graceful.** Windows cannot deliver Ctrl+C to another process group, and the
default action for the signal that *does* get through kills the process before any
`finally: save()` runs. So jobs are started in their own process group, stopped with
Ctrl+Break, and `cli.main()` maps that onto `KeyboardInterrupt` when the launcher set
`CLASHRL_UI_CHILD`. Outside the launcher the CLI behaves exactly as before.

**Config edits are line patches, not rewrites.** `config.yaml` is ~60 KB of which most is
explanatory comments. A `yaml.safe_dump` round-trip would delete all of it, so `editor.py`
locates the one line, replaces the value, keeps the trailing comment, then re-parses the
result and deep-compares it against the intended document before writing. The previous
file is copied to `data/config_backups/` first. Invalid YAML is never written.

**Metrics come from stdout.** The trainers already print everything the dashboard needs.
Scraping those lines means there are no metric hooks inside the training loops that could
drift out of sync, and a run started from a terminal is recorded just the same.

**One GPU job at a time.** GPU and game window exist once. `procs.py` refuses to start a
second job that needs either.

**The panel never keeps a stale config.** It re-reads `config.yaml` whenever the file's
timestamp moves, so a value it just wrote, or one you edited in an editor, is visible
immediately.

---

## When nothing seems to work

Open **Live** first. It shows whether the window is captured at all, whether the frame
registers as `IN_MATCH`, and how close each screen template comes to its threshold. Most
"nothing produces any data" reports end there: the shipped templates were cut from one
client, one window size, one interface language. A different window shape or a
non-English client scores far below the threshold, `detect_state` returns `UNKNOWN`, and
every downstream command then finds nothing.

The fix is `calibrate`: it takes the frames around your own logged clicks as in-match,
the frames before your first click as menu, and cuts a new template from the region that
stays still while playing and differs most from the menu. That is independent of language
and window size. See `docs/PIPELINE.md`.

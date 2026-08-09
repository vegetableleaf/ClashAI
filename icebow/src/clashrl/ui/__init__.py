"""Local launcher UI (Flask) for the learning bot.

`run.py ui` serves a localhost-only control panel that drives the EXISTING CLI as
subprocesses -- it never reimplements a command. See `app.py` for the routes and
`procs.py` for the process lifecycle (start / stream / graceful stop).
"""

"""Catalog of the CLI subcommands the UI can launch, with their arguments.

This is a DESCRIPTION of the existing CLI, not a second implementation: every entry
maps 1:1 onto `run.py <cmd> [flags]`. Adding a flag here only exposes something
argparse already accepts -- `build_argv` re-checks that before spawning anything.

`gpu: True` marks the jobs that occupy the GPU (or the game window / mouse). The
process manager refuses to start a second one while any of them runs.
"""
from __future__ import annotations

from typing import Any, Dict, List

# arg spec: name (the argparse flag without "--"), type, label/help in German, default.
#   type: "int" | "float" | "str" | "bool" (store_true) | "choice" | "session" | "ckpt"
COMMANDS: List[Dict[str, Any]] = [
    {
        "cmd": "train-sim",
        "group": "Simulator-Training",
        "title": "Sim-Training (DDQN)",
        "desc": "Trainiert die Policy im headless Simulator gegen skriptierte Bots + Self-Play. "
                "Der Hauptweg zu einem Prior; schreibt data/policy_sim.pt (+ _best).",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "matches", "type": "int", "default": 20000, "label": "Matches (max)",
             "help": "Obergrenze; der Lauf stoppt danach. Stop speichert jederzeit."},
            {"name": "envs", "type": "int", "default": None, "label": "Parallele Envs",
             "help": "Vektorisierte Match-Instanzen pro Learner. Leer = sim.envs aus der Config."},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed",
             "help": "RNG-Seed des Simulators. Gleicher Seed = vergleichbare Läufe."},
            {"name": "resume", "type": "bool", "default": False, "label": "Fortsetzen (--resume)",
             "help": "Setzt data/policy_sim.pt fort statt from scratch zu starten."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board-Auflösung",
             "help": "576=[18,32] fein / 432=[18,24] grob. Leer = action.grid aus der Config. "
                     "NICHT mit --resume der anderen Größe kombinieren."},
        ],
    },
    {
        "cmd": "train-sim-ppo",
        "group": "Simulator-Training",
        "title": "Sim-Training (PPO)",
        "desc": "On-policy Geschwister von train-sim mit eigenem Checkpoint policy_sim_ppo.pt. "
                "Der DDQN-Baseline-Checkpoint bleibt unberührt.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "matches", "type": "int", "default": 20000, "label": "Matches (max)"},
            {"name": "envs", "type": "int", "default": None, "label": "Parallele Envs"},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed"},
            {"name": "resume", "type": "bool", "default": False, "label": "Fortsetzen (--resume)"},
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm-Start (--init)",
             "help": "Policy+Gate aus einem Checkpoint übernehmen (Value-Head trainiert frisch)."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board-Auflösung"},
        ],
    },
    {
        "cmd": "train-bc",
        "group": "Aus Aufnahmen lernen",
        "title": "Behaviour Cloning",
        "desc": "Imitationslernen aus deinen gelabelten Aufnahmen -> data/policy.pt. "
                "Braucht gelabelte Sessions (label) und Hand-Templates.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm-Start (--init)",
             "help": "z.B. data/policy_sim.pt -- kombiniert den Sim-Prior mit deinem Spiel."},
            {"name": "iterations", "type": "int", "default": 1, "label": "Iterationen",
             "help": "N aufeinanderfolgende BC-Durchläufe, jeder warm-startet vom vorigen."},
        ],
    },
    {
        "cmd": "train-rl",
        "group": "Live am Spiel",
        "title": "Live-RL (echte Matches)",
        "desc": "Fine-tuning auf echten Matches am laufenden Spiel. Braucht das Spielfenster "
                "und die Maus -- der Rechner ist während des Laufs belegt.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm-Start (--init)",
             "help": "Default: data/policy_rl.pt falls vorhanden, sonst data/policy.pt."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board-Auflösung",
             "help": "Muss zum --init-Checkpoint passen."},
        ],
    },
    {
        "cmd": "play",
        "group": "Live am Spiel",
        "title": "Spielen (Policy live)",
        "desc": "Lässt die trainierte Policy live spielen. Braucht Spielfenster + Maus.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board-Auflösung", "help": "Muss zum Policy-Checkpoint passen."},
        ],
    },
    {
        "cmd": "record",
        "group": "Aus Aufnahmen lernen",
        "title": "Aufnehmen",
        "desc": "Nimmt dein eigenes Spiel auf (Bild + Mausklicks) als Imitationsdaten. "
                "Belegt Bildschirm und Maus-Hook.",
        "gpu": True,
        "metrics": False,
        "args": [],
    },
    {
        "cmd": "label",
        "group": "Aus Aufnahmen lernen",
        "title": "Labeln",
        "desc": "Baut aus Aufnahmen den (Beobachtung, Aktion)-Datensatz für BC.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Session",
             "help": "Leer = neueste Session."},
            {"name": "all", "type": "bool", "default": False, "label": "Alle Sessions"},
            {"name": "debug", "type": "bool", "default": False, "label": "Debug-Frames speichern"},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board-Auflösung",
             "help": "Quantisiert den Datensatz -- überall dieselbe Größe verwenden."},
        ],
    },
    {
        "cmd": "outcomes",
        "group": "Aus Aufnahmen lernen",
        "title": "Ergebnisse erkennen",
        "desc": "Erkennt Sieg/Niederlage pro Match aus dem Ergebnisbildschirm der Aufnahme.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Session"},
            {"name": "all", "type": "bool", "default": False, "label": "Alle Sessions"},
            {"name": "debug", "type": "bool", "default": False, "label": "Verbose"},
        ],
    },
    {
        "cmd": "verify",
        "group": "Analyse & Diagnose",
        "title": "Verifizieren",
        "desc": "Legt Overlays auf aufgezeichnete Frames, um Erkennung und Kalibrierung zu prüfen.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Session"},
            {"name": "towers", "type": "bool", "default": False, "label": "Türme"},
            {"name": "hand", "type": "bool", "default": False, "label": "Handkarten"},
            {"name": "spells", "type": "bool", "default": False, "label": "Zauber/Truppenmasse"},
            {"name": "threats", "type": "bool", "default": False, "label": "Bedrohungen"},
            {"name": "clock", "type": "bool", "default": False, "label": "2x/3x-Elixier-Badge"},
            {"name": "all", "type": "bool", "default": False, "label": "Alle Sessions"},
        ],
    },
    {
        "cmd": "diag",
        "group": "Analyse & Diagnose",
        "title": "Diagnose",
        "desc": "Prüft die Menü-Navigation: Template-Match-Scores auf dem aktuellen Bildschirm.",
        "gpu": False,
        "metrics": False,
        "args": [],
    },
    {
        "cmd": "sim-bench",
        "group": "Simulator-Training",
        "title": "Geschwindigkeits-Test",
        "desc": "Misst Matches/Sekunde bei verschiedenen Env-Zahlen auf DIESEM PC und schlägt die "
                "schnellste Einstellung vor. Schreibt NICHT policy_sim.pt (eigener Ordner data/bench/).",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "envs", "type": "str", "default": "", "label": "Env-Zahlen",
             "help": "Kommaliste, z.B. 8,16,32,48. Leer = aus deiner Hardware abgeleitet."},
            {"name": "seconds", "type": "float", "default": 30, "label": "Sekunden pro Messung",
             "help": "Länger = weniger Rauschen. 30s pro Einstellung reichen für einen klaren Trend."},
            {"name": "warmup", "type": "float", "default": 8, "label": "Aufwärmen (s)",
             "help": "Verworfener Vorlauf, damit der CUDA-Start nicht die erste Messung verfälscht."},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed"},
        ],
    },
    {
        "cmd": "policy-stats",
        "group": "Analyse & Diagnose",
        "title": "Strategie-Analyse",
        "desc": "Spielt greedy Matches im Simulator und zählt, welche Karten die Policy wie oft "
                "und wo spielt -> data/policy_stats.json (Strategie-Tab).",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "ckpt", "type": "ckpt", "default": "", "label": "Checkpoint",
             "help": "Leer = data/policy_sim_best.pt falls vorhanden, sonst policy_sim.pt."},
            {"name": "matches", "type": "int", "default": 60, "label": "Matches"},
            {"name": "envs", "type": "int", "default": 8, "label": "Parallele Envs"},
            {"name": "seed", "type": "int", "default": 4242, "label": "Seed"},
            {"name": "epsilon", "type": "float", "default": 0.0, "label": "Epsilon",
             "help": "0 = rein greedy (das, was die Policy wirklich tut)."},
        ],
    },
]

BY_CMD: Dict[str, Dict[str, Any]] = {c["cmd"]: c for c in COMMANDS}


class ArgError(ValueError):
    """A submitted argument value is not acceptable for this command."""


def build_argv(cmd: str, values: Dict[str, Any]) -> List[str]:
    """Turn a {arg_name: value} dict into the argv tail for `run.py`.

    Only flags declared in COMMANDS pass; values are coerced to the declared type.
    Anything else raises -- the UI must not be able to smuggle a shell string into
    the child process.
    """
    spec = BY_CMD.get(cmd)
    if spec is None:
        raise ArgError(f"unbekanntes Kommando: {cmd}")
    known = {a["name"]: a for a in spec["args"]}
    argv: List[str] = [cmd]
    for name, raw in (values or {}).items():
        a = known.get(name)
        if a is None:
            raise ArgError(f"unbekannter Parameter '{name}' für {cmd}")
        t = a["type"]
        if t == "bool":
            if raw:
                argv.append(f"--{name}")
            continue
        if raw is None or str(raw).strip() == "":
            continue                                    # empty = leave the CLI default alone
        s = str(raw).strip()
        if t == "int":
            try:
                s = str(int(s))
            except ValueError:
                raise ArgError(f"{a.get('label', name)}: '{raw}' ist keine ganze Zahl") from None
        elif t == "float":
            try:
                s = str(float(s))
            except ValueError:
                raise ArgError(f"{a.get('label', name)}: '{raw}' ist keine Zahl") from None
        elif t == "choice":
            if s not in a.get("choices", []):
                raise ArgError(f"{a.get('label', name)}: '{raw}' ist keine gültige Auswahl")
        elif t in ("session", "ckpt", "str"):
            if any(ch in s for ch in '"\'\n\r|&;<>'):
                raise ArgError(f"{a.get('label', name)}: unerlaubte Zeichen")
        argv += [f"--{name}", s]
    return argv

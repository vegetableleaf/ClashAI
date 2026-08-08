"""Catalog of the CLI subcommands the panel can launch, with their arguments.

This is a DESCRIPTION of the existing CLI, not a second implementation: every entry
maps 1:1 onto `run.py <cmd> [flags]`. Adding a flag here only exposes something
argparse already accepts -- `build_argv` re-checks that before spawning anything.

`gpu: True` marks the jobs that occupy the GPU (or the game window / mouse). The
process manager refuses to start a second one while any of them runs.
"""
from __future__ import annotations

from typing import Any, Dict, List

# arg spec: name (the argparse flag without "--"), type, label, help, default.
#   type: "int" | "float" | "str" | "bool" (store_true) | "choice" | "session" | "ckpt"
COMMANDS: List[Dict[str, Any]] = [
    {
        "cmd": "train-sim",
        "group": "Playing AI: training",
        "title": "Sim training (DDQN)",
        "desc": "Trains the policy in the headless simulator against scripted bots and past "
                "copies of itself. The main route to a usable policy; writes data/policy_sim.pt.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "matches", "type": "int", "default": 20000, "label": "Matches (limit)",
             "help": "The run stops there. Stop saves at any point, so this is only an upper bound."},
            {"name": "envs", "type": "int", "default": None, "label": "Parallel matches",
             "help": "How many matches run at once feeding one learner. Empty uses sim.envs."},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed",
             "help": "RNG seed of the simulator. Same seed makes two runs comparable."},
            {"name": "resume", "type": "bool", "default": False, "label": "Continue (--resume)",
             "help": "Carries on from data/policy_sim.pt instead of starting from scratch."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board resolution",
             "help": "576=[18,32] fine / 432=[18,24] coarse. Empty uses action.grid. Do NOT "
                     "combine with --resume of the other size."},
        ],
    },
    {
        "cmd": "train-sim-ppo",
        "group": "Playing AI: training",
        "title": "Sim training (PPO)",
        "desc": "On-policy sibling of train-sim with its own checkpoint policy_sim_ppo.pt. "
                "The DDQN baseline checkpoint is left alone.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "matches", "type": "int", "default": 20000, "label": "Matches (limit)"},
            {"name": "envs", "type": "int", "default": None, "label": "Parallel matches"},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed"},
            {"name": "resume", "type": "bool", "default": False, "label": "Continue (--resume)"},
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm start (--init)",
             "help": "Take policy and gate from a checkpoint; the value head trains fresh."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board resolution"},
        ],
    },
    {
        "cmd": "sim-bench",
        "group": "Playing AI: run and measure",
        "title": "Throughput benchmark",
        "desc": "Measures matches per second at different numbers of parallel matches on THIS "
                "machine and suggests the best setting. Writes to data/bench/, never to "
                "policy_sim.pt.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "auto", "type": "bool", "default": True, "label": "Search automatically",
             "help": "Doubles the number of parallel matches until it stops getting faster or "
                     "free memory would run short."},
            {"name": "apply", "type": "bool", "default": True, "label": "Apply the result",
             "help": "Writes the recommended setting into the config, with a backup."},
            {"name": "envs", "type": "str", "default": "", "label": "Values to test (manual)",
             "help": "Comma list, e.g. 8,16,32,48. Only used without the automatic search."},
            {"name": "seconds", "type": "float", "default": 30, "label": "Seconds per measurement",
             "help": "Longer is less noisy. 30 s per setting gives a clear trend."},
            {"name": "warmup", "type": "float", "default": 8, "label": "Warm-up (s)",
             "help": "Discarded first run so the CUDA start does not skew the first measurement."},
            {"name": "seed", "type": "int", "default": 0, "label": "Seed"},
        ],
    },
    {
        "cmd": "train-bc",
        "group": "Playing AI: training",
        "title": "Behaviour cloning",
        "desc": "Imitation learning from your labelled recordings into data/policy.pt. "
                "Needs labelled sessions and hand templates.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm start (--init)",
             "help": "e.g. data/policy_sim.pt, which combines the simulator prior with your play."},
            {"name": "iterations", "type": "int", "default": 1, "label": "Iterations",
             "help": "N successive passes, each warm-starting from the previous one."},
        ],
    },
    {
        "cmd": "record",
        "group": "Setup: screen and deck",
        "title": "Record",
        "desc": "Records your own play (screen and mouse clicks) as imitation data. "
                "Occupies the screen and the mouse hook.",
        "gpu": True,
        "metrics": False,
        "args": [],
    },
    {
        "cmd": "calibrate",
        "group": "Setup: screen and deck",
        "title": "Calibrate match detection",
        "desc": "Re-cuts the 'I am in a match' detection from YOUR recording. Needed when your "
                "window has a different size, or the game runs in a different language than the "
                "shipped templates.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Recording",
             "help": "Empty uses the newest. It has to contain your clicks."},
            {"name": "dry-run", "type": "bool", "default": False, "label": "Report only",
             "help": "Reports the result without writing anything."},
        ],
    },
    {
        "cmd": "cards-art",
        "group": "Setup: screen and deck",
        "title": "Fetch card pictures",
        "desc": "Downloads one reference picture per card from the Clash Royale wiki into "
                "templates/cardart/. The basis for automatic deck recognition; needed once.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "refresh", "type": "bool", "default": False, "label": "Re-download existing"},
        ],
    },
    {
        "cmd": "deck-detect",
        "group": "Setup: screen and deck",
        "title": "Detect the deck",
        "desc": "Reads the deck out of a recording instead of having you rename image crops. "
                "The proposal is shown in the Deck tab for confirmation.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Recording",
             "help": "Empty uses the newest."},
            {"name": "samples", "type": "int", "default": 400, "label": "Frames sampled",
             "help": "More frames also catch the cards you rarely play."},
            {"name": "per-face", "type": "int", "default": 6, "label": "Views per card",
             "help": "How many views of the same card are averaged. Six was enough for every "
                     "card in the measurement."},
            {"name": "write-templates", "type": "bool", "default": False,
             "label": "Write hand templates",
             "help": "Saves every confidently recognised card as a hand template under its real "
                     "name. That removes the renaming step entirely."},
            {"name": "overwrite-templates", "type": "bool", "default": False,
             "label": "Replace existing ones"},
            {"name": "player-tag", "type": "str", "default": "", "label": "Player tag (optional)",
             "help": "With a tag and an API token the card levels are read from your account. "
                     "Without it the levels in cards.yaml are kept."},
        ],
    },
    {
        "cmd": "import-from",
        "group": "Setup: screen and deck",
        "title": "Import an older installation",
        "desc": "Copies checkpoints, recordings and templates out of an older copy of this "
                "project. Nothing is deleted and nothing here is overwritten unless you say so.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "old", "type": "str", "positional": True, "default": "",
             "label": "Old folder",
             "help": "Path to the old installation, either the repository root or the icebow "
                     "folder inside it."},
            {"name": "dry-run", "type": "bool", "default": True, "label": "Only list",
             "help": "Shows what would be copied without touching anything."},
            {"name": "no-sessions", "type": "bool", "default": False, "label": "Skip recordings",
             "help": "Recordings are the large part; skip them if you only want the policies."},
            {"name": "with-config", "type": "bool", "default": False, "label": "Also take the config",
             "help": "cards.yaml and config.yaml decide the deck and the screen calibration, so "
                     "they are left alone by default."},
            {"name": "overwrite", "type": "bool", "default": False, "label": "Replace existing files"},
        ],
    },
    {
        "cmd": "detect-train",
        "group": "Vision AI: training",
        "title": "Train the vision AI",
        "desc": "Trains the board detector on the frames you labelled in the Labelling tab. "
                "This is the SECOND network -- it names the units on the board; it does not "
                "play. Needs labelled frames with boxes in them.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "model", "type": "choice",
             "choices": ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt", "yolo11l.pt", "yolo11x.pt"],
             "default": "yolo11s.pt", "label": "Model size",
             "help": "Bigger is more accurate but needs more VRAM and trains slower. Start small."},
            {"name": "epochs", "type": "int", "default": 120, "label": "Epochs",
             "help": "Upper bound; it early-stops on its own when it stops improving."},
            {"name": "imgsz", "type": "int", "default": 960, "label": "Image size",
             "help": "Units are small on the board, so a high value matters here."},
            {"name": "resume", "type": "bool", "default": False, "label": "Continue (--resume)",
             "help": "Carry on from the newest interrupted run instead of starting over."},
        ],
    },
    {
        "cmd": "label",
        "group": "Playing AI: training",
        "title": "Label",
        "desc": "Turns recordings into the (observation, action) dataset used by behaviour cloning.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Recording",
             "help": "Empty uses the newest."},
            {"name": "all", "type": "bool", "default": False, "label": "All recordings"},
            {"name": "debug", "type": "bool", "default": False, "label": "Save debug frames"},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board resolution",
             "help": "Quantises the dataset. Use the same value everywhere."},
        ],
    },
    {
        "cmd": "outcomes",
        "group": "Check the setup",
        "title": "Detect results",
        "desc": "Reads win/loss per match off the result screen of a recording.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Recording"},
            {"name": "all", "type": "bool", "default": False, "label": "All recordings"},
            {"name": "debug", "type": "bool", "default": False, "label": "Verbose"},
        ],
    },
    {
        "cmd": "train-rl",
        "group": "Playing AI: training",
        "title": "Live RL (real matches)",
        "desc": "Fine-tuning on real matches in the running game. Needs the game window and the "
                "mouse, so the machine is occupied while it runs.",
        "gpu": True,
        "metrics": True,
        "args": [
            {"name": "init", "type": "ckpt", "default": "", "label": "Warm start (--init)",
             "help": "Default: data/policy_rl.pt if present, otherwise data/policy.pt."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board resolution", "help": "Has to match the --init checkpoint."},
        ],
    },
    {
        "cmd": "play",
        "group": "Playing AI: run and measure",
        "title": "Play (policy live)",
        "desc": "Lets the trained policy play by itself. Needs the game window and the mouse.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "init", "type": "ckpt", "default": "", "label": "Checkpoint",
             "help": "Which policy to play. Empty means data/policy_rl.pt if present, otherwise "
                     "data/policy.pt. A pure simulator policy such as policy_sim_best.pt works "
                     "just as well."},
            {"name": "size", "type": "choice", "choices": ["", "576", "432"], "default": "",
             "label": "Board resolution", "help": "Has to match the policy checkpoint."},
        ],
    },
    {
        "cmd": "verify",
        "group": "Check the setup",
        "title": "Verify",
        "desc": "Draws overlays on recorded frames to check recognition and calibration.",
        "gpu": False,
        "metrics": False,
        "args": [
            {"name": "session", "type": "session", "default": "", "label": "Recording"},
            {"name": "towers", "type": "bool", "default": False, "label": "Towers"},
            {"name": "hand", "type": "bool", "default": False, "label": "Hand cards"},
            {"name": "spells", "type": "bool", "default": False, "label": "Spells / troop mass"},
            {"name": "threats", "type": "bool", "default": False, "label": "Threats"},
            {"name": "clock", "type": "bool", "default": False, "label": "2x/3x elixir badge"},
            {"name": "all", "type": "bool", "default": False, "label": "All recordings"},
        ],
    },
    {
        "cmd": "diag",
        "group": "Check the setup",
        "title": "Diagnose",
        "desc": "Checks menu navigation: how well each screen template matches the current screen.",
        "gpu": False,
        "metrics": False,
        "args": [],
    },
    {
        "cmd": "policy-stats",
        "group": "Playing AI: run and measure",
        "title": "Strategy analysis",
        "desc": "Plays greedy matches in the simulator and counts which cards the policy plays, "
                "how often and where, into data/policy_stats.json.",
        "gpu": True,
        "metrics": False,
        "args": [
            {"name": "ckpt", "type": "ckpt", "default": "", "label": "Checkpoint",
             "help": "Empty uses data/policy_sim_best.pt if present, otherwise policy_sim.pt."},
            {"name": "matches", "type": "int", "default": 60, "label": "Matches"},
            {"name": "envs", "type": "int", "default": 8, "label": "Parallel matches"},
            {"name": "seed", "type": "int", "default": 4242, "label": "Seed"},
            {"name": "epsilon", "type": "float", "default": 0.0, "label": "Epsilon",
             "help": "0 means purely greedy, which is what the policy actually does."},
        ],
    },
]

BY_CMD: Dict[str, Dict[str, Any]] = {c["cmd"]: c for c in COMMANDS}


_FORBIDDEN = '"\'\n\r|&;<>'      # never reaches a child process, whatever the panel sends


class ArgError(ValueError):
    """A submitted argument value is not acceptable for this command."""


_AVAILABLE: Dict[str, List[Dict[str, Any]]] = {}


def available(root) -> List[Dict[str, Any]]:
    """The commands this checkout actually has.

    The panel is useful on its own, so it must not offer buttons for features that were
    not merged: it asks argparse which subcommands exist and hides the rest. That is what
    lets the launcher be adopted separately from the tools it can drive.

    Asking costs a subprocess, so the answer is kept for the life of the process.
    """
    import subprocess
    import sys
    key = str(root)
    if key in _AVAILABLE:
        return _AVAILABLE[key]
    try:
        out = subprocess.run([sys.executable, str(root / "run.py"), "--help"], cwd=str(root),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60).stdout
    except Exception:                                  # noqa: BLE001 -- offer everything rather than nothing
        return COMMANDS
    have = {line.split()[0] for line in out.splitlines()
            if line.startswith("    ") and line.strip() and not line.startswith("     ")}
    known = [c for c in COMMANDS if c["cmd"] in have]
    _AVAILABLE[key] = known or COMMANDS
    return _AVAILABLE[key]


def build_argv(cmd: str, values: Dict[str, Any]) -> List[str]:
    """Turn a {arg_name: value} dict into the argv tail for `run.py`.

    Only flags declared in COMMANDS pass; values are coerced to the declared type.
    Anything else raises -- the panel must not be able to smuggle a shell string into
    the child process.
    """
    spec = BY_CMD.get(cmd)
    if spec is None:
        raise ArgError(f"unknown command: {cmd}")
    known = {a["name"]: a for a in spec["args"]}
    argv: List[str] = [cmd]
    for name, raw in (values or {}).items():
        a = known.get(name)
        if a is None:
            raise ArgError(f"unknown parameter '{name}' for {cmd}")
        t = a["type"]
        if a.get("positional"):
            s = str(raw).strip()
            if not s or any(ch in s for ch in _FORBIDDEN):
                raise ArgError(f"{a.get('label', name)}: not a usable path")
            argv.append(s)
            continue
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
                raise ArgError(f"{a.get('label', name)}: '{raw}' is not a whole number") from None
        elif t == "float":
            try:
                s = str(float(s))
            except ValueError:
                raise ArgError(f"{a.get('label', name)}: '{raw}' is not a number") from None
        elif t == "choice":
            if s not in a.get("choices", []):
                raise ArgError(f"{a.get('label', name)}: '{raw}' is not one of the choices")
        elif t in ("session", "ckpt", "str"):
            if any(ch in s for ch in '"\'\n\r|&;<>'):
                raise ArgError(f"{a.get('label', name)}: contains characters that are not allowed")
        argv += [f"--{name}", s]
    return argv

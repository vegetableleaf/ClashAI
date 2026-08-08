"""Edit config.yaml / cards.yaml from the UI without losing the files' documentation.

`config.yaml` is ~60 KB of which most is explanatory comments, and `cards.yaml`
carries per-card notes. A load -> `yaml.safe_dump` round-trip would silently delete
all of it, so every write here is a SURGICAL text patch: locate the exact line for a
key path, replace only the value, keep the trailing comment.

Every write is then verified before it touches disk:
  1. the patched text must still parse as YAML,
  2. the parsed result must equal the old document with EXACTLY the intended change
     (deep compare -- so a botched patch can never silently reshape the config),
  3. the previous file is copied to data/config_backups/ first.
Anything short of that raises and the file on disk stays as it was.
"""
from __future__ import annotations

import copy
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml


class EditError(ValueError):
    """A requested edit is invalid or could not be applied safely."""


# --- the curated set of config.yaml fields the UI exposes -------------------------
# Only scalars and single-line lists: those are the ones a line patch can handle
# safely, and they are the knobs that actually get turned between runs.
FIELDS: List[Dict[str, Any]] = [
    # -- Simulator / Trainingslauf
    {"path": ["sim", "envs"], "type": "int", "min": 1, "max": 256, "group": "Simulator",
     "label": "Parallel matches (sim.envs)",
     "help": "How many matches run at the same time feeding one learner. More means a more "
             "varied replay buffer and better GPU use, but also more memory."},
    {"path": ["sim", "agent_dt"], "type": "float", "min": 0.1, "max": 5.0, "group": "Simulator",
     "label": "Decision interval in seconds (sim.agent_dt)",
     "help": "Simulated seconds between two decisions. Smaller reacts faster but costs many "
             "more steps per match."},
    {"path": ["sim", "regulation_s"], "type": "int", "min": 30, "max": 600, "group": "Simulator",
     "label": "Regulation time (s)", "help": "Length of a match before overtime."},
    {"path": ["sim", "overtime_s"], "type": "int", "min": 0, "max": 600, "group": "Simulator",
     "label": "Overtime (s)", "help": "Extra time when the score is level after regulation."},
    {"path": ["sim", "my_tower_level"], "type": "int", "min": 1, "max": 20, "group": "Simulator",
     "label": "Your tower level",
     "help": "Reference level of your towers. Only RATIOS matter in the simulator: move this "
             "together with the card levels, or the balance shifts."},
    {"path": ["sim", "enemy_levels"], "type": "intlist", "group": "Simulator",
     "label": "Opponent card levels (pool)",
     "help": "Every opponent card rolls its level from this list. Higher makes the ladder benchmark harder."},
    {"path": ["sim", "adaptive_prob"], "type": "float", "min": 0.0, "max": 1.0, "group": "Simulator",
     "label": "Share of adaptive bots",
     "help": "Chance that a scripted opponent uses the adaptive rules: anti-siege, holding a "
             "counter, punishing an overspend, split pushing."},
    # -- Exploration
    {"path": ["sim", "epsilon_start"], "type": "float", "min": 0.0, "max": 1.0, "group": "Exploration",
     "label": "Epsilon start", "help": "Initial share of random moves (1.0 is fully random)."},
    {"path": ["sim", "epsilon_end"], "type": "float", "min": 0.0, "max": 1.0, "group": "Exploration",
     "label": "Epsilon end", "help": "Remaining randomness once the decay is done."},
    {"path": ["sim", "epsilon_decay_steps"], "type": "int", "min": 1, "max": 10 ** 7,
     "group": "Exploration", "label": "Epsilon decay steps",
     "help": "Learning steps, not matches, over which epsilon falls linearly from start to end."},
    {"path": ["sim", "explore_count_based"], "type": "bool", "group": "Exploration",
     "label": "Count-based exploration",
     "help": "Weights random card picks toward rarely played cards, so situational cards get "
             "tried at all."},
    {"path": ["train", "explore_wait_prob"], "type": "float", "min": 0.0, "max": 1.0,
     "group": "Exploration", "label": "Wait share while exploring",
     "help": "How often a random action is a wait instead of playing a card."},
    {"path": ["train", "min_play_elixir"], "type": "int", "min": 0, "max": 10,
     "group": "Exploration", "label": "Minimum elixir for a random play",
     "help": "Below this the exploration branch always waits."},
    # -- Lernen
    {"path": ["train", "device"], "type": "choice", "choices": ["cuda", "cpu"], "group": "Learning",
     "label": "Device", "help": "cuda uses the GPU and falls back to the CPU when none is usable."},
    {"path": ["train", "lr"], "type": "float", "min": 1e-7, "max": 1e-1, "group": "Learning",
     "label": "Learning rate", "help": "Adam learning rate. Too high destabilises the Q values, too low crawls."},
    {"path": ["train", "gamma"], "type": "float", "min": 0.0, "max": 1.0, "group": "Learning",
     "label": "Gamma (Discount)", "help": "How much later rewards count. 0.99 is a long horizon; smaller values make the "
                                          "bot short-sighted."},
    {"path": ["train", "n_step"], "type": "int", "min": 1, "max": 20, "group": "Learning",
     "label": "N-step returns",
     "help": "How many real rewards go into the learning target of one action. Higher links "
             "cause and effect faster but adds variance."},
    {"path": ["train", "batch_size"], "type": "int", "min": 8, "max": 4096, "group": "Learning",
     "label": "Batch size", "help": "Samples per optimisation step."},
    {"path": ["train", "replay_size"], "type": "int", "min": 1000, "max": 5_000_000,
     "group": "Learning", "label": "Replay size", "help": "Maximum number of stored transitions."},
    {"path": ["train", "min_replay"], "type": "int", "min": 1, "max": 1_000_000, "group": "Learning",
     "label": "Replay warm-up", "help": "How many transitions before the learner starts."},
    {"path": ["train", "target_sync"], "type": "int", "min": 1, "max": 100000, "group": "Learning",
     "label": "Target sync (steps)", "help": "How often the target network is refreshed."},
    {"path": ["train", "grad_clip"], "type": "float", "min": 0.0, "max": 1000.0, "group": "Learning",
     "label": "Gradient clipping", "help": "Upper bound on the gradient norm."},
    {"path": ["train", "bc_epochs"], "type": "int", "min": 1, "max": 500, "group": "Learning",
     "label": "BC epochs", "help": "Epochs per behaviour cloning pass."},
    # -- Self-Play & Benchmark
    {"path": ["sim", "selfplay_prob"], "type": "float", "min": 0.0, "max": 1.0, "group": "Self-Play",
     "label": "Self-play share", "help": "Chance of playing a frozen copy of itself instead of a "
                                          "scripted bot. 0 turns it off."},
    {"path": ["sim", "selfplay_ramp_matches"], "type": "int", "min": 0, "max": 10 ** 7,
     "group": "Self-Play", "label": "Self-play ramp (matches)",
     "help": "Over how many matches that share is ramped up."},
    {"path": ["sim", "selfplay_snapshot_every"], "type": "int", "min": 1, "max": 10 ** 6,
     "group": "Self-Play", "label": "Snapshot every N matches"},
    {"path": ["sim", "selfplay_league_size"], "type": "int", "min": 1, "max": 64,
     "group": "Self-Play", "label": "League size", "help": "How many past copies are kept."},
    {"path": ["sim", "selfplay_pfsp"], "type": "bool", "group": "Self-Play", "label": "PFSP enabled",
     "help": "Prefers sparring against the snapshots that currently beat you."},
    {"path": ["sim", "selfplay_pfsp_power"], "type": "float", "min": 0.0, "max": 8.0,
     "group": "Self-Play", "label": "PFSP sharpness", "help": "Higher concentrates harder on the difficult opponents."},
    {"path": ["sim", "eval_every_matches"], "type": "int", "min": 0, "max": 10 ** 6,
     "group": "Benchmark", "label": "Benchmark every N matches", "help": "0 disables it."},
    {"path": ["sim", "eval_matches"], "type": "int", "min": 1, "max": 5000, "group": "Benchmark",
     "label": "Matches per benchmark",
     "help": "More means less noise (about +-4pp at 150 against +-10pp at 24) but a longer pause."},
    {"path": ["sim", "eval_envs"], "type": "int", "min": 1, "max": 256, "group": "Benchmark",
     "label": "Benchmark matches", "help": "Capped at --envs."},
    {"path": ["sim", "eval_smooth_window"], "type": "int", "min": 1, "max": 50, "group": "Benchmark",
     "label": "Smoothing window", "help": "How many benchmarks the average runs over."},
    {"path": ["sim", "fair_eval"], "type": "bool", "group": "Benchmark", "label": "Fair benchmark",
     "help": "An extra run with opponent cards at YOUR level, with the handicap removed."},
    {"path": ["sim", "log_every_matches"], "type": "int", "min": 1, "max": 10000,
     "group": "Benchmark", "label": "Log line every N matches"},
    {"path": ["sim", "save_every_matches"], "type": "int", "min": 1, "max": 10000,
     "group": "Benchmark", "label": "Checkpoint every N matches"},
    # -- Belohnungen
    {"path": ["rewards", "win"], "type": "float", "min": -100, "max": 100, "group": "Rewards",
     "label": "Win", "help": "Final reward for winning a match."},
    {"path": ["rewards", "loss"], "type": "float", "min": -100, "max": 100, "group": "Rewards",
     "label": "Loss"},
    {"path": ["rewards", "take_enemy_tower"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Enemy tower destroyed"},
    {"path": ["rewards", "lose_own_tower"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Own tower lost"},
    {"path": ["rewards", "tower_chip_scale"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Tower chip scale", "help": "Shapes the reward for chip damage on a tower."},
    {"path": ["rewards", "hp_scale"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Tower HP difference scale"},
    {"path": ["rewards", "threat_response"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Threat countered"},
    {"path": ["rewards", "threat_miss"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Threat ignored"},
    {"path": ["rewards", "elixir_trade"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Elixir trade"},
    {"path": ["rewards", "wincon_exec"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Win condition placed well"},
    {"path": ["rewards", "wincon_misplace"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Win condition misplaced"},
    {"path": ["rewards", "leak_penalty"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Elixir leaked"},
    {"path": ["rewards", "spell_waste"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Spell wasted"},
    {"path": ["rewards", "cycle_plan"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Cycle planned"},
    {"path": ["rewards", "cycle_waste"], "type": "float", "min": -100, "max": 100,
     "group": "Rewards", "label": "Cycle wasted"},
    {"path": ["rewards", "correctness_cap"], "type": "float", "min": 0, "max": 1000,
     "group": "Rewards", "label": "Cap on shaping rewards",
     "help": "Limits how much the correctness rewards weigh against the match outcome."},
    # -- perception / actions
    {"path": ["action", "grid"], "type": "intlist", "group": "Perception",
     "label": "Placement grid [columns, rows]",
     "help": "[18,32] fine or [18,24] coarse. Has to match both the dataset and the checkpoint."},
    {"path": ["observation", "arena_size"], "type": "intlist", "group": "Perception",
     "label": "Observation size [W,H]", "help": "Resolution of the arena image fed to the network."},
    {"path": ["observation", "use_detector"], "type": "bool", "group": "Perception",
     "label": "Use the detector", "help": "YOLO detection for the semantic observation."},
    {"path": ["observation", "detector_conf"], "type": "float", "min": 0.0, "max": 1.0,
     "group": "Perception", "label": "Detector confidence"},
    {"path": ["record", "fps"], "type": "int", "min": 1, "max": 60, "group": "Perception",
     "label": "Recording FPS"},
    {"path": ["window", "title_contains"], "type": "str", "group": "Perception",
     "label": "Window title contains", "help": "How the game window is found."},
    {"path": ["play", "act_period"], "type": "float", "min": 0.05, "max": 10.0, "group": "Live",
     "label": "Action interval when playing (s)"},
    {"path": ["play", "epsilon"], "type": "float", "min": 0.0, "max": 1.0, "group": "Live",
     "label": "Epsilon when playing", "help": "0 makes the policy purely greedy."},
]

FIELD_BY_KEY: Dict[str, Dict[str, Any]] = {".".join(f["path"]): f for f in FIELDS}


# --- low-level text patching ------------------------------------------------------
def _comment_split(value_part: str) -> Tuple[str, str]:
    """Split 'value   # note' into (value, comment), respecting quotes."""
    in_s = in_d = False
    for i, ch in enumerate(value_part):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d and (i == 0 or value_part[i - 1].isspace()):
            return value_part[:i], value_part[i:]
    return value_part, ""


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_key_line(lines: Sequence[str], key: str, start: int, end: int, indent: int) -> int:
    pat = re.compile(r"^ {%d}%s\s*:" % (indent, re.escape(key)))
    for i in range(start, end):
        if pat.match(lines[i]):
            return i
    raise EditError(f"key '{key}' not found (indent {indent}).")


def _block_bounds(lines: Sequence[str], head: int, indent: int) -> Tuple[int, int, int]:
    """Body range of the block that starts at `head`, plus the child indentation."""
    i = head + 1
    child_indent = -1
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        ind = _indent_of(ln)
        if ind <= indent:
            break
        if child_indent < 0:
            child_indent = ind
        i += 1
    if child_indent < 0:
        child_indent = indent + 2
    return head + 1, i, child_indent


def _locate(lines: Sequence[str], path: Sequence[str]) -> int:
    start, end, indent = 0, len(lines), 0
    for depth, key in enumerate(path):
        idx = _find_key_line(lines, key, start, end, indent)
        if depth == len(path) - 1:
            return idx
        start, end, indent = _block_bounds(lines, idx, indent)
    raise EditError("leerer Pfad")


def _yaml_float(v: float) -> str:
    """A float literal PyYAML actually resolves as a float.

    PyYAML's implicit float resolver needs a decimal point AND a signed exponent:
    `5e-05` loads as the STRING '5e-05', `5.0e-05` as the number. repr() happily
    produces the former, so normalise it here instead of writing a config value
    that silently changes type.
    """
    s = repr(float(v))
    if s in ("inf", "-inf", "nan"):
        return {"inf": ".inf", "-inf": "-.inf", "nan": ".nan"}[s]
    if "e" in s or "E" in s:
        mant, exp = re.split("[eE]", s, maxsplit=1)
        if "." not in mant:
            mant += ".0"
        if exp[0] not in "+-":
            exp = "+" + exp
        return f"{mant}e{exp}"
    return s if "." in s else s + ".0"


def fmt_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return _yaml_float(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(fmt_value(x) for x in v) + "]"
    if isinstance(v, dict):                       # flow mapping, the style these files already use
        return "{" + ", ".join(f"{k}: {fmt_value(x)}" for k, x in v.items()) + "}"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{}&*!|>'\"%@`]", s) or s.strip() != s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def patch_scalar(text: str, path: Sequence[str], value: Any) -> str:
    lines = text.split("\n")
    idx = _locate(lines, path)
    line = lines[idx]
    m = re.match(r"^(\s*[^:]+:)(.*)$", line)
    if not m:
        raise EditError(f"the line for {'.'.join(path)} cannot be patched: {line!r}")
    head, rest = m.group(1), m.group(2)
    _old, comment = _comment_split(rest)
    lines[idx] = f"{head} {fmt_value(value)}" + (("  " + comment.strip()) if comment.strip() else "")
    return "\n".join(lines)


def _deep_set(data: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    node = data
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value


def _deep_get(data: Any, path: Sequence[str], default: Any = None) -> Any:
    node = data
    for k in path:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def backup(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
    n = 1
    while dst.exists():
        dst = backup_dir / f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}-{n}.bak"
        n += 1
    shutil.copy2(path, dst)
    return dst


def _write_verified(path: Path, new_text: str, expected: Any, backup_dir: Path) -> Path:
    """Parse-check + deep-compare, back up, then write. Raises instead of writing junk."""
    try:
        parsed = yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        raise EditError(f"the result would not be valid YAML, so nothing was written ({exc})") from None
    if parsed != expected:
        raise EditError("safety check failed: the result is not exactly the intended change, "
                        "so nothing was written.")
    bak = backup(path, backup_dir)
    path.write_text(new_text, encoding="utf-8")
    return bak


# --- config.yaml -------------------------------------------------------------------
def coerce(field: Dict[str, Any], raw: Any) -> Any:
    t = field["type"]
    label = field.get("label", ".".join(field["path"]))
    if t == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on", "ja")
    if t == "int":
        try:
            v: Any = int(str(raw).strip())
        except (TypeError, ValueError):
            raise EditError(f"{label}: '{raw}' is not a whole number") from None
    elif t == "float":
        try:
            v = float(str(raw).strip())
        except (TypeError, ValueError):
            raise EditError(f"{label}: '{raw}' is not a number") from None
    elif t == "intlist":
        parts = [p for p in re.split(r"[,\s\[\]]+", str(raw).strip()) if p]
        try:
            v = [int(p) for p in parts]
        except ValueError:
            raise EditError(f"{label}: '{raw}' is not a list of whole numbers") from None
        if not v:
            raise EditError(f"{label}: the list must not be empty")
        return v
    elif t == "choice":
        v = str(raw).strip()
        if v not in field.get("choices", []):
            raise EditError(f"{label}: '{raw}' is not one of the choices")
        return v
    else:
        v = str(raw)
        return v
    lo, hi = field.get("min"), field.get("max")
    if lo is not None and v < lo:
        raise EditError(f"{label}: {v} is below the minimum {lo}")
    if hi is not None and v > hi:
        raise EditError(f"{label}: {v} is above the maximum {hi}")
    return v


def read_config_fields(cfg_path: Path) -> List[Dict[str, Any]]:
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    out = []
    for f in FIELDS:
        val = _deep_get(data, f["path"], None)
        item = {k: v for k, v in f.items() if k != "path"}
        item["key"] = ".".join(f["path"])
        item["value"] = val
        item["present"] = val is not None or _deep_get(data, f["path"][:-1], None) is not None
        out.append(item)
    return out


def save_config_fields(cfg_path: Path, changes: Dict[str, Any], backup_dir: Path) -> Dict[str, Any]:
    """Apply {`sim.envs`: 12, ...}. Returns {'backup':..., 'changed':[...]} or raises."""
    text = cfg_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    expected = copy.deepcopy(data)
    applied: List[Dict[str, Any]] = []
    new_text = text
    for key, raw in (changes or {}).items():
        field = FIELD_BY_KEY.get(key)
        if field is None:
            raise EditError(f"field '{key}' is not editable.")
        value = coerce(field, raw)
        old = _deep_get(data, field["path"], None)
        if old == value and type(old) is type(value):
            continue
        new_text = patch_scalar(new_text, field["path"], value)
        _deep_set(expected, field["path"], value)
        applied.append({"key": key, "old": old, "new": value})
    if not applied:
        return {"backup": None, "changed": []}
    bak = _write_verified(cfg_path, new_text, expected, backup_dir)
    return {"backup": str(bak), "changed": applied}


# --- cards.yaml deck block ---------------------------------------------------------
_DECK_LINE = re.compile(r"^\s*-\s*\{\s*card:\s*(?P<card>[A-Za-z0-9_]+)")


def read_deck(cards_path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(cards_path.read_text(encoding="utf-8")) or {}
    deck = data.get("deck") or {}
    return {"name": deck.get("name", "deck"),
            "cards": [dict(c) for c in (deck.get("cards") or [])]}


def _deck_bounds(lines: Sequence[str]) -> Tuple[int, int]:
    head = None
    for i, ln in enumerate(lines):
        if re.match(r"^deck\s*:", ln):
            head = i
            break
    if head is None:
        raise EditError("no 'deck:' block found in cards.yaml.")
    j = head + 1
    while j < len(lines):
        ln = lines[j]
        if ln.strip() and not ln.startswith(" ") and not ln.lstrip().startswith("#"):
            break
        j += 1
    # trailing blank/comment lines belong to whatever follows, not to the deck
    end = j
    while end - 1 > head and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return head, end


# --- tower troops (sim.tower_troops / opponent_tower_weights / king_tower) ---------
# Which extra keys the engine understands per tower troop, beyond hp/dps/hit_speed
# (see sim/engine.py `_make_tower`): Dagger Duchess' loaded burst and Royal Chef's buff.
TOWER_EXTRA_FIELDS = ["ammo", "empty_dps", "reload_s",
                      "cook_period_s", "cook_delay_s", "buff_mult", "buff_min_frac"]
_TOWER_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def _entry_comments(lines: Sequence[str], start: int, end: int) -> Dict[str, str]:
    """Trailing comments of `  key: ...` lines inside a block, keyed by their key."""
    out: Dict[str, str] = {}
    for ln in lines[start:end]:
        m = re.match(r"^\s+([A-Za-z0-9_]+)\s*:", ln)
        if m:
            _v, comment = _comment_split(ln)
            if comment.strip():
                out[m.group(1)] = comment.strip()
    return out


def _replace_mapping_block(text: str, path: Sequence[str], entries: Dict[str, Any]) -> str:
    """Rewrite a nested `key:` block as `  name: <value>` lines, keeping the header line
    (with its comment) and any per-entry trailing comment whose key survives."""
    lines = text.split("\n")
    head = _locate(lines, path)
    indent = _indent_of(lines[head])
    start, end, child_indent = _block_bounds(lines, head, indent)
    comments = _entry_comments(lines, start, end)
    body = [" " * child_indent + f"{k}: {fmt_value(v)}"
            + (f"   {comments[k]}" if k in comments else "")
            for k, v in entries.items()]
    return "\n".join(lines[:start] + body + lines[end:])


def read_towers(cfg_path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    sim = data.get("sim") or {}
    return {
        "my_tower_troop": sim.get("my_tower_troop", "princess"),
        "my_tower_level": sim.get("my_tower_level", 15),
        "tower_range": sim.get("tower_range", 8.0),
        "king_range": sim.get("king_range", 7.5),
        "tower_first_hit": sim.get("tower_first_hit", 0.8),
        "king_tower": dict(sim.get("king_tower") or {}),
        "tower_troops": {k: dict(v) for k, v in (sim.get("tower_troops") or {}).items()},
        "opponent_tower_weights": dict(sim.get("opponent_tower_weights") or {}),
        "extra_fields": TOWER_EXTRA_FIELDS,
    }


def _num(label: str, raw: Any, lo: float, hi: float, integer: bool = False):
    try:
        v = int(float(str(raw).strip())) if integer else float(str(raw).strip())
    except (TypeError, ValueError):
        raise EditError(f"{label}: '{raw}' is not a number") from None
    if not lo <= v <= hi:
        raise EditError(f"{label}: {v} is outside {lo}...{hi}")
    return v


def save_towers(cfg_path: Path, payload: Dict[str, Any], backup_dir: Path) -> Dict[str, Any]:
    """Write the tower-troop setup back into config.yaml (blocks rewritten, comments kept).

    Adding a troop here is enough for the engine to use it: `sim/engine.py` looks every
    profile up by name at match reset, and the opponent rolls one from the weights -- so a
    new entry immediately shows up as an opponent tower the policy has to cope with.
    """
    troops_in = payload.get("tower_troops") or {}
    if not troops_in:
        raise EditError("at least one tower troop has to be defined.")
    troops: Dict[str, Dict[str, Any]] = {}
    for raw_name, spec in troops_in.items():
        name = str(raw_name).strip().lower().replace(" ", "_").replace("-", "_")
        if not _TOWER_NAME.match(name):
            raise EditError(f"'{raw_name}' is not a valid tower name "
                            "(lower case, digits, underscore; 2 to 32 characters).")
        if name in troops:
            raise EditError(f"tower '{name}' appears twice.")
        out: Dict[str, Any] = {
            "hp": _num(f"{name}.hp", (spec or {}).get("hp"), 1, 1_000_000, integer=True),
            "dps": _num(f"{name}.dps", (spec or {}).get("dps"), 0, 100_000, integer=True),
            "hit_speed": _num(f"{name}.hit_speed", (spec or {}).get("hit_speed"), 0.05, 10.0),
        }
        for f in TOWER_EXTRA_FIELDS:
            v = (spec or {}).get(f)
            if v is None or str(v).strip() == "":
                continue
            out[f] = _num(f"{name}.{f}", v, 0, 100_000)
            if f in ("ammo", "empty_dps"):
                out[f] = int(out[f])
        troops[name] = out

    my = str(payload.get("my_tower_troop", "princess")).strip().lower()
    if my not in troops:
        raise EditError(f"your tower troop '{my}' does not appear in the tower list.")

    weights_in = payload.get("opponent_tower_weights") or {}
    weights: Dict[str, int] = {}
    for k, v in weights_in.items():
        name = str(k).strip().lower()
        if name not in troops:
            raise EditError(f"the weight for '{name}' has no matching tower troop.")
        w = int(_num(f"weight of {name}", v, 0, 10_000, integer=True))
        if w > 0:
            weights[name] = w
    if not weights:
        raise EditError("at least one opponent tower needs a weight above 0.")

    king_in = payload.get("king_tower") or {}
    king = {
        "hp": _num("king.hp", king_in.get("hp"), 1, 1_000_000, integer=True),
        "dps": _num("king.dps", king_in.get("dps"), 0, 100_000, integer=True),
        "hit_speed": _num("king.hit_speed", king_in.get("hit_speed"), 0.05, 10.0),
    }
    scalars = {
        ("sim", "my_tower_troop"): my,
        ("sim", "my_tower_level"): int(_num("tower level", payload.get("my_tower_level", 15),
                                            1, 20, integer=True)),
        # TILES since the 18x32 board rebuild. These bounds used to be (0.01, 1.0) from the old
        # SCREEN-NORMALISED era, which silently CLAMPED a saved 8.0-tile range down to 1.0 -- i.e.
        # opening and saving this editor would have quietly disarmed every crown tower.
        ("sim", "tower_range"): _num("tower range (tiles)", payload.get("tower_range", 8.0), 0.5, 32.0),
        ("sim", "king_range"): _num("king tower range (tiles)", payload.get("king_range", 7.5), 0.5, 32.0),
        ("sim", "tower_first_hit"): _num("first shot delay",
                                         payload.get("tower_first_hit", 0.8), 0.0, 10.0),
    }

    text = cfg_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    expected = copy.deepcopy(data)
    new_text = _replace_mapping_block(text, ["sim", "tower_troops"], troops)
    new_text = _replace_mapping_block(new_text, ["sim", "opponent_tower_weights"], weights)
    new_text = patch_scalar(new_text, ["sim", "king_tower"], king)
    expected["sim"]["tower_troops"] = troops
    expected["sim"]["opponent_tower_weights"] = weights
    expected["sim"]["king_tower"] = king
    for p, v in scalars.items():
        new_text = patch_scalar(new_text, list(p), v)
        _deep_set(expected, list(p), v)
    bak = _write_verified(cfg_path, new_text, expected, backup_dir)
    return {"backup": str(bak), "troops": sorted(troops), "weights": weights}


def save_deck(cards_path: Path, name: str, cards: List[Dict[str, Any]], backup_dir: Path,
              valid_keys: Optional[set] = None) -> Dict[str, Any]:
    """Rewrite ONLY the `deck:` block (flow style, as in the file), keeping per-card comments."""
    if not isinstance(cards, list) or not (1 <= len(cards) <= 8):
        raise EditError("a deck needs 1 to 8 cards (Clash Royale: exactly 8).")
    seen = set()
    norm: List[Dict[str, Any]] = []
    for c in cards:
        key = str(c.get("card", "")).strip().lower()
        if not key:
            raise EditError("empty card name in the deck.")
        if valid_keys is not None and key not in valid_keys:
            raise EditError(f"card '{key}' is not in the card database.")
        if key in seen:
            raise EditError(f"card '{key}' appears twice in the deck.")
        seen.add(key)
        try:
            lvl = int(c.get("level", 11))
        except (TypeError, ValueError):
            raise EditError(f"the level of '{key}' is not a number.") from None
        if not 1 <= lvl <= 20:
            raise EditError(f"the level of '{key}' has to be between 1 and 20.")
        entry: Dict[str, Any] = {"card": key}
        if c.get("evolved"):
            entry["evolved"] = True
        entry["level"] = lvl
        norm.append(entry)

    text = cards_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    lines = text.split("\n")
    head, end = _deck_bounds(lines)

    comments: Dict[str, str] = {}
    for ln in lines[head:end]:
        m = _DECK_LINE.match(ln)
        if m:
            _v, comment = _comment_split(ln)
            if comment.strip():
                comments[m.group("card")] = comment.strip()

    block = ["deck:", f"  name: {fmt_value(str(name).strip() or 'deck')}", "  cards:"]
    for e in norm:
        inner = f"card: {e['card']}"
        if e.get("evolved"):
            inner += ", evolved: true"
        inner += f", level: {e['level']}"
        cm = comments.get(e["card"])
        block.append(f"    - {{{inner}}}" + (f"   {cm}" if cm else ""))

    new_text = "\n".join(lines[:head] + block + lines[end:])
    expected = copy.deepcopy(data)
    expected["deck"] = {"name": str(name).strip() or "deck", "cards": norm}
    bak = _write_verified(cards_path, new_text, expected, backup_dir)
    return {"backup": str(bak), "cards": norm}

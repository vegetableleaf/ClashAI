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
     "label": "Parallele Envs (sim.envs)",
     "help": "Wieviele Match-Instanzen gleichzeitig laufen und einen Learner füttern. "
             "Mehr = vielfältigerer Replay und bessere GPU-Auslastung, aber mehr RAM."},
    {"path": ["sim", "agent_dt"], "type": "float", "min": 0.1, "max": 5.0, "group": "Simulator",
     "label": "Agenten-Takt in Sekunden (sim.agent_dt)",
     "help": "Simulierte Sekunden zwischen zwei Entscheidungen. Kleiner = reaktiver, aber "
             "deutlich mehr Schritte pro Match."},
    {"path": ["sim", "regulation_s"], "type": "int", "min": 30, "max": 600, "group": "Simulator",
     "label": "Reguläre Spielzeit (s)", "help": "Länge eines Matches vor der Verlängerung."},
    {"path": ["sim", "overtime_s"], "type": "int", "min": 0, "max": 600, "group": "Simulator",
     "label": "Verlängerung (s)", "help": "Zusatzzeit, wenn nach regulärer Zeit unentschieden."},
    {"path": ["sim", "my_tower_level"], "type": "int", "min": 1, "max": 20, "group": "Simulator",
     "label": "Eigenes Turm-Level",
     "help": "Referenzlevel deiner Türme. Im Sim zählen nur VERHÄLTNISSE: dieses Level und die "
             "Deck-Level müssen gemeinsam bewegt werden, sonst verschiebt sich die Balance."},
    {"path": ["sim", "enemy_levels"], "type": "intlist", "group": "Simulator",
     "label": "Gegner-Kartenlevel (Pool)",
     "help": "Aus dieser Liste würfelt jede Gegnerkarte ihr Level. Höher = härterer Ladder-Benchmark."},
    {"path": ["sim", "adaptive_prob"], "type": "float", "min": 0.0, "max": 1.0, "group": "Simulator",
     "label": "Anteil adaptiver Bots",
     "help": "Wahrscheinlichkeit, dass ein skriptierter Gegner die adaptiven Regeln nutzt "
             "(Anti-Siege, Konter halten, Bestrafen, Split-Push)."},
    # -- Exploration
    {"path": ["sim", "epsilon_start"], "type": "float", "min": 0.0, "max": 1.0, "group": "Exploration",
     "label": "Epsilon Start", "help": "Anfangs-Zufallsanteil der Aktionswahl (1.0 = rein zufällig)."},
    {"path": ["sim", "epsilon_end"], "type": "float", "min": 0.0, "max": 1.0, "group": "Exploration",
     "label": "Epsilon Ende", "help": "Rest-Zufall am Ende des Decays."},
    {"path": ["sim", "epsilon_decay_steps"], "type": "int", "min": 1, "max": 10 ** 7,
     "group": "Exploration", "label": "Epsilon-Decay Schritte",
     "help": "Lernschritte (nicht Matches!), über die Epsilon linear von Start auf Ende fällt."},
    {"path": ["sim", "explore_count_based"], "type": "bool", "group": "Exploration",
     "label": "Count-based Exploration",
     "help": "Gewichtet zufällige Karten-Picks Richtung selten gespielter Karten, damit "
             "situative Karten überhaupt getestet werden."},
    {"path": ["train", "explore_wait_prob"], "type": "float", "min": 0.0, "max": 1.0,
     "group": "Exploration", "label": "Warte-Anteil beim Explorieren",
     "help": "Wie oft eine Zufallsaktion 'Warten' ist statt eine Karte zu legen."},
    {"path": ["train", "min_play_elixir"], "type": "int", "min": 0, "max": 10,
     "group": "Exploration", "label": "Mindest-Elixier für Zufallsplay",
     "help": "Unter diesem Stand wartet der Explorationszweig grundsätzlich."},
    # -- Lernen
    {"path": ["train", "device"], "type": "choice", "choices": ["cuda", "cpu"], "group": "Lernen",
     "label": "Gerät", "help": "cuda = GPU. Fällt automatisch auf CPU zurück, wenn keine GPU nutzbar ist."},
    {"path": ["train", "lr"], "type": "float", "min": 1e-7, "max": 1e-1, "group": "Lernen",
     "label": "Lernrate", "help": "Adam-Lernrate. Zu hoch = instabile Q-Werte, zu niedrig = zäh."},
    {"path": ["train", "gamma"], "type": "float", "min": 0.0, "max": 1.0, "group": "Lernen",
     "label": "Gamma (Discount)", "help": "Wie stark späte Belohnungen zählen. 0.99 ≈ langer Horizont."},
    {"path": ["train", "n_step"], "type": "int", "min": 1, "max": 20, "group": "Lernen",
     "label": "N-Step Returns",
     "help": "Wieviele echte Belohnungen in das Lernziel einer Aktion einfließen. Höher = "
             "schnellere Ursache-Wirkung-Zuordnung, aber mehr Varianz."},
    {"path": ["train", "batch_size"], "type": "int", "min": 8, "max": 4096, "group": "Lernen",
     "label": "Batch-Größe", "help": "Samples pro Optimierungsschritt."},
    {"path": ["train", "replay_size"], "type": "int", "min": 1000, "max": 5_000_000,
     "group": "Lernen", "label": "Replay-Größe", "help": "Maximale Anzahl gespeicherter Transitionen."},
    {"path": ["train", "min_replay"], "type": "int", "min": 1, "max": 1_000_000, "group": "Lernen",
     "label": "Replay-Mindestfüllung", "help": "Ab wievielen Transitionen der Learner startet."},
    {"path": ["train", "target_sync"], "type": "int", "min": 1, "max": 100000, "group": "Lernen",
     "label": "Target-Sync (Schritte)", "help": "Abstand, in dem das Target-Netz nachgezogen wird."},
    {"path": ["train", "grad_clip"], "type": "float", "min": 0.0, "max": 1000.0, "group": "Lernen",
     "label": "Gradient Clipping", "help": "Obergrenze der Gradientennorm."},
    {"path": ["train", "bc_epochs"], "type": "int", "min": 1, "max": 500, "group": "Lernen",
     "label": "BC-Epochen", "help": "Epochen pro Behaviour-Cloning-Durchlauf."},
    # -- Self-Play & Benchmark
    {"path": ["sim", "selfplay_prob"], "type": "float", "min": 0.0, "max": 1.0, "group": "Self-Play",
     "label": "Self-Play Anteil", "help": "Wahrscheinlichkeit, gegen eine eingefrorene eigene Kopie "
                                          "zu spielen statt gegen einen skriptierten Bot. 0 = aus."},
    {"path": ["sim", "selfplay_ramp_matches"], "type": "int", "min": 0, "max": 10 ** 7,
     "group": "Self-Play", "label": "Self-Play Anlauf (Matches)",
     "help": "Über wieviele Matches der Anteil linear hochgefahren wird."},
    {"path": ["sim", "selfplay_snapshot_every"], "type": "int", "min": 1, "max": 10 ** 6,
     "group": "Self-Play", "label": "Snapshot alle N Matches"},
    {"path": ["sim", "selfplay_league_size"], "type": "int", "min": 1, "max": 64,
     "group": "Self-Play", "label": "Liga-Größe", "help": "Wieviele vergangene Kopien aufbewahrt werden."},
    {"path": ["sim", "selfplay_pfsp"], "type": "bool", "group": "Self-Play", "label": "PFSP aktiv",
     "help": "Bevorzugt beim Sparring die Snapshots, die dich aktuell schlagen."},
    {"path": ["sim", "selfplay_pfsp_power"], "type": "float", "min": 0.0, "max": 8.0,
     "group": "Self-Play", "label": "PFSP Schärfe", "help": "Höher = konzentrierter auf harte Gegner."},
    {"path": ["sim", "eval_every_matches"], "type": "int", "min": 0, "max": 10 ** 6,
     "group": "Benchmark", "label": "Benchmark alle N Matches", "help": "0 = kein Benchmark."},
    {"path": ["sim", "eval_matches"], "type": "int", "min": 1, "max": 5000, "group": "Benchmark",
     "label": "Matches pro Benchmark",
     "help": "Mehr = weniger Rauschen (~±4pp bei 150 gegen ~±10pp bei 24), aber längere Pause."},
    {"path": ["sim", "eval_envs"], "type": "int", "min": 1, "max": 256, "group": "Benchmark",
     "label": "Benchmark-Envs", "help": "Wird auf --envs gedeckelt."},
    {"path": ["sim", "eval_smooth_window"], "type": "int", "min": 1, "max": 50, "group": "Benchmark",
     "label": "Glättungsfenster", "help": "Über wieviele Benchmarks der Durchschnitt läuft."},
    {"path": ["sim", "fair_eval"], "type": "bool", "group": "Benchmark", "label": "Fairer Benchmark",
     "help": "Zusätzlicher Durchlauf mit Gegnerkarten auf DEINEM Level (Handicap entfernt)."},
    {"path": ["sim", "log_every_matches"], "type": "int", "min": 1, "max": 10000,
     "group": "Benchmark", "label": "Logzeile alle N Matches"},
    {"path": ["sim", "save_every_matches"], "type": "int", "min": 1, "max": 10000,
     "group": "Benchmark", "label": "Checkpoint alle N Matches"},
    # -- Belohnungen
    {"path": ["rewards", "win"], "type": "float", "min": -100, "max": 100, "group": "Belohnungen",
     "label": "Sieg", "help": "Endbelohnung für einen gewonnenen Match."},
    {"path": ["rewards", "loss"], "type": "float", "min": -100, "max": 100, "group": "Belohnungen",
     "label": "Niederlage"},
    {"path": ["rewards", "take_enemy_tower"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Gegnerturm zerstört"},
    {"path": ["rewards", "lose_own_tower"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Eigenen Turm verloren"},
    {"path": ["rewards", "tower_chip_scale"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Turmschaden-Skala", "help": "Formt Chip-Schaden am Turm."},
    {"path": ["rewards", "hp_scale"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "HP-Differenz-Skala"},
    {"path": ["rewards", "threat_response"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Bedrohung gekontert"},
    {"path": ["rewards", "threat_miss"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Bedrohung ignoriert"},
    {"path": ["rewards", "elixir_trade"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Elixier-Trade"},
    {"path": ["rewards", "wincon_exec"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Win-Condition richtig gesetzt"},
    {"path": ["rewards", "wincon_misplace"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Win-Condition falsch gesetzt"},
    {"path": ["rewards", "leak_penalty"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Elixier verschwendet (Leak)"},
    {"path": ["rewards", "spell_waste"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Zauber verschwendet"},
    {"path": ["rewards", "cycle_plan"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Cycle geplant"},
    {"path": ["rewards", "cycle_waste"], "type": "float", "min": -100, "max": 100,
     "group": "Belohnungen", "label": "Cycle verschwendet"},
    {"path": ["rewards", "correctness_cap"], "type": "float", "min": 0, "max": 1000,
     "group": "Belohnungen", "label": "Deckel für Shaping-Summe",
     "help": "Begrenzt, wieviel die 'Korrektheits'-Belohnungen gegenüber dem Spielausgang wiegen."},
    # -- Wahrnehmung / Aktionen
    {"path": ["action", "grid"], "type": "intlist", "group": "Wahrnehmung",
     "label": "Platzierungsraster [Spalten, Zeilen]",
     "help": "[18,32] fein / [18,24] grob. Muss zu Datensatz UND Checkpoint passen."},
    {"path": ["observation", "arena_size"], "type": "intlist", "group": "Wahrnehmung",
     "label": "Beobachtungsgröße [B,H]", "help": "Auflösung des Arena-Bildes für das CNN."},
    {"path": ["observation", "use_detector"], "type": "bool", "group": "Wahrnehmung",
     "label": "Detektor verwenden", "help": "YOLO-Erkennung für die semantische Beobachtung."},
    {"path": ["observation", "detector_conf"], "type": "float", "min": 0.0, "max": 1.0,
     "group": "Wahrnehmung", "label": "Detektor-Konfidenz"},
    {"path": ["record", "fps"], "type": "int", "min": 1, "max": 60, "group": "Wahrnehmung",
     "label": "Aufnahme-FPS"},
    {"path": ["window", "title_contains"], "type": "str", "group": "Wahrnehmung",
     "label": "Fenstertitel enthält", "help": "So wird das Spielfenster gefunden."},
    {"path": ["play", "act_period"], "type": "float", "min": 0.05, "max": 10.0, "group": "Live",
     "label": "Aktions-Takt live (s)"},
    {"path": ["play", "epsilon"], "type": "float", "min": 0.0, "max": 1.0, "group": "Live",
     "label": "Epsilon live", "help": "0 = die Policy spielt rein greedy."},
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
    raise EditError(f"Schlüssel '{key}' nicht gefunden (Einrückung {indent}).")


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
        raise EditError(f"Zeile für {'.'.join(path)} ist nicht patchbar: {line!r}")
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
        raise EditError(f"Ergebnis wäre ungültiges YAML -- nichts geschrieben ({exc})") from None
    if parsed != expected:
        raise EditError("Sicherheitsprüfung fehlgeschlagen: das Ergebnis entspricht nicht exakt "
                        "der beabsichtigten Änderung -- nichts geschrieben.")
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
            raise EditError(f"{label}: '{raw}' ist keine ganze Zahl") from None
    elif t == "float":
        try:
            v = float(str(raw).strip())
        except (TypeError, ValueError):
            raise EditError(f"{label}: '{raw}' ist keine Zahl") from None
    elif t == "intlist":
        parts = [p for p in re.split(r"[,\s\[\]]+", str(raw).strip()) if p]
        try:
            v = [int(p) for p in parts]
        except ValueError:
            raise EditError(f"{label}: '{raw}' ist keine Liste ganzer Zahlen") from None
        if not v:
            raise EditError(f"{label}: Liste darf nicht leer sein")
        return v
    elif t == "choice":
        v = str(raw).strip()
        if v not in field.get("choices", []):
            raise EditError(f"{label}: '{raw}' ist keine gültige Auswahl")
        return v
    else:
        v = str(raw)
        return v
    lo, hi = field.get("min"), field.get("max")
    if lo is not None and v < lo:
        raise EditError(f"{label}: {v} liegt unter dem Minimum {lo}")
    if hi is not None and v > hi:
        raise EditError(f"{label}: {v} liegt über dem Maximum {hi}")
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
    """Apply {`sim.envs`: 12, ...}. Returns {'backup':…, 'changed':[…]} or raises."""
    text = cfg_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    expected = copy.deepcopy(data)
    applied: List[Dict[str, Any]] = []
    new_text = text
    for key, raw in (changes or {}).items():
        field = FIELD_BY_KEY.get(key)
        if field is None:
            raise EditError(f"Feld '{key}' ist nicht editierbar.")
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
        raise EditError("Kein 'deck:'-Block in cards.yaml gefunden.")
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


def save_deck(cards_path: Path, name: str, cards: List[Dict[str, Any]], backup_dir: Path,
              valid_keys: Optional[set] = None) -> Dict[str, Any]:
    """Rewrite ONLY the `deck:` block (flow style, as in the file), keeping per-card comments."""
    if not isinstance(cards, list) or not (1 <= len(cards) <= 8):
        raise EditError("Ein Deck braucht 1-8 Karten (Clash Royale: genau 8).")
    seen = set()
    norm: List[Dict[str, Any]] = []
    for c in cards:
        key = str(c.get("card", "")).strip().lower()
        if not key:
            raise EditError("Leerer Kartenname im Deck.")
        if valid_keys is not None and key not in valid_keys:
            raise EditError(f"Karte '{key}' steht nicht in der Kartendatenbank.")
        if key in seen:
            raise EditError(f"Karte '{key}' ist doppelt im Deck.")
        seen.add(key)
        try:
            lvl = int(c.get("level", 11))
        except (TypeError, ValueError):
            raise EditError(f"Level von '{key}' ist keine Zahl.") from None
        if not 1 <= lvl <= 20:
            raise EditError(f"Level von '{key}' muss zwischen 1 und 20 liegen.")
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

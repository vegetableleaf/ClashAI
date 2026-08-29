"""Overnight watchdog for a `train-sim-ppo` run: alert on DEATH, STALL, or COLLAPSE.

    python tools/ppo_watchdog.py data/policy_ppo_drill.pt [--every 300] [--quiet-min 25]

The run writes to a terminal, not a log file, so the checkpoint is the signal. Every cycle this
reads it and records `matches`, `best_wr`, and the health numbers that have actually caught
failures on this project before. It prints a line to stdout -- and posts to Discord -- ONLY when
something is wrong, so it can be left running all night without becoming noise.

WHAT IT WATCHES, and why each one is here rather than invented:

  DEAD        no `train-sim-ppo` process left. The run died or was killed.
  STALLED     the checkpoint has not advanced in `--quiet-min` minutes. At ~0.2 ep/s a save
              should land many times an hour; silence means a hang or a crashed worker pool.
  GATE        P(play) collapsed. Measured on this project: a gate at P(play) 0.938 with min
              0.911 "never holds at any threshold, elixir never passes 5, and the 6-cost win
              conditions stay masked (= zero policy gradient) forever" -- the reason
              --reset-gate exists. The mirror (P(play) ~ 0) is a policy that has stopped playing.
  CELL        the 432-way cell head pinned at maximum entropy. Only checked after 4000
              matches: `ppo_cell_entropy` anneals to its floor over 3000 episodes, so a max-entropy
              head before that is the SCHEDULE doing its job, not a fault -- it was 8.36 of 8.37 after 500
              matches, indistinguishable from an untrained net, which made every placement-
              dependent reward unreachable. Also flags the opposite failure, collapse to a
              handful of cells (it once sat on 3 of 432, 79% of plays on one tile).
  ELIXIR      the bar never reaches 6, so X-Bow and Rocket can never be played at all.
              Only after 6000 matches: early on the policy is near-random and plays far too
              often to bank anything, which is the ENTROPY SCHEDULE, not a fault.

Health is appended to data/ppo_watchdog.log every cycle whether or not it alerts, so the morning
has a trace rather than just the last state. The webhook is a SECRET: read from
data/discord_webhook.txt, never printed, never put in an error message.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np                                      # noqa: E402
import torch                                            # noqa: E402


def _post_discord(text: str) -> None:
    """Post an alert. Failures are reported by TYPE only -- the URL never reaches a log line."""
    p = _ROOT / "data" / "discord_webhook.txt"
    if not p.exists():
        return
    body = json.dumps({"content": text[:1900]}).encode()
    req = urllib.request.Request(
        p.read_text(encoding="utf-8").strip(), data=body,
        headers={"Content-Type": "application/json",
                 # Discord answers 403 to urllib's default UA -- verified on this webhook.
                 "User-Agent": "icebow-monitor/1.0 (+local)"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:                               # noqa: BLE001
        print("[watchdog] discord post failed: %s" % type(e).__name__, flush=True)


def _running() -> int:
    """How many train-sim-ppo processes are alive."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" |"
             " Where-Object { $_.CommandLine -match 'train-sim-ppo' }).Count"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return int(out or 0)
    except Exception:                                    # noqa: BLE001
        return -1                                        # unknown: never alert on a probe failure


def _entropy(p) -> float:
    p = np.asarray(p, dtype=np.float64)
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def health(ckpt: Path, envs: int = 6, steps: int = 400) -> dict:
    """Run the trained net on real boards and measure gate / cell / elixir behaviour."""
    import torch.nn as nn
    from clashrl.config import Config
    from clashrl.model import PolicyNet
    from clashrl.sim.env import SimMatchEnv

    cfg = Config.load(_ROOT / "config" / "config.yaml")
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    pool = [SimMatchEnv(cfg, seed=4242 + i) for i in range(envs)]
    e0 = pool[0]
    for e in pool:
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False
            e.domain_rand.resample()
    in_ch = int(state.get("in_ch") or 12)
    thr_dim = int(state.get("threat_dim") or e0.threat_dim)

    class PPONet(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(in_ch, e0.n_cards, e0.n_cells, threat_dim=thr_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)

        def forward(self, x, hand, nxt, elx, thr):
            # forward_parts, NOT features_vec + a dense readout: the spatial cell head needs the
            # pre-pool feature map, and `cell_head` is not a module at all (its docstring says so --
            # that dense readout was the collapse this head replaced).
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z)

    net = PPONet()
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > in_ch:
            x = x[:, :, :in_ch]
        elif x.shape[2] < in_ch:
            x = np.concatenate([x, np.zeros((x.shape[0], x.shape[1], in_ch - x.shape[2]),
                                            dtype=x.dtype)], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0

    def thr_t(v):
        t = np.asarray(v, np.float32)
        return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim
                                else np.pad(t, (0, thr_dim - t.shape[0])))

    cellmask = np.asarray(e0.actions.deployable_mask(False), dtype=bool)
    obs = [e.reset() for e in pool]
    p_play, elixir, cell_ent, card_ent, cells = [], [], [], [], []
    with torch.no_grad():
        for _ in range(steps):
            xb = torch.stack([obs_t(o) for o in obs])
            hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
            nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
            eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
            tb = torch.stack([thr_t(e.threat_vec) for e in pool])
            cq, ceq, gq = net(xb, hb, nb, eb, tb)
            pg = torch.softmax(gq, dim=1)[:, 1].numpy()
            pc = torch.softmax(cq, dim=1).numpy()
            for i, e in enumerate(pool):
                p_play.append(float(pg[i]))
                elixir.append(float(e.eng.elixir[0]))
                card_ent.append(_entropy(pc[i]))
                # MASK TO THE DEPLOYABLE SET, because that is what the policy chooses among and
                # what training updates. Only 157 of 432 cells are deployable, so an unmasked
                # softmax measures 275 never-updated logits alongside the real ones and dilutes the
                # signal ~6x: the same checkpoint reads 6.05 of 6.07 unmasked and 5.038 of 5.056
                # masked. It also means the MAXIMUM to compare against is ln(157), not ln(432).
                top = int(np.argmax(pc[i]))
                lg = ceq[i, top].numpy().copy()
                lg[~cellmask] = -1e9
                pcell = np.exp(lg - lg.max())
                pcell = pcell / pcell.sum()
                cell_ent.append(_entropy(pcell))
                cells.append(int(np.argmax(pcell)))
                # SAMPLE THE CARD FROM THE CARD HEAD, not hand[0]. Taking the first affordable
                # card means taking the CHEAPEST one nearly every time, which drains the bar under
                # the probe's own policy and then reads as "elixir never reaches 6" -- a property
                # of the measurement, not of the run. The policy picks a card; so must this.
                hand = [c for c in e._hand_ids()
                        if 0 <= c < len(e.specs) and e.eng.elixir[0] >= e.specs[c].elixir]
                if hand:
                    w = np.asarray([pc[i][c] for c in hand], dtype=np.float64)
                    w = w / w.sum() if w.sum() > 0 else None
                    pick = int(np.random.choice(hand, p=w)) if w is not None else int(hand[0])
                else:
                    pick = None
                # SAMPLE the gate, do not threshold it. Forcing a play whenever P(play)>0.25
                # drains the bar under the probe's own policy, which then reads as "elixir never
                # reaches 6" -- an artifact of the measurement, not of the run. Training samples;
                # so does this.
                play = bool(hand) and bool(np.random.random() < pg[i])
                act = (1, pick, int(e0.n_cells // 2)) if (play and pick is not None) else (0, 0, 0)
                nobs, _r, done, _i = e.step(act)
                obs[i] = e.reset() if done else nobs
    return {
        "matches": int(state.get("matches") or 0),
        "best_wr": float(state.get("best_wr", -1.0)),
        "p_play_mean": float(np.mean(p_play)), "p_play_min": float(np.min(p_play)),
        "p_play_max": float(np.max(p_play)),
        "elixir_mean": float(np.mean(elixir)),
        "elixir_ge6": float(np.mean(np.asarray(elixir) >= 6.0)),
        "cell_ent": float(np.mean(cell_ent)),
        "cell_ent_max": float(math.log(max(2, int(cellmask.sum())))),
        "cell_distinct": int(len(set(cells))),
        "card_ent": float(np.mean(card_ent)), "card_ent_max": float(math.log(e0.n_cards)),
    }


def cell_structure(ckpt: Path) -> float:
    """WITHIN-card cell-logit spread, relative to an untrained net. The sensitive measure.

    ENTROPY IS THE WRONG INSTRUMENT HERE and this replaces it. A distribution over 157 deployable
    cells barely moves in entropy for a large change in structure: measured on the same checkpoint,
    the head carried 719x an untrained net's within-card logit spread while its entropy had fallen
    only 0.018 nats out of 5.056 -- which reads as "indistinguishable from untrained" and is not.
    That false alarm is the reason this function exists.

    WITHIN-card, not across the whole map: a head can learn a per-CARD bias (this card's logits are
    all higher) without learning any PLACEMENT at all, and only the spread inside one card's own map
    is what "where to put it" means.
    """
    import torch.nn as nn                                # noqa: F401
    from clashrl.config import Config
    from clashrl.model import PolicyNet
    from clashrl.sim.env import SimMatchEnv

    cfg = Config.load(_ROOT / "config" / "config.yaml")
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    st = torch.load(ckpt, map_location="cpu", weights_only=False)
    e = SimMatchEnv(cfg, seed=5)
    o = e.reset()
    mask = np.asarray(e.actions.deployable_mask(False), dtype=bool)
    ich = int(st.get("in_ch") or 12)
    td = int(st.get("threat_dim") or e.threat_dim)

    def spread(trained):
        n = PolicyNet(ich, e.n_cards, e.n_cells, threat_dim=td)
        if trained:
            n.load_state_dict(st["model"])
        n.eval()
        with torch.no_grad():
            x = torch.from_numpy(np.asarray(o)[:, :, :ich]).float().permute(2, 0, 1).unsqueeze(0) / 255.0
            h = torch.from_numpy(np.asarray(e.hand_vec, np.float32)).unsqueeze(0)
            nx = torch.from_numpy(np.asarray(e.next_vec, np.float32)).unsqueeze(0)
            el = torch.from_numpy(np.asarray(e.elixir_vec, np.float32)).unsqueeze(0)
            t = np.asarray(e.threat_vec, np.float32)
            t = t[:td] if t.shape[0] > td else np.pad(t, (0, td - t.shape[0]))
            th = torch.from_numpy(t).unsqueeze(0)
            _z, _cq, ceq = n.forward_parts(x, h, nx, el, th)
            lg = ceq[0].numpy()[:, mask]
        return float(np.mean(np.std(lg, axis=1)))

    base = spread(False)
    return spread(True) / max(1e-9, base)


class _Drift:
    """RELATIVE-DECLINE detector: does this run still do what IT used to do?

    Absolute thresholds cannot catch the failure this project actually has, because the healthy
    P(play) for the drill regime is UNKNOWN. Measured points, all real: match-only training is
    healthy at 0.92-0.99; an untrained net is 0.49; the drill-regime collapse lands at 0.107-0.151;
    and the live 8k checkpoint sits at 0.171 while failing every ACT drill (banks elixir to >=6 on
    41.7% of steps and never spends it). A band tuned to any one of those either never fires or
    fires forever -- the shipped 0.05 never-play floor sits BELOW every number in that list, so it
    would have watched the whole 8k run in silence.

    What IS well defined is the run's own trajectory. A policy that was playing and stops has
    declined against itself, and that is measurable without knowing what healthy looks like. This
    also matches the shape of the failure that has actually cost this project a run: the 40k run
    decayed GRADUALLY (ladder 33% -> 20% over ~8k episodes), it did not fall off a cliff.

    Peaks are per-run and in-memory: restarting the watchdog re-arms it, which is correct -- a peak
    carried across a trainer restart would compare two different policies.
    """

    def __init__(self, frac: float = 0.60, min_matches: int = 300, min_peak: float = 0.05,
                 window: int = 9, min_history: int = 5):
        self.frac, self.min_matches, self.min_peak = frac, min_matches, min_peak
        self.window, self.min_history = int(window), int(min_history)
        self.hist: dict = {}

    def check(self, label: str, value, matches: int):
        """One verdict string, or None. Sustain is NOT handled here -- the caller's `_streak`
        already requires two consecutive cycles before anything is posted."""
        if value is None or matches < self.min_matches:
            return None
        h = self.hist.setdefault(label, [])
        h.append(float(value))
        del h[:-self.window]
        if len(h) < self.min_history:
            return None
        # ROLLING MEDIAN, NOT A RUNNING MAX. The first version compared against the running
        # maximum, which RATCHETS: every high excursion raises the bar, so the next normal low
        # reads as a big decline. MEASURED on the live search run -- P(play) oscillated 0.093-0.359
        # and returned to its highs repeatedly, and the max-based rule fired three times on a
        # metric that was not decaying at all. A median is unmoved by the excursions.
        srt = sorted(h[:-1]) or [value]
        base = srt[len(srt) // 2]
        if base < self.min_peak or value >= self.frac * base:
            return None
        return ("%s DRIFT -- now %.3f, which is %.0f%% below this run's rolling median of %.3f "
                "over %d readings (matches=%d). Gradual decay is what killed the 40k run; it will "
                "not trip an absolute floor."
                % (label, value, 100.0 * (1.0 - value / base), base, len(h) - 1, matches))


def verdicts(h: dict, matches: int) -> list:
    """Only conditions that have actually broken a run on this project."""
    out = []
    # /!\ THE ALWAYS-PLAY PREMISE WAS DISPROVED (2026-08-27). --reset-gate's help still claims the
    # gate "COLLAPSED to always-play, P(play) 0.938 min 0.911"; re-measured on the live checkpoint
    # with a REPAIRED gate_probe (it had been raising AttributeError on every call since the
    # spatial-cell refactor, so nothing downstream of it was ever measured) the gate is 0.171 mean
    # and never exceeds 0.60 -- the collapse runs the OTHER WAY. Both absolute bands are kept
    # because each still describes a real catastrophic end state, but NEITHER is calibrated against
    # a known-healthy value, and the live failure sits in the silent gap between them. The DRIFT
    # check above is what covers that gap; do not re-tune these two without a measurement.
    if h["p_play_mean"] > 0.90 and h["p_play_min"] > 0.80:
        out.append("GATE COLLAPSED to always-play (mean %.3f, min %.3f) -- it never holds, so the "
                   "bar cannot climb and the 6-cost win conditions stay masked."
                   % (h["p_play_mean"], h["p_play_min"]))
    if h["p_play_mean"] < 0.05:
        out.append("GATE COLLAPSED to never-play (mean %.3f)." % h["p_play_mean"])
    # STRUCTURE, NOT ENTROPY. Entropy over 157 cells is far too blunt: a head carrying 719x an
    # untrained net's within-card logit spread still reads within 0.018 nats of maximum entropy, and
    # reading that as "untrained" produced a false alarm and a needless restart recommendation.
    if matches >= 4000 and h.get("cell_struct", 99.0) < 3.0:
        out.append("CELL HEAD FLAT: within-card logit spread only %.1fx an untrained net after %d "
                   "matches -- no placement is being learned." % (h.get("cell_struct", 0.0), matches))
    # The opposite failure: collapse onto a handful of cells (it once sat on 3 of 432, 79% of plays
    # on one tile). Entropy IS the right instrument for this direction -- a collapse moves it a lot.
    if matches >= 4000 and (h["cell_ent"] / max(1e-9, h["cell_ent_max"]) < 0.25
                            or h["cell_distinct"] <= 3):
        out.append("CELL HEAD COLLAPSED (%.2f of %.2f, %d distinct cells)."
                   % (h["cell_ent"], h["cell_ent_max"], h["cell_distinct"]))
    if matches >= 6000 and h["elixir_ge6"] < 0.005:
        out.append("ELIXIR NEVER REACHES 6 (%.2f%% of steps) -- X-Bow and Rocket are unplayable."
                   % (100.0 * h["elixir_ge6"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt", nargs="?", default="data/policy_ppo_drill.pt")
    ap.add_argument("--every", type=int, default=300, help="seconds between cycles")
    ap.add_argument("--quiet-min", type=int, default=25, help="stall alert after N idle minutes")
    ap.add_argument("--once", action="store_true", help="one cycle, print health, exit")
    a = ap.parse_args()

    ckpt = Path(a.ckpt)
    if not ckpt.is_absolute():
        ckpt = _ROOT / a.ckpt
    logf = _ROOT / "data" / "ppo_watchdog.log"
    last_m, last_change, alerted = -1, time.time(), set()
    # DEBOUNCE. `elixir >= 6` is a ~1% event, and at the old 640-observation sample it
    # read 1.6% one cycle and 0.0% the next -- the 0.0% fired an alert that a 1600-step
    # probe then contradicted (x_bow affordable 1.3% of steps, played 2.4% of plays).
    # A condition now has to hold on two CONSECUTIVE cycles before it is believed.
    _streak = {}
    _drift = _Drift()

    while True:
        now = datetime.now().strftime("%H:%M")
        try:
            h = health(ckpt)
            h["cell_struct"] = cell_structure(ckpt)
        except Exception as e:                           # noqa: BLE001
            print("[%s] watchdog: health probe failed: %s" % (now, type(e).__name__), flush=True)
            if a.once:
                return 1
            time.sleep(a.every)
            continue

        if h["matches"] != last_m:
            last_m, last_change = h["matches"], time.time()
        idle_min = (time.time() - last_change) / 60.0
        n_proc = _running()

        line = ("[%s] matches=%d best_wr=%.3f P(play) mean=%.3f min=%.3f max=%.3f | "
                "elixir mean=%.2f >=6 %.1f%% | cell_struct %.1fx (vs untrained) ent %.2f/%.2f "
                "distinct=%d | card_ent %.2f/%.2f | idle %.0fm procs=%s"
                % (now, h["matches"], h["best_wr"], h["p_play_mean"], h["p_play_min"],
                   h["p_play_max"], h["elixir_mean"], 100 * h["elixir_ge6"],
                   h.get("cell_struct", 0.0), h["cell_ent"], h["cell_ent_max"],
                   h["cell_distinct"], h["card_ent"], h["card_ent_max"],
                   idle_min, n_proc))
        try:
            with logf.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:                                # noqa: BLE001
            pass
        if a.once:
            print(line, flush=True)
            for v in verdicts(h, h["matches"]):
                print("  ALERT: " + v, flush=True)
            return 0

        alerts = verdicts(h, h["matches"])
        # RELATIVE DECLINE, checked every cycle so the peak keeps updating even while healthy.
        # ELIXIR>=6 IS NOT AN INDEPENDENT SIGNAL. Measured on this run,
        # corr(P(play), elixir>=6) = -0.940 -- playing more banks less, which is arithmetic, not a
        # pathology. Alerting on both turned one event into two alarms and made a healthy run look
        # doubly sick. It stays in the printed line; it is no longer a trigger.
        for _lbl, _val in (("GATE", h["p_play_mean"]),
                           ("CELL STRUCTURE", h.get("cell_struct"))):
            _d = _drift.check(_lbl, _val, h["matches"])
            if _d:
                alerts.append(_d)
        if n_proc == 0:
            alerts.append("PROCESS GONE -- no train-sim-ppo running (last matches=%d)." % h["matches"])
        elif idle_min >= a.quiet_min:
            alerts.append("STALLED -- checkpoint unchanged for %.0f minutes at matches=%d."
                          % (idle_min, h["matches"]))

        keys = {v.split("(")[0].split("--")[0].strip() for v in alerts}
        for k in list(_streak):
            if k not in keys:
                _streak.pop(k, None)                      # broke the streak -> start again
        for v in alerts:
            key = v.split("(")[0].split("--")[0].strip()
            _streak[key] = _streak.get(key, 0) + 1
            if _streak[key] < 2 and not key.startswith(("PROCESS", "STALLED")):
                continue                                  # one cycle is not evidence
            if key in alerted:
                continue                                  # one alert per condition, not per cycle
            alerted.add(key)
            msg = "**PPO watchdog** %s\n%s\n`%s`" % (now, v, line)
            print("ALERT %s | %s" % (v, line), flush=True)
            _post_discord(msg)
        if not alerts:
            alerted.clear()                               # recovered -> re-arm
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())

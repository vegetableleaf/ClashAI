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


def verdicts(h: dict, matches: int) -> list:
    """Only conditions that have actually broken a run on this project."""
    out = []
    if h["p_play_mean"] > 0.90 and h["p_play_min"] > 0.80:
        out.append("GATE COLLAPSED to always-play (mean %.3f, min %.3f) -- it never holds, so the "
                   "bar cannot climb and the 6-cost win conditions stay masked."
                   % (h["p_play_mean"], h["p_play_min"]))
    if h["p_play_mean"] < 0.05:
        out.append("GATE COLLAPSED to never-play (mean %.3f)." % h["p_play_mean"])
    frac = h["cell_ent"] / max(1e-9, h["cell_ent_max"])
    if matches >= 4000 and frac > 0.995:
        out.append("CELL HEAD PINNED at maximum entropy (%.2f of %.2f) after %d matches -- "
                   "indistinguishable from untrained, so no placement is being learned."
                   % (h["cell_ent"], h["cell_ent_max"], matches))
    if matches >= 4000 and (frac < 0.25 or h["cell_distinct"] <= 3):
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

    while True:
        now = datetime.now().strftime("%H:%M")
        try:
            h = health(ckpt)
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

        line = ("[%s] matches=%d best_wr=%.3f P(play) mean=%.3f min=%.3f max=%.3f | elixir "
                "mean=%.2f >=6 %.1f%% | cell_ent %.2f/%.2f distinct=%d | card_ent %.2f/%.2f | "
                "idle %.0fm procs=%s"
                % (now, h["matches"], h["best_wr"], h["p_play_mean"], h["p_play_min"],
                   h["p_play_max"], h["elixir_mean"], 100 * h["elixir_ge6"], h["cell_ent"],
                   h["cell_ent_max"], h["cell_distinct"], h["card_ent"], h["card_ent_max"],
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

"""L58 gate, Part 2: the current policy's OWN placements scored with geometry_reward (for w_geom calibration).

Harness = L56 tesla_probe's greedy path ("own" arm: argmax card, argmax cell of that card's own map, own-half
mask, gate at tau) on c2r_best; the env's `self.eng.deploy(0, spec, nx, ny, delay_s=...)` call (sim/env.py:3051)
is intercepted by wrapping the ENGINE INSTANCE's bound `deploy` so each accepted team-0 placement is scored with
`board_from_engine(env.eng, 0)` BEFORE the deploy. No edit to env.py. Optional Part 3 collection: at every
step with EXACTLY one enemy troop on our half, (trunk feature vector, that troop's base) pairs.

    PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L58/policy_probe.py --out ../scratchpad/gauntlet/L58/p2 --seeds 1234,5678,9012 --matches 24
"""
import sys, json, csv, collections, argparse, time
from pathlib import Path
import numpy as np, torch
_ROOT = Path("C:/Users/benpe/ClashBot/icebow")
sys.path.insert(0, str(_ROOT / "src"))
import importlib.util
_spec = importlib.util.spec_from_file_location("tesla_probe", Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L56/tesla_probe.py"))
TP = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(TP)
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl import geometry_reward as GR

GRADED = ("p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
          "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility")


def run(ckpt, matches, seed, gate_tau, rows, probe_pairs, collect_probe):
    cfg = Config.load(_ROOT / "config" / "config.yaml")
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    env = SimMatchEnv(cfg, seed=seed)
    if getattr(env, "domain_rand", None) is not None:
        env.domain_rand.enabled = False; env.domain_rand.resample()
    net, in_ch, thr_dim = TP.load(ckpt, env)
    names = [str(getattr(sp, "key", i)) for i, sp in enumerate(env.specs)]
    own = np.zeros(env.n_cells, bool); own[12 * 18:] = True

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > in_ch: x = x[:, :, :in_ch]
        elif x.shape[2] < in_ch:
            x = np.concatenate([x, np.zeros((x.shape[0], x.shape[1], in_ch - x.shape[2]), dtype=x.dtype)], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0

    def thr_t(v):
        t = np.asarray(v, np.float32)
        return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim else np.pad(t, (0, thr_dim - t.shape[0])))

    state = {"match": 0, "n_in_match": collections.Counter()}

    def install_hook(eng):
        if getattr(eng.deploy, "_l58_hook", False):
            return                      # the engine persists across env.reset(): never double-wrap
        orig = eng.deploy

        def deploy(team, spec, x, y, *a, **k):
            sc = None
            if team == 0:
                board = GR.board_from_engine(eng, 0)                       # BEFORE the deploy
                sc = GR.score_placement(board, GR.placement_from_spec(
                    spec, x, y, siege_sight=eng.siege_sight, tower_range=eng.tower_range, king_range=eng.king_range))
            ok = orig(team, spec, x, y, *a, **k)
            if ok and sc is not None:
                rec = {"seed": seed, "match": state["match"], "t": round(float(eng.t), 2), "card": str(spec.key),
                       "base": str(spec.base), "kind": str(spec.kind), "tx": round(x * 18.0, 2), "ty": round(y * 32.0, 2),
                       "threat": sc["threat_base"], "d_threat": round(float(sc["d_threat"]), 2),
                       "n_enemy_troops": sum(1 for u in eng.units if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"),
                       "bb_detected": sc["bridge_block_detected"], "bb_case": sc["bridge_block_case"]}
                for kk in GRADED:
                    rec[kk] = round(float(sc[kk]), 4)
                rec["sum"] = round(sum(float(sc[kk]) for kk in GRADED), 4)
                rows.append(rec); state["n_in_match"][str(spec.base)] += 1
            return ok
        deploy._l58_hook = True
        eng.deploy = deploy

    obs = env.reset(); install_hook(env.eng); done_n = 0
    per_match_counts = []
    with torch.no_grad():
        while done_n < matches:
            xb = obs_t(obs)[None]; hb = torch.from_numpy(np.asarray(env.hand_vec, np.float32))[None]
            nb = torch.from_numpy(np.asarray(env.next_vec, np.float32))[None]
            eb = torch.from_numpy(np.asarray(env.elixir_vec, np.float32))[None]; tb = thr_t(env.threat_vec)[None]
            cq, ceq, gq = net(xb, hb, nb, eb, tb)
            if collect_probe:
                enemies_here = [u for u in env.eng.units if u.team == 1 and u.hp > 0 and u.spec.kind == "troop" and u.y >= 0.5]
                if len(enemies_here) == 1:
                    z = net.policy.forward_parts(xb, hb, nb, eb, tb)[0][0].numpy().astype(np.float32)
                    probe_pairs.append((z, str(enemies_here[0].spec.base), seed, done_n))
            elx = float(env.eng.elixir[0])
            hand = [c for c in env._hand_ids() if 0 <= c < len(env.specs) and elx >= env.specs[c].elixir]
            act = (0, 0, 0)
            if hand:
                pc = torch.softmax(cq, 1)[0].numpy()
                pick = int(max(hand, key=lambda c: pc[c]))
                p_play = float(torch.sigmoid(gq[0, 1] - gq[0, 0]))
                if p_play > gate_tau:
                    m = ceq[0, pick].numpy().copy(); m[~own] = -1e9; cell = int(m.argmax())
                    act = (1, pick, cell)
            obs, _r, d, _i = env.step(act)
            if d:
                per_match_counts.append({"seed": seed, "match": done_n, **dict(state["n_in_match"]), "t": round(float(env.eng.t), 1)})
                done_n += 1; state["match"] = done_n; state["n_in_match"] = collections.Counter()
                obs = env.reset(); install_hook(env.eng)      # reset may rebuild the engine
    return per_match_counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=str(_ROOT / "data/bench/c2r_best_36k_backup.pt"))
    ap.add_argument("--out", required=True); ap.add_argument("--matches", type=int, default=24)
    ap.add_argument("--seeds", default="1234,5678,9012"); ap.add_argument("--tau", type=float, default=0.25)
    ap.add_argument("--probe", action="store_true", help="also collect Part 3 (trunk feature, deepest-enemy base) pairs")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, pairs, counts = [], [], []
    t0 = time.time()
    for s in [int(x) for x in a.seeds.split(",")]:
        np.random.seed(s); torch.manual_seed(s)
        counts += run(a.ckpt, a.matches, s, a.tau, rows, pairs, a.probe)
        print(f"seed {s}: placements so far {len(rows)}, probe pairs {len(pairs)}, {time.time()-t0:.0f}s", flush=True)
    keys = list(rows[0].keys())
    with (out / "policy_scores.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=keys); w.writeheader(); w.writerows(rows)
    ck = sorted({k for c in counts for k in c})
    with (out / "policy_match_counts.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=ck); w.writeheader(); w.writerows(counts)
    if pairs:
        np.savez_compressed(out / "probe_pairs.npz", z=np.stack([p[0] for p in pairs]),
                            base=np.array([p[1] for p in pairs]), seed=np.array([p[2] for p in pairs]), match=np.array([p[3] for p in pairs]))
    print("done", len(rows), "placements", len(pairs), "probe pairs", f"{time.time()-t0:.0f}s")

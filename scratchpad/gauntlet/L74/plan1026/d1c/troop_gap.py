"""D1-C: is the tower-troop crown gap (faults.py summary: crowns match 67.0% troop vs 73.3% Princess, replays where every
input ran) the engine or the player population? Deck-matched comparison on the same 20k grades.

    python troop_gap.py OUT DATA             # OUT = faults.py run dir, DATA = HF data dir (pyarrow on PYTHONPATH)
    python troop_gap.py sides OUT            # within-replay troop-side vs Princess-side errors (faults.py --tags run)

Strata = the exact 8-card deck (card keys incl. -ev1 / -hero) of the troop side; a Princess replay joins a stratum when
either of its sides plays that deck. Per stratum with both kinds: the troop and Princess crowns-match rates; the summary
is the Mantel-Haenszel risk difference (stratum weight n_t n_p / (n_t + n_p)) with a replay bootstrap 95% interval
(strata resampled). Also: the same with the opponent's deck held fixed instead, and the raw gap inside matches of the
same length class (regulation / overtime) and the same RNG-card presence (G0's cards that draw after the deal).
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

TROOP = {"dagger-duchess", "cannoneer", "royal-chef"}
RNG = {"arrows", "princess", "hunter", "skeleton-king"}   # G0 (extract.DRAWERS): the Ladder cards that draw after the deal


def load(out: Path, data: Path) -> list[dict]:
    import pyarrow.parquet as pq
    gs = {}
    for p in sorted((out / "grades").glob("*.jsonl")):
        for line in open(p):
            g = json.loads(line)
            if "towers_match" in g:                       # every input ran (faults.py summary's population)
                gs[g["tag"]] = g
    rows = []
    for sid, lo, hi in json.loads((out / "sample.json").read_text()):
        part = sid.rsplit("_", 1)[0]
        for r in pq.read_table(data / "replays" / f"{part}.parquet").slice(lo, hi - lo).to_pylist():
            g = gs.get(r["replay_tag"])
            if g is None:
                continue
            b = json.loads(r["payload_json"])["battle"]
            decks = [tuple(sorted(c["card_key"] for c in b[k]["players"][0]["deck"])) for k in ("team", "opponent")]
            rows.append(dict(tag=g["tag"], towers=g["towers"], decks=decks, y=bool(g["crowns_match"]),
                             ot=g["end_tick"] > 3600 + 40, rng=any(c.split("-ev1")[0].split("-hero")[0] in RNG
                                                                  for d in decks for c in d)))
    return rows


def mh(strata: dict) -> float | None:
    num = den = 0.0
    for t, p in strata.values():
        if t and p:
            w = len(t) * len(p) / (len(t) + len(p))
            num += w * (sum(t) / len(t) - sum(p) / len(p))
            den += w
    return num / den if den else None


def stratify(rows: list[dict], own: bool) -> dict:
    """deck -> ([troop y], [princess y]); own: the troop side's deck, else its opponent's."""
    s = defaultdict(lambda: ([], []))
    for r in rows:
        tr = [i for i in (0, 1) if r["towers"][i] in TROOP]
        if len(tr) == 1:
            i = tr[0] if own else 1 - tr[0]
            s[r["decks"][i]][0].append(r["y"])
        elif not tr:
            for d in set(r["decks"]):
                s[d][1].append(r["y"])
    return {k: v for k, v in s.items() if v[0] and v[1]}


def boot(strata: dict, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng, keys, out = random.Random(seed), list(strata), []
    for _ in range(n):
        pick = {i: strata[k] for i, k in enumerate(rng.choice(keys) for _ in keys)}
        v = mh(pick)
        if v is not None:
            out.append(v)
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]


def rate(ys):
    return round(sum(ys) / len(ys), 4) if ys else None


def main(out: Path, data: Path) -> dict:
    rows = load(out, data)
    troop = [r for r in rows if any(t in TROOP for t in r["towers"])]
    prin = [r for r in rows if not any(t in TROOP for t in r["towers"])]
    res = dict(n_troop=len(troop), n_princess=len(prin), raw=dict(troop=rate([r["y"] for r in troop]),
                                                                  princess=rate([r["y"] for r in prin])))
    for name, own in (("troop_side_deck", True), ("opponent_deck", False)):
        s = stratify(rows, own)
        res[name] = dict(strata=len(s), troop_n=sum(len(t) for t, _ in s.values()),
                         princess_n=sum(len(p) for _, p in s.values()), mh_diff=round(mh(s), 4),
                         ci95=[round(x, 4) for x in boot(s)])
    cells = {}
    for ot in (False, True):
        for rg in (False, True):
            t = [r["y"] for r in troop if r["ot"] == ot and r["rng"] == rg]
            p = [r["y"] for r in prin if r["ot"] == ot and r["rng"] == rg]
            cells[f"ot={int(ot)} rng={int(rg)}"] = dict(troop=[len(t), rate(t)], princess=[len(p), rate(p)])
    res["by_length_and_rng"] = cells
    return res


def sides(out: Path) -> dict:
    """Within-replay: in a match with one troop side T, is crforge wrong more often on T's towers (the crowns T's
    opponent took, T's end tower hp) than on the Princess side's? Same players, same match: the population cancels.
    Princess-only control: the same per side (team / opponent)."""
    gs = [json.loads(line) for p in sorted((out / "grades").glob("*.jsonl")) for line in open(p)]
    gs = [g for g in gs if "tower_hp" in g]

    def side_err(g, s):          # (crowns taken FROM side s wrong, |hp error| summed over side s's towers)
        o = str(1 - s)
        hp, hf = g["tower_hp"][s], g["hf_towers"][s]
        return (g["crowns"][o] != g["hf_crowns"][o],
                abs(hp[0] - hf[0]) + sum(abs(a - b) for a, b in zip(sorted(hp[1:]), sorted(hf[1:]))))
    pairs, ctrl = [], []
    for g in gs:
        tr = [i for i in (0, 1) if g["towers"][i] in TROOP]
        if len(tr) == 1:
            pairs.append((g["towers"][tr[0]], side_err(g, tr[0]), side_err(g, 1 - tr[0])))
        elif not tr:
            ctrl.append((side_err(g, 0), side_err(g, 1)))
    res = dict(n_troop_one_side=len(pairs), n_princess=len(ctrl))
    for name in ["all"] + sorted(TROOP):
        sel = [p for p in pairs if name == "all" or p[0] == name]
        if not sel:
            continue
        b = sum(t[0] and not q[0] for _, t, q in sel)     # wrong on the troop towers only
        c = sum(q[0] and not t[0] for _, t, q in sel)     # wrong on the princess towers only
        res[name] = dict(n=len(sel), crowns_wrong_on_troop_towers=sum(t[0] for _, t, _ in sel),
                         crowns_wrong_on_princess_towers=sum(q[0] for _, _, q in sel), discordant=[b, c],
                         mcnemar_chi2=round((b - c) ** 2 / (b + c), 2) if b + c else None,
                         mean_hp_err_troop_towers=round(sum(t[1] for _, t, _ in sel) / len(sel), 1),
                         mean_hp_err_princess_towers=round(sum(q[1] for _, _, q in sel) / len(sel), 1))
    res["princess_control"] = dict(crowns_wrong_side0=sum(a[0] for a, _ in ctrl), crowns_wrong_side1=sum(b[0] for _, b in ctrl),
                                   mean_hp_err_side0=round(sum(a[1] for a, _ in ctrl) / max(len(ctrl), 1), 1),
                                   mean_hp_err_side1=round(sum(b[1] for _, b in ctrl) / max(len(ctrl), 1), 1))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "sides":
        print(json.dumps(sides(Path(sys.argv[2])), indent=1))
    else:
        print(json.dumps(main(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))

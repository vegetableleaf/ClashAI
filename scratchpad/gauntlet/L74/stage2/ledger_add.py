"""Append knob-ledger rows (stage2/ledger.jsonl) for every 'eval' line of a pod queue, BEFORE the runs' results are read.
    python ledger_add.py POD QUEUE_FILE [QUEUE_FILE...]   (POD = P5 | P6 | ...; rows already present by look name are skipped)"""
import hashlib, json, os, sys, time
H = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(H, "ledger.jsonl")
sha = lambda p: hashlib.sha256(open(os.path.join(H, p), "rb").read()).hexdigest()[:12]
have = {json.loads(l)["look"] for l in open(L)} if os.path.exists(L) else set()
pod = sys.argv[1]
with open(L, "a", newline="\n") as f:
    for q in sys.argv[2:]:
        for line in open(q):
            w = line.split()
            if not w or w[0] != "eval" or w[1] in have: continue
            n, cb, ck, pool, rest = w[1], w[2], w[3], w[4], " ".join(w[5:])
            mark = "CXXXVIII" if "cue_u250" in ck else "CXXIV"
            cand, cki = (("s2_hog_" + n.split("_")[1], n.split("_")[2]) if n.startswith("C_") else (n.rsplit("_", 1)[0], "-"))
            f.write(json.dumps(dict(look=n, candidate=cand, checkpoint=cki, band="13k" if mark == "CXXXVIII" else "12k", mark=mark,
                                    levels="levels13k.json" if "cb_13k" in cb else "live_levels.json", games=960, seeds=[741200, 742000],
                                    pool=os.path.basename(pool), opp_flags=rest or "E4 T .1 (gap default)",
                                    gate="hog" if n.startswith("C_") else "full", gate_s2_sha=sha("gate/gate_s2.py"),
                                    frozen_sha=sha("gate/FROZEN.txt"), pod=pod, code="cb_tt = HEAD 7c93f19 (SIM files) + overlay " + sha("pod/s2_manifest.sha"),
                                    written=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), result_read=False)) + "\n")
            have.add(n)
print(len(have), "looks in the ledger")

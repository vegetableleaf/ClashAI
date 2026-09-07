p = "scratchpad/gauntlet/L65/_matchcount.py"
s = open(p, encoding="utf-8").read()
old = """                if prev is None:
                    blocks.append([round(t, 1), round(t, 1)])
                else:
                    d = float(np.abs(m.astype(np.int16) - prev.astype(np.int16)).mean())
                    jitter.append(d)
                    if d > 0.12:                    # well above within-match jitter (reported below)
                        blocks.append([round(t, 1), round(t, 1)])
                    else:
                        blocks[-1][1] = round(t, 1)
                prev, prev_t = m, t"""
new = """                if prev is None:
                    blocks.append([round(t, 1), round(t, 1)]); ref, pend = m, 0
                else:
                    # compare against the BLOCK's reference mask, not the previous sample: a name is
                    # static for minutes, so within-match diff is 0.000 (measured p50) and any sustained
                    # non-zero diff is a new opponent. Requiring 2 consecutive samples rejects the
                    # transient overlays (deploy rings, damage flashes) that a single-sample rule would
                    # count as matches. First cut used d > 0.12 against the PREVIOUS sample and found
                    # nothing: real name changes measured only ~0.09 (jitter_p99), under the threshold.
                    d = float(np.abs(m.astype(np.int16) - ref.astype(np.int16)).mean())
                    jitter.append(d)
                    if d > 0.02:
                        pend += 1
                        if pend >= 2:
                            blocks.append([round(t, 1), round(t, 1)]); ref, pend = m, 0
                    else:
                        pend = 0
                        blocks[-1][1] = round(t, 1)
                prev, prev_t = m, t"""
assert s.count(old) == 1
s = s.replace(old, new)
s = s.replace("    prev, prev_t, blocks, jitter = None, None, [], []",
              "    prev, prev_t, blocks, jitter = None, None, [], []\n    ref, pend = None, 0")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")

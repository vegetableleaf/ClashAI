import statistics as st, sys
for tag, p in (("pre ", sys.argv[1]), ("post", sys.argv[2])):
    v = sorted(float(x) for x in open(p) if x.strip())
    print(tag, len(v), "confirmed; latency_s median %.2f p90 %.2f p99 %.2f max %.2f" % (st.median(v), v[int(.9*len(v))], v[int(.99*len(v))], v[-1]))

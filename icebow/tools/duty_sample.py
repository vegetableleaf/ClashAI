"""Duty-cycle sampler for the LIVE real run: parent CPU% vs summed worker CPU%, 1 Hz.

Read-only (psutil counters). Prints one line per second and a summary. Used to see how much of
the wall clock the 12 workers sit idle -- i.e. how much of each cycle is parent-only work.
"""
import sys, time
import psutil

MAIN = int(sys.argv[1]); SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 240
main = psutil.Process(MAIN)
workers = [c for c in main.children() if "multiprocessing" in " ".join(c.cmdline())]
print("main=%d workers=%d cores=%d" % (MAIN, len(workers), psutil.cpu_count()), flush=True)
main.cpu_percent(None); [w.cpu_percent(None) for w in workers]
rows = []
t_end = time.time() + SECS
while time.time() < t_end:
    time.sleep(1.0)
    m = main.cpu_percent(None); ws = [w.cpu_percent(None) for w in workers]
    tot = psutil.cpu_percent(None)
    rows.append((m, sum(ws), tot))
    print("%s main %6.0f%%  workers %6.0f%% (busy %2d/%d)  box %4.0f%%"
          % (time.strftime("%H:%M:%S"), m, sum(ws), sum(1 for x in ws if x > 5), len(ws), tot), flush=True)
n = len(rows)
idle = sum(1 for _, w, _ in rows if w < 25)          # workers collectively under a quarter core
print("SUMMARY %ds: workers idle (<25%% summed) %d/%d s = %.0f%% of wall | mean main %.0f%% | mean workers %.0f%% | mean box %.0f%%"
      % (n, idle, n, 100.0 * idle / max(1, n), sum(r[0] for r in rows) / n, sum(r[1] for r in rows) / n,
         sum(r[2] for r in rows) / n), flush=True)

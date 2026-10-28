"""memwatch.py OUT.tsv ROOT_PID [SECONDS] [GUARD_GB] [INTERVAL_S] -- sample the pod container's memory while a run is alive.

Every INTERVAL_S (default 5): unix ts, cgroup memory.current (MB), memory.events oom / oom_kill, cgroup anon / file / shmem
(MB), /dev/shm used (MB), the number of processes in ROOT_PID's tree, their summed RSS (MB), the main process's RSS and the
largest child RSS (MB). Stops when ROOT_PID is gone or after SECONDS. GUARD_GB (default 100): when memory.current exceeds it, the
sampler SIGKILLs ROOT_PID's whole tree (exact PIDs of the run; nothing else) and logs GUARD -- so a repro of an out-of-memory
death can never take the shared cgroup (125 GB, other workers' jobs) down with it."""
import os
import signal
import subprocess
import sys
import time

out, root = sys.argv[1], int(sys.argv[2])
secs = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
guard = float(sys.argv[4]) * 1e9 if len(sys.argv) > 4 else 100e9
every = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0


def cg(name):
    try:
        return open("/sys/fs/cgroup/" + name).read()
    except OSError:
        return ""


def tree():
    rows = {}
    for l in subprocess.run(["ps", "-eo", "pid,ppid,rss"], capture_output=True, text=True).stdout.splitlines()[1:]:
        p = l.split()
        rows[int(p[0])] = (int(p[1]), int(p[2]) / 1024.0)
    kids, todo = {root}, [root]
    while todo:
        x = todo.pop()
        for pid, (pp, _) in rows.items():
            if pp == x and pid not in kids:
                kids.add(pid)
                todo.append(pid)
    return {p: rows[p][1] for p in kids if p in rows}


t_end = time.time() + secs
with open(out, "a") as fh:
    fh.write("ts\tcgroup_MB\toom\toom_kill\tanon_MB\tfile_MB\tshmem_MB\tdevshm_MB\tn_procs\tsum_rss_MB\tmain_rss_MB\tmax_child_MB\tnote\n")
    while time.time() < t_end:
        ev = dict(l.split() for l in cg("memory.events").splitlines() if l.strip())
        st = dict(l.split() for l in cg("memory.stat").splitlines() if l.strip())
        cur = int(cg("memory.current") or 0)
        t = tree()
        if root not in t:
            fh.write("%d\t\t\t\t\t\t\t\t0\t\t\t\tROOT_GONE\n" % time.time())
            break
        try:
            sv = os.statvfs("/dev/shm")
            shm = (sv.f_blocks - sv.f_bfree) * sv.f_frsize / 1e6
        except OSError:
            shm = -1
        kids = [v for p, v in t.items() if p != root]
        note = ""
        if cur > guard:
            note = "GUARD_KILL"
            for p in sorted(t, reverse=True):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
        fh.write("%d\t%.0f\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%d\t%.0f\t%.0f\t%.0f\t%s\n" % (
            time.time(), cur / 1e6, ev.get("oom"), ev.get("oom_kill"), int(st.get("anon", 0)) / 1e6, int(st.get("file", 0)) / 1e6,
            int(st.get("shmem", 0)) / 1e6, shm, len(t), sum(t.values()), t[root], max(kids or [0]), note))
        fh.flush()
        if note:
            break
        time.sleep(every)

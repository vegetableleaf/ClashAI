"""D2-G stack sampler (test harness, not pipeline code). Started by sitecustomize when D2_SAMPLE=<dir>: a daemon thread
samples the MAIN thread's Python stack every 10 ms and, every 60 s, writes <dir>/<pid>.json = {samples, inclusive: {func:
n}, leaf: {func: n}} (func = "file:function", file relative to pipeline/ or the basename). A JNI call (crforge) shows as
its Python caller, so crforge engine time is inside crforge_core.step / state."""
import json
import os
import sys
import threading
import time
from collections import Counter


def _name(code):
    f = code.co_filename
    i = f.find('/pipeline/')
    return (f[i + 10:] if i >= 0 else os.path.basename(f)) + ':' + code.co_name


def start(out):
    os.makedirs(out, exist_ok=True)
    main = threading.main_thread().ident
    inc, leaf, n = Counter(), Counter(), [0]

    def run():
        last = time.monotonic()
        while True:
            time.sleep(0.01)
            fr = sys._current_frames().get(main)
            if fr is not None:
                n[0] += 1
                leaf[_name(fr.f_code)] += 1
                seen = set()
                while fr is not None:
                    seen.add(_name(fr.f_code))
                    fr = fr.f_back
                inc.update(seen)
            if time.monotonic() - last > 60:
                last = time.monotonic()
                tmp = f'{out}/{os.getpid()}.json.tmp'
                with open(tmp, 'w') as fh:
                    json.dump({'samples': n[0], 'inclusive': dict(inc.most_common(150)),
                               'leaf': dict(leaf.most_common(80))}, fh)
                os.replace(tmp, f'{out}/{os.getpid()}.json')

    threading.Thread(target=run, daemon=True, name='d2sample').start()

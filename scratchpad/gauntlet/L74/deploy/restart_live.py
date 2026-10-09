"""Apply a new LIVE_OPTIONS between matches: STOP file -> wait for the supervisor to end -> start it again.
Never kills anything. Usage: python restart_live.py "<why>"   (posts start/finish to Discord)."""
import subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ab'))
from ab_watch import BASH, L, PY, REPO, live_running, stop_and_wait   # noqa: E402


def say(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    m = Path(__file__).with_name('_msg.txt')
    m.write_text('ClashAI live: ' + msg, encoding='utf-8')
    subprocess.run([PY, str(REPO / 'scratchpad/gauntlet/L69/discord/post.py'), str(m)], timeout=60, capture_output=True)


why = sys.argv[1] if len(sys.argv) > 1 else 'new live options'
say(f'restarting live between matches to apply: {why}')
if not stop_and_wait():
    say('live did not stop within 30 min -- restart abandoned, STOP left in place'); sys.exit(1)
(L / 'STOP').unlink(missing_ok=True)
subprocess.Popen([BASH, str(L / 'run_live.sh')], cwd=str(REPO), env={k: v for k, v in __import__("os").environ.items() if k != "LIVE_ARGS"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
time.sleep(90)
say(f"live restarted ({why}); live processes now: {live_running()}")

# Extract frames where the hero Ice Wizard is on the board, from a RAW `run.py record` session (no drawn boxes),
# timed off the `PLAY ice_wizard ... wall=HH:MM:SS.mmm` lines that `run.py play` prints to stdout.
# Label Studio guide step (b): scratchpad/gauntlet/L67/label_studio_hero_guide.md
#
# usage (from icebow/):
#   .\.venv\Scripts\python.exe ..\scratchpad\gauntlet\L67\hero_frames.py data\sessions\<stamp> <play stdout log> [out_dir]
# out_dir defaults to data\detect\images\to_label_hero (the folder `pre-annotate --subdir to_label_hero` reads).
import sys, re, json, datetime as dt
from pathlib import Path
import cv2
sys.path.insert(0, "src")
from clashrl.detect import _read_at           # nearest recorded frame to a capture time (detect.py:71)

if len(sys.argv) < 3:
    sys.exit("usage: hero_frames.py <session dir> <play stdout log> [out_dir]")
session, play_log = Path(sys.argv[1]), Path(sys.argv[2])
out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/detect/images/to_label_hero")
out.mkdir(parents=True, exist_ok=True)
OFFSETS = [0.5, 1.0, 2.0, 3.0, 4.5, 6.0, 8.0, 10.0, 12.0]   # deploy circle, walking/fighting, button, snowman

raw = play_log.read_bytes()                   # Tee-Object / '>' in PS 5.1 writes UTF-16 (run17's log starts FF FE)
text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
day = dt.datetime.strptime(session.name[:8], "%Y%m%d").date()
cap = cv2.VideoCapture(str(session / "video.mp4"))
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
t_end = meta["frame_times"][-1]
seen, n, plays, outside = set(), 0, 0, 0
for m in re.finditer(r"\] (?:STALL-)?PLAY ice_wizard .*?wall=(\d\d):(\d\d):(\d\d)\.(\d{3})", text):
    plays += 1
    h, mi, s, ms = map(int, m.groups())
    t_play = dt.datetime.combine(day, dt.time(h, mi, s, ms * 1000)).timestamp()   # local wall -> epoch
    if not (0 <= t_play - meta["start_time"] <= t_end):
        outside += 1                              # this play happened while the recorder was not running
        continue
    for off in OFFSETS:
        t = t_play + off - meta["start_time"]                                     # seconds into the video
        if t < 0 or t > t_end:
            continue
        frame, fi = _read_at(cap, meta["frame_times"], t, total)
        if frame is None or fi in seen:
            continue
        seen.add(fi)
        cv2.imwrite(str(out / f"hero_{session.name}_f{fi:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        n += 1
print(f"{plays} hero plays in the log, {outside} outside this recording, {n} frames -> {out}")

#!/bin/bash
# One command -> one vertical MP4 of the current model playing a real pro opponent, for the daily post.
#
#   bash pipeline/daily_clip.sh icebow icebow/data/pipeline/s1_icebow_v4lat_s1.pt "icebow S1 v4  19.8% top-1"
#
# Picks the first match of the fixed seed-0 pool, so clips from different days are the SAME opening and
# the difference you see is the model, not the draw. Change --seed for a different matchup.
set -e
cd "$(dirname "$0")/.."
DECK=${1:?deck}
CKPT=${2:?checkpoint}
LABEL=${3:-"$DECK"}
SEED=${4:-0}
PORT=${5:-37031}
OUT=scratchpad/clips/$(date -u +%Y%m%d)
mkdir -p "$OUT"

.venv/Scripts/python.exe pipeline/engine_play.py "$DECK" --ckpt "$CKPT" --port "$PORT" \
    --matches 1 --seed "$SEED" --gate sample --record-every 2 --out "$OUT" > "$OUT/play.out" 2>&1
tail -1 "$OUT/play.out"

FR=$(ls "$OUT"/frames_*.json | head -1)
.venv/Scripts/python.exe pipeline/match_video.py "$FR" -o "$OUT/clip.mp4" --speed 2 --label "$LABEL"
# the frames file is ~7 MB a match and is only an intermediate -- the mp4 is the artifact
rm -f "$FR"
echo "clip: $OUT/clip.mp4"

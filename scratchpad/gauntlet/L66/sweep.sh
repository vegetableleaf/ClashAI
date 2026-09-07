#!/bin/bash
# Stage 1 of the mining pipeline: classify channel videos by deck, cheaply, in parallel.
#
# One ~180 s slice per video -- one match. That length is not a guess: known-icebow footage cut to 20 s
# scores 0.558 (reads NEGATIVE) and cut to 180 s scores 0.625, while sampling more FRAMES from the same
# 180 s changes nothing (0.625 either way, §5cs.82 E). An eight-card deck has to cycle before the hand
# can show it, and that takes a match, not a moment.
#
# Downloads only; profiling is a separate pass so a failed download never costs a re-profile and vice
# versa. 4 concurrent fetches -- enough to hide per-video latency, few enough to stay polite.
#
# usage: sweep.sh <ids_file> <out_dir> [parallel]
#        ids_file: "<video_id>\t<duration_s>" per line, UNIX line endings (a \r turns $((dur/2)) into an
#                  arithmetic syntax error -- that is how the first attempt died)
set -u
IDS=${1:?ids file}
OUT=${2:?out dir}
P=${3:-4}
mkdir -p "$OUT"
cd /c/Users/benpe/ClashBot
export PATH="/c/Users/benpe/tools/bin:$PATH"

fetch() {
  id=$1; dur=$2; out=$3
  ls "$out/$id".* >/dev/null 2>&1 && return 0          # resumable: already have it
  mid=$((dur / 2))
  s=$(printf "%02d:%02d:%02d" $((mid / 3600)) $(((mid % 3600) / 60)) $((mid % 60)))
  e=$(printf "%02d:%02d:%02d" $(((mid + 180) / 3600)) $((((mid + 180) % 3600) / 60)) $(((mid + 180) % 60)))
  timeout 600 ./.venv/Scripts/yt-dlp.exe -q --no-warnings -f "bv*[height<=1280]" \
    --download-sections "*$s-$e" --force-keyframes-at-cuts \
    -o "$out/$id.%(ext)s" "https://www.youtube.com/watch?v=$id" >/dev/null 2>&1
  echo "$id $?"
}
export -f fetch

tr -d '\r' < "$IDS" | awk -v o="$OUT" '{print $1, $2, o}' \
  | xargs -P "$P" -n 3 bash -c 'fetch "$0" "$1" "$2"'
echo "SWEEP_DONE $(ls "$OUT" | grep -vc part)"

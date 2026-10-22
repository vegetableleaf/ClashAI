#!/bin/bash
# W18 job runner (pod-local): runs the lines of /workspace/w18/jobs_STREAM.txt in order, one at a time, each once (marker
# /workspace/w18/done/<md5 of the line>); re-reads the file after every job, so jobs are queued by APPENDING lines (never
# rewrite this script or a running job's script: bash reads them as it goes). A line 'END' stops the stream; an empty queue
# waits 60 s and re-reads (a stream never exits on its own, so a queued job always starts at once).
#     setsid nohup bash /workspace/w18/w18_runner.sh A > /dev/null 2>&1 < /dev/null &
set -uo pipefail
ST=$1; W=/workspace/w18; Q=$W/jobs_$ST.txt; LOG=$W/runner_$ST.log
mkdir -p $W/done; touch $Q
log() { echo "$(date -u +%FT%TZ) [$ST] $*" >> $LOG; }
log "runner start pid $$"
while true; do
  ran=0
  while IFS= read -r line; do
    [ -z "$line" ] || [ "${line:0:1}" = "#" ] && continue
    [ "$line" = END ] && { log END; exit 0; }
    h=$(echo -n "$line" | md5sum | cut -c1-16)
    [ -f $W/done/$h ] && continue
    log "START $h $line"
    t0=$(date +%s)
    bash -c "$line" >> $W/job_$h.log 2>&1
    rc=$?
    echo "$rc $line" > $W/done/$h
    log "DONE $h rc $rc $(( ($(date +%s) - t0) / 60 )) min"
    ran=1
    break                                   # re-read the queue file after every job
  done < $Q
  [ $ran = 0 ] && sleep 60
done

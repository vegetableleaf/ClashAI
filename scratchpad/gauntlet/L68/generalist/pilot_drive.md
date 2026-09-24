# Generalist pilot drive -- runbook (L68, launched 2026-09-24 14:53:39 UTC)

Slice: top-100 base decks x first 200 sides = 20,000 sides / 17,857 replays (`pilot_select.py` -> `pilot_tags.json`).
Converted with `tools/hf_to_crawl.py --tags-file pilot_tags.json --chunk 250` -> 17,853 replays (4 had no plays) in
72 chunks (`pilot/crawl/chunk_000..071`). Chunks exist because `replay_drive.load_battle` re-reads the whole crawl
CSV for every tag. Known loss: 6,438 replays (36%) contain evo Elite Barbarians (26000043), which the sandbox cannot
build (`pilot/evo_loss.json`, VM `precheck.json`). They fail in ~0 s, which leaves at most 12,864 drivable top-100 sides.

VM: `ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@136.111.202.176`. Everything lives in
`~/cb/scratchpad/gauntlet/ext/corpus_gen_pilot/`: `crawl/`, `run_pilot.sh`, `s0..s3/` (replay_*.json + summary.jsonl
+ aggregate.json of the LAST chunk only), `s0..s3.log`, `sN.done` per slot, `DONE` when all four finish.
Slot s = port 37031+s drives chunk_k with k % 4 == s (`--record-every 20 --record-plays --level 11`, default
`--determinism-every 10`).

## Check progress
    ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@136.111.202.176 \
      'cd ~/cb && python3 scratchpad/gauntlet/ext/corpus_gen_pilot/progress.py; ls scratchpad/gauntlet/ext/corpus_gen_pilot/*done* scratchpad/gauntlet/ext/corpus_gen_pilot/DONE 2>/dev/null'
Prints ok/failed per slot, failure reasons, replays/hour and hours left. `tail -n 3 .../sN.log` shows the live line.

## Resume after a crash or a reboot
Slots do not survive a VM or AVD restart. Boot the AVD, `adb root`, then start the slots ONE AT A TIME (two traps below), then re-run the launcher. Tags that already have a
summary line are skipped:
    source ~/sb/runtime.env.sh; export PATH=$ANDROID_SDK_ROOT/platform-tools:$PATH
    nohup setsid $CR_SANDBOX_EMULATOR -avd royale_worker_api31 -port 5554 -no-window -no-audio -no-boot-anim -no-snapshot \
      -gpu swiftshader_indirect -accel on -memory 4096 -cores 4 > ~/emulator_pilot.log 2>&1 < /dev/null &
    # wait for: adb -s emulator-5554 shell getprop sys.boot_completed == 1  (~35 s)
    adb -s emulator-5554 root
    cd ~/sb/cr-native-sandbox; for s in 0 1 2 3; do bash scripts/start_direct_service.sh --serial emulator-5554 --port $((37031+s)) --slot $s | head -c 90; echo; done
    cd ~/cb/scratchpad/gauntlet/ext/corpus_gen_pilot && nohup setsid bash run_pilot.sh > run.log 2>&1 < /dev/null &
Traps seen on 2026-09-24:
- without `adb root`, the guest `tar -xf` fails with `can't remove ... Permission denied`, because the earlier session
  extracted the assets as root.
- starting slots in PARALLEL races on the shared host-side `artifacts/runtime-assets.tar`. That caused the old
  `svc_0/2/3.log` errors ("tar: tilemaps/tilemap.csv: Cannot stat" / "Remote hash mismatch").
- Launch from ssh with the job's stdout redirected. Otherwise the ssh session hangs; closing it is safe once the job
  has been started with setsid.

## Stop
    pkill -f run_pilot.sh; pkill -f replay_batch.py
This kills only the drive. The engine slots and the AVD keep running, and the summary lines already written are kept.
To stop the slots too:
    source ~/sb/runtime.env.sh; cd ~/sb/cr-native-sandbox
    for s in 0 1 2 3; do bash scripts/stop_direct_service.sh --serial emulator-5554 --port $((37031+s)) --slot $s; done

## Fetch results to the box (NOT run yet; expected ~3.5 GB of JSON, ~0.3 MB per ok replay)
From Git Bash on the box. rsync is not in Git Bash, so pipe tar over ssh. The output compresses well, so gzip on the VM side:
    mkdir -p /c/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_gen_pilot
    ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@136.111.202.176 \
      'cd ~/cb/scratchpad/gauntlet/ext && tar -cf - corpus_gen_pilot/s0 corpus_gen_pilot/s1 corpus_gen_pilot/s2 corpus_gen_pilot/s3 corpus_gen_pilot/*.log corpus_gen_pilot/precheck.json | gzip -1' \
      | tar -xzf - -C /c/Users/benpe/ClashBot/scratchpad/gauntlet/ext/
(The crawl is already local at `L68/generalist/pilot/crawl`.) After fetching, check that the replay_*.json count equals
the number of ok rows in the four summary.jsonl files before powering off.

## Power the VM off afterwards (owner / lead, after the fetch is verified)
    ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@136.111.202.176 'sudo poweroff'
The VM bills while it is up, even when idle.

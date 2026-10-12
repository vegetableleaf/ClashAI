# Live icebow A/B blocks

`live_ab.py` alternates A/B blocks (default 5 completed matches), stopping at 150
counted matches per arm by default. This is a new runner; the existing `ab_watch.py`
and its historical outputs are untouched. Nothing starts on import or during the
dry run. No training, emulator, live game, or Discord post was launched to validate
this implementation.

From the repository root, in PowerShell (the prompts are necessary until the owner
supplies both actual checkpoint paths and B's configuration):

```powershell
$newsimBase = Read-Host 'NEWSIM base checkpoint path'
$secondArm = Read-Host 'B configuration as label:checkpoint-path:on|off'
& .\icebow\.venv\Scripts\python.exe scratchpad/gauntlet/L74/ab/live_ab.py --arm "A:NEWSIM base:${newsimBase}:off" --arm "B:${secondArm}" --block 5 --total 150
```

Paths may contain spaces and Windows drive colons. Labels cannot contain colons.
Both checkpoints must exist when launched; SHA256 is pinned at argument parsing
and rechecked before every start. No checkpoint path or B configuration is guessed.
There is no scheduled launch or automatic resume. Each invocation has a unique
run ID, fresh counters, and appends to the existing `results.jsonl`.

Offline verification (standard-library Python 3.11+; no checkpoint arguments):

```powershell
python scratchpad/gauntlet/L74/ab/live_ab.py --dry-run
```

The fake supervisor in `ab_dryrun.py` advances virtual time and writes real-format
JSONL files, including partial writes and shutdown races, into unique disposable
`.dryrun/` directories beside the scripts. `test_live_ab.py` exercises the same
Runner, tailer, scoring and reporting code used live. Subprocess creation is
blocked by the suite. It does not invoke Bash, model loading, Discord, or a device.

## Before the real launch

Use the main account and the icebow deck. The runner requires the persisted
`LIVE_DECK` to already be `icebow\n`, and `LIVE_EMOTES` to be `on\n` or `off\n`
(LF newline). This is necessary because the unchanged `start_live.sh` always
rewrites these two files: the A/B passes the existing emote choice so their bytes
and effective settings remain identical. It refuses bait rather than changing
another setting. Current device account selection is checked only from new logs.

Unset inherited `CKPT`, `LIVE_ARGS`, `LIVE_FAST`, `LIVE_EMOTES`, `LIVE_DECK`, and
`HAND_READER` overrides. Keep other orchestrators from controlling live concurrently.
`RUNNING.lock` prevents two copies of this runner; it cannot lock unrelated scripts.
The real adapter uses the existing icebow Python environment (including psutil),
Git Bash, and the existing Windows live-control paths.

The runner first writes live `STOP` and waits for both supervisor and ladder
processes to end, then changes only `CKPT_OVERRIDE` and `LIVE_FAST`. Every start
uses `start_live.sh icebow [--no-fast-plays] [--emotes] --check`, requires exit zero
and the JSON `LIVE_CHECK_PASS` receipt with the expected SHA, then calls the same
starter without `--check`. The check is offline. The restart helper is deliberately
not called: it skips the required check and starts the supervisor directly.

## Counting and safety

- Only newly created logs after the block begins are eligible, using a pre-start
  filename snapshot and the log's local timestamp. Header `ckpt_sha256` must equal
  the pinned checkpoint hash. `pipeline_decisions=true` means fast ON; absent or
  false means OFF, matching the existing writer. Dry-run headers, missing SHA,
  malformed records, backwards clocks and incomplete final lines cannot count.
- Every new match's first decision must show both own princess towers at maximum
  HP 4424 and X-Bow in `public.own_deck`, or in `public.own_hand` when the deck is
  unavailable. Current logs expose only the hand. **A valid icebow opening without
  X-Bow therefore fails closed**, because the full deck cannot be verified from
  this evidence. STOP is requested immediately and no next arm starts. This is
  stronger than checking only the first match after each start. It cannot prevent
  the first wrong-account match from starting; STOP takes effect between matches.
- A count requires an `end` event, valid final public towers and tick >=2400,
  following scorecard/phase_stats. The phase_stats early-terminal exception is
  retained: `battle_over_hands_visible`, one side has no living towers and the
  other has >=2. Tower coordinates exclude spurious card_id=-1 bodies.
  `tower_diff` is crowns taken minus crowns lost; W/L/D uses its sign. These are
  tower-state outcomes, including tower-state draws, not an official result API.
- STOP is armed as soon as the block's final required match is observed underway.
  Shutdown is drained and completed logs are recorded before switching. Polling
  cannot guarantee exactly N actual games if a match is missed between polls:
  extra completed games are retained, block overshoot contributes toward the
  arm's total, and games beyond `--total` are recorded with `counted:false` and
  excluded from statistics. No completed matching log is silently discarded.
- Dead supervisors (90 s startup grace) or stalls (default 1200 s without a counted
  completion, configurable with `--stall-seconds`) receive at most **three recovery
  starts across the whole run**, each preceded by STOP, full drain and --check.
  The reused supervisor's internal restart policy is unchanged.
- `--poll` defaults to one second. If STOP takes more than 2400 seconds, a warning
  is posted, further starts are forbidden, and the runner keeps reasserting STOP
  until processes and a possibly delayed starter have actually ended. It never
  kills a process, switches under a running supervisor, or restores settings while
  the starter could still overwrite them. This may require an unbounded safe wait.
- Protected settings are checked on every scan. External changes abort the run;
  the runner never rewrites `LIVE_OPTIONS`, `LIVE_DECK`, `LIVE_EMOTES`, or
  `HAND_READER_ENABLED` itself. No opponent private fields are used or persisted.

## Stop, restore and reports

```powershell
New-Item -ItemType File -Force scratchpad/gauntlet/L74/ab/STOP_AB
```

`STOP_AB`, Ctrl+C and SIGTERM finish the current block, drain live, restore the
original two files and leave live STOP present. An existing STOP_AB prevents a
new run; remove it yourself when deliberately beginning another experiment.
Errors also drain and restore. The original exact bytes, including absent-file
state, are retained under `backups/<run-id>/` with `manifest.json` (true = existed).
Live remains stopped; the prior supervisor is not restarted.

A forced OS termination or power loss cannot execute Python cleanup. In that case,
keep live STOP present, verify all live/starter/runner processes have ended, restore
the two files from the appropriate backup (remove a file only if its manifest says
it was originally absent), then remove the stale RUNNING.lock. An incomplete
restoration deliberately retains the lock. Do not run this concurrently with the
overnight orchestrator or historical watcher.

`results.jsonl` contains run/block ID, match path, arm/label, SHA, fast flag, W/L/D,
tower difference, counted flag and trophy evidence. `events.jsonl` records checks,
starts, guards, restarts, boundaries, reports and restoration. Every ten counted
matches of either arm triggers a summary of both arms, plus a final report and
error/restart notices, using only `L69/discord/post.py`. Webhook contents and child
transport errors are never printed. Failed posts are retained locally and do not
discard results.

Win rate is W/(W+L), with draws reported separately. Its 95% interval is Wilson;
B-minus-A uses Newcombe's independent two-proportion Wilson construction. Empty
or all-draw arms have no estimated rate/difference. Intervals are nominal,
unadjusted for repeated looks or within-session correlation; alternating blocks
reduces time confounding but does not establish causality or statistical power.

Trophies come from an explicit match-log `trophies_total` when present; otherwise
the latest ladder-nav trophy read observed **within the same block** is attached
with source/time. Missing reads stay null. Per-arm first/last observations are
reported, not summed or attributed as earned trophies: intervening other-arm
games can affect those readings.

# LIVE-OPS status (worker LIVE-OPS, account 2; written 2026-10-28 ~14:20 EDT)

No live change was made: LIVE_OPTIONS, live_play, ladder_nav.py, templates, stuck_watch.sh, run_live.sh and the supervisor are
untouched (git status clean for them). Everything below is read-only analysis plus PROPOSALS under `scratchpad/gauntlet/L74/liveops/`.
Live at 14:10: CLXIII NOLEAK Ranked, `--barrel-decoy on`, supervisor run started 12:16:20 (auto restart 1/10), 34 logs since the 11:45 deploy.

## 1. Decoy measurement (details in `../gb_decoy/STATUS.md`, section "Post-deploy watch")
- (a) 33 finished logs since 11:45, 15 opponent barrel casts: 14 plain, 1 evo. All 34 start events: `barrel_decoy true`, merged_sf reader;
  0 tracebacks, 0 decoy warnings, 0 error events.
- (a) the one evo cast (live_play_20261028_130522, tick 3237): the model's input holds ONE opponent barrel (real lane x = 0.194); the
  mirrored decoy is gone (pre-deploy: two tokens in 80/80). First answer Skeletons, then Log + Knight, all in the real lane: 1/1
  (before 30/50, replay with the fix 43/50). n = 1: it shows the filter is live, not the rate.
- (a) plain casts: first answer in the real lane 13/13 answered (before 446/467).
- (b) the rate needs ~30 evo casts (1 per ~18 matches, ~540 matches, ~2.5 days): `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/gb_decoy/postdeploy.py`
  daily (one command: scan + measure + start-flag check on every finished log since the deploy; 6 s when the logs are cached).

## 2. The 12:15 "[nav] run stopped before match 7: screenshots failing for 60 s"
- (a) timeline: match live_play_20261028_120902 ended normally (tick 6260, `end` written, device frames regular to the last tick, no gaps
  > 0.6 s). Its p3_capture then FAILED ("pulled frames file missing or empty": both `adb pull` calls produced nothing, the capture dir is
  empty). The nav started at 12:14:13.98; its FIRST grab failed 0.04 s later and every grab for the next 60.3 s failed (nav log
  ladder_nav_20261028_121413.jsonl: 2 events, nograb at t0+0.04 s and the stop at t0+60.3 s). `[sup]` restarted live_play at 12:16:20;
  the watcher's own `adb exec-out screencap -p` at 12:17:12 worked (stuck_1217.png, 1.59 MB) and live has played normally since.
- (a) what it was NOT: the first failed grab came back in 0.04 s, so it was not the 5 s screencap timeout (`grab()` has timeout=5) and
  not CPU starvation making screencaps slow (that would be a 5 s wait per failure); the adb SERVER was not restarted (adb.exe PID 77576
  started 10-19 08:39:32 and is still the same process); the emulator process is the same (MuMuNxDevice since 10-26 12:58); the decoy flag
  cannot touch adb. Windows Application log 12:10-12:20: nothing relevant.
- (a) the p3 failure and the nograb are the same outage: of 623 matches since 10-26 14:14 with a known p3 status, the only one with
  p3_capture ok=false AND a mapped next nav (the 12:09 match) had a nograb episode (60.3 s); the 622 matches with p3 ok=true had none
  (the other 3 p3 failures are unmapped: 10-27 04:26 maintenance, 18:24 and 18:26 supervisor hand-over).
- (b) cause, most likely: the adb TCP transport to 127.0.0.1:16384 dropped at the end of the match (adb returned an immediate error) and
  was only re-established by the `adb connect` that live_play does at its start (`screen_size()`); the navigator has no repair step, it
  just waits 60 s and stops. NOT proven: nothing logged why the transport dropped (candidates: another tool's `adb root` / `adb tcpip` /
  `adb disconnect` on the shared server, or the emulator's adbd restarting). The navigator discards the screencap's stderr, so this
  cannot be settled from logs; the proposal below logs it.
- (a) history: 5,888 nav logs, 9 with a nograb episode, 11 episodes (results/nograb_history.md): five of 1-5 s, four of 5-15 s (all
  10-18 .. 10-21, self-healed), two of >= 60 s that ended the run: 10-19 08:17 (the current adb server process started 08:39 the same morning, so a server
  restart is the likely cause there, b) and today 12:14. Rate 2 / 5,888 navs = 0.03%; one match slot (~1-2 min) lost each time.
- Fix (PROPOSAL P1b, below): after 4 failed grabs the navigator logs `adb devices -l`, the `adb connect` reply and the screencap rc/stderr
  as a `nograb_diag` event and runs `adb connect` (idempotent, an input-free no-op when connected), at most once per 10 s. Offline test:
  fake adb + fake clock (test_nav_proposed.py section 4).

## 3. Other stalls found while checking (not asked; listed so nothing is lost)
- (a) 10-27 04:24-05:20: 11 consecutive `[nav] run stopped ... transition over 300 s` (game maintenance, stuck_0425.png /
  maintenance_20261027_0430.png) burnt the supervisor's 10 restarts in 55 min; `NOT restarting` at 05:20; live stayed down until the
  06:57 manual start (hours 04-06 show 0-5 matches). The new watcher alerts on `NOT restarting` (GAVE_UP). A supervisor back-off (sleep
  10 min instead of 60 s when the reason is `transition over 300 s`) would ride out a maintenance; not built, say if wanted.
- (a) the "Claim All" stall is NOT a one-off: the same orange button screen stopped the run six times in a row on 10-19 23:57 - 10-20
  00:37 ("Rewards", Magic Lucky Chest; 41 frames each) and on 10-28 02:55 ("Supercell Support"). One template covers both (see P1a).
- (a) `[nav] run stopped` reasons over the whole overnight.out (84 stops): transition over 300 s 32, 40 tap-throughs 25, ANOTHER_DEVICE 12,
  loading 60 s 11, screenshots failing 2, TROPHY_ROAD_ALERT 2 (results/transitions.md lists them all).

## 4. Proposals awaiting the lead's go (none deployed)
### P1a Claim All screen (navigator template + action) -- `nav/`
- Template: one 256x106 crop of the orange "Claim All" button (`nav/templates/claim_all.png`, manifest entry `nav/manifest_fragment.json`,
  threshold 0.85, search region (150,1300)-(750,1600)); title-independent. Action `claim_all` (allowlisted tap rectangle (330,1415)-(570,1510),
  tap point = the matched centre = (450,1461)), at most 6 taps per transition (`CLAIM_MAX`, then `stop`: "claim_all tapped 6 times ...").
  A new screen class `claim_all` is also a launch-probe screen (NAV_SCREENS), so a restart onto that screen navigates instead of
  assuming a battle.
- (a) separation on the recorded corpus (score_corpus.py, 2,897 frames: ladder_unknown, ladder_stop_*, raw captures, stuck_*, fixtures,
  ranked_nav): 276 frames score >= 0.99 (9 stall runs: six on 10-19/20, the 10-28 run, stuck_0258.png, one ladder_stop), the highest
  non-hit is 0.366. Positives viewed: "Rewards" (Magic Lucky Chest) and "Supercell Support" (Unique Snippet).
- (a) `test_nav_proposed.py` (4 min on this laptop, I/O bound): (0) the live `test_ladder_nav.py`, every original assertion, passes unchanged on the
  proposed module + merged templates; (1) full classifier on 19 positives, 50 sampled non-hits and the 43 raw captures: 0 wrong, the
  source frame -> tap 450 1461; (2) planner: act claim_all, stop after 6 taps, allowlist refuses (450,450), the Shop-tab corner and
  (450,1530); (3) runner with fake adb + clock: claim x2 -> main -> Battle -> handoff; a tap that never lands stops after exactly 6.
- Files: `nav/ladder_nav_claim_all_nograb.patch` (git apply --check OK against HEAD 87e759f, base sha256 9c66763b...; 9 hunks: TARGETS,
  classify, plan, acted, NAV_SCREENS, constants = P1a; adb_diag + the loop hook = P1b), `nav/ladder_nav_proposed.py` (the full result),
  `nav/install_claim_all.py` (copies the png + merges the manifest, idempotent, backup; tested on a temp copy).
- Deploy (lead decides; at a match boundary after a blind check): (1) `git apply --check -p1 <patch>` then `git apply -p1 <patch>`;
  (2) `install_claim_all.py`; (3) run `test_ladder_nav.py` (live dir) and `nav/test_nav_proposed.py`; (4) the code is read at live_play start:
  it takes effect at the next supervisor start (a planned `stop_live.sh` -> '[sup] done' -> `start_live.sh icebow --no-fast-plays --ranked`,
  or any auto restart). Either half alone is inert (an old manifest never classifies claim_all; a new manifest entry is unused by old code).
  Rollback: `git checkout -- scratchpad/gauntlet/L68/live_reader/ladder_nav.py` (restores HEAD) and `cp manifest.json.pre_claim_all manifest.json`.
### P1b nograb diagnosis + `adb connect` (same patch, the `adb_diag` / `nograb_diag` hunks)
- (b) it repairs the 10-28 failure class if the cause was a dropped TCP transport; if not, the `nograb_diag` event settles the cause on
  the next occurrence. Never an input. Can be split off by dropping the last two hunks.
### P2 tightened stuck watcher -- `stuck_watch2.py` (+ `test_stuck_watch2.py`)
- (a) measured on overnight.out (78,155 lines, results/transitions.md + test replay): the old rule fires in 5,312 12-line windows
  (my independent recount equals Codex's 5,312); 2,478 of them lie entirely inside normal HANDOFF transitions. `tap_through` counts do not
  separate real stalls from benign chest openings (benign max 34 of 5,775 transitions, p99 6; a stall reaches the 40 cap), so the new
  watcher never looks at unknown / tap_through / handoff lines.
- Alerts (one stdout line each, keeps running, so it re-arms itself; `--once` = the old exit-on-alert behaviour): `STOP[class]` for each
  `[nav] run stopped` line (adb_down, unknown_screen, transition_timeout, another_device, loading_stuck, trophy_road, other; same class
  within 20 min counted, re-reported at the 3rd/6th/9th), `GAVE_UP` (supervisor.log `NOT restarting`), `NO_PROGRESS` (no `{"played"` /
  `[ladder] result:` line for 12 min with a live_play process; match-start gaps: median 4.1 min, p99 8 min, 6 of 629 gaps > 10 min, every one an
  incident), `PROC_GONE` (no live_play for 10 min, no STOP file). `[live] stop file ... found` never alerts. Screenshot (read-only
  `adb exec-out screencap -p`, timeout 20 s) per alert except adb_down / another_device / GAVE_UP / PROC_GONE; `--no-screenshot` turns it off.
- (a) `test_stuck_watch2.py` (6 s): synthetic cases (throttle 1/3/6/9, class mapping, no-progress, proc-gone, stop-file silence, a stop
  restarts the window); the run loop reads appended lines, ignores history, handles a half-written line, re-arms after each alert, `--once` exits;
  replay of the whole overnight.out: 84 STOP lines -> 37 alerts (unknown_screen 10, another_device 7, transition_timeout 13, trophy_road 1,
  loading_stuck 4, adb_down 2), 0 alerts on any other line; the 12:14 slice -> exactly one `STOP[adb_down]`; the 11:45-12:14 normal stretch -> silent.
  Smoke run against the live files for 20 s: no alert, no crash.
- (b) untested live: the NO_PROGRESS rule is only synthetic-tested (overnight.out has no timestamps).
- Run: `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/stuck_watch2.py` under Monitor (every alert line is a notification and
  it keeps watching), or with `--once` in the background as before (re-launch after each alert). It reads files only; the old
  stuck_watch.sh can be stopped by exact PID when this one runs.

## 5. Live health since CLXIII returned (10-26 14:14; `results/health_table.md`, `results/health_rows.jsonl`, 629 matches, scan 13:41)
| window (EDT) | matches | W-L-? | win rate [Wilson 95%] | unconfirmed / 100 plays | p3 failures |
|---|---|---|---|---|---|
| 10-26 from 14:14 | 137 | 44-92-1 | 32.4% [25.1, 40.6] | 3.22 | 0 |
| 10-27 | 299 | 93-203-3 | 31.4% [26.4, 36.9] | 3.44 | 3 |
| 10-28 before 11:45 | 165 | 59-106-0 | 35.8% [28.8, 43.3] | 2.87 | 0 |
| 10-28 from 11:45 (decoy on) | 28 | 8-19-1 | 29.6% [15.9, 48.5] | 5.21 | 1 |
| all | 629 | 204-420-5 | 32.7% [29.1, 36.5] | 3.2 | 4 |
- Win rate: no drift (6-hour blocks 28.0% - 34.7%; the post-deploy interval is inside the baseline interval). 13 matches / hour (median).
- Restarts since 10-26 14:14: supervisor starts 10-26 14:14 and 15:25; 10 automatic restarts 10-27 04:25-05:14 (maintenance, `transition over
  300 s`, limit reached 05:20); manual starts 10-27 06:57, 07:37, 18:52 (after a supervisor swap), 10-28 07:53, 11:45 (decoy deploy);
  one automatic restart today 12:16 (screenshots). Stop-file exits 4 (10-27 07:23, 18:23, 10-28 07:52, 11:43).
- **Open item: unconfirmed taps rose after 11:45** (a) measured: 5.21% of plays (61 / 1,170) vs 3.23% over the 597 earlier matches; per
  match 1.64 `unconfirmed` events vs 0.93 (81 matches 06:00-11:45); 0 of 571 sliding windows of 27 earlier matches reach 5.2% (max 5.0%);
  by card post: Knight 17, Log 11, Tornado 11, Xbow 5, IceWizard 5, Skeletons 5 (pre: Tesla 13, Knight 12, IceWizard 12, Skeletons 9, Xbow 9, Log 8,
  Tornado 7, Rocket 5). Tap confirmation latency is unchanged (median 1.20 s, p90 1.90 s, p99 2.30 s both periods, 3,438 / 1,371 confirmed taps).
  (c) "the decoy flag causes it" is contradicted by mechanism: the replay found 1,572 / 1,572 non-evo plain decisions identical flag off vs on, all 163
  differences inside evo windows, and only 1 of the 33 post-deploy matches has an evo cast; the start events of a pre and a post log differ only in
  `barrel_decoy`, the seed and the options message (startdiff.py). Cause unknown (b: host load / tap path / opponent mix). Measure: re-run
  `unconf.py` after ~100 more matches; if it persists, the lead can decide on a paired off / on check (no change by me).

## 6. How to re-run
- Health table: `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/health.py` (7 s; reads first line + last 64 KB of each log).
- Nograb history: `.../nograb_history.py` (2 min); transitions: `.../transitions.py` (<1 s).
- Decoy watch: `.../gb_decoy/postdeploy.py`; unconfirmed rate: `.../liveops/unconf.py`; card split / latency: grep dumps then `unconf_cards.py` / `lat.py`
  (commands in their docstrings; inputs `grep -a -h '^{"event": "unconfirmed"' live_play_*.jsonl`).
- Tests: `.../liveops/test_stuck_watch2.py` (6 s), `.../liveops/nav/test_nav_proposed.py` (4 min).
- Codex helper: `.../liveops/lastmsg.py OUT.jsonl` prints a Codex run's final message (codex_final.py crashes on non-cp1252 characters).

## 7. Codex dispatches (tickets in .foreman/scratch/a2/codex/)
| ticket | effort | outcome |
|---|---|---|
| LIVEOPS_1 | medium | BLOCKED (a `"log": null` outcome was not in the decision tree) |
| LIVEOPS_1b | medium | DONE, health.py + health_table.md + health_rows.jsonl; numbers re-checked: 8 W / 19 L / 1 in-progress post-deploy equals my own newlogs count |
| LIVEOPS_2 | medium | BLOCKED (transition coverage vs GAP lines) |
| LIVEOPS_2b | medium | Part B DONE (transitions.md; its 5,312 old-rule windows equals my recount), Part A timed out at 295 s |
| LIVEOPS_3 | medium | BLOCKED (supervisor.log date format `Tue, Oct 13, 2026 10:07:34 AM`) |
| LIVEOPS_3b | medium | DONE (nograb_history.md; anchors checked: 12:14 episode 60.3 s, 10-19 08:20 line) |
Lesson for the next ticket: list every input format variant and say "skip and count" in the decision tree; three of six runs stopped on a spec gap.

## 8. Two 0-3 losses in ~66 s (live_play_20261028_154218 tick 1328, 154335 tick 1311; analysis 10-28 ~16:00, no live change)
Scripts and data in `short0_3/` (timeline.py, defence_geom.py, battles.py, short_losses.py/.md). Labels: (a) measured, (b) plausible untested, (c) contradicted.
- (a) Tick = 20 / s (wall 65.6 s / 65.9 s for 1328 / 1311 ticks): the matches really lasted ~66 s. A king-tower kill ends a match 3-0 whatever the princesses are.
- (a) Battle log (crapi/data/own_battlelog.jsonl, 15:43:19 / 15:44:37 EDT): mode Ranked1v1_NewArena (same as every recent match), opponents at max card levels, decks:
  154218 = Battle Ram evo, Balloon (hero), Royal Recruits evo, Zappies, Barbarian Barrel, Goblin Cage, Arrows, Furnace; 154335 = PEKKA evo, Elite Barbarians, Musketeer evo,
  Zap, Mega Minion, Mega Knight, Freeze, Arrows. Both are ordinary meta decks, not a mode / bot effect.
- Match 154218 (a): our first card Xbow at (0.139, 0.609) t258 (10 elixir), Tesla (0.278, 0.563) t284 vs the opponent's 3 Zappies (visible t270); we were at 0.5 elixir at t310. 6 Royal Recruits
  crossed t510; our Log t479 (before they appeared), Skeletons t504, hero Ice Wizard t597, Tornado t765, Knight t933. Both buildings died by t671 (Tesla 162 hp at t571; buildings also decay). Hero Balloon
  reached our left towers t631; princesses 4858 -> 802 / 150 by t991 (Recruits + Balloon), both gone by t1031. Battle Ram t1071, Barbarians + Furnace + Fire Spirits t1191; king 7728 -> 6518 (t1111)
  -> 936 (t1232) -> 0 (t1272). Our Xbow took their left princess 4858 -> 1372 before it died.
- Match 154335 (a): Ice Wizard t200, Xbow t278 (left bridge), PEKKA seen t311 left lane, Musketeer t551, our Tesla at (0.5, 0.656) t543 = centre; PEKKA walked down x 0.18-0.25 and the nearest PEKKA-to-Tesla
  distance in 60-tick samples was 6.4 tiles (> Tesla range 5.5): the Tesla never fired at the PEKKA (b: exact min distance not checked per tick). Our Xbow took their left princess 4858 -> 392 (92%) before its lifetime ended
  (t751). Elite Barbarians t831, Mega Minion t1111. Our left princess died t1031 and the king 7728 -> 6502 (t1152) -> 3584 -> 0 (t1234) with the second princess still standing: PEKKA + Musketeer + 2 Elite Barbarians + Mega Minion on the king (~20 elixir in one push).
- (a) Bot health: all 7 / 8 plays confirmed, 0 unconfirmed; landing error 0 - 0.58 tiles (Skeletons 0.58 = the usual offset); tap latency 1.1 - 2.3 s (baseline p99 2.30; the 2.2 s ones are early taps for 2.6 elixir cards, afford_ticks 23);
  decisions 102 / 101 = 0.077 per tick (same as full matches); reader: my_side 0, towers, ents and elixir consistent every frame; no frame gaps; plays in the first 1330 ticks 7 and 8 vs a median of 9 over the last 56 matches
  (range 5-11; 25% of matches have <= 7). Hero Ice Wizard ability: 154335 pressed once (confirmed); 154218 withheld 12 times ("state", the button not ready) while the Ice Wizard lived <= 190 ticks.
  So (c) "reader / side / tap / decision freeze" is contradicted.
- (b) What it was: an elixir race lost. Both openings spent 10 elixir on Xbow + (Tesla) at t258-284 (before the opponent's card showed), leaving 0.5 - 3 elixir when a 20-elixir push (Recruits + Balloon hero; PEKKA +
  Musketeer + Barbarians) arrived; the defensive Tesla in 154335 was out of range of the lane the PEKKA took. The Xbow chip (92% / 72% of one princess) was not enough. This is the model's play, not a malfunction; no
  evidence that the decoy flag or P1/P2 anything is involved (Tesla / Xbow / opening are not evo-barrel decisions; decisions are identical flag off vs on outside evo windows).
- (a) Variance vs regression (`short0_3/short_losses.md`, 1,573 matches 10-20 .. 10-28 from navigator outcomes, 10-24 has no navigator logs): opponent-3-crown losses under 90 s: 10 in 1,573 (0.64%), under 75 s: 6, under 67.5 s: 4 -
  two of them today, the other two 10-23 00:04 (tick 1313, CLX_PARITY) and 10-26 22:25 (1345, CLXIII). Since CLXIII returned (655 matches): 5 under 90 s (0.76%). Today: 2 / 224 under 90 s (0.9%, expected 1.4 at the base rate) -
  unremarkable as a count; the adjacency (two in a row) has precedent (10-23 00:02 / 00:04, ticks 1827 / 1313, a different model). Overall 3-crown-loss rate 5.15% (81 / 1,573), today 7.1% (16 / 224) vs 4.8% before: borderline, (b).
  Verdict: variance plus a model weakness vs fast pushes, not a new regression; 0.15% per match for a < 1350 loss means two in a row stays surprising (~1 in 10^5 per pair if independent), so check the matchup / queue (b) - the 15:41-15:45 matches were against back-to-back push decks.
- Video: no Discord clip or overlay exists for these matches (clips are cut every 30 min; the 153755 raw video is 247 s and covers only that match). The timelines above come from the frame logs.
- Codex: LIVEOPS_4 (medium) BLOCKED on a strict `won` check (an outcome with won null); I removed the check and re-ran the script (DONE, anchors present).

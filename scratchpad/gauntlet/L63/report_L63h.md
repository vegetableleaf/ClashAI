**GAUNTLET loop L63h** — Square One S0 close-out + the overnight trigger
**Did:** Tested why 3 nights died: launched a 60 s background timer task and ended the turn. Graded the finished icebow corpus batch.
**Found:** (a) `ScheduleWakeup`/cron never fire while the session is idle; (a) a background task's exit re-invokes the loop within seconds. Rule written into the gauntlet skill + HANDOFF §7: every loop now ends on a `sleep N` timer task, batches stay background tasks. (a) Icebow corpus final: 493/619 converted (120 EB-evo refusals, 6 duplicated-row tags), 41,015/41,338 plays accepted 99.2%, crowns match 76.9%, engine ends early 22.9%, determinism 49/49, 177.6 MB. Hogeq (L63g): 241/296, 98.7%, crowns 56.4%. S1 corpus = 734 replays with a full obs before every play (old: 211).
**Means:** S0 step 3 is done for both decks; engine idle. Overnight autonomy now has a measured trigger instead of a hoped-for one.
**Next:** the cleanup loop (owner ruling: manifest + backups, data/ untouched), then the S1 dataset build from play_frames through `from_engine` for both decks.
**Cost:** 15 min wall; nothing running.

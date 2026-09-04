

### §5cs.23 -- SIM-ONLY SWARM PROBE (2026-09-04, L53): in our sim an UNANSWERED evo Skeleton Army takes a whole L11 princess tower plus 895 king HP (3947) in 12 s, a Knight in front of the tower changes NOTHING (3947 -> 3947) while it cuts the non-evo army to 407, and an Ice Wizard zeroes it (Gerry dies to splash at 3.1 s); `shadow_skeleton_speed_tiles: 1.0` in cards.yaml is never read by engine.py (ghosts run at 1.5); the driver patch for it is a population null (55/211 -> 55/211). Opponent decks with any Skeleton Army: sim crowns-match 3/32 = 9.4% vs 29.1% for the rest -- but the side-0 bias is present in every subset (112/140 sim side-0 wins where no swarm card is in the deck, real 55/140)

**What ran.** `scratchpad/gauntlet/L53/skarmy_probe.py` (sim only, `ParityEngine` at L11, seed 424242, 0.1 s ticks,
attacker at the left bridge, optional defender dropped 1.5 tiles in front of the left princess tower; results in
`L53/skarmy_probe.json`, `L53/skarmy_probe_shadow.json`); `sim_replay_drive.py --patch shadow_speed` over the 211
(`L53/simbatch_shadow/`); a crowns-match split of the L51 base run by opponent-deck swarm cards; the wiki page
`Skeleton Army/Evolution` via api.php (rule text + stat tables). c2r at 17:32: 35,000 eps, 0.5 ep/s, 17 procs,
4 GB free, untouched; ETA 40k ~20:15.

**(a) measured -- in OUR sim (these say what the sim does; the real-game side of each is untested).**
- Unanswered `skeleton_army_evo` vs the L11 princess tower (3052): first tower damage 4.3 s, tower dead at 10 s,
  king 4824 -> 3929 by 16 s: 3947 total. `skeleton_army` (non-evo): tower 3052 -> 773, 2279 total, the pack dead
  by 14 s. The tower kills one live skeleton per shot either way; the difference is the 15 ghosts (hp 1,
  untargetable, indestructible, still swinging 81 per 1.1 s) that keep hitting.
- Gerry (81 hp + 81 shield, placed 1 tile BEHIND the drop, engine.py ~2309) trails the pack by 2-4 tiles and is
  first damaged at 12.2 s / dead at 13.1 s -- the tower reaches him only after the last live skeleton dies,
  because it always has a nearer live target. Ghosts vanish the moment he dies (the rule works).
- Knight (1766 hp) in front of the tower: non-evo army 2279 -> 407 (knight dies, kills 4-5); evo army 3947 -> 3947
  -- the knight dies at ~3 s having killed 3, and the ghosts of everything it killed carry on.
- Ice Wizard in front of the tower: evo army 0 tower damage -- splash strips Gerry's shield at 1.5 s and kills him
  at 3.1 s, every ghost vanishes. Splash-on-Gerry is a full counter; single-target damage is none.
- `shadow_skeleton_speed_tiles: 1.0` (cards.yaml line 593, wiki: shadows Medium (60) since the 12/01/2026 balance)
  is read by nothing in engine.py (grep: 0 hits); ghosts are `Unit(u.spec, ...)` and move at the live skeleton's
  1.5 tiles/s (measured: Gerry alone 1.50 t/s, skeletons 1.5-2.0 with formation push, knight 1.00). Driver patch
  `--patch shadow_speed` (ghost spec swapped for a speed-1.0 copy): unanswered 3947 -> 3785, with knight 3947 ->
  3703; 211-match crowns-match 55 -> 55 (3 matches changed). NULL. Not the lever.
- Clip 08QPVCPC9QQU (real and engine 0-1, sim 3-0 at 41.6 s): the evo army spawns 1.5 tiles behind the bridge on
  the icebow evo Knight; the knight dies in 3.2 s (18 hits, kills 3 -- plausible), the pack's live front is at
  y 12.7-13.3 by 25 s, and the pro's Ice Wizard, dropped at (3.5, 14.5) at 25.3 s, lands INSIDE 10 live + 5 ghost
  skeletons and dies in 0.7 s (688 hp = 9 hits) before its 1 s deploy ends. In the real game the same drop
  stopped the push. The only sim-side candidate this leaves is the real pack's POSITION/STATE at 25.3 s.
- Crowns-match by opponent deck (L51 base run): any skeleton-army 3/32 = 9.4% (evo 2/24, non-evo 1/8) vs 52/179 =
  29.1% for the rest; other swarm/spawner (goblin-gang, minion-horde, witch, skeleton-king, night-witch, bats)
  without skarmy 8/39 = 20.5%; none of those 44/140 = 31.4%. Sim side-0 wins: 30/32, 38/39, 112/140 (real side-1
  wins 20/32, 24/39, 85/140). So swarm decks are the WORST subset, but the side-0 bias is in every subset.
- Wiki rules confirmed: shadows spawn when skeletons die, unlimited HP, untargetable by troops/buildings/towers,
  hit by spells, vanish when Gerry dies; Gerry 1.0 s hit, 1.6 range, Fast; shadows 1.1 s hit, Medium (60);
  balance 12/01/2026 also moved the General "closer to the Shadow Skeletons" (formation) -- the sim's "1 tile
  behind" is the OLD formation (untested which is closer to the tower).

**(b) what this does NOT establish.** Whether the REAL evo army does 3947 to an undefended tower or 0 to a
knight+tower: an unanswered evo army is known-devastating in the real game, so the undefended number may well be
right; the knight case is where the doubt is (the real pack would stop on the knight, then the tower reaches
Gerry as he walks with the pack under the new formation -- plausible, untested). The Ice-Wizard-dies-in-0.7 s
clip is the sharpest question for the engine record: where was the real pack at 25.3 s, and does a deploying
unit take hits (it does in the real game -- so the answer is position, not invulnerability). Settled only by
oracle step 2 on the swarm tags (§6 list; add 08QPVCPC9QQU's tick 430-560 window as the first thing to look at).
The subset split is an association over open-loop replays (the same caveat as §5cs.22).

**Traps found.** (1) A cards.yaml key that no engine code reads is silent -- `verified: true` next to it means
the NUMBER was verified, not that it is USED; grep engine.py for every curated key before trusting a mechanic.
(2) The engine's per-tick coordinate scale is 1000 units per tile on BOTH axes (18000/18, 32000/32); a
"within 1.5 tiles" filter hides melee hits, because reach 0.5 + two 0.5 radii = 1.5 centre-to-centre exactly.
(3) `skarmy_probe.py`'s `ghost` counter reads a `u.ghost` attribute that does not exist -- ghosts are `hp <= 1`
+ `invis_left >= 9999`; the `skel` column in its rows therefore counts live + ghost bodies (always 15).

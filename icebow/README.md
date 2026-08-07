# Learning ClashBot (`icebow/`) — imitation learning → RL

> 🚀 **New here / setting this up on another PC? Start with [Instructions.txt](Instructions.txt)** —
> a complete, plain-English, from-scratch guide: prerequisites → install → screen
> calibration → recording → processing the data → training (simulator + imitation + live RL)
> → letting the bot play. No coding experience needed.

> 🔀 **Current deck: Icebow X-Bow Control (Classic 1v1)** — the standard X-Bow 2.9 control list.
> [DECK_SWITCH.md](DECK_SWITCH.md) is the ordered runbook for switching the deck (record → templates → label → train).

A second, **learning** bot (separate from the scripted `../trol` bot). Goal: an
agent that actually *plays* 1v1 Clash Royale (Classic / ladder), rewarded for
**taking enemy towers**, **defending its own towers**, and **winning**, and punished
for the opposite. It runs on PC via Google Play Games — the same rendering it trains on.

> ⚠️ **Honest expectations.** Learning to play from scratch on a *live* game is a
> research-grade problem: matches are real-time (~3–4 min), you can't parallelize
> one game instance, and rewards must be screen-scraped. A from-scratch agent
> would start random and likely plateau at weak play. So the plan leads with
> **imitation learning** (clone *your* play first), then RL fine-tune. This is a
> **train-it-yourself framework**, not a turnkey pro bot.
>
> Same responsible-use rules as `trol`: throwaway account, private/consenting
> matches only. Automation violates Supercell ToS.

## Pipeline

```
0. train-sim headless simulator: pretrain vs ~1000 meta decks + self-play  [BUILT]
1. record    you play on PC; capture screen + your mouse                    [BUILT]
2. label     sessions -> (observation, action) dataset                      [BUILT]
3. outcomes  auto win/loss per match from the results scoreboard            [BUILT]
4. train-bc  behaviour-cloning: CNN policy learns to copy you               [BUILT]
5. train-rl  Double-DQN fine-tune, tower/win rewards (live matches)         [BUILT]
6. play      the policy plays live                                          [BUILT]

optional (Stage 3): a YOLO object detector adds opponent awareness    [in progress]
```

The agent sees a **downscaled arena image + the hand** (which cards are in hand)
and picks a **discrete action**: which **card identity** to play — not the tray
slot (cards cycle), and an **evolved card counts as its own identity** since it
plays differently — placed on a grid cell, or no-op. Rewards: `+take_enemy_tower`,
`+` for keeping your towers alive (defense), `+win`; `−` for the opposite (see
`config/config.yaml`).

## Launcher (Browser-Oberfläche) — `run.py ui`

Statt jedes Kommando im Terminal zu tippen: **`start_ui.bat` im Repo-Root doppelklicken**
(oder `.\.venv\Scripts\python.exe run.py ui`). Es startet einen lokalen Server auf
`http://127.0.0.1:8765` — **nur localhost**, kein Netzwerkzugriff, keine Anmeldung —
und öffnet den Browser.

Beim ersten Start erscheint ein kurzes Willkommensfenster mit dem ToS-Hinweis und startet
auf Wunsch eine **geführte Tour**: sie wechselt selbst durch die Bereiche und hebt dabei
jeweils genau das Bedienelement hervor, um das es geht. Beides ist jederzeit über
„Einführung“ bzw. „Hinweise“ oben rechts wieder erreichbar.

Die Oberfläche bietet:

* **Übersicht** — Stand des Projekts (Checkpoints, Deck, Türme, gemessenes Tempo) und
  konkrete Vorschläge, was als nächstes sinnvoll ist.
* **Steuerung** — Start/Stop für `train-sim`, `train-sim-ppo`, `train-bc`, `train-rl`,
  `play`, `record`, `label`, `outcomes`, `verify`, `diag`, `policy-stats`, `sim-bench`,
  nach Zweck gruppiert. Stop sendet das Ctrl+C-Äquivalent, damit die bestehende
  Checkpoint-Speicherung beim Abbruch greift. Zwei GPU-Jobs gleichzeitig lässt der
  Launcher nicht zu.
* **Tempo** — liest CPU, RAM und GPU aus, schätzt den RAM-Bedarf des Replay-Puffers und
  misst mit `sim-bench`, wieviele Matches pro Sekunde dieser PC bei welcher Env-Zahl
  schafft. `sim-bench --auto` verdoppelt die Zahl gleichzeitiger Matches so lange, bis es
  nicht mehr schneller wird oder der Arbeitsspeicher knapp würde, und `--apply` schreibt
  das Ergebnis gleich in die Config.
* **Deck erkennen** — `cards-art` lädt einmalig je ein Referenzbild pro Karte aus dem
  Fandom-Wiki, danach ordnet `deck-detect` die Kartenbilder einer Aufnahme automatisch den
  Karten zu. Das manuelle Umbenennen von `_cand_*.png` entfällt; das Ergebnis wird im
  Deck-Tab mit Sicherheitswert und Alternativen zur Bestätigung angezeigt.
* **Türme** — Turmtruppen des Simulators: eigener Turm, Bezugslevel, Reichweiten,
  Königsturm sowie beliebig viele Turmtypen mit HP/DPS/Schussintervall und der
  Gewichtung, mit der der Gegner sie würfelt. Neue Typen wirken sofort, ohne Codeänderung.
* **Live-Log** des laufenden Prozesses (Server-Sent Events); Volltext unter `data/ui_logs/`.
* **Dashboard** — Winrate, Reward, Loss, Epsilon, Matches/Sekunde, Benchmark-Kurve,
  Restzeit bis zur Ziel-Matchzahl. Persistiert in `data/metrics.jsonl` (übersteht Neustarts),
  CSV-Export per Knopfdruck.
* **Strategie** — welche Karten die Policy wie oft spielt, Platzierungs-Heatmap über
  `action.grid`, Wait-Gate-Quote, nie gespielte Karten. Datenquelle: `run.py policy-stats`.
* **Deck** — aktuelles Deck aus `cards.yaml` mit Elixier/Rolle/Durchschnitt, Karten per
  Auswahlliste tauschbar, Level pro Karte. Warnt, was ein Deckwechsel ungültig macht.
* **Config** — die wichtigsten Felder aus `config.yaml` mit Erklärung und Validierung.
  Geschrieben wird **zeilenweise**, sodass alle Kommentare der Datei erhalten bleiben;
  vorher Backup nach `data/config_backups/`, ungültiges YAML wird nie geschrieben.
* **Checkpoints** — `.pt`-Dateien mit Datum, Matchzahl, bestem Benchmark und Deck-Abgleich;
  übernehmbar als `--init` für den nächsten Lauf.

Die CLI bleibt vollständig funktionsfähig — das UI ruft sie auf, es ersetzt sie nicht.

### Trainingstempo

`train-sim` schiebt seine Beobachtungen jetzt **gebündelt** auf die GPU statt einzeln
(eine Kopie pro Batch statt 128 winziger Kopien je Optimierungsschritt). Gemessen auf
einem RTX 3070 / 16 Threads, 60 Matches bei `--envs 16`, Seed 0, je zwei Läufe:

| Pfad | Matches/s |
|---|---|
| vorher (pro Sample) | 1,04 / 1,01 |
| nachher (gebündelt) | 2,07 / 1,90 |

Dazu kommt die Env-Zahl. `run.py sim-bench` misst sie auf deinem Rechner (je 30 s,
gleicher Seed, schreibt nach `data/bench/`, nie auf `policy_sim.pt`):

Dazu kommt die Zahl gleichzeitiger Matches. `run.py sim-bench --auto` verdoppelt sie und
misst jede Stufe (je 25 s, gleicher Seed, schreibt nach `data/bench/`, nie auf
`policy_sim.pt`):

| gleichzeitige Matches | 8 | 16 | 32 | 64 | 128 | 256 |
|---|---|---|---|---|---|---|
| Matches/s | 2,20 | 3,16 | 4,08 | **4,32** | 3,47 | 2,35 |
| Lernschritte je Match | 23,1 | 12,0 | 6,1 | 3,6 | 2,6 | 2,3 |

Mehr ist also ausdrücklich **nicht** immer besser: ab 64 fällt der Durchsatz wieder, und
die Zahl der Lernschritte, die auf ein einzelnes Match entfallen, sinkt durchgehend. Die
Automatik hört deshalb auf, sobald zwei Verdopplungen nichts mehr bringen, und empfiehlt
von den gleich schnellen Einstellungen die kleinste.

Zusammen mit dem Transfer-Fix rund **5×** gegenüber dem alten Default (0,85 m/s bei 8
Envs, alter Code). Die Kurve flacht ab, weil `train-sim` EIN Prozess ist: die Envs rechnen
wegen des GIL nacheinander auf einem Kern. Echte Mehrkern-Nutzung braucht Worker-Prozesse
(geplant).

Der **Start** eines Laufs kostete vorher ~0,4 s pro Env, weil jede Env-Instanz sich ihre
eigene Kartendatenbank baute und die ~1000 Meta-Decks neu parste: bei 64 Envs rund 27 s,
bevor der erste Zug fiel. Beides wird jetzt einmal geladen und geteilt (schreibgeschützt,
Cache verfällt bei geänderter Datei). 64 Envs brauchen dafür noch 0,12 s.

> ⚠️ Auch hier gilt: Automatisiertes Spielen verstößt gegen die Supercell-ToS
> (Warnhinweis steht im Launcher).

## Setup

```powershell
cd <your-cloned-repo>\icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# GPU PyTorch (needed for training, not for recording) — pick your CUDA build:
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## Step 1 — record your play (do this now)

You just play normally; the recorder captures the game region and logs your
mouse. No phone or tap-overlay needed — on PC your mouse *is* the action.

```powershell
.\.venv\Scripts\python.exe run.py record
```

- Have Clash Royale in its usual Google Play Games window (region in
  `config/config.yaml` is reused from the `trol` calibration — re-check if the
  window moved).
- Play your matches, then press **Ctrl+C** to stop.
- The more matches the better (imitation wants hundreds). You do **not** need to
  track win/loss by hand — `run.py outcomes` reads each match's result off the
  end screen (crowns per team) automatically.

Each run saves a session under `data/sessions/<timestamp>/`:
- `video.mp4` — the game region at `record.fps`.
- `events.jsonl` — every mouse click `{t, x, y, button, pressed}`.
- `meta.json` — fps, region, and per-frame timestamps (to align clicks to frames).

## Config

All tunables in [config/config.yaml](config/config.yaml): `window.region`,
`record.*`, `observation.arena_size`, `action.grid`, `rewards.*`, `outcome.*`,
`env.*` (live RL + tower anchors), `train.*`.

## Status

- ✅ Project skeleton + `record` (screen + mouse capture).
- ✅ `verify` — overlays your logged clicks on a recorded session to sanity-check
  capture, timing, and coordinate mapping (`run.py verify [--session <path>]`).
  `--towers` instead overlays the RL tower-detection anchors on in-match frames
  (green = read alive, red = destroyed; yellow = HP-number crops with the CNN
  read) so you can calibrate tower shaping and the chip-damage reward.
- ✅ `label` — pairs clicks into card plays, **recognizes which deck card** was in
  the selected slot (so the target is card identity, not tray position), and saves
  an `(observation, hand, card, cell)` dataset per session as `dataset.npz`
  (`run.py label [--session <path>] [--all] [--debug]`). Needs card templates first
  (`hand-templates`).
- ✅ `hand-templates` — extracts your deck cards' tray portraits from a recording
  so the hand can be recognized by identity; you rename the crops to deck keys and
  check with `run.py verify --hand` (`run.py hand-templates [--session <path>]`).
- ✅ `outcomes` — auto-detects **win/loss per match** from the 1v1 results
  scoreboard (you = blue/bottom, enemy = red/top; counts gold crowns per
  side). No manual tracking. Writes `outcomes.json` per session and prints the
  W-L record (`run.py outcomes [--session <path>] [--all]`).
- ✅ `train-bc` — CNN behaviour-cloning: trains the policy to predict
  `(card identity, placement cell)` from the observation + hand (the card head is
  masked to the cards actually in hand), checkpoints to `train.checkpoint`
  (`run.py train-bc`). Needs PyTorch (install the CUDA build).
- ✅ `play` — runs the bot live and **fully autonomous**: a scripted state
  machine (reused from trol: `home_menu`/`party_menu`/`in_match`/`match_end`
  templates + button taps) navigates HOME → queue → exit → re-queue, while the
  learned CNN policy plays cards in-match (`run.py play`).
- ✅ `train-rl` — DQN fine-tune of the BC policy on **live matches**. Reuses the
  scripted nav to play match-to-match; reward = per-step **tower shaping** (take
  enemy towers / defend yours) + the **win/loss** terminal reward from the
  results scoreboard. The Q-net is the BC policy reused as a factored
  card/cell Q-function (card values masked to the hand) plus a learned **no-op**
  gate; it saves to
  `train.rl_checkpoint`, which `play` then prefers (`run.py train-rl`).

## Recording note

Record **continuously across many matches, including the menu navigation** — you
do not need to stop between matches. The labeler ignores menu clicks and extracts
only in-match card plays. The policy never has to learn navigation (that's the
scripted layer), so just play naturally and Ctrl+C when you're done for the session.

## Data collection loop

```powershell
run.py record          # play matches, Ctrl+C after the results screen
run.py hand-templates  # ONE-TIME per deck: build card templates from a recording,
                       #   rename each _cand_*.png to its deck key (extra crops of the
                       #   same card: <key>_2.png; evolved face: <key>_evo.png), then
                       #   check with run.py verify --hand
run.py label --all     # (re)build datasets from every recording (needs the templates)
run.py outcomes --all  # auto win/loss record from every recording
```
The policy acts on **card identity** (an evolved card is a **separate identity**
from the normal one), so labeling recognizes which card sits in each tray slot —
that needs `templates/cards/<identity>.png` (e.g. both `tesla.png` and
`tesla_evo.png`), built once per deck with `hand-templates` and verified with
`verify --hand`. Do this before `label`.
More recordings = a better behaviour-cloning start. `label --debug` writes
annotated frames under a session's `labeled/` so you can eyeball the pairing.

## Letting the bot play & train (train-rl)

`train-rl` improves the imitation policy by **playing real matches** and learning
from the reward. It reuses the same scripted navigation as `play`, so it queues,
plays, exits, and re-queues on its own.

**Set up the game interface first:**

1. Open Clash Royale in the **Google Play Games** desktop app, windowed, and
   leave the window where the capture region expects it. The region lives in
   [config/config.yaml](config/config.yaml) under `window.region`
   (`[left, top, width, height]`, physical pixels).
2. Sanity-check capture/coords on your latest recording:
   `run.py verify` (overlays clicks) — if they line up, the region is good. If the
   window moved, re-calibrate the region (reuse the `trol` calibrate step) and
   re-check. To calibrate the tower reward, `run.py verify --towers` overlays the
   tower anchors (green = alive, red = destroyed) on in-match frames. To calibrate
   card recognition, `run.py verify --hand` overlays the recognized card on each
   tray slot (green = recognized, red = not). To calibrate the spell/defense
   rewards, `run.py verify --spells` tints the pixels counted as enemy troops and
   shows the arena `enemy_mass`.
3. Leave the account on the **HOME** screen (the 1v1 battle mode selected, as in
   your recordings). Use a throwaway account and private/friendly matches only.
4. Keep the mouse hand free: **pyautogui failsafe** is on — slam the cursor into a
   screen corner to abort instantly. `Ctrl+C` stops and saves.

**Run the loop:**

```powershell
run.py train-bc      # 1) imitation baseline from your recordings (offline, GPU)
run.py train-rl      # 2) live RL fine-tune; it plays match-to-match, Ctrl+C to stop
run.py play          # watch the current policy (prefers the RL checkpoint)
```

`train-rl` prints a line per match (outcome, reward, W-L record) and checkpoints
to `data/policy_rl.pt` as it goes; stop and resume anytime. Re-run `train-bc`
to reset back to the pure-imitation baseline.

**Reward / tower shaping.** The **win/loss** reward reads the end-of-match
scoreboard crowns, **cross-checked against the towers felled during the match**
(crowns == towers destroyed): the two are combined per side so a crown the
scoreboard misses is recovered from the in-match tower latch (this fixes losses
that used to read as a "draw"), and a felled **king tower** is decisive. The
per-step **tower** reward reads each side's towers by team colour at fixed anchors
(`env.enemy_towers` / `env.my_towers`) and latches a tower "destroyed" only after
a few sustained empty reads. Because the win/loss cross-check now leans on these
anchors too, **calibrate them with `run.py verify --towers`** (green = alive, red
= destroyed). Each match line prints `crowns=b-r`, and `(sb=… tw=…)` when the
scoreboard and tower reads disagree, so mismatches are easy to spot. Set
`env.tower_shaping: false` to fall back to the scoreboard alone.

**Chip-damage reward.** Destroying a tower is rare; most games are decided by
*chipping* the enemy princess (exactly what a rocket-cycle deck does). So each
princess tower's printed HP is read by a small digit CNN (shipped as
`src/clashrl/hp_digits.npz`) and **partial** HP loss is rewarded even when the
tower survives — positive for chipping the enemy, negative for HP lost on yours,
normalized so a full tower's worth of chip equals `rewards.hp_scale`. Per-digit
OCR is only ~92%, but tower HP is piecewise-constant and monotonic, so a value is
only confirmed once it reads the same on `env.hp_consensus` frames — transient
misreads never reach consensus, giving near-zero false damage (it may miss a hit
during heavy occlusion; the destruction latch covers the actual kill). Calibrate
the HP-number crops with `run.py verify --towers` (yellow boxes show the read +
confidence); set `env.hp_reward: false` to disable it. The crops are tight and
calibrated for the standard **Princess Tower** — a tower troop (Cannoneer / Dagger
Duchess / Royal Chef) puts its bar at a different height, so recalibrate the boxes
(and, if needed, re-collect crops and retrain, see [tools/hp_ocr/](tools/hp_ocr/README.md))
from a recording that has that tower type.

**Combat, spell & defense rewards.** HP lost on **your** princess tower is penalised
**gradually** as it's chipped — accumulating up to `|rewards.lose_own_tower|` per tower
(and topped up to it on destruction) — so chip damage costs proportionally rather than a
flat hit only when the tower falls. **Defeating enemy troops** by any means is
rewarded each step by the **signed** change in enemy-troop (red) pixel mass over the
arena (`rewards.troop_defeat`): mass falling (you cleared troops) is positive, mass
rising (a push is building) is negative. It is **potential-based** — symmetric, so it
telescopes over a match and can't be farmed by idling while the enemy army naturally
ebbs and flows. **Spells** add to that: when one is cast, its
effect is sampled over a short window around its **predicted impact**. A rocket's
flight time scales ~linearly with the distance it travels, so the impact moment is
estimated per cast (`rocket_base_time + rocket_travel_rate ×` distance from
`rocket_origin`, capped at `spell_eval_time`); a tornado lands in `tornado_time`.
The most enemy-troop mass seen in the target box during that window is "troops in the
blast", and the reward **scales with the size of the biggest unit caught** — the
largest connected red blob, since one fat unit is a single big blob while a swarm is
many tiny ones. So a rocket that lands on a **group of skeletons/goblins earns little**
(their largest blob is small) while one that catches a **Witch/Bowler/Balloon earns
more** (a big high-HP blob). A caught unit that then dies earns `size × spell_troop_damage`;
one that **survives** earns the smaller `size × spell_hit`; a rocket that hits the
**enemy princess and troops at once** earns a flat `spell_combo` (a value play); a cast
on empty ground is a `spell_whiff` (this is what stops the random throwing / king
activations); aimed at a princess alone is the small tower-HP chip. Waiting while the
board is quiet is **neutral** (the old standing `patience` reward is now `0` — a per-step
bonus for doing nothing was itself an incentive to stall); waiting while a real enemy
push is on the board is penalised (`rewards.idle_penalty`).
This was **calibrated on your recorded casts** (correlating `events.jsonl` cast times
to the frames): the reliable signal is the troop-mass change *at the spell's target in
the seconds after the cast* (not the explosion/ring, which is always present and whose
exact timing is too noisy to detect — hence predicting the impact from distance
instead). Near the enemy princess the target box overlaps the tower's own red, so a
combo needs a clear kill or heavy troop presence (`spell_combo_present`) and the
size-scaling is only applied in the midfield (the blob size is capped at
`spell_size_cap` so a tight clump can't over-score). A tornado's
target-drop is a *pull*, not damage, so only a rocket earns the kill/combo; the
tornado's value (pulling troops off your tower / grouping them for the kill) shows up
in the defence + general-defeat rewards. Tune `env.spell_radius` / `spell_min_drop` /
`defeat_min` and check the detection with `run.py verify --spells` (red = troops);
`env.spell_effect_reward: false` disables the spell part.

**Rocket auto-aim.** Whenever the policy chooses to rocket an enemy *princess* tower,
the target is snapped to whichever of the two princesses has **less remaining HP** (read
by the tower-HP OCR), so the rocket finishes off the weaker tower instead of splitting
chip across both. It only kicks in when both princesses are still standing and their HP
differs — a tie, a downed princess, or a non-princess aim is left exactly as the model
chose. This applies both in live `play` and during RL training (so behaviour matches).

**Range-aware defensive placement (Ice Wizard / Musketeer / Tesla).** When there's a clear
push, these ranged units are placed on the **threatened lane** a **unit's attack reach
behind the enemy front** (`env.range_offsets`, keyed by the card's knowledge-base range) —
so the attackers have to close that gap under fire instead of landing on top of the unit.
The enemy "front" is the deepest enemy troop on that lane; a unit with longer range is set
further back. When there's no clear threat the model places the card itself (so the Tesla
stays free to be reward‑shaped). **Evo Musketeer** always goes to the **very back** for its
charged long-range first shot. Tune `ice_wizard_lanes`, `range_offsets`,
`musketeer_evo_center`, and `defense_threat_frac`.

**Tesla kill reward.** On top of the above, a placed Tesla is credited (`rewards.tesla_kill`)
for the enemy troops it kills near it over its life — a Tesla that survives and keeps
defending keeps earning, which a **central** placement does best. Tune `env.tesla_track_steps`
/ `tesla_radius`.

**King-damage penalty.** Damaging the enemy **king** tower with a spell just wakes it early,
so it's **heavily penalised** (`rewards.spell_king_penalty`). It fires when the king's HP
number shows it took damage (`env.enemy_king_hp_box`, read by the tower‑HP model) **or** the
spell was aimed at the king — discouraging wasting a Tornado/Rocket on the king (e.g. trying
to clip it alongside a princess). Calibrate the king box with `run.py verify --towers` (the
`K` box).

**Winning is the goal.** The terminal `rewards.win` / `rewards.loss` are large (±10) so the
policy is pushed to actually **win matches** rather than farm shaping rewards.

**Chat-icon guard.** The in-match emote/chat icon (bottom-left) opens a wheel that stalls
the bot if tapped, so any card placement that would land on it (`buttons.chat_avoid_box`)
is nudged up out of the way.

> Note: partial HP damage to a troop that survives isn't detectable (no per-troop
> bars), so "damage" is approximated as troops *removed* (killed/scattered).

> Reality check: this is live, one match at a time (~3–4 min each), so RL is slow
> and needs a decent BC start. It's a framework for steady improvement, not a
> quick path to a strong bot.

## Card knowledge base + elixir

A card knowledge base ([config/cards.yaml](config/cards.yaml), loaded by
`src/clashrl/cards.py`) holds per-card attributes — elixir, kind, targeting,
movement, splash, and behaviour flags — for your deck plus common opponent cards.
Inspect it or refresh the stats with:

```powershell
run.py cards          # deck, average elixir, and combat-stat coverage
run.py cards-import   # scrape current level-11 stats from the Clash Royale wiki
```

- **Curated fields** ([config/cards.yaml](config/cards.yaml)) — elixir, targeting,
  splash, behaviour flags, abilities (e.g. Ronin's Parry), and the deck definition
  — are hand-maintained and always win.
- **Combat stats** (hitpoints / damage / DPS / hit-speed at level 11) are imported
  by `cards-import` from **clashroyale.fandom.com** (community-maintained, so it
  tracks recent balance changes) into `config/cards_stats.json`, which the curated
  file overlays. Re-run `cards-import` after a balance update.
- **Champions and Evolutions** are imported too: champion (hero) cards from the
  Champion category, and each card's `<Card>/Evolution` variant keyed `<base>_evo`
  (e.g. `musketeer_evo`). A deck slot marked `evolved: true` overlays the Evolution
  stats, so Evo Musketeer / Evo Tesla show their evolved numbers in `run.py cards`.
- The deck's cards use their **real account levels** (12–16), set per card in the
  deck definition; the imported stats are a level-11 baseline the engine scales by
  card level.

**Elixir** is read from your bar (`Vision.read_elixir`, calibrated in the `elixir`
config) and used to avoid wasting cards while exploring (`train.min_play_elixir`).
Note: only *your* elixir is on screen, so a full **elixir-trade** signal (your
spend vs. theirs) needs identifying the opponent's cards — that's the next stage
(a troop detector trained from your recordings).

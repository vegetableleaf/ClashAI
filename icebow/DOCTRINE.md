# Icebow doctrine — niches, synergies, and the counter catalog

**Status: DRAFT for user review (2026-08-14).** Once approved, each row compiles into a
doctrine-prior exploration rule (the annealed sampling-mixture shape agreed in log.txt
2026-08-14): trigger → our card → a placement distribution over grid cells. Nothing here is a
hard override; greedy eval and live play never see the scaffold.

**Coordinate conventions** (normalized frame coords, the env/sim space): enemy king y≈0.11,
enemy princesses (0.25, 0.205) / (0.745, 0.205), river y≈0.48, our deploy line y≈0.44 (env)
–0.50, our defensive band y 0.52–0.62, our princess line y≈0.615, our king (0.48, 0.72).
Lanes: left x≈0.25, centre x≈0.48, right x≈0.745. "Threat lane" = the lane the enemy unit is in;
"pull side" = 2–3 tiles toward centre from the threat.

**Meta notes (Aug 2026)**: X-Bow shot-wasting fixed this month (net +1.4% DPS — locks stick
better). Evolved Knight and Evolved Royal Recruits are the meta's premier anti-siege tools;
expect bows to be answered harder than the older guides assume. Hero Ice Golem's freeze-blast
was reworked (slow, not freeze) — Hog + Hero Ice Golem is less lethal than early-2026 footage
shows.

---

## 0. Fundamentals — the tier above the catalog

**Added 2026-08-16** after live play showed the model "defending" a lone Skeletons. Everything in
§3 answers *what beats X*; nothing asked *is X worth beating*. These rules run **first**, and the
catalog only applies once they say there is a decision to make.

| # | Rule | The number behind it | Where it lives |
|---|---|---|---|
| F1 | **Triage: is it worth a card?** A Princess Tower kills small things unaided. | `threat_value.ignore_cost_frac` — tower HP lost if ignored, from our own card DB at our tower level. Skeletons **0.4%**, Spear Goblins 1.5%, Bats 2.7%, Ice Wizard 2.9%. 28 cards under 5%; 22 over 20%. | `threat_value.py`; sim = top of `doctrine_cards`, live = `_needs_answer()` in train_rl, **before** the advisor |
| F2 | **Threats add.** Three ignorable units arriving together are one real push. | `group_ignore_frac` sums the group; triage is never per-body | same |
| F3 | **Outrange beats health.** Anything reaching past the tower never enters the trade at all. | Princess, Mortar, X-Bow → **unbounded**, never ignorable however little health they have. The naive model called the Princess free at 0.4% | `ignore_cost_frac` returns `inf` |
| F4 | **Defence is minimising damage, not preventing it** (the 2.6 Hog principle). Taking 200 damage beats overspending; never spend more than the push cost. | `elixir_trade` = *(enemy value eliminated − elixir spent)*, normalised and clipped — this rule priced on EVERY play, not merely described. 41 fires in a 12-match ledger. | **sim: `env._trade_reward`** (this row said "advisor prompt" until 2026-08-23, which understated it); live advisor prompt |
| F5 | **Cheapest card that works; keep the answer** to their win condition in hand. | — | advisor prompt |
| F6 | **Hold is a play.** The advisor may decline to spend. | Was structurally impossible: the reply schema was `enum=hand`, so the grammar forbade what the prompt asked for | `llm_advisor.HOLD` |

## 1. Card niches

| Card | Niche | Key facts the rules lean on |
|---|---|---|
| **X-Bow** | The win condition. Two modes: OFFENSIVE (your side, behind-bridge or centre-front, locks the princess at ≤11.5 tiles) and DEFENSIVE (centre band, acts as a second pull building). | Deploy 3.5 s — everything about protecting it happens in that window. Off-lane bows must sit on the frontmost row or the diagonal is out of reach (measured in env comments). |
| **Tesla (Evo)** | Core defensive building; pulls every building-targeter; evo adds a periodic stun pulse + 25 s life. | Hidden underground between shots: untargetable by spells mid-cycle, wastes single-target locks (Inferno). Centre placement drags wincons across both towers' fire. |
| **Ice Wizard** | Permanent-value defensive support: −35% attack/move slow, small splash. | Almost never the kill — he's the multiplier. Behind the engagement, out of spell-stack range. Survives Log; dies to Fireball+chip. |
| **Tornado** | Displacement: clump (for IW splash/Tesla pulse/Rocket), king activation, drag units off a lock, ruin charge lines. | Pulls AIR too (Balloon→king works). Cannot damage-kill anything alone; a naked nado on a single tank is wasted. |
| **Knight (Evo)** | Mini-tank, body-blocker, X-Bow bodyguard. Evo: −60% damage taken while NOT attacking. | The evo walk-tank: while walking (kited, not swinging) he absorbs entire pushes. Body-block works on building-targeters via collision even though they won't retarget him. |
| **Skeletons** | 1-elixir cycle + surround-DPS + triangle distraction. | 3 bodies kill a distracted single-target melee shockingly fast under tower. The cycle card TO the Rocket/X-Bow. |
| **The Log** | GROUND-ONLY swarm floor-clear, knockback/charge-reset, bait answer, last-resort chip. | Rolls 9.6 tiles: cast from your side, reaches their chip range. Knockback resets Prince/Ram charges and shoves units off the X-Bow for one more shot. **Never a rule vs air** (bats/minions/dragons/balloon are untouchable). |
| **Rocket** | The second win condition (defensive phase): tower chip + heavy removal. | Value rule: tower + ≥4-elixir support in one blast = always fire. Pump within 12 s of placement = always fire (unless king-adjacent). |

## 2. Internal synergies

| Synergy | Geometry | What it buys |
|---|---|---|
| **Tesla + Tornado** | Nado clump at (threat_x→centre, 0.55); Tesla already centre | Whole push eats pulse + both towers; the deck's core defensive engine |
| **Ice Wizard + Tornado** | Nado clump; IW 3–4 tiles behind at (0.48, 0.66) | Entire push slowed at once — buys the towers 2× time |
| **Rocket + Tornado** | Nado at (x, 0.55) first, Rocket onto the clump ~1 s later | Push erased; vs 3M-class clumps it's game-winning |
| **Tornado → King activation** | Nado pulls a melee/tower-bound unit to (0.48, 0.70) | Permanent extra tower for the match; icebow's defense scales up forever |
| **Knight in front of X-Bow** | Bow at lock spot; Knight 1 row ahead (bow_x, bow_y−0.04) | Answers get body-blocked; evo Knight barely takes damage until he swings |
| **Ice Wizard behind X-Bow** | (bow_x±0.06, bow_y+0.08) | Slows everything sent at the bow; out of one-spell range of it |
| **Log ahead of a locked X-Bow** | Cast at the GROUND defenders walking onto the bow (air answers are IW/pulse's job) | Knockback = 1–2 more bow shots; resets charges |
| **Skeletons + Tesla** | Skels ON the attacker at the Tesla | Surround DPS while the pull holds aggro |
| **Evo Knight walk-tank + IW slow** | Knight placed to WALK across the push, IW behind | Near-zero-damage defense vs mid pushes |
| **X-Bow + Tesla double-building** | Defensive bow (0.48, 0.55) + Tesla (0.48±0.05, 0.58) | Two pulls: RG/Hog never touches a tower |

## 3. Counter catalog

Feasibility: **S** = sim rule possible now (engine ground truth), **S+** = needs a new placement
helper (small), **L** = live-limited (detector must name the card; class-level fallback noted).

### 3a. Ground building-targeting win conditions

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 1 | **Hog Rider** | Tesla | Centre band (0.48±0.04, 0.56) | As he crosses the bridge, not before | +1 trade or better; Skels behind him if Tesla down | S |
| 2 | Hog Rider (Tesla out of cycle) | Knight body-block + Skels | Knight ON his path at (hog_x, 0.60); Skels surround | Block first, surround second | Accepts ~1 hit; cheaper than tanking 3 | S+ |
| 3 | Hog Rider (king asleep, nado in hand) | **Tornado → king** | Nado destination (0.48, 0.70) | The moment he commits past the bridge | The classic activation — highest-value single play the deck owns | S |
| 4 | **Ram Rider / Battle Ram** | Log first, then Tesla | Log INTO the charge (head-on, threat lane); Tesla centre band | Log while charging = reset | Never let a charged ram connect with a tower/bow | S |
| 5 | **Giant** | Tesla pull + Skels surround + IW | Tesla centre; Skels on his back; IW (0.48, 0.66) | Tesla early (he's slow); support later | Kill the SUPPORT with Log/Rocket math, not the Giant first | S |
| 6 | **Royal Giant** | Tesla + defensive X-Bow (second building) | Tesla (0.44, 0.56); def. bow (0.52, 0.55) | Tesla at his bridge commit; bow only if he's supported | Evo RG: expect one recoil knockback — place buildings deeper (0.58) | S |
| 7 | **Golem (placed behind their king)** | **Opposite-lane offensive X-Bow immediately** + minimal defense later | Bow at behind-bridge lock (opp_lane_x, 0.50) | The instant the Golem lands (8-elixir window) | The repo's punish rule; do NOT out-tank a golem push — out-tempo it | S |
| 8 | Golem push arriving | IW + Tesla + nado-clump the support behind the Golem | Nado at support, NOT the golem; IW behind | Support first — golem alone can't kill you fast | Rocket the clumped support if ≥2 mediums | S |
| 9 | **Elixir Golem** | Do NOT kill it early; IW slow + towers; Rocket the support pumping behind | IW (0.48, 0.64) | Let the tower work; nado blobs together only WITH IW/pulse up | Killing it fast feeds their Healer/NW golemites | S |
| 10 | **Miner** (on tower) | Skeletons surround (3-body triangle) | (miner_x±0.03, miner_y±0.03) around him | Within 1 s of him popping | +2 trade every rotation; IW if skels out of cycle | S/L |
| 11 | **Goblin Drill** | Skels ON the drill spawn + Log the gobs | On the emerging spot | On emerge | Tesla too slow here; keep Log for the pop | S/L |
| 12 | **Wall Breakers** | Log head-on | Into their path, your half | Immediately — they're fast | Never tank WBs with Knight (they target buildings… they'll pass him) | S |
| 13 | **Royal Hogs (split or single)** | Split answer: Tesla centre + Log the wider pack; single-lane: Tesla + skels | Tesla (0.48, 0.56) exactly centre so it pulls BOTH lanes | On bridge commit | This deck's structurally hardest wincon (with Recruits); play for even trades + rocket chip wins | S |
| 14 | **Hog + Earthquake** | **Anti-EQ Tesla spot** + Knight/Skels carry the rest | Tesla at the "(0-3)" spot: centre column, ~3 tiles from the river ≈ (0.48, 0.545) — one tile SHALLOWER than the standard 4–5-tile pull spot | Tesla on his bridge commit, as usual | EQ players anchor the quake at the princess's INNER CORNER extending centre-ward, which catches the princess AND every standard-depth centre Tesla. The (0-3) spot sits above that region, still pulls the Hog, and the same placement dodges Lightning/Poison value (Theria Tesla guide). Match-flag once EQ seen: all Teslas use the anti-EQ spot; Knight block (#2) when Tesla is out of cycle | S (match-flag) |

### 3b. Air win conditions

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 15 | **Balloon** | Tesla pull + IW slow | Tesla centre band; IW under its path (loon_x−0.05, 0.60) | Tesla BEFORE it crosses (deploy time!) | Slowed loon dies to tower+Tesla before dropping ≥2 bombs. LAST RESORT ONLY: Rocket it mid-flight when Tesla AND nado-king are both unavailable — 6 elixir on one unit is a losing habit, acceptable only against a connected bomb | S |
| 16 | Balloon (Tesla dead/out) | **Tornado → king** + IW | Nado destination (0.48, 0.70) | As it passes your princess line | King + princess + IW shred it; death-bomb lands on king (fine) | S |
| 17 | **Lava Hound** | Ignore the hound; Rocket/IW the pups + support | IW centre-back; Rocket on Loon if Lavaloon | Rocket timed for pup-pop clump | Hound alone = 0 threat; never Tesla a hound (waste) | S |
| 18 | **Lavaloon** | Rocket the Balloon + pups mid-flight; nado leftovers to king | Rocket lead: aim (loon_x, loon_y+0.05) | When loon+pups stack after hound pops | The only clean answer this deck has — bank 6+ elixir vs lava decks | S+ |
| 19 | **Skeleton Barrel** | Log the SPAWNED skeletons (the barrel itself is AIR — the Log never touches it) | Rolling through its flight end-point | Timed so the roll arrives as it pops | Pre-log beats post-log; Tesla/tower handle the barrel body | S/L |
| 20 | **Miner + Balloon** | Skels on Miner, Tesla/nado-king on Loon | Split answers, never stack them | Miner first (he tanks tower) | The nado-king line is mandatory if Tesla is out of rotation | S+ |

### 3c. Swarms & bait

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 21 | **Goblin Barrel** | Log the landing | Predicted landing spot (tower centre) | As the barrel is mid-flight | If Log is baited out: skels pre-placed ON the tower eat it | S/L (projectile read) |
| 22 | **Skeleton Army** | Log | Through the pack, rolling toward more of them | Immediately | Log is THE answer; IW splash secondary | S |
| 23 | **Goblin Gang** | Log (kills stabbers, hurts spears) + tower | Through the pack | Immediate | Don't rocket gangs — Log trade is +1 | S |
| 24 | **Minion Horde** | IW + Tesla pulse + tower; nado-clump into IW | IW behind Tesla; nado at (horde_x, 0.55) | Nado only when they've committed onto a target | No Arrows in this deck: IW is the horde answer — protect him | S |
| 25 | **Bats/Minions on Tesla or X-Bow** | IW splash + evo-Tesla pulse (AIR: the Log cannot touch them) | IW within 3 tiles of the building | Fast — bats melt buildings | This is WHY IW shadows every bow push; vs air swarms IW is the only splash we own | S |
| 26 | **Log-bait package (Princess/Gang/Barrel/Rascals)** | Rotation discipline: Log ONLY on Barrel or Princess-on-bridge; skels eat Barrel when Log is cycling | — | — | Track what the Log is FOR each rotation (match-flag: bait deck seen) | S (flag) |
| 27 | **Princess at the bridge** | Log her (exact range); Rocket-include her in tower chip; or **Skeletons ON TOP of her once she's tower-locked** | Log cast reaching her (roll covers 9.6 tiles); skels at (princess_x, princess_y) | On her first shot; skels any time AFTER she locks the tower (locked = she won't retarget them before they connect) | Never let princess chip free; the skels line mitigates her damage while the Log is mid-cycle | S/L |

### 3d. Bridge threats & assassins (the anti-siege package)

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 28 | **Prince / Dark Prince** | Log the charge → Knight block → Skels surround | Log head-on; Knight on-path | Log DURING charge windup | Charged prince into a bow/tower is a disaster; always reset first | S |
| 29 | **Bandit** | Skels bait the dash + Knight | Skels 2 tiles ahead of her dash line | Bait first (she's invuln mid-dash) | Never IW-first into a dash | S/L |
| 30 | **Mega Knight (on our bow or bridge)** | Skels triangle + Knight walk-tank + IW; NEVER clump | Spread: skels (x±0.05), knight ahead, IW 4 tiles back | Skels first (eat the jump), then knight | Rocket him only when he stands with ≥1 support in blast | S |
| 31 | **PEKKA sent at the bow** | Kite her CENTRE with Knight/skels + IW slow | Kite bait at (0.48, 0.62) walking away from the bow lane | The moment she targets the bow | Bow survives if she's dragged 3+ tiles off-path; she never reaches the tower after | S+ |
| 32 | **Evo Knight walking at our bow** (meta's #1 bow answer) | Tesla pull + skels BEHIND him (he takes full damage only when swinging) | Tesla centre; skels at his back | Force him to keep walking through damage | His DR is only while not attacking: make him ATTACK the Tesla | S |
| 33 | **Fisherman** (hooks the bow) | Pre-empt: bow placement 1 row back vs fisherman decks; Log him on approach | — | — | Match-flag once seen | S (flag) |
| 34 | **Royal Ghost** | Skels/Knight placed IN his path (forces materialise) + tower | On-path, your half | While invisible: only body-blocks reveal him | IW can't target him invisible | S |

### 3e. Support & backline (rocket/log math)

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 35 | **Musketeer / E-Wiz / Wizard behind a tank** | **Rocket the support + tower when aligned**; else nado support INTO the tank then IW | Rocket aim = support centre clipping tower if ≤2 tiles gap | When they enter tower-blast alignment | The 2-for-1 rule already coded (rocket_combo); nado-merge feeds Tesla pulse | S |
| 36 | **Witch / Night Witch** | Log the spawn stream + Knight on her | Log through skels/bats to her; Knight on top | Early — spawn value compounds | Never skels into witch splash | S |
| 37 | **Sparky** | Nado her ACROSS the river centre + Rocket, or Skels surround to eat the shot + Knight | Nado to (0.48, 0.50); skels triangle | Rocket while she's nado-dragged (can't fire) | Evo Tesla stun also resets her charge | S+ |
| 38 | **Inferno Tower/Dragon on our bow** | Evo Tesla pulse resets it; skels distract (the Dragon retargets ground); IW slows its beam ramp | Tesla adjacent to bow; skels between bow and inferno | Immediately on lock | The stun-reset is why Evo Tesla shadows offensive bows vs inferno decks. (Dragon is AIR — no Log; skels+pulse+IW is the whole kit) | S |
| 39 | **Executioner / Bowler / Baby Dragon** | Don't clump! Tesla pull + tower, IW OFF-axis | IW at ±0.10 lateral offset from the splash line | — | These exist to punish our clumps; spacing IS the counter | S+ |
| 40 | **Magic Archer on bridge** | Log him (exact kill at level parity) or Knight on top | Log reaching his spot | Before he lines up tower | Free chip if ignored | S/L |
| 41 | **Firecracker** | Log as she jumps back; ignore + rocket-include later; or **king-activation bait**: Knight/Skels placed so her shrapnel splashes the king | Bait unit at 4 tiles in front of the king, 2 tiles inside the princess tower ≈ (0.35, 0.63) left / (0.61, 0.63) right; Tornado-dragging her aggro to the king also activates | Bait placed while she's approaching/locked our half | The activation is worth far more than the FC herself — permanent king for one cheap card. Confirmed tech (zleague/TikTok guides): "works with most units" | S+ |
| 42 | **Hunter** | Keep distance: IW + tower; never Knight INTO him point-blank | IW at max range | — | His point-blank burst kills mini-tanks | S |
| 43 | **Archer Queen (invisibility)** | Skels to waste the ability + Tesla; Rocket if she stalls with support | Skels on her, Tesla centre | After her ability pops | Match-flag: champion seen | S/L |

### 3f. Spells, buildings, siege mirror, economy

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 44 | **Fireball/Poison decks** | SPACING doctrine: Tesla, IW, and bow never within one blast radius of each other | Offsets ≥0.12 apart | Standing rule | The anti-spell formation is a PLACEMENT prior, perfect for the doctrine mixture | S |
| 45 | **Earthquake seen** | Building-lean OFF for the match (see #14); Knight/skels carry defense | — | Match-flag | | S (flag) |
| 46 | **Lightning deck** | Never 3 medium targets in one 3.5-tile circle near the bow | Spread supports | Standing rule | | S+ |
| 47 | **Rocket mirror / their Rocket on our bow** | Bow placements hug the EDGE column so their rocket can't clip tower+bow | Bridge-edge lock spots (0.16/0.84, 0.50) | Standing rule vs rocket decks | Measured: Hunter's lane bows sit at 0.16/0.84 — this is why | S |
| 48 | **Enemy X-Bow (mirror)** | OUR X-Bow placed to outrange/trade + Rocket theirs when it locks + Knight blocks theirs | Counter-bow at (their_x, 0.52) | Immediately | Whoever defends cheaper wins; rocket math decides | S |
| 49 | **Mortar** | **Knight INTO the 3.5-tile blind spot** (forces it to lose the lock/retarget) + skels chew it; a near-bridge Tesla both absorbs the retargeted lock AND out-shoots a bridge mortar | Knight walks inside 3.5 tiles of it (drop at bridge edge, he enters the blind zone); Tesla at (0.48, 0.52–0.54) if it's a bridge mortar | Knight immediately on mortar placement, BEFORE its first shell lands on the tower | Mortar cannot hit anything inside 3.5 tiles (blind spot, buffed to 3.5 in 2018); a unit entering it forces retarget — the classic RG-in-blind-spot tech, ours is Knight. Distraction-at-distance also works but costs more time. Never let it free-chip | S |
| 50 | **Elixir Collector** | **Rocket it within 12 s** (+princess clip if aligned; never king-adjacent) | Already coded (pump punish) | Fresh pump only | | S (exists) |
| 51 | **Graveyard** | IW ON the tower + skels perimeter + nado skeletons to KING (activation + kill) | IW at (tower_x, tower_y+0.03); nado (0.48, 0.70) | IW pre-emptive at their 9 elixir if GY seen | Poison-bait discipline: don't stack IW+skels | S+ |
| 52 | **3 Musketeers** | **Nado all three together + Rocket** | Nado midpoint of the split; Rocket the clump | As they split at their deploy | The named RoyaleAPI line for this deck; game-winning trade (+5) | S+ |

### 3h. Midladder heavies — the ~10k-trophy package (added 2026-08-14)

**Macro read**: midladder decks stack several 5–8 elixir cards (Mega Knight, PEKKA, Boss Bandit,
E-Barbs, Wizard/Witch walls) around one over-levelled win condition, and they OVERCOMMIT. That is
structurally GOOD for icebow: measured community data has X-Bow siege at **~65% win rate vs Mega
Knight decks** (he cannot reach a bow 11 tiles back — they must commit their secondary wincon,
which we out-building). Doctrine consequences: the opposite-lane punish window (#7/#53) opens far
more often; the rocket 2-for-1 (#35) is near-constant value because midladder clumps supports in
one blast radius; and our anti-spell spacing (#44) matters double because their spells chase our
clumps. Meta note (2026): decks carry exactly 1 Evolution + 1 Hero + 1 Wild slot since the March
rework; `_hero` variants hit a tier harder than base — the detector folds them onto base keys, so
every rule below applies to the hero versions automatically.

| # | Threat | Answer | Placement | Timing | Notes | Feas. |
|---|---|---|---|---|---|---|
| 58 | **Mega Knight** (dropped on our defense/bridge) | NEVER clump. Skels eat the spawn/jump + Knight walk-tank + IW from range; kite him CENTRE | Skels spread at his landing; Knight ahead walking; IW ≥4 tiles back | Skels FIRST (absorb the jump), knight second | He takes damage MID-JUMP (no i-frames, unlike Bandit/GK) — Tesla keeps shooting through it. Kill his support with Log/Rocket; MK alone chips slowly | S (jump not modeled in sim — approx. as heavy melee) |
| 59 | **MK king activation — PRIMARY line (Skels → Knight, no Tornado)** | Skeletons bait his jump, then **Knight placed in front of the king immediately before/after he jumps onto the skels** — his next jump/slam splash clips the king | Skels at ~4 tiles from the king in his lane; Knight at (0.48±0.06, 0.66–0.68), directly in front of the king | Knight timed to the jump onto the skels (just before or just after) | User-verified in play + community-documented ("5 ways without tornado"; cheap-troop chains: skels/ice-spirit/spear-gobs). 2 elixir + Knight for a permanent king vs their 7-elixir card | **L** (live-only: the sim engine has no jump-slam splash) |
| 60 | MK king activation — Tornado alternative | Cheap bait holds him in front of the crown tower (inner side), Tornado pulls him to the king; his slam splash activates | Bait at (tower_x±0.08 toward centre, 0.63); nado destination (0.48, 0.70) | Nado as he winds up on the bait | Use when the skels→knight chain timing is missed or knight is out of rotation (3 elixir nado vs 1+3 chain) | **L** |
| 61 | **PEKKA deck** (their MK answer piloted as beatdown) | Kite her CENTRE off the bow (#31); kill her SUPPORT with Rocket; never Rocket the PEKKA herself | Kite bait (0.48, 0.62); rocket the support line behind her | Bait the moment she targets our bow | 6 elixir for partial HP on a 7-cost tank is losing math — her support dying is what stops the push. She cannot catch a kited bow | S+ |
| 62 | **Elite Barbarians** | IW slow + Log knockback + Tesla + tower | IW early on their lane (0.48±0.1, 0.64); Log head-on as they cross; Tesla centre band | Log INTO their sprint | Never face-tank with Knight alone (they shred mini-tanks); slowed+logged E-Barbs die to towers for +1 | S |
| 63 | **Wizard / Witch / E-Wiz support wall** | Rocket the wall + tower when aligned (#35); else nado-merge INTO the tank and IW | Rocket centred on the support cluster clipping the tower | The instant two supports overlap one blast | Midladder stacks supports — this is the highest-frequency rocket value in the bracket | S |
| 64 | **Valkyrie on our bow/Tesla** | Skels BEHIND her (her spin can't cover bow + backside), Tesla pull, IW at range | Skels at her back (valk_x, valk_y+0.05); never IW adjacent | — | Spin punishes clumps; attack her from two sides at range | S |
| 65 | **Boss Bandit** (champion — VERIFIED mechanics) | Dash triggers on targets in her **3.5–6 tile window** (0.8 s windup, DOUBLE damage). Ability = **Getaway Grenade**: 1 elixir, invisible 1 s, teleports **6 tiles backwards**, usable 2× (3 s cooldown) — she teleports out then RE-DASHES the same target, which the teleport put back in her dash window. **The counter: keep a body INSIDE 3.5 tiles of her post-teleport landing** — nothing in the window, no dash, she walks like a normal troop | Skels bait the first dash 2–3 tiles ahead of her line; after her teleport, drop skels/Knight ON her landing (~6 tiles behind where she vanished); Tesla pull continues | Bait → she dashes (i-framed) → expect the grenade → smother the landing | The re-dash denial converts her 7-elixir kit into an overpriced Bandit. Two grenades max, then she has no escape | **L** for the teleport-smother (ability not in sim); base bait/block handling = S once she's in the meta pool |
| 66 | **Electro Giant** | Kill from RANGE only: IW + tower + Tesla pull; Rocket his support; NEVER melee-swarm his front | IW/Tesla outside his zap reflex radius; skels only at his BACK | Tesla early (he's slow) | His reflect punishes everything adjacent — the ranged-only rule is absolute; he IS a building-targeter so Tesla pulls him off-lane | S |
| 67 | **Prince + Dark Prince double charge** | Log resets BOTH charges in one roll; Knight block; skels only AFTER DP's shield/splash is spent | Log head-on through both; Knight on-path | Log during their charge windup | Never skels-first (DP splash erases them); a reset double-prince dies to Tesla+tower | S |
| 68 | **Balloon + Rage/Freeze midladder** | Tesla pre-position + the nado-king line (#16); EXPECT Freeze on the Tesla — hold Skels as the post-Freeze backup | Tesla centre band EARLY; skels queued for the freeze window | — | Freeze-on-Tesla is the midladder killshot; the held skels + IW bridge the frozen seconds | S (freeze modeled) |

### 3g. Offense execution (when WE attack)

| # | Situation | Play | Placement | Notes | Feas. |
|---|---|---|---|---|---|
| 53 | Opponent spent ≥7 elixir away from our bow lane | Offensive X-Bow | Behind-bridge lock (0.26/0.73, 0.50); centre-forward (0.42–0.58, 0.46) only on the front row | The punish window (coded); Knight ready behind | S |
| 54 | Bow is deploying (3.5 s) | Pre-shield | Knight at (bow_x, bow_y−0.04) BEFORE their answer lands | The deploy window is when bows die | S+ |
| 55 | Their building drops to pull our locked bow | Log/nado their building's pull OR accept + rocket chip | Nado drags their DEFENDER off, not the building | Kill-the-defender beats fight-the-building | S+ |
| 56 | 2×/3× elixir, no breakthrough | Rocket-cycle mode (coded) + defensive bow only | Rocket weaker princess; bow (0.48, 0.55) | The phase machine exists; doctrine adds: keep ONE spell always in hand | S |
| 57 | Both princesses even HP | Rocket the one their DECK defends worse (fewer buildings that side) | — | Tie-break beyond current weaker-HP snap | S+ |

---

## 3b. Evolution addenda (2026-08-14 — Phase C; all 42 evos now modeled in sim)

How the evolutions CHANGE our answers. Rows keyed to the counter catalog's numbering style.

| # | Threat (evo) | What changes vs the base counter | Our line |
|---|---|---|---|
| E1 | **Evo Royal Giant** (recoil 81 / 2.5 t / 1-t shove, air immune) | Swarm-ON-TOP dies: skels placed inside his recoil ring get blasted + shoved every shot | Skels BEHIND him (outside 2.5 t of his body), Tesla pull stays king; Ice Wizard outranges the ring entirely |
| E2 | **Evo Mega Knight** (uppercut: victim launched 4 t toward OUR tower, then he re-jumps) | The kite-centre knight gets punched INTO our side — the kite walk must start deeper so the launch doesn't gift him a jump onto the tower | Kite spot moves ~2 t deeper (0.48, 0.68); skels-bait + knight king-bait chain unchanged (uppercut on a 1-elixir skel is a win); NEVER tank the uppercut next to our princess tower |
| E3 | **Evo E-Barbs** (284 javelin every 5 s, hits crowns; rage trails) | They chip towers from range and self-rage crossing their own trails — pure kiting leaks tower hp | Answer FAST and off-trail: Tesla pull + IW slow (slow counters the rage tempo); do not path our counters through the glowing lanes |
| E4 | **Evo Valkyrie** (0.5 s whirlwind, 5.5 t pull, air too) | Her spin drags our skels/IW INTO her splash — spaced defense collapses inward | IW from ≥6 t (outside the pull), skels only AFTER her swing lands (0.5 s window), Tesla pull is immune (building) |
| E5 | **Evo Zap** (3 growing rings, 1 s apart) | Our skels die to ring 1 AND the re-cycle dies to ring 3 — don't re-drop skels into the ring sequence | Wait out the third ring (~2 s) before recommitting swarm; Tesla eats all three stuns but keeps lock resets in mind |
| E6 | **Evo Musketeer** (3 infinite-range snipes at 1.8×, only when idle-ranged) | She snipes our Ice Wizard/back-line from across the arena while walking | Deny her idle range: engage her with knight quickly or keep IW BEHIND towers until her 3 rounds are spent (count them) |
| E7 | **Evo Hunter** (net roots 3 s every 5 s) | Our kiting knight gets rooted mid-kite and shredded point-blank | Kite with skels instead (1 elixir to eat the net), knight commits only inside the 5 s net cooldown window |
| E8 | **Evo Witch** (heals 109 per friendly bone death, overheal 130%) | Rocket math changes: an overhealed witch (1035) survives rocket (863) | Rocket her BEFORE her skels die en masse (early push phase), or finish with Log after; our own skels feeding her heal is a real anti-synergy — prefer Tesla/IW answers |
| E9 | **Evo Wizard** (shield burst 281 + 3-t shove on break) | Skels that break his shield get blasted + scattered — the surround dies at the break moment | Break the shield with TESLA/IW/log FIRST, then swarm; never let the shield break inside our skels |
| E10 | **Evo Bomber** (bombs bounce 2.5 t twice) | His bounces reach our Tesla BEHIND the tank he targets — the standard center Tesla eats chip | Offset Tesla laterally from his approach line; knight ON TOP of him (bounces fly past, not around) |
| E11 | **Evo Firecracker** (spark trails: 192/60 dps zones, 15% slow) | Her spark carpets zone our skels' path to her | Approach off-line (lateral knight), or tank the small-spark lane (60 dps) never the carrier lane (192) |
| E12 | **Evo Skarmy** (shielded General; skels ghost while he lives) | Log alone no longer clears — ghosts keep chewing until the General dies | Log THE GENERAL's cluster first (shield 240 + 219 hp needs log + one Tesla zap), or IW slow + tower fire; ghosts vanish with him |
| E13 | **Evo Goblin Barrel** (mirror decoy barrel, 3 decoys) | Two lanes light up at once; decoys are 81 hp paper but 89-dmg real threats | Log the REAL side (watch the throw origin lane), tower + one skel eats the decoy side |
| E14 | **Evo Skeleton Barrel** (75% mid-drop, both barrels on arrival) | Shooting it down early now costs 7 skels mid-lane + 7 more at death | IW the barrel (slow + splash kills the drop), Tesla ignores it (air) only if IW is rotating |
| E15 | **Evo Battle Ram** (bounces and re-rams until dead) | One Tesla pull no longer ends it — it re-charges from the bounce | Kill the RAM'S HP, not its charge: Tesla + skels sustained; breaking it spawns EVO barbs (self-raging) — keep IW for the barbs |
| E16 | **Evo Royal Hogs** (airborne until they attack/get hurt) | Ground-only answers (skels, log) whiff the approach phase | Tesla and IW both hit air — either touch drops them to ground, where log/skels resume normal service |
| E17 | **Evo PEKKA / Evo Inferno D** (kill-heal / stage-keep) | Feeding 1-elixir skels now HEALS her (470/kill) or preserves his ramp | Do NOT drip-feed singles: bulk value trades only (knight), Tesla pull + rocket on the support behind |

## 4. Standing placement priors (the always-on shape hints)

1. **Defensive band discipline**: buildings at y 0.52–0.62, centre-biased; never deeper than 0.62 unless EQ-flag.
   > ⚠️ **MEASURED CONFLICT (2026-08-16) — needs your call.** Every guide says the centre pull's
   > payoff is that *both* princess towers reach the pulled unit. On this engine (8.0-tile reach,
   > towers at y 0.7969) that starts **3.69 tiles from the river**, and after the 24-row grid
   > quantises it, **row 15 (y 0.6458, 4.67 tiles) is the shallowest double-covered cell — row 14
   > (0.6042) is covered by neither tower.** So "never deeper than 0.62" and "both towers cover"
   > cannot both hold: there is no compromise cell on this grid.
   >
   > Worse, the existing Tesla pull spot (0.48, 0.585) is **8.51 tiles from both** towers — outside
   > each — so the rule named for the centre pull was collecting the pull and none of the crossfire
   > meant to pay for it.
   >
   > Not silently overridden. The row-15 spot is added **alongside** the shallow one at a comparable
   > weight so PPO samples both and the reward arbitrates — the trade (deeper buys crossfire,
   > shallower stops the push further out) is not decidable from geometry. Suppressed under the
   > EQ-flag, where the shallow spot exists precisely to dodge their quake region.
2. **Anti-spell spacing**: our defensive trio never within one fireball radius (0.12) of each other (#44).
   Now also enforced against **their** spells: a structure is down-weighted where one cast would
   cover it *and* a princess tower. Exact, since a circle of radius r covers two points only within
   2r — radii read from the engine's own specs (rocket 2.0, fireball 2.5, lightning/poison 3.5
   tiles), never transcribed, so they cannot drift apart from the sim.
3. **Lane bows at the edges** vs rocket/spell decks (#47); centre-forward bows only on the front row.
4. **IW default depth**: 0.64–0.68, behind whatever is tanking; never first.
5. **Skeletons cycle spot**: back corners (0.10/0.86, 0.85+) when cycling; ON the target when defending.
6. **Nado destinations, not positions**: king (0.48, 0.70) for activation; centre-band (0.48, 0.55) for clumps; never on a lone tank.

## 5. Sources

- RoyaleAPI deck page for this exact list (matchup framing: beats hog cycle, struggles vs heavy beatdown/RG/split-lane): royaleapi.com/decks/stats/ice-wizard,knight,rocket,skeletons,tesla,the-log,tornado,x-bow
- Clash Royale Wiki: Deck:3.5_IceBow_Updated, Deck:X-Bow_Ice_Wizard_Control, X-Bow card page
- Theria Games X-Bow and Tesla guides (Tesla centre-pull, reactive-not-preplaced doctrine)
- Supercell August 2026 balance notes (X-Bow shot-wasting fix; Hero Ice Golem rework) + thephrasemaker.com August 2026 balance explainer (Evo Knight / Evo Recruits as anti-siege)
- Repo measurements: Hunter CR mined response matrix (log.txt 2026-08-12 night), his X-Bow placement/timing distributions (53% offensive both-lane bridge spots at 0.16–0.27/0.73–0.84 × y 0.50; 25% defensive band 0.42–0.63 × 0.56–0.59; ~5.4 bows/match, re-bow median 24 s; phases 1x 39 / 2x 32 / 3x 5)
- User-review corrections (2026-08-14): anti-EQ Tesla "(0-3)" spot confirmed via Theria Tesla guide; Firecracker king-activation bait geometry via zleague.gg + TikTok tech guides; Mortar 3.5-tile blind-spot/retarget mechanics via Clash Royale Wiki + clash.world Mortar guide; Log ground-only purge; Rocket-on-Balloon demoted to last resort; skels-on-locked-princess mitigation added
- **Defensive fundamentals sweep (2026-08-16)** — the §0 tier. ClashDecks (top-5 defensive tips; elixir management 101; counter-push mechanics with opponent-elixir thresholds 0-3/3-5/6+/full; control-deck mastery), clashroyalearena.com common-mistakes and deploying guides, jeu.video "defend for less" (spend only what the attack requires; a few points of tower damage do not justify a second troop and a spell), clashroyale.wiki kiting guide, 2.6 Hog guides ("the art of 2.6 defence is minimising damage, not preventing it"; 4-3 vs 4-2 against jumping win conditions; 3-3 vs Mega Knight), sportskeeda win-condition/bridge-spam/graveyard defence guides, Fandom building-placement blogs (X-Y convention; 7-2/7-3 dodges Rocket value, 2-3/3-4 dodges Fireball, 4-6/3-5 dodges Lightning/Poison), highgroundgaming archetype guide, elixir-rate references (1 per 2.8s / 1.4s / 0.933s).
  The recurring finding: **every fundamental is stated as prose or as a tile number to memorise, never as something computable** — so §0's numbers come from our own card DB and the engine's geometry instead, which is how the 8.51-tile pull-spot error surfaced.
- Midladder package (3h, 2026-08-14): X-Bow ~65% WR vs Mega Knight + kite-centre/mini-tank-plus-DPS counters via TrophyCoach, gamerant, androidayuda MK guides + Clash Royale Wiki (MK takes damage mid-jump, no i-frames); MK king-activation lines (Tornado pull-to-king; two-jump bait chain: unit 4 tiles from king +1 into his lane, then skels 1 tile from king pre-second-jump) via TikTok tech guides (mauticlive et al.); 2026 meta context (Hero powers + March deck-slot rework: 1 Evo/1 Hero/1 Wild) via lootbar/ldshop/kingboost/trophycoach 2026 meta articles. Boss Bandit mechanics NOT reliably documented -- row 65 marked for in-game verification.

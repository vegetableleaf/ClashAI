# Hog Earthquake doctrine — card roles, synergies, and the counter plan

**Status: DRAFT, 2026-08-17.** Written from research at the deck switch; nothing here has been
compiled into sim rules yet. The icebow doctrine that used to live in this file is preserved in
`../icebow/DOCTRINE.md` and does not apply — this deck wins a different way.

**Deck (Classic 1v1, real account levels):** Hog Rider 13, Evo Firecracker 13, Mighty Miner 14
(champion), Evo Tesla 14, The Log 14, Earthquake 13, Skeletons 15, Ice Spirit 13.
Average elixir **2.75** (classic 2.6 with Mighty Miner in the Knight's slot).

**Coordinate conventions** are inherited unchanged from the icebow doctrine: normalised frame
coords, river y≈0.48, our deploy line y≈0.44–0.50, our princess line y≈0.615, our king (0.48, 0.72),
lanes left x≈0.25 / centre x≈0.48 / right x≈0.745.

---

## 1. How this deck wins, and why that changes everything

Icebow won by **refusing to lose**: defend for less, then chip from range with a siege building.
Hog EQ wins by **cycling faster than the answer**. The Hog is 4 elixir and cannot be defended for
free forever; the plan is to keep arriving, spend less on defence than they do, and use Earthquake
to delete the one class of card that reliably stops a Hog — a building.

Two consequences the icebow rules got exactly backwards:

* **Banking is no longer correct.** Icebow is 3.5 cycle and holds elixir. This is 2.75 and its
  advantage IS the cycle — sitting at 10 with a Hog in hand is a wasted rotation, not patience.
* **There is no defensive win condition.** The X-Bow could win a match from our own half. Nothing
  here does. Tower damage comes from the Hog connecting and from chip, so a defence that ends with
  no counter-pressure has only broken even.

**Cycle maths (from the guides):** a full rotation costs 21 elixir; in double elixir (1 per 1.4 s)
the Hog comes back every **29.1 s**. That number is the deck's clock and most decisions are really
"does this play cost me my next Hog".

## 2. Card roles

| Card | Role | Key facts the rules will lean on |
|---|---|---|
| **Hog Rider** (4) | The win condition. Building-targeting, fast, jumps the river. | Cannot be ignored, so it forces a response every cycle. Its whole problem is buildings — which is what Earthquake is in the deck for. |
| **Earthquake** (3) | Building removal, and the Hog's escort. | Kills Tesla / Cannon / Tombstone / Bomb Tower outright, damages over a duration rather than instantly, and hits a **hidden Tesla** (the one damage spell that does). Also resets a Goblin Drill and clears skeleton swarms slowly. |
| **Evo Firecracker** (3) | Air answer, ground knockback, and chip. | Knockback keeps ground troops permanently shoved off her; evolution adds extra recoil sparks. Dies to any spell — never place her where a Fireball also hits a tower. |
| **Mighty Miner** (4, CHAMPION) | Tank killer and the defensive spine. | Damage **ramps on a single target** (modelled: 48 → 246 → 494 per hit), so he melts Giant/Golem/RG/Lava. Knockback-immune. His 1-elixir ability is a second card — see §4. |
| **Evo Tesla** (4) | The defensive building. Pulls, survives, hits air. | Hides underground between shots: invulnerable to every damage spell **except Earthquake**. Evolution adds a stun pulse. |
| **The Log** (2) | Ground swarm clear, charge reset, cycle. | Cannot hit air — Firecracker covers that. Rolls 9.6 tiles, so it clears the Hog's path from our own side. |
| **Skeletons** (1) | Distraction, charge reset, cycle. | The cheapest way to buy the Tesla or Mighty Miner free seconds. Not a defence on their own. |
| **Ice Spirit** (1) | Freeze, cycle, and the Hog's escort. | One freeze buys the Hog an extra hit or stops a counter mid-swing. The cheapest tempo card in the deck. |

## 3. Synergies

| Synergy | Geometry / timing | What it buys |
|---|---|---|
| **Hog + Earthquake** | Cast the moment the Hog CROSSES THE BRIDGE, not after | The core of the deck. An Inferno Tower placed *after* the quake lands still dies before it ramps. They lose 4–5 elixir and the Hog walks on. |
| **Hog + Ice Spirit** | Spirit onto whatever meets the Hog | The freeze converts "one hit" into two or three. |
| **Hog + Firecracker** | Firecracker behind, on our side | Her knockback shoves the ground answer off the Hog while she chips. |
| **Mighty Miner + Tesla** | Tesla pulls the tank, Miner ramps on it | Tesla holds aggro while the Miner's ramp reaches stage 3. |
| **Skeletons / Ice Spirit + Mighty Miner** | Cheap body first, Miner behind | The distraction keeps him on ONE target so the ramp never resets. |
| **Earthquake + Skeleton swarms** | Quake the clump | Slow, but it clears Skeleton Army / Goblin Gang without spending the Log. |
| **Firecracker + The Log** | Log the ground swarm, Firecracker holds air | Between them they answer both halves of a mixed push. |

## 4. Mighty Miner's ability — "Explosive Escape"

**1 elixir, 13 s cooldown**, and it is effectively a ninth card. What it does, precisely:

1. After a **1 second delay** he becomes intangible and moves to the **horizontally mirrored
   position** — same depth, opposite lane.
2. He leaves a **bomb at his original position**, which explodes after ~1 s for medium area damage
   to **ground and air**, knocking back **1.8 tiles**.

**Use cases, in rough priority:**

* **Swarm answer.** Swarms are his weakness; the bomb is the fix. Bait the swarm onto him, then
  escape — the bomb clears them and he arrives elsewhere.
* **Lane switch on offence.** Dropped on their side opposite a tower, the escape puts him on the
  *other* tower with almost no reaction time.
* **Escaping a committed counter.** The classic skill: players who trigger too early waste it. The
  ability is worth most **after** they commit their answer, not before.
* **Split-lane defence.** He can answer one lane, then mirror to the other.

**The timing rule the guides all state:** the single biggest skill is knowing *when* to trigger.
Early = wasted; late = dead. That makes it a genuine learned decision, not a scripted one.

## 5. Standing placement priors (first draft — to be checked against frames)

1. **Hog at the bridge**, in the lane with less defensive investment; never from the back.
2. **Earthquake on the building**, cast as the Hog crosses — not on troops unless it is a swarm
   that a 3-elixir spell out-trades.
3. **Tesla in the centre pull band**, same geometry the icebow doctrine measured: the double-cover
   zone begins **3.69 tiles from the river** at this engine's 8.0-tile tower reach.
4. **Firecracker behind the engagement**, out of one Fireball of the tower, never in spell range of
   a second target.
5. **Mighty Miner onto the tank**, with a cheap body in front so his ramp never resets.
6. **Skeletons / Ice Spirit** on the attacker, not behind it.

## 6. Sources

- RoyaleAPI deck statistics for Hog FC 2.6 Cycle (earthquake, firecracker, hog-rider, ice-spirit,
  knight/knight-ev1, skeletons, tesla, the-log)
- Clash Royale Wiki: Deck:2.6_Hog_EQ_Cycle, Earthquake, Hog Rider, Mighty Miner
- TrophyCoach "How to Play Hog 2.6 Cycle" (cycle maths: 21 elixir a rotation, Hog every 29.1 s in
  double elixir), RoyaleTracker Hog EQ 2026 guide (Earthquake-on-bridge timing, the 1-second
  window), Theria Games Mighty Miner and Earthquake guides
- Supercell balance note: Explosive Escape cost 2 → 1, Mighty Miner immune to knockback,
  Earthquake crown-tower damage −23%
- Engine ground truth (this repo): Mighty Miner damage stages 48.3 / 246.2 / 493.7 at level 13

# measure1026 -- REPORT (10-26: overtime chip races + Mortar defence, live / pro / SIM)

Grades: (a) measured, (b) plausible-untested, (c) contradicted. Wilson 95 % on shares; match-cluster bootstrap on per-placement means.
Live = 819 main-account Ranked matches since 10-20 13:28 (CLX 510, CLXIII 299, CLXIV 10). SIM = CLXIII gate rows, 3,840 (E4 + cal).

## Q1 OT / chip races (q1_ot.out)
- (a) Reached OT: live CLX+CLXIII 63.3 % [59.9, 66.5] vs SIM 66.2 % [64.7, 67.7]; diff -2.9 pp [-6.6, +0.6].
- (a) Tiebreak (equal crowns at 300 s): live 22.0 % [19.3, 25.0] vs SIM 24.8 % [23.4, 26.2].
- (a) Tiebreak decided by <= 546 HP (1 Rocket): live 5.1 % [3.8, 6.8] vs SIM 5.7 % [5.0, 6.5]; 23 % of tiebreaks in both.
- (c) "the SIM lacks chip races": frequency equal within CIs. (a) The gap is conversion: OT win 48.0 % live vs 67.9 % SIM;
  tiebreak win 41.0 % vs 55.7 %; pre-drain 1-0 up 32.0 % vs 47.7 %, 1-0 down 29.4 % vs 17.6 %; 0-0 21.4 % vs 22.4 %;
  1-1 1.5 % vs 2.3 %; 3-crown against 4.3 % vs 4.0 %; 3-crown for 2.2 % vs 0.0 %.

## Q2 Mortar
- (a) SIM: CLXIII vs Mortar decks 28.8 % [21.4, 37.6] (n 118) vs others 66.8 %: -37.9 pp [-45.5, -29.1]. Branches 32.3 % vs 73.4 %.
  Training decks (cx3): 18 / 895 decks hold a Mortar = 2.9 % of draws; census evo 1.5 %.
- (a) Live win rate vs Mortar decks: 34.8 % [18.8, 55.1] (8/23 matches, 2.8 % of matches) vs 48.6 % (387/796); -13.8 pp
  [-30.2, +6.8]. CLX 7/17, CLXIII 1/5, CLXIV 0/1.
- (a) Live per enemy Mortar (raw frame track; 112 Mortars in 23 matches = the 112 detector placements):
  hit our tower 39/112 = 34.8 % [26.6, 44.0]; >= 3 tower shells 15/112 = 13.4 % [8.3, 20.9]; 100 tower shells = 0.89 per Mortar
  (2.56 per tower-hitting Mortar), 2.89 shells per Mortar in all (the rest at troops); per-shell tower drop median 425 HP
  (n 95) = the level-16 Mortar damage; presence median 15.8 s (p25 8.7, p75 25.3; includes 3.5 s deploy); gone before 31 s
  92/104 = 88.5 %, 12 ran to expiry. CLX: 29/85 hit, CLXIII 7/23, CLXIV 3/4.
- (a) Our plays within 8 s, in-reach Mortars (pro rule, n 72 in 21 matches) vs pros (icebow8, n 640 in 144):
  ON it (<= 3.5 t) 2.8 % [0, 8.8] vs 12.3 % [9.8, 15.2]; ON it in 30 s 4.2 % [0, 10.9] vs 23.9 % [20.6, 27.6];
  Rocket ON it 2.8 % vs 10.5 %; in front of the threatened princess (troop/building <= 6 t) 37.5 % [28.2, 47.9] vs
  46.6 % [42.5, 50.5]; own X-Bow 26.4 % [16.9, 34.9] vs 12.0 %; lane princess lost in 30 s 775 HP [567, 1009] vs 611 [553, 664];
  >= 10 % lost 51.4 % [39.3, 65.6] vs 36.1 % [32.2, 39.6]. CLX in reach n 48: ON 4.2 % / 6.2 % (8 / 30 s), front 29.2 %,
  X-Bow 22.9 %; CLXIII n 20: ON 0 / 0, front 50.0 %, X-Bow 40.0 %.
- Live vs enemy X-Bow (in reach n 26, 7 matches): ON it 15.4 % (Rocket) vs pros 44.2 %.
- Owner claim: (a) we almost never hit the Mortar itself and the threatened princess loses more than the pros'; (c) "pummels
  for free" as the typical case: 65 % of Mortars never land a tower shell, 88.5 % are gone before expiry. (b) who kills it.

## Q3 SIM fidelity (agent)
- (a) J1 opp Mortar 0.971 [0.923, 1.0] n 35 (FIN13, parity/diag_night/r7_closer/cmp/FIN13_stamped_CEILING_strict.txt:79).
- (a) Stats equal to the device tables: 425 / shell at L16, crown towers 100 %, hit speed 4.7 s, range 3.5-11.5 (min range
  enforced), deploy 3.5 s, life 30 s, splash 2. (b) shell flight time. Open: no Mortar shot template in the parity harness.

## Known bug in live_siege.py (not fixed: plan mode)
bodies_of() counts evolved-Mortar Goblins (same reader card id 13000098, 323 HP) as Mortars: skip bodies with max HP < 1000.
The live per-Mortar numbers above come from a raw-log awk pass with that filter.

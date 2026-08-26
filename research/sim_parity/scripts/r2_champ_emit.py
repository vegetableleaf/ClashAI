# -*- coding: utf-8 -*-
"""R2 sim-parity ledger for the 8 champion keys. Emits ledger/r2_champions.jsonl.

Three independent paths per (key, field):
  P1 vardefines ({{#vardefine:<name>_11|v}}) -- level-11 anchors
  P2 the unit-attributes / ability-attributes tables and infobox
  P3 balance-history reconstruction (page History + master Version History)
All 8 pages: live revid == archive revid on 2026-08-26, content byte-identical,
api.php returned the requested title (no redirect to a Merge Tactics or spawned-unit page).
"""
import json, os
from collections import Counter

LED = r'C:/Users/benpe/ClashBot/research/sim_parity/ledger'
W = 'https://clashroyale.fandom.com/wiki/'
F = '2026-08-26'
REV = {
    'archer_queen': ('Archer_Queen', 436755), 'boss_bandit': ('Boss_Bandit', 437146),
    'goblinstein': ('Goblinstein', 437348), 'golden_knight': ('Golden_Knight', 437147),
    'little_prince': ('Little_Prince', 437347), 'mighty_miner': ('Mighty_Miner', 437349),
    'monk': ('Monk', 437140), 'skeleton_king': ('Skeleton_King', 436753),
}
VH = (W + 'Version_History', 437451)
rows = []


def src(key, raw):
    p, r = REV[key]
    return {'url': W + p, 'revid': r, 'fetched': F, 'raw': raw}


def vh(raw):
    return {'url': VH[0], 'revid': VH[1], 'fetched': F, 'raw': raw}


def old(key, rev, raw):
    p, _ = REV[key]
    return {'url': W + p + '?oldid=%d' % rev, 'revid': rev, 'fetched': F, 'raw': raw}


def R(key, field, cur, p1, p2, p3, sources, vote, verdict, notes):
    rows.append({'key': key, 'field': field, 'current_db': cur, 'p1_vardefine': p1,
                 'p2_table': p2, 'p3_history': p3, 'sources': sources, 'vote': vote,
                 'cross_checks': {'edit_war': 'pass'}, 'verdict': verdict, 'notes': notes})


SINGLE_USE = vh('{{Balance|Nerf|Hero}} Champions and [[Heroes]] (minus [[Boss Bandit]]): Will no '
                'longer have multi-use abilities. Instead, they will be single use')

LT = ("load_time_s/mass/sight/collision do NOT come from the wiki: import_mechanics.py reads "
      "RoyaleAPI cr-api-data cards_stats.json, meta.source_frozen=2023-10-18. PROOF they are a "
      "different metric from the wiki's First Hit Speed: Archer Queen's first-attack interval was "
      "set to 0.3s on 7/2/2023, BEFORE the 2023-10-18 freeze, yet the frozen file yields "
      "load_time_s 0.9. No constant offset across the group (AQ .9/.3, GK .7/.2, Monk .6/.2, "
      "SK 1.3/.3). NOT asserted as a delta; the wiki value is recorded as a field the KB row lacks.")

# ------------------------------------------------------------------ archer_queen (verified:false)
k = 'archer_queen'
R(k, 'first_hit_speed_s', None, None, '0.3 sec',
  "On 7/2/2023, a Balance Update, increased the Archer Queen's first attack time interval to 0.3 seconds (from 0.1 seconds).",
  [src(k, '! First Hit Speed | ... |5||1.2 sec||0.3 sec||Medium (60)||1 sec||5||800||Air & Ground||x1')],
  '2of3', 'update', 'KB row carries no first-hit field. ' + LT)
R(k, 'ability_cost', None, None, '1', 'Cloaking Cape Attributes: Cost 1; infobox AbilityCost=1',
  [src(k, '{{Card Infobox|Cost=5|AbilityCost=1|...}} / Cloaking Cape Attributes |1||Slow (45)||3.5 sec||+180%||0.933 sec||17 sec')],
  '2of3', 'update',
  'Archer Queen KB row has NO ability block at all (contrast boss_bandit/mighty_miner which do). '
  'decisions.md ruling 3: all abilities get full engine fidelity.')
R(k, 'ability_duration_s', None, None, '3.5 sec',
  '4/11/2021 duration -> 3 sec (from 3.5); 3/1/2024 duration -> 3.5 sec (from 3 sec)',
  [src(k, "Duration 3.5 sec; History: On 3/1/2024, a Balance Update, increased the Cloaking Cape's duration to 3.5 seconds (from 3 seconds).")],
  '3of3', 'update', 'Table and history agree at 3.5 s.')
R(k, 'ability_attack_speed_boost', None, None, '+180%',
  "On 4/4/2022, decreased the Cloaking Cape's attack speed buff to 180% (from 200%).",
  [src(k, 'TABLE Boost=+180% | PROSE="having a 80% increase in attack speed" | HISTORY="attack speed buff to 180% (from 200%)"')],
  'split', 'escalate',
  'conflicts.md C8 open item, now narrowed: history ("to 180% from 200%") and prose ("80% increase") '
  'BOTH describe a x1.8 multiplier -> hit speed 1.2/1.8 = 0.667 s. The table\'s leading "+" is the '
  'outlier (it would mean x2.8 -> 0.429 s). 2 of 3 favour x1.8. Neither reproduces the strategy '
  'claim "exactly 7 shots for the full duration": x1.8 over 3.5 s gives 6 shots, x2.8 gives 9. '
  'Owner ruling needed on which of the three the engine implements.')
R(k, 'ability_move_speed_tiles', None, None, 'Slow (45)',
  'On 3/2/2022, made it so that Cloaking Cape would decrease her speed to 45 (now classified as Slow) when active.',
  [src(k, 'Cloaking Cape Attributes Speed=Slow (45); History 3/2/2022 "decrease her speed to 45"')],
  '3of3', 'update',
  '45 speed units = 0.75 tiles/s under the 60=1.0 convention (confirmed on this page: her body '
  'Medium (60) == KB speed_tiles 1.0, and Boss Bandit Fast (90) == 1.5). The sim has no '
  'during-ability speed override, so her ability is currently a pure buff in-sim with none of its cost.')
R(k, 'ability_uses', None, None, None,
  '4/8/2026: Champions and Heroes (minus Boss Bandit) will no longer have multi-use abilities. Instead, they will be single use',
  [SINGLE_USE], '2of3', 'update',
  'Master Version History only; the Archer Queen page History has NO 4/8/2026 entry '
  '(conflicts.md C6, class-wide staleness). Matches decisions.md ruling 6 (single use PER BODY).')
R(k, 'ability_cooldown_s', None, None, '17 sec',
  '2/11/2021 15s; 8/1/2025 -> 17 sec (from 15 seconds); superseded 4/8/2026 by single-use',
  [src(k, 'Ability Cooldown 17 sec'), SINGLE_USE], '2of3', 'pin',
  'Do NOT import 17. decisions.md C6 + its open question: per-page cooldowns were never updated for '
  'the 4/8/2026 single-use change and are dead numbers. Same treatment the sim already gives '
  'mighty_miner (ability_cooldown_s 0.0).')
R(k, 'ability_invisible', None, None, 'Ability name "Cloaking Cape"',
  '1/11/2021 fixed some Archer Queen invisibility issues; 8/4/2022 fixed invisible AQ not receiving splash damage',
  [src(k, '"the Archer Queen activates her Cloaking Cape, becoming invisible (untargetable by enemy troops)"')],
  '3of3', 'update',
  'Untargetable by TROOPS; still takes splash and spell damage (8/4/2022 fix). Same invisibility '
  'class as Royal Ghost per the intro. Strategy prose adds that Tesla will not reveal itself against '
  'an invisible target.')
R(k, 'ability_cast_time_s', None, None, '0.933 sec', 'none',
  [src(k, 'PROSE "After a 1-second delay"; TABLE Cast Time 0.933 sec; TABLE body Deploy Time 1 sec')],
  'split', 'escalate',
  'conflicts.md C7 boilerplate, reconfirmed live on all 8 champion pages: prose 1 s delay vs table '
  'Cast Time 0.933 / 0.944 / 0.766. Engine needs one convention.')

# ------------------------------------------------------- boss_bandit (verified:TRUE -> never auto-overwrite)
k = 'boss_bandit'
R(k, 'leap_invulnerable', None, None, 'Dash Attributes publishes no invulnerability column',
  '8/7/2025 and 12/1/2026 entries do not touch dash invulnerability',
  [src(k, 'CARD QUOTE: "Boss Bandit dashes to her targets and is invulnerable while dashing." | '
          'STRATEGY: "Her dash invulnerability will allow her to nullify charge damage from the Dark '
          'Prince and the Prince, as well as the first attack of the Valkyrie and the Fisherman, '
          "since they hit during the Boss Bandit's dash time\" | \"Boss Bandit's dash also nullifies "
          "the Golden Knight's ability\"")],
  '2of3', 'escalate',
  'CURATED COMMENT IS CONTRADICTED BY THE LIVE PAGE. icebow/config/cards.yaml (boss_bandit block) '
  'states: "NOTE she is NOT described as immune during it -- that line is the Bandit\'s alone -- so '
  'no leap_invulnerable." Revid 437146 describes her dash invulnerability in the official card quote '
  'AND twice in strategy prose. Row is verified:true so this is an owner-review overturn request, '
  'not an auto-update.')
R(k, 'leap_towers', True, None, 'Dash Attributes: Target=Ground, Transport=Ground', 'no entry',
  [src(k, 'INTRO: "If there are ground units between 3.5 and 6 tiles of her..." | Dash Attributes Target=Ground')],
  'split', 'escalate',
  'Unsupported either way. The intro gates the dash on "ground UNITS" (which would exclude Crown '
  'Towers); the table\'s Target=Ground is about air-vs-ground and does not exclude buildings. '
  'Contrast mega_knight, whose page explicitly says it jumps Crown Towers (that curated note cites '
  'it). verified:true, so flagged not changed.')
R(k, 'first_hit_speed_s', None, None, '0.4 sec', 'no entry',
  [src(k, '|6||1.1 sec||0.4 sec||Fast (90)||1 sec||Melee: Short (0.8)||Ground||x1')],
  '2of3', 'update', 'KB row lacks the field. ' + LT)
R(k, 'ability_delay_s', None, None, 'Cast Time 0.933 sec', 'no entry',
  [src(k, 'PROSE "After a 1 second delay, the Boss Bandit becomes invisible for 1 second, then '
          'teleports 6 tiles behind her original position." | TABLE Cast Time 0.933 sec')],
  'split', 'escalate',
  'C7 again. The sim gives mighty_miner ability_delay_s 1.0 but boss_bandit no delay field at all, '
  'so her grenade resolves instantly in-engine. Also load-bearing for decisions.md ruling 7 (the '
  'elixir refund fires if the body dies DURING the delay -- with no delay there is no refund window).')

# ------------------------------------------------------------------- goblinstein (verified:false)
k = 'goblinstein'
GS_HIST = ('On 4/8/2026, a Balance Update, made it so that the Goblinstein would no longer have a '
           'cooldown timer in-between abilities. Instead, his ability will no be single use. The '
           "doctor's damage was increased by 47% and the ability DPS was decreased by 12%")
GS_VH = ('{{Balance|Neutral}}[[Goblinstein]]: ** {{Balance|Buff}}Doctor Damage +47% '
         '** {{Balance|Nerf}}Ability DPS -12%')
GS_LAG = ('VARDEFINE LAG PROVEN, not inferred: the vardefine block was authored by JohnSchmidt04 on '
          '2026-07-16 (revid 436759, page 13856->17317 b, the edit that installed the '
          'auto-calculating statistics tables on the champion pages). dmg_11=92 / link_11=107 / '
          'crown_11=23 are byte-identical at revid 436759 (2026-07-16) and at live revid 437348. '
          'The only later edit, 437348 (2026-08-14, R. Claiborne), is section-scoped "/* History */" '
          'and added the 4/8/2026 bullet WITHOUT recomputing the stats.')
R(k, 'components[0].damage (Doctor)', 92.0, 'dmg_11 = 92',
  'Card Statistics column "Doctor Damage" is driven by {{#var:dmg_11}}',
  GS_HIST + ' -> 92 x 1.47 = 135.24 -> 135',
  [src(k, '{{#vardefine: dmg_11 | 92 }}'),
   old(k, 436759, '{{#vardefine: dmg_11 | 92 }} @ 2026-07-16, pre-4/8/2026'), vh(GS_VH)],
  '2of3', 'update',
  'conflicts.md C4 RESOLVED. ' + GS_LAG + ' Doctor DPS follows: 135/1.8 = 75 (KB has no doctor dps '
  'field). Card-level goblinstein.damage (128) is the MONSTER and is unaffected.')
R(k, 'lightning_link_damage', None, 'link_11 = 107',
  'Card Statistics column "Lightning Link Damage"; Lightning Link Attributes gives Hit Speed 0.5 sec but no damage',
  '4/8/2026 Ability DPS -12% -> 107/0.5 = 214 dps -> 188.32 -> damage 94.16 -> 94',
  [src(k, '{{#vardefine: link_11 | 107 }} ; Lightning Link Attributes |2||4 sec||0.5 sec||Air & Ground||2||0.933 sec||17 sec'),
   vh(GS_VH)], 'split', 'escalate',
  'KB row carries NO lightning-link damage field at all. Two unresolved layers: (a) 107 is '
  'pre-4/8/2026 (same lag proof as the Doctor row); (b) the note nerfs "Ability DPS", not damage, so '
  'the -12% could land on damage (-> 94 at 0.5 s) or on hit speed (-> 0.568 s at 107). The same '
  '4/8/2026 update states hit-speed changes explicitly for Battle Healer, Void and X-Bow, which '
  'favours the damage reading, but that is inference, not source.')
R(k, 'lightning_link_crown_tower_damage', None, 'crown_11 = 23',
  'Card Statistics column "Lightning Link Crown Tower Damage"',
  '17/10/2024 decreased its Crown Tower Damage by 36%; 16/12/2024 fixed King Tower reduced damage; 4/8/2026 Ability DPS -12%',
  [src(k, '{{#vardefine: crown_11 | 23 }}'), vh(GS_VH)], 'split', 'escalate',
  'Doubly derived: 23 is pre-4/8/2026 and 23/107 = 21.5% of link damage, so a post-nerf value (~20) '
  'depends on resolving the link-damage row first. KNOWN PINS note: the crown-tower damage family was '
  're-curated post-1/6/2026, so this must go through owner review, never auto-import.')
R(k, 'ability_cost', None, None, 'Lightning Link Attributes Cost = 2', 'none',
  [src(k, '|2||4 sec||0.5 sec||Air & Ground||2||0.933 sec||17 sec')], '2of3', 'update',
  'KB row has no ability block.')
R(k, 'ability_duration_s', None, None, 'Duration 4 sec',
  "On 17/10/2024, decreased the Lightning Link's duration to 4 seconds (from 5 seconds)",
  [src(k, 'Duration 4 sec ; History 17/10/2024')], '3of3', 'update', '')
R(k, 'ability_hit_speed_s', None, None, 'Hit Speed 0.5 sec', 'none',
  [src(k, 'Lightning Link Attributes Hit Speed 0.5 sec')], '2of3', 'update',
  '8 ticks over the 4 s duration.')
R(k, 'ability_radius_tiles', None, None, 'Radius 2', 'none',
  [src(k, 'Lightning Link Attributes Radius 2')], '2of3', 'escalate',
  'Value is published (2 tiles) but conflicts.md C8 geometry is still unresolved: 2 tiles measured '
  'from the Doctor, from the Monster, or from the line between them is never stated anywhere on '
  'revid 437348.')
R(k, 'ability_cooldown_s', None, None, '17 sec',
  '17/10/2024 increased its cooldown to 17 seconds (from 15 seconds); superseded 4/8/2026',
  [src(k, 'Ability Cooldown 17 sec'), src(k, GS_HIST), SINGLE_USE], '2of3', 'pin',
  "Dead number under single-use; the page's OWN History bullet says the cooldown was removed, so the "
  'table contradicts its own page.')
R(k, 'ability_uses', None, None, None, GS_HIST, [src(k, GS_HIST), SINGLE_USE], '3of3', 'update',
  'Goblinstein is one of only 3 in-group pages that actually logged the 4/8/2026 change.')
R(k, 'first_hit_speed_s', None, None, 'Doctor 0.5 sec / Monster 0.8 sec', 'none',
  [src(k, 'Doctor Attributes First Hit Speed 0.5 sec ; Monster Attributes First Hit Speed 0.8 sec')],
  '2of3', 'update', 'Per-component; KB components carry no first-hit field. ' + LT)
R(k, 'deploy_time', None, None, 'Card Attributes: Deploy Time 1 sec', 'none',
  [src(k, 'Card Attributes |5||1 sec||[[:Category:Troop Cards|Troop]]||{{Rarity|Champion}}')],
  '2of3', 'update',
  'Goblinstein is the ONLY key in the group whose KB row omits deploy_time (the other seven all carry '
  '1.0). Caught by the match-verifier, not by the diff -- a field that is absent cannot mismatch. '
  'Both bodies land on the shared card-level 1 s deploy; the Guardienne-style per-body deploy offset '
  'that Little Prince has (0.3 s) has no counterpart here.')
R(k, 'range_tiles (card level)', 5.5, None,
  'Doctor Range 5.5 / Monster Range Melee: Medium (1.2)', 'none',
  [src(k, 'Doctor Attributes Range 5.5 ; Monster Attributes Range Melee: Medium (1.2)')],
  '2of3', 'escalate',
  'SNAPSHOT HYGIENE, not a wiki conflict. The card-level goblinstein row mixes the two bodies: '
  'hitpoints 2393 / damage 128 / hit_speed 1.5 are the MONSTER, but range_tiles 5.5 is the DOCTOR '
  'while range is "melee". Both component rows are individually correct. Same class as the tombstone '
  'spawn_interval_s inconsistency already logged in conflicts.md.')

# ----------------------------------------------------------------- golden_knight (verified:false)
k = 'golden_knight'
R(k, 'ability_move_speed_tiles', None, None,
  'Dashing Dash Attributes: Speed = Very Fast (120)', 'no entry',
  [src(k, '|1||Very Fast (120)||5.5||10||0.766 sec||12 sec ; PROSE "gaining a movement speed boost '
          'if he is not within 5.5 tiles of an enemy unit"')], '2of3', 'update',
  'AMENDS decisions.md ruling 10 GK-extras, which records only that "dash TRAVEL SPEED is '
  'unpublished" and never mentions this field. Two DISTINCT speeds exist: (1) this published movement '
  'boost to Very Fast (120) = 2.0 tiles/s (from Medium (60) = 1.0) that applies while NO target is '
  'within 5.5 tiles, and (2) the unpublished intra-dash travel speed (separate row). The ruling '
  'remains CORRECT that (2) is unpublished -- 120 is not it. Prose also notes this boost "cannot be '
  'reset or cancelled by The Log, Zap, Freeze or other things that will normally stop a charge".')
R(k, 'ability_dash_travel_speed', None, None, 'not published', 'not published',
  [src(k, 'PROSE: "Once a unit is in range, he dashes to it quickly" -- no figure anywhere on revid 437147')],
  'split', 'escalate',
  'NULL on all three paths -> escalate per the missing-value rule. Confirms decisions.md ruling 10 '
  'amendment. The placeholder analog is 500 speed units (8.33 tiles/s) taken from the Bandit / Boss '
  'Bandit Dash Speed columns; Golden Knight publishes no Dash Speed column at all. Still untested.')
R(k, 'ability_dash_range_tiles', None, None, 'Maximum Dash Distance 5.5',
  '3/2/2022 -> 5 (from 6); 4/4/2022 -> 6 (from 5); 4/4/2023 -> 5.5 tiles (from 6 tiles)',
  [src(k, 'Maximum Dash Distance 5.5 ; History 4/4/2023 "decreased the Dashing Dash\'s maximum dash '
          'range to 5.5 tiles (from 6 tiles)" ; PROSE "dashes towards the closest enemy unit within a '
          '5.5-tile radius"')], '3of3', 'update',
  'Table, prose and the last dated history entry all land on 5.5. Doubles as the chain re-target search radius.')
R(k, 'ability_max_dashes', None, None, 'Maximum Dashes 10', 'no entry',
  [src(k, 'PROSE "He will stop dashing after dashing 10 times, if no other valid targets are within '
          'range, or if the last target hit is a Crown Tower"')], '2of3', 'update',
  'Matches decisions.md ruling 10 (10-dash cap) and its amendment (THREE terminators).')
R(k, 'ability_cost', None, None, 'Dashing Dash Attributes Cost 1', 'none',
  [src(k, '|1||Very Fast (120)||5.5||10||0.766 sec||12 sec')], '2of3', 'update',
  'KB row has no ability block; only dash_damage 335 is present.')
R(k, 'ability_dash_delay_s', None, None, 'no column',
  'On 3/11/2025, a Balance Update, decreased Dashing Dash Delay to 0.05 seconds (from 0.2 seconds).',
  [src(k, 'History 3/11/2025 "decreased Dashing Dash Delay to 0.05 seconds (from 0.2 seconds)"')],
  '2of3', 'escalate',
  'decisions.md ruling 10 amendment calls this "defined nowhere". Its VALUE and lineage are now '
  'sourced (0.2 -> 0.05 on 3/11/2025) but its SEMANTICS are still undefined by any table or prose on '
  'revid 437147; best reading remains an intra-chain wind-up. Distinct from Cast Time 0.766.')
R(k, 'dash_invulnerable', None, None, 'no column',
  '1/11/2021 fixed Dashing Dash so it does not end if the target dies before the dash connects',
  [src(k, 'PROSE "His dashes have invulnerability and deal increased damage, like the Bandit."')],
  '2of3', 'update', 'Sim models dash_damage 335 but not the i-frames.')
R(k, 'ability_no_repeat_target', None, None, 'no column', 'no entry',
  [src(k, 'PROSE "He cannot dash into the same troop per ability use."')], '2of3', 'update',
  'Chain-selection constraint; the sim has no dash chain at all.')
R(k, 'ability_cooldown_s', None, None, '12 sec',
  '3/2/2022 -> 11 (from 8); 5/3/2024 -> 8 (from 11); 12/1/2026 -> 12 seconds (from 8 seconds); superseded 4/8/2026',
  [src(k, 'Ability Cooldown 12 sec ; History 12/1/2026'), SINGLE_USE], '2of3', 'pin',
  'Table and history agree at 12 s and the value is current as published, but single-use kills it. '
  "Golden Knight's page History has NO 4/8/2026 entry (C6).")
R(k, 'ability_uses', None, None, None, '4/8/2026 single use', [SINGLE_USE], '2of3', 'update',
  'Master Version History only.')
R(k, 'ability_cast_time_s', None, None, 'Cast Time 0.766 sec', 'none',
  [src(k, 'PROSE "After a 1 second delay" ; TABLE Cast Time 0.766 sec')], 'split', 'escalate',
  "C7. Note GK's 0.766 differs from the 0.933 used by five of the other champions and 0.944 for "
  'Little Prince, so this is not pure boilerplate.')
R(k, 'first_hit_speed_s', None, None, '0.2 sec', 'none',
  [src(k, '|4||0.9 sec||0.2 sec||Medium (60)||1 sec||Melee: Medium (1.2)||Ground||x1')],
  '2of3', 'update', 'KB row lacks the field. ' + LT)

# ---------------------------------------------------------------- little_prince (verified:TRUE)
k = 'little_prince'
LP_LAG = ('Same proven vardefine lag as goblinstein: guard_dmg_11=217 is byte-identical at revid '
          '436758 (2026-07-16, the edit that installed the vardefine block) and at live revid '
          '437347, whose only later edits (437346/437347, 2026-08-14) are section-scoped "/* History */".')
R(k, 'attack_ramp.mults[1]', 1.5, '2_atk_speed = 0.6', 'Hit Speed (Stage 2) = 0.6 sec',
  '17/11/2023 increased the number of attacks required to change stages to 3 (from 2); no stage-2 hit-speed change ever logged',
  [src(k, '{{#vardefine: 2_atk_speed | 0.6 }} ; TABLE |3||1.2 sec||0.6 sec||0.4 sec||0.4 sec||Medium (60)'),
   old(k, 433587, '2025-12-21 table row: |3||1.2 sec||0.6 sec||0.4 sec||0.4 sec -- 0.6 is stable back '
                  'to at least Dec 2025, so it is not a fresh unsourced edit')],
  '3of3', 'escalate',
  'REAL SIM ERROR, quantified. engine.py applies atk_ramp_mults as a CADENCE divisor '
  '(u.cooldown = hit_speed / spd / rm), so mults [1.0,1.5,3.0] with hit_speed 1.2 produce stages '
  '1.2 / 0.800 / 0.400 s. The wiki publishes 1.2 / 0.600 / 0.400 s on both P1 and P2. Stages 1 and 3 '
  'are exact; stage 2 should be mults[1] = 2.0, not 1.5. Effect: stage-2 DPS is 104/0.8 = 130 in-sim '
  'vs 104/0.6 = 173.3 published -- the sim is 25% low for the whole middle stage. The engine comment '
  'at engine.py ~2552 even hardcodes the stale "(1.2s -> 0.8s -> 0.4s)", matching the cards.yaml '
  'curation note "1.2 s -> 0.8 s -> 0.4 s (dps 82 -> 123 -> 247)". Row is verified:true -> owner '
  'review, no auto-write. per_stage 3 is CORRECT and confirmed by the 17/11/2023 entry.')
R(k, 'guardienne damage (spawn_unit_stats)', None, 'guard_dmg_11 = 217',
  'Card Statistics column "Guardienne Damage"',
  '3/6/2025 +1%; 3/11/2025 +7%; 4/8/2026 Guardian Melee Damage +7% -> 217 x 1.07 = 232.19 -> 232',
  [src(k, '{{#vardefine: guard_dmg_11 | 217 }}'),
   old(k, 436758, 'guard_dmg_11 = 217 @ 2026-07-16, pre-4/8/2026'),
   vh('{{Balance|Buff}}[[Little Prince]]: ** {{Balance|Buff}}Guardian Melee Damage +7%')],
  '2of3', 'escalate',
  'TWO defects in one field. (a) spawn_unit_stats carries only hit_speed/range_tiles/speed_tiles -- '
  'the Guardienne has NO damage and NO hitpoints in the KB, so the sim\'s summoned tank is statless. '
  '(b) The published 217 is itself stale. ' + LP_LAG + ' Current value is 232. verified:true -> escalate.')
R(k, 'guardienne hitpoints (spawn_unit_stats)', None, 'guard_hp_11 = 1600',
  'Card Statistics column "Guardienne Hitpoints"',
  "3/1/2024 decreased the Guardienne's hitpoints by 11%; no change on 4/8/2026",
  [src(k, '{{#vardefine: guard_hp_11 | 1600 }}')], '2of3', 'escalate',
  'Missing from spawn_unit_stats. 1600 is NOT affected by the 4/8/2026 note (damage only), so it is '
  'current as published.')
R(k, 'royal_rescue_damage', 0, 'charge_11 = 256', 'Card Statistics column "Royal Rescue Damage"',
  '17/6/2024 Royal Rescue damage -48.1%; 3/6/2025 +11%; 1/9/2025 +11%',
  [src(k, '{{#vardefine: charge_11 | 256 }} ; column header "Royal Rescue Damage"')],
  '3of3', 'escalate',
  'NAMING COLLISION worth an owner ruling. The KB field charge_damage: 0 is a deliberate curation '
  'meaning "he has no Prince-style charge attack", and that is correct. But the page\'s charge_11 '
  'vardefine is the ABILITY dash damage (column header "Royal Rescue Damage") = 256, a completely '
  'different quantity that the KB does not carry anywhere. Risk: a future importer keyed on charge_* '
  'would silently write 256 into charge_damage and give him a phantom charge attack. 256 is current '
  '(all three logged changes predate the 2026-07-16 vardefine authoring).')
R(k, 'royal_rescue_dash_range_tiles', None, None, 'Royal Rescue Attributes: Dash Range 4',
  "13/11/2023 decreased the Royal Rescue's dash range to 4.5 tiles (from 5 tiles) -- last dated entry",
  [src(k, 'TABLE Dash Range 4 ; PROSE "Although the Royal Rescue\'s range is 4 tiles, the Guardienne '
          'has an extra 0.8 tile collision radius" ; HISTORY 13/11/2023 "-> 4.5 tiles (from 5 tiles)"')],
  'split', 'escalate',
  'Table (4) and strategy prose (4) agree against the newest dated history entry (4.5). Unlike the '
  'other lag cases the history is here the OLDER reading, so an undocumented 4.5 -> 4 change '
  'happened. 2 of 3 favour 4. Prose adds that Guardienne\'s 0.8 collision radius extends effective '
  'reach beyond the nominal 4.')
R(k, 'royal_rescue_pushback_tiles', None, None, 'no column',
  '17/11/2023 pushback -> 2.5 (from 3.5); 17/6/2024 -> 2 tiles (from 2.5); 1/9/2025 increased the '
  "Royal Rescue's pushback to 2.5 tiles (from 2 tiles)",
  [src(k, "History 1/9/2025 \"increased the Royal Rescue's pushback to 2.5 tiles (from 2 tiles)\"")],
  '2of3', 'escalate',
  'RESOLVES the little_prince half of conflicts.md C8 ("prose 0-2 tiles vs History 1/9/2025 2.5 '
  'tiles"): the history chain is complete and monotone, so 2.5 is CURRENT and the prose is stale at '
  'the pre-1/9/2025 value. KB carries no pushback field.')
R(k, 'ramp_move_grace_s', None, None, 'no column',
  '4/8/2026: Little Prince will now maintain his charged-up Hit Speed for up to 0.3 seconds while moving',
  [src(k, 'On 4/8/2026, a Balance Update, ... The Little Prince will now maintain his charged-up Hit '
          'Speed for up to 0.3 seconds while moving'),
   vh('{{Balance|Buff}}Little Prince will now maintain his charged-up Hit Speed for up to 0.3 seconds while moving')],
  '2of3', 'escalate',
  'NEW MECHANIC the sim does not model. engine.py resets ramp_shots on movement with no grace window '
  '(and the 14/12/2023 entry fixed a bug where the ramp did NOT reset on movement, so reset-on-move '
  'is the base behaviour). Strategy prose confirms the reset is exploitable: "Cards with knockback '
  'and stun effects like The Log, Zap, Fireball, and Giant Snowball can reset his attack speed ramp up".')
R(k, 'ability_cost', None, None, 'Royal Rescue Attributes Cost 3', 'none',
  [src(k, '|3||4||Ground||0.944 sec||30 sec')], '2of3', 'escalate',
  'KB row has no ability block. Note this is the most expensive champion ability in the group '
  '(3 elixir on a 3-elixir card).')
R(k, 'ability_uses', None, None, None, '4/8/2026 single use (page History + master log)',
  [src(k, 'On 4/8/2026 ... his ability will no be single use'), SINGLE_USE], '3of3', 'escalate',
  'verified:true row.')
R(k, 'ability_cooldown_s', None, None, '30 sec',
  'superseded by 4/8/2026 single-use, logged on this page',
  [src(k, 'Ability Cooldown 30 sec'), SINGLE_USE], '2of3', 'pin',
  "Table contradicts its own page History bullet.")
R(k, 'guardienne deploy_time_s', None, None, 'Guardienne Attributes Deploy Time 0.3 sec', 'none',
  [src(k, 'Guardienne Attributes |1.2 sec||0.5 sec||Medium (60)||0.3 sec||Melee: Medium (1.2)||Ground||Ground')],
  '2of3', 'escalate', 'Missing from spawn_unit_stats.')
R(k, 'guardienne first_hit_speed_s', None, None, 'Guardienne Attributes First Hit Speed 0.5 sec',
  "17/6/2024 increased Guardienne's first attack time interval to 0.5 seconds (from 0.2 seconds)",
  [src(k, 'Guardienne First Hit Speed 0.5 sec ; History 17/6/2024')], '3of3', 'escalate', '')
R(k, 'first_hit_speed_s', None, None, '0.4 sec', 'none',
  [src(k, '|3||1.2 sec||0.6 sec||0.4 sec||0.4 sec||Medium (60)||1 sec||5.5||800')],
  '2of3', 'escalate', 'KB row lacks the field; verified:true row so not an auto-update. ' + LT)
R(k, 'ability_cast_time_s', None, None, 'Cast Time 0.944 sec', 'none',
  [src(k, 'PROSE "After a 1-second delay" ; TABLE Cast Time 0.944 sec')], 'split', 'escalate', 'C7.')

# ------------------------------------------------------------------ mighty_miner (verified:false)
k = 'mighty_miner'
MM_LAG = ('Same proven vardefine lag: 1_dmg_11/2_dmg_11/3_dmg_11 = 40/204/409 are byte-identical at '
          'revid 436756 (2026-07-16), revid 437122 (2026-08-11, a full-page edit that also left them '
          'alone) and live revid 437349.')
MM_VH = '{{Balance|Buff}}[[Mighty Miner]]: Base Damage +8%'
R(k, 'ability_bomb_damage', 366, 'escape_11 = 332',
  'Card Statistics column "Explosive Escape Damage"',
  'no post-vardefine change to Explosive Escape damage',
  [src(k, '{{#vardefine: escape_11 | 332 }} ; column header "Explosive Escape Damage"')],
  '2of3', 'update',
  'conflicts.md C1, CLOSED by decisions.md ruling 9 -- this row is the R2 verification the ruling '
  'asked for, and it holds. The wiki publishes 332 @L11; the KB\'s 366 was reverse-derived from an '
  'in-game 440 reading anchored at a nonexistent champion level 1. With champions floored at L11 and '
  "the page's own ladder x1.1^(L-11), 332 -> 365 -> 402 -> 440 reaches 440 EXACTLY at L14. The "
  'cards.yaml comment "is not published in the KB" is false and is deleted with the value. Fix was '
  'scheduled for Phase I stage I5 and has NOT landed: hogeq/config/cards.yaml still reads '
  'ability_bomb_damage: 366.')
R(k, 'ability_bomb_radius', 2.5, 'no vardefine',
  'Explosive Escape Attributes publishes only Cost / Deploy Time / Cast Time / Ability Cooldown -- no radius column',
  'no radius figure in any dated entry',
  [src(k, 'PROSE "dealing medium area damage to enemies around it after 1 second" -- no tile figure '
          'anywhere on revid 437349')], 'split', 'escalate',
  'conflicts.md C2 RECONFIRMED against the live revision: NULL on all three paths -> escalate per the '
  "missing-value rule. The sim's 2.5 tiles remains an unsourced guess. TRAP restated: the only tile "
  'figure on the page is the 1.8-tile knockback, which is a DISPLACEMENT, not a radius -- do not let '
  'a later pass conflate them. Resolution path is an owner in-game measurement.')
R(k, 'damage / damage_stages[0] / damage_ramp.damages[0]', 40, '1_dmg_11 = 40',
  'Card Statistics column "1 stage Damage"',
  MM_VH + ' + page History "His base damage was increased by 8%" -> 40 x 1.08 = 43.2 -> 43',
  [src(k, '{{#vardefine: 1_dmg_11 | 40 }}'),
   old(k, 437122, '1_dmg_11 = 40 @ 2026-08-11, i.e. one week AFTER the 4/8/2026 update, still un-recomputed'),
   vh(MM_VH)], '2of3', 'update',
  'ROBUST UNDER BOTH READINGS of "base damage" (stage-1-only or all-stages), so stage 1 can be moved '
  'on its own. ' + MM_LAG + ' Follow-on: dps 100 -> 43/0.4 = 107.5 -> 108. Note the KB duplicates '
  'these numbers in THREE places (damage, damage_stages, damage_ramp.damages) -- all three must move together.')
R(k, 'damage_stages[1] / damage_ramp.damages[1]', 204, '2_dmg_11 = 204',
  'Card Statistics column "2 stage Damage"',
  MM_VH + ' -> 204 (base-only reading) or 204 x 1.08 = 220.3 -> 221 (all-stages reading)',
  [src(k, '{{#vardefine: 2_dmg_11 | 204 }}'), vh(MM_VH)], 'split', 'escalate',
  'AMBIGUOUS, do not auto-write. "Base Damage +8%" may mean the stage-1 figure only, or the single '
  'underlying base that all stages derive from. Evidence for the all-stages reading: the three '
  'published stages are consistent with ONE base b~40.09 at multipliers 1 / 5.1 / 10.2 '
  '(40.09 -> 40, 204.5 -> 204, 408.9 -> 409), which is how the game files usually store a ramp; then '
  "b' = 43.30 gives 43 / 221 / 442. Evidence for base-only: the wording says \"base\". Owner ruling needed.")
R(k, 'damage_stages[2] / damage_ramp.damages[2]', 409, '3_dmg_11 = 409',
  'Card Statistics column "3 stage Damage"', MM_VH + ' -> 409 (base-only) or 442 (all-stages)',
  [src(k, '{{#vardefine: 3_dmg_11 | 409 }}'), vh(MM_VH)], 'split', 'escalate',
  'Same ruling as damage_stages[1]; the two must be decided together.')
R(k, 'damage_charge_speed_s', None, None,
  'Mighty Miner Attributes: "Damage Charge Speed" = 2 sec',
  'On 8/1/2025, a Balance Update, decreased the time required to change stages to 2 seconds (from 2.25 seconds).',
  [src(k, 'RAW TABLE: !Damage Charge / Speed / {{Icon|I=Time}} ... |4||0.4 sec (newline) |2 sec||Medium (60)||1 sec|| Melee: Long (1.6)')],
  '3of3', 'update',
  'The KB models the stage ramp with damage_ramp {damages, hit_speed} and has NO stage-advance timer, '
  'so nothing in the sim governs WHEN a stage steps. Table and history agree at 2 s. NOTE the column '
  'header is split across raw lines ("Damage Charge" / "Speed"), which shifts naive row-to-header '
  'alignment on this page by one -- values here were read off the raw wikitext, not the parse.')
R(k, 'ability_cooldown_s', 0.0, None,
  'Explosive Escape Attributes: Ability Cooldown 13 sec',
  '8/4/2022 cost -> 1 elixir; 4/8/2026 "would no longer have a cooldown timer in-between abilities. '
  'Instead, his ability will now be single use"',
  [src(k, 'Ability Cooldown 13 sec ; History 4/8/2026'), SINGLE_USE], '2of3', 'pin',
  "The KB's 0.0 is CORRECT and the wiki table is the stale side. Recording it as an explicit pin so a "
  'future sweep does not "fix" 0.0 back to 13. The page contradicts itself: the table says 13 s, its '
  'own 4/8/2026 History bullet says the cooldown was removed.')
R(k, 'ability_cast_time_s', None, None, 'Cast Time 0.933 sec', 'none',
  [src(k, 'PROSE "After a 1-second delay" ; TABLE Deploy Time 1 sec ; TABLE Cast Time 0.933 sec')],
  'split', 'escalate',
  'C7. Mighty Miner is the one in-group card where the KB already picks a convention '
  '(ability_delay_s 1.0 = the prose/Deploy Time reading), so whichever way C7 is ruled, this row is '
  'the precedent.')

# --------------------------------------------------------------------------- monk (verified:false)
k = 'monk'
R(k, 'knockback_immune', None, None, 'no column',
  '24/11/2025 made Monk no longer immune to Evo Mega Knight / another Monk knockback, and no longer '
  "immune to Fireball and Giant Snowball knockbacks on the corner of their AoE; On 12/12/2025, a "
  'Balance Update made Monk immune to any knockback.',
  [src(k, 'On 12/12/2025, a Balance Update made Monk immune to any knockback.')], '2of3', 'update',
  'HIGHEST-IMPACT ROW IN THE GROUP. The KB monk row has flags [knockback, knockback_all] -- those '
  'describe the knockback he DEALS on the 3rd combo hit -- and carries NO knockback_immune flag, '
  'unlike skeleton_king and mighty_miner which carry both the flag and knockback_immune: true. The '
  '12/12/2025 entry is the LATEST dated statement, is unqualified ("immune to any knockback"), and '
  'deliberately reverses the 24/11/2025 partial removal. Also RESOLVES the monk half of conflicts.md '
  'C8 (ability-scoped vs unqualified immunity): the ability prose ("impervious to all forms of '
  "knockback and the Tornado's pull during Pensive Protection's duration\") is the NARROWER, older "
  'statement and is now stale. Consequence in-sim today: The Log, Fireball, Snowball and Zap all '
  'shove the Monk when they should not. Note the Monk is ALSO absent from the Bowler-page '
  'knockback-immune list that icebow/config/cards.yaml cites as its source for that flag, so this is '
  'a source-coverage gap, not a transcription error.')
R(k, 'combo_damage', None, 'combo_11 = 422', 'Card Statistics column "Combo Damage"',
  "On 17/6/2024, increased the Monk's combo damage by 0.47%. It also fixed certain issues with damage multipliers on the Monk.",
  [src(k, '{{#vardefine: combo_11 | 422 }} ; column header "Combo Damage" ; INTRO "The Monk uses a '
          '3-hit combo: the first 2 attacks deal normal damage, while the 3rd strike deals extra '
          'damage and knockback, even if the targeted troop is normally immune to knockback"')],
  '3of3', 'escalate',
  'conflicts.md C3 CONFIRMED: the value IS published (422 @L11) and the cards.yaml comment "The 3rd '
  'hit\'s EXTRA DAMAGE is not published, so only the shove is modelled" is factually wrong -- same '
  'error class as C1. The sim currently gives the Monk 140 on his 3rd hit instead of ~422, a ~3x '
  'under-count every third swing. Escalated rather than updated because the SEMANTICS are still '
  'unruled: 422/140 = 3.01 exactly, which reads as a clean x3 REPLACEMENT multiplier, but the intro '
  'wording "deals extra damage" reads as ADDITIVE (which would give 562). The page never '
  'disambiguates. The 17/6/2024 "fixed certain issues with damage multipliers" hints the game stores '
  'it as a multiplier. Owner ruling needed before the number is wired in.')
R(k, 'ability_damage_reduction', None, None, 'Pensive Protection Attributes: Damage Reduced -65%',
  "On 8/7/2025, decreased the Pensive Protection's damage reduction boost to 65% (from 80%).",
  [src(k, 'TABLE Damage Reduced -65% ; PROSE "reducing all incoming damage he takes by 65%" ; HISTORY 8/7/2025')],
  '3of3', 'update', 'Clean 3-of-3. KB has no ability block for the Monk.')
R(k, 'ability_duration_s', None, None,
  'Pensive Protection Attributes: "Invulnerability Duration" 4 sec', 'none',
  [src(k, 'TABLE header "Invulnerability Duration" = 4 sec ; PROSE never uses the word invulnerable, '
          'only "reducing all incoming damage he takes by 65%"')], '2of3', 'update',
  'Value 4 s is solid; the COLUMN LABEL is a misnomer. He is not invulnerable, he takes 35% damage -- '
  'the header conflicts with both the adjacent "Damage Reduced -65%" cell and the prose. Import as '
  'ability_duration_s, NOT as an invulnerability window.')
R(k, 'ability_reflect', None, None, 'no column',
  "On 12/12/2022, made it so that the Heal Spirit's projectile can no longer be deflected by the "
  'Monk; 31/3/2025 fixed various issues related to Pensive Protection',
  [src(k, 'PROSE "reflect all incoming projectile-based ranged attacks back to the said offender. '
          'Spells are always reflected to the closest opposing Crown Tower. He cannot protect nearby '
          'allies from melee attacks, non-projectile ranged attacks and non-projectile spells."')],
  '2of3', 'update',
  'decisions.md ruling 3 explicitly requires FULL fidelity here ("including Monk\'s projectile '
  'reflection"), and the KB carries nothing. Three distinct rules to encode: projectiles -> back to '
  'the shooter; spells -> nearest enemy Crown Tower regardless of source; melee / non-projectile '
  'ranged / non-projectile spells -> unaffected. Heal Spirit is a named exception (12/12/2022).')
R(k, 'ability_cost', None, None, 'Pensive Protection Attributes Cost 1', 'none',
  [src(k, '|1||4 sec||-65%||0.933 sec||17 sec ; INTRO "his ability costs an additional 1 Elixir to activate"')],
  '3of3', 'update', '')
R(k, 'ability_cooldown_s', None, None, '17 sec',
  "On 2/11/2022, increased the Pensive Protection's cooldown time to 17 seconds (from 15 seconds); superseded 4/8/2026",
  [src(k, 'Ability Cooldown 17 sec'), SINGLE_USE], '2of3', 'pin',
  'Monk page History ends 12/12/2025 and never logs 4/8/2026 (conflicts.md C6).')
R(k, 'ability_uses', None, None, None, '4/8/2026 single use', [SINGLE_USE], '2of3', 'update',
  'Master Version History only.')
R(k, 'ability_tornado_immune', None, None, 'no column',
  '12/12/2025 blanket knockback immunity does not mention Tornado',
  [src(k, 'PROSE "The Monk is impervious to all forms of knockback and the Tornado\'s pull during '
          "Pensive Protection's duration.\"")], 'split', 'escalate',
  'Tornado-pull immunity is stated ONLY as ability-scoped, while knockback immunity has since become '
  'permanent (12/12/2025). Whether the pull immunity followed it is unstated. KB carries neither.')
R(k, 'first_hit_speed_s', None, None, '0.2 sec',
  "On 7/2/2023, decreased the Monk's attack time interval to 0.8 seconds (from 0.9 seconds) -- body hit speed, not first hit",
  [src(k, '|5||0.8 sec||0.2 sec||Medium (60)||1 sec||Melee: Medium (1.2)||Ground||x1')],
  '2of3', 'update', 'KB row lacks the field. ' + LT)
R(k, 'ability_cast_time_s', None, None, 'Cast Time 0.933 sec', 'none',
  [src(k, 'PROSE "After a 1-second delay" ; TABLE Cast Time 0.933 sec')], 'split', 'escalate', 'C7.')

# ----------------------------------------------------------------- skeleton_king (verified:false)
k = 'skeleton_king'
R(k, 'spawn_unit_stats.hitpoints', None,
  'no skel_hp vardefine exists (only skel_dmg_11 / skel_atk_speed)',
  'Soul Summoning Attributes: Skeleton Hitpoints = 1',
  "30/3/2022 fixed a stats rounding issue with the Skeleton King's summoned Skeletons",
  [src(k, 'TABLE Skeleton Hitpoints 1 ; PROSE "The Skeletons he summons have a bluish tint and behave '
          "identically to cloned Skeletons, which means you can't clone them further with said card, "
          'and they only have 1 hitpoint."')], '3of3', 'update',
  'MAJOR FIDELITY GAP, and the value looks like a typo but is not -- table and prose independently '
  'state 1 HP, and the absence of any skel_hp vardefine (while skel_dmg_11 exists) is the third '
  'corroboration: the stat does not scale with level, so the auto-calculating ladder has nothing to '
  'compute. The summoned skeletons are CLONE-class 1-HP bodies, so any splash, any tower shot, any '
  'spell wipes the whole summon. The KB spawn_unit_stats carries only hit_speed/range_tiles/'
  'speed_tiles; if the engine falls back to the base skeletons card (~81 HP @L11) then Soul Summoning '
  'is worth roughly 16x81 = 1296 effective HP in-sim instead of 16. Check the spawn fallback path when wiring this.')
R(k, 'spawn_unit_stats.damage', None, 'skel_dmg_11 = 81', 'Card Statistics column "Skeleton Damage"',
  "On 6/10/2025, increased the Skeleton's attack time interval to 1.1 seconds (from 1.0 seconds) -- hit speed only",
  [src(k, '{{#vardefine: skel_dmg_11 | 81 }} ; column header "Skeleton Damage" ; ladder row 11 || {{#var:skel_dmg_11}}')],
  '3of3', 'update', 'Missing from spawn_unit_stats. 81 @L11, scales x1.1^(L-11) like the body.')
R(k, 'ability_spawn_count', None, None, 'Soul Summoning Attributes: Skeleton Count 6-16',
  '7/6/2022 decreased the Skeletons spawned to 18 (from 20); 2/8/2022 decreased to 16 (from 18)',
  [src(k, 'TABLE Skeleton Count 6-16 ; PROSE "With no souls, the Skeleton King will spawn 6 '
          'Skeletons, but with a maximum of 10 souls, he can summon 16 Skeletons."')],
  '3of3', 'update',
  'Full soul mechanic the KB does not model: floor 6, +1 per soul, soul cap 10, ceiling 16. A soul is '
  'earned per TROOP death on either team while he is deployed; cloned troops and ability-summoned '
  'skeletons do NOT count, and sub-troops (Elixir Golem, Golem, Lava Hound, Battle Ram) do not count, '
  'only final forms -- with Goblin Giant as a stated exception. Prose also states soul accrual '
  '"continues, even if the Skeleton King dies", which bears directly on the still-open lifecycle '
  'question logged under decisions.md ruling 8.')
R(k, 'ability_spawn_radius_tiles', None, None, 'no column',
  "On 24/10/25, a maintenance break, decreased Soul Summoning's skeleton spawn radius to 3.5 tiles (from 4 tiles).",
  [src(k, 'PROSE "summoning a varied amount of Skeletons in a 4-tile radius around himself" ; HISTORY '
          '24/10/2025 "-> 3.5 tiles (from 4 tiles)"')], '2of3', 'update',
  'RESOLVES the skeleton_king half of conflicts.md C8. The history entry POSTDATES the prose and names '
  'the prose value as the old one ("from 4 tiles"), so 3.5 is current and the 4-tile prose is stale -- '
  'a textbook P3 catch. KB carries no spawn radius.')
R(k, 'ability_spawn_interval_s', None, None, 'no column', 'none',
  [src(k, 'PROSE "The Skeletons spawn 1 at a time at random positions in the circle every 0.25 seconds."')],
  '2of3', 'update',
  '16 skeletons therefore take ~4 s to fully materialise -- not an instant burst. KB has no field.')
R(k, 'ability_cost', None, None, 'Soul Summoning Attributes Cost 2', 'none',
  [src(k, '|2||6-16||1||0.933 sec||20 sec ; PROSE "The Soul Summoning ability costs 2 Elixir to activate."')],
  '3of3', 'update',
  "The only 2-elixir ability in the group besides Goblinstein's; KB has no ability block.")
R(k, 'ability_cooldown_s', None, None, '20 sec', 'superseded 4/8/2026 single-use',
  [src(k, 'Ability Cooldown 20 sec'), SINGLE_USE], '2of3', 'pin',
  'Skeleton King page History ends 24/10/2025 and never logs 4/8/2026 (conflicts.md C6).')
R(k, 'ability_uses', None, None, None, '4/8/2026 single use', [SINGLE_USE], '2of3', 'update',
  'Master Version History only. Interacts with decisions.md ruling 8 (the soul bar stops filling once '
  'a body has spent its use).')
R(k, 'first_hit_speed_s', None, None, 'body 0.3 sec / summoned skeleton 0.5 sec', 'none',
  [src(k, '|4||1.6 sec||0.3 sec||Medium (60)||1 sec||Melee: Medium (1.2)||1.3||Ground||x1 ; Skeleton '
          'Attributes |1.1 sec||0.5 sec||Fast (90)||Melee: Short (0.5)')],
  '2of3', 'update', 'KB row lacks both. ' + LT)
R(k, 'ability_cast_time_s', None, None, 'Cast Time 0.933 sec', 'none',
  [src(k, 'PROSE "After a 1-second delay" ; TABLE Cast Time 0.933 sec')], 'split', 'escalate', 'C7.')

out = os.path.join(LED, 'r2_champions.jsonl')
with open(out, 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

c = Counter(r['verdict'] for r in rows)
print('wrote', out, len(rows), 'rows')
print(dict(c))
for kk in ['archer_queen', 'boss_bandit', 'goblinstein', 'golden_knight', 'little_prince',
           'mighty_miner', 'monk', 'skeleton_king']:
    sub = [r for r in rows if r['key'] == kk]
    print('  %-15s %2d rows  %s' % (kk, len(sub), dict(Counter(r['verdict'] for r in sub))))

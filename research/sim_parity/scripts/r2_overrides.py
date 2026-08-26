# -*- coding: utf-8 -*-
"""Hand-resolved proposals for R2 fields whose three paths publish prose, not a scalar.

Imported by both r2_merge.py (writes stat_diffs.jsonl) and r2_review_md.py (writes
R2_REVIEW.md) so the ledger and the review table cannot disagree.
"""

# hand overrides where all three paths publish prose rather than a scalar
PROP_OVERRIDE = {
    ("archer_queen", "ability_uses"): "1 (single use per body)",
    ("archer_queen", "ability_invisible"): "true (untargetable by troops; still takes splash/spell)",
    ("goblinstein", "ability_uses"): "1 (single use per body)",
    ("goblinstein", "first_hit_speed_s"): "Doctor 0.5 / Monster 0.8",
    ("golden_knight", "dash_invulnerable"): "true (i-frames during the dash)",
    ("golden_knight", "ability_no_repeat_target"): "true (cannot dash the same troop twice per use)",
    ("golden_knight", "ability_uses"): "1 (single use per body)",
    ("monk", "knockback_immune"): "true (unqualified, 12/12/2025)",
    ("monk", "ability_reflect"): "true (projectiles to shooter, spells to nearest enemy tower)",
    ("monk", "ability_uses"): "1 (single use per body)",
    ("skeleton_king", "ability_spawn_count"): "6-16 (floor 6, +1 per soul, soul cap 10)",
    ("skeleton_king", "ability_spawn_radius_tiles"): "3.5",
    ("skeleton_king", "ability_spawn_interval_s"): "0.25 (1 skeleton at a time)",
    ("skeleton_king", "ability_uses"): "1 (single use per body)",
    ("skeleton_king", "first_hit_speed_s"): "body 0.3 / summoned skeleton 0.5",
    ("clone", "targets"): "friendly troops (not buildings)",
    ("goblin_curse", "spawns_troop"): "goblin (hp 202 / dmg 120 / 1.1 s)",
    ("inferno_tower", "attacks"): "[air, ground]",
}

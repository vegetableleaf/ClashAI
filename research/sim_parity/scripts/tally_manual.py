# -*- coding: utf-8 -*-
"""Hand-verified (key, field) checks that the automated P1/P2 sweep cannot reach:
secondary/tertiary tables, history-only (P3) reconstructions, derived values,
and fields absent from the KB. Each entry is (key, field, outcome).

outcome: 'match'    -> agreed with current_db, no ledger line
         'line'     -> disagreed / flagged, has a ledger line
"""
MANUAL = [
 # --- secondary-table mechanics verified as MATCHING ---
 ("bandit", "dash_time_s", "match"),          # secondary: Dash Time 0.8 sec
 ("bandit", "leap_min_tiles", "match"),       # secondary: Dash Range 3.5-6
 ("bandit", "leap_max_tiles", "match"),
 ("bandit", "leap_speed_tiles", "match"),     # 500 game-units / 60 = 8.33 tiles/s
 ("fisherman", "hook_time_s", "match"),       # secondary: Hook Time 1.3 sec
 ("fisherman", "hook_min_tiles", "match"),    # secondary: Hook Range 3.5-7
 ("fisherman", "hook_max_tiles", "match"),
 ("fisherman", "hook_speed_tiles", "match"),  # 800 / 60 = 13.33 tiles/s
 ("balloon", "death_radius_tiles", "match"),  # 2nd table: Death Damage Splash Radius 3
 ("balloon", "death_delay_s", "match"),       # 2nd table: Deploy Time 3 sec
 ("electro_giant", "reflect_radius_tiles", "match"),  # secondary: Radius 3
 ("electro_giant", "reflect_stun_s", "match"),        # secondary: Stun Duration 0.5 sec
 ("electro_wizard", "spawn_radius_tiles", "match"),   # 2nd table: Radius 3
 ("electro_wizard", "stun_duration_s", "match"),
 ("battle_ram", "charge_speed_tiles", "match"),       # secondary: Very Fast (120) = 2.0
 ("battle_ram", "charge_range", "match"),             # P2 says 3.5 but P3 8/8/2023 -> 3, prose "after it travels 3 tiles"
 ("dark_prince", "charge_range", "match"),            # secondary: Charge Range 3; P3 8/1/2025 -> 3
 ("dark_prince", "charge_speed_tiles", "match"),      # secondary: Very Fast (120) = 2.0
 ("dark_prince", "splash_radius", "match"),           # primary table Splash Radius 1.1
 ("furnace", "spawn_unit_stats.range_tiles", "match"),   # secondary: Range 2.5
 ("furnace", "spawn_unit_stats.speed_tiles", "match"),   # secondary: Very Fast (120) = 2.0
 ("elixir_golem", "spawns.on_death", "match"),           # secondary Count x2
 ("elixir_golemite", "spawns.on_death", "match"),        # tertiary Count x4 = 2 mites x 2
 ("bush_goblin", "count", "match"),                      # x2 lives on suspicious_bush.spawns.on_death
 ("bush_goblin", "range_tiles", "match"),                # secondary table 0.8 (NOT the Bush's 0.5)
 ("decoy_goblin", "speed_tiles", "match"),               # 3rd table Very Fast (120) = 2.0
 ("ghost_souldier", "speed_tiles", "match"),             # 3rd table Fast (90) = 1.5
 ("executioner", "hit_speed", "match"),                  # P2 0.9 + Axe Time 1.5 = 2.4 = P1 & P3
 ("executioner", "projectile_width_tiles", "match"),
 # --- P3-only reconstructions verified as MATCHING ---
 ("firecracker", "recoil_tiles", "match"),    # 4/8/2025 -> 1 tile
 ("dart_goblin", "sight", "match"),           # 2/3/2026 -> 7.5 tiles
 ("fire_spirit", "range_tiles", "match"),     # 4/2/2025 -> 2.5 tiles
 ("cannon_cart", "shield_hp", "match"),       # 5/5/2025 REMOVED the shield; absence is correct
 ("furnace", "kind", "match"),                # 4/8/2025 building -> walking troop
 ("furnace", "speed_tiles", "match"),         # 6/10/2025 Slow -> Medium = 1.0
 ("dark_prince", "river_jump", "match"),      # 3/2/2022 gained river jump
 ("barbarians", "hitpoints", "match"),        # Barbarians CARD page current; Battle Ram page lags
 ("electro_spirit", "hits_per_attack", "match"),  # 8 others + jumped unit = 9
 ("electro_dragon", "hits_per_attack", "match"),  # 1 + 2 others = 3
 # --- flagged: has a ledger line ---
 ("bowler", "projectile_range", "line"),
 ("executioner", "projectile_range", "line"),
 ("furnace", "range_tiles", "line"),
 ("furnace", "spawn_interval_s", "line"),
 ("furnace", "hit_speed", "line"),
 ("furnace", "lifetime_s", "line"),
 ("firecracker", "sight", "line"),
 ("firecracker", "projectile_speed", "line"),
 ("dart_goblin", "speed", "line"),
 ("fire_spirit", "range", "line"),
 ("battle_ram", "spawn_unit_stats.speed_tiles", "line"),
 ("electro_spirit", "projectile_speed", "line"),
 ("electro_spirit", "chain_period_s", "line"),
 ("electro_spirit", "chain_range_tiles", "line"),
 ("electro_dragon", "chain_range_tiles", "line"),
 ("cannon_cart", "building_activation_pct", "line"),
 ("battle_healer", "heal_per_pulse", "line"),
 ("battle_healer", "heal_interval_s", "line"),
 ("battle_healer", "heal_radius_tiles", "line"),
 ("battle_healer", "spawn_heal", "line"),
 ("electro_giant", "crown_tower_damage", "line"),
 ("fisherman", "slow_duration_s", "line"),
 ("fisherman", "slow_pct", "line"),
 ("balloon", "knockback_tiles", "line"),
 ("bats", "hit_speed", "line"),
 ("dark_prince", "splash_radius_tiles", "line"),
 ("dark_prince", "charge_splash_radius_tiles", "line"),
 ("ghost_souldier", "invisibility_time_s", "line"),
 ("ghost_souldier", "spawn_damage", "line"),
 ("dark_prince", "dps", "line"),
 ("electro_giant", "dps", "line"),
]

if __name__ == "__main__":
    m = sum(1 for _, _, o in MANUAL if o == "match")
    l = sum(1 for _, _, o in MANUAL if o == "line")
    print("manual checks:", len(MANUAL), " match:", m, " flagged:", l)
    # sweep numbers, with the executioner hit_speed false-positive corrected to a match
    sweep_checked, sweep_matched = 363, 343
    # three sweep "matches" are really P3-lag updates already counted in MANUAL as lines
    # (bowler/executioner projectile_range, furnace range_tiles) -> and four sweep "matches"
    # are really P3 splits already counted as lines (bats/furnace hit_speed, firecracker
    # projectile_speed, ghost_souldier invisibility_time_s). Remove those 7 double-counts.
    dedup = 7
    print()
    print("fields_checked =", sweep_checked + len(MANUAL) - dedup)
    print("matches        =", sweep_matched + m - dedup)

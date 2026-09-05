"""Patch step 2 for jni_bridge.cpp (v2 buffs + area_effects): entity-loop additions.
Run from anywhere: python re_patch_bridge_loop.py <path to jni_bridge.cpp>
"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()

old = """    const int32_t level = raw_i32(0x120) + 1;
    if (category >= 4000000 && category < 5000000) {
      if (compact_observation) {
        continue;
      }"""
new = """    const int32_t level = raw_i32(0x120) + 1;
    if (!compact_observation) {
      // v2 debug histogram (does not alter any existing gate).
      const int32_t series = category < 0 ? -1 : category / 1000000;
      if (series >= 0 &&
          series < static_cast<int32_t>(class_histogram.size())) {
        ++class_histogram[static_cast<size_t>(series)];
        const uint64_t vtable_probe = raw_u64(0x00);
        if (vtable_probe >= base &&
            vtable_probe - base == kAreaEffectVtableRva) {
          ++area_effect_vtable_histogram[static_cast<size_t>(series)];
        }
      }
    }
    if (!compact_observation && category >= 0 && category < 4000000) {
      // v2: LogicAreaEffectObject (3M series; bridge_re.md section 4).
      // Keyed on the vtable so a wrong series assumption cannot leak junk.
      const uint64_t vtable = raw_u64(0x00);
      const uint64_t vtable_rva = vtable >= base ? vtable - base : 0;
      if (vtable_rva != kAreaEffectVtableRva || (side != 0 && side != 1)) {
        continue;
      }
      ObservedAreaEffect area{};
      area.id = entity;
      area.vtable_rva = vtable_rva;
      area.data_ptr = raw_u64(0x48);
      area.category = category;
      area.kind = kind;
      area.side = side;
      area.x = x;
      area.y = y;
      area.z = raw_i32(0x8C);
      area.card_id = card_id;
      area.owner_slot_a = raw_i32(0x94);
      area.owner_slot_b = raw_i32(0x98);
      area.level = raw_i32(0xFC);
      area.elapsed_ms = raw_i32(0x100);
      area.life_override_ms = raw_i32(0x114);
      area.follow_behaviour = raw[0x119];
      if (area.data_ptr != 0) {
        read_data_name(area.data_ptr, &area.name);
        memory.read(area.data_ptr + 0x40, &area.data_id);
        memory.read(area.data_ptr + 0xB8, &area.max_radius);
        memory.read(area.data_ptr + 0x118, &area.hit_speed_ms);
        memory.read(area.data_ptr + 0x121, &area.hits_air);
        memory.read(area.data_ptr + 0x122, &area.hits_ground);
        memory.read(area.data_ptr + 0x124, &area.damage);
        memory.read(area.data_ptr + 0x129, &area.only_enemies);
        memory.read(area.data_ptr + 0x12A, &area.only_own_troops);
        memory.read(area.data_ptr + 0x170, &area.life_base_ms);
        memory.read(area.data_ptr + 0x174, &area.life_per_level_ms);
        memory.read(
            area.data_ptr + 0x178, &area.life_per_level_over_cap_ms);
        memory.read(area.data_ptr + 0x17C, &area.radius);
        memory.read(area.data_ptr + 0x194, &area.controls_buff);
        memory.read(area.data_ptr + 0x1A0, &area.buff_time_base_ms);
        memory.read(area.data_ptr + 0x1A4, &area.buff_time_per_level_ms);
        uint64_t buff_data = 0;
        if (memory.read(area.data_ptr + 0xE8, &buff_data) &&
            buff_data != 0) {
          area.has_buff = 1;
        }
        unsigned char deflect = 0;
        memory.read(area.data_ptr + 0x1D0, &deflect);
        area.grows =
            (deflect != 0 || (area.life_override_ms & 6) != 0) ? 1 : 0;
      }
      // Life duration: 0xF6B4F0 -> [+0x114] if >= 0 else 0xDD5FD0(data,
      // level) = base + level * per_level (uncapped branch; the tournament
      // cap branch needs the Rarity virtual and is not evaluated here).
      if (area.life_override_ms >= 0) {
        area.life_ms = area.life_override_ms;
      } else if (area.data_ptr != 0) {
        area.life_ms =
            area.life_base_ms + area.level * area.life_per_level_ms;
      }
      if (area.life_ms >= 0) {
        area.remaining_ms = area.life_ms - area.elapsed_ms;
        if (area.remaining_ms < 0) {
          area.remaining_ms = 0;
        }
      }
      // 0xF6B520: radius grows linearly from Radius to MaxRadius over life.
      area.current_radius = area.radius;
      if (area.grows && area.life_ms > 0 && area.max_radius > area.radius) {
        const int64_t span =
            static_cast<int64_t>(area.max_radius - area.radius);
        int64_t t = area.elapsed_ms;
        if (t > area.life_ms) {
          t = area.life_ms;
        }
        area.current_radius =
            area.radius + static_cast<int32_t>(span * t / area.life_ms);
      }
      observed_area_effects.push_back(area);
      continue;
    }
    if (category >= 4000000 && category < 5000000) {
      if (compact_observation) {
        continue;
      }"""
assert old in s
s = s.replace(old, new, 1)

old = """    uint64_t target = 0;
    int32_t target_previous_x = 0, target_previous_y = 0;
    int32_t attack_progress_ms = 0, attack_load_timer_ms = 0;"""
new = """    // v2: buff manager = component[3] (getter 0xF852E0: bit 3 of [+0x30],
    // [+0x24] >= 4, [[+0x18]+0x18]). Manager: +0x18 array, +0x24 count.
    std::vector<ObservedBuff> buffs;
    int32_t buff_manager_count = -1;
    uint64_t buff_manager_vtable_rva = 0;
    const int32_t component_count = raw_i32(0x24);
    if (!compact_observation && (kind & 8) != 0 && component_count >= 4 &&
        component_array != 0) {
      uint64_t manager = 0;
      uint64_t manager_vtable = 0;
      uint64_t buff_array = 0;
      int32_t buff_count = -1;
      if (memory.read(component_array + 0x18, &manager) && manager != 0 &&
          memory.read(manager, &manager_vtable) &&
          memory.read(manager + 0x18, &buff_array) &&
          memory.read(manager + 0x24, &buff_count)) {
        buff_manager_vtable_rva =
            manager_vtable >= base ? manager_vtable - base : 0;
        buff_manager_count = buff_count;
        const int32_t usable = buff_count < 0
            ? 0
            : (buff_count > kMaxObservedBuffs ? kMaxObservedBuffs
                                              : buff_count);
        for (int32_t buff_index = 0; buff_index < usable; ++buff_index) {
          uint64_t instance = 0;
          unsigned char instance_raw[0x70] = {};
          if (buff_array == 0 ||
              !memory.read(
                  buff_array + static_cast<uintptr_t>(buff_index) * 8,
                  &instance) ||
              instance == 0 ||
              !memory.read_bytes(
                  instance, instance_raw, sizeof(instance_raw))) {
            continue;
          }
          auto inst_i32 = [&instance_raw](size_t offset) {
            int32_t value = 0;
            std::memcpy(&value, instance_raw + offset, sizeof(value));
            return value;
          };
          uint64_t owner = 0, buff_data = 0;
          std::memcpy(&owner, instance_raw + 0x00, sizeof(owner));
          std::memcpy(&buff_data, instance_raw + 0x18, sizeof(buff_data));
          ObservedBuff buff{};
          buff.remaining_ms = inst_i32(0x08);
          buff.total_ms = inst_i32(0x0C);
          buff.level = inst_i32(0x28);
          buff.instigator_side = inst_i32(0x40);
          buff.shield_hp = inst_i32(0x54);
          if (owner != entity) {
            buff.flags |= 0x80000000u;  // owner mismatch: layout suspect
          }
          if (buff_data != 0) {
            read_data_name(buff_data, &buff.name);
            memory.read(buff_data + 0x40, &buff.data_id);
            memory.read(buff_data + 0xC0, &buff.damage_reduction);
            memory.read(buff_data + 0xE0, &buff.hit_speed_multiplier);
            memory.read(buff_data + 0xE4, &buff.speed_multiplier);
            memory.read(buff_data + 0xEC, &buff.spawn_speed_multiplier);
            memory.read(buff_data + 0x108, &buff.invisible);
            memory.read(buff_data + 0x12B, &buff.enable_stacking);
            memory.read(buff_data + 0x140, &buff.data_shield);
            memory.read(buff_data + 0x19C, &buff.hitpoint_multiplier);
            memory.read(buff_data + 0x1D0, &buff.damage_per_second);
            memory.read(buff_data + 0x1D4, &buff.heal_per_second);
            memory.read(buff_data + 0x200, &buff.lock_target);
            memory.read(buff_data + 0x220, &buff.switch_team);
          }
          // Derived flags (interpretation, not engine state):
          //   1 cannot_attack (hit speed mult <= -100)
          //   2 cannot_move (speed mult <= -100)
          //   4 slowed (-100 < speed mult < 0)
          //   8 hasted (speed or hit speed mult > 0)
          //  16 shield (instance shield hp > 0)
          //  32 invisible  64 dot  128 heal  256 damage_reduction
          // 512 switch_team  1024 lock_target  2048 permanent (-1)
          if (buff.hit_speed_multiplier <= -100) buff.flags |= 1u;
          if (buff.speed_multiplier <= -100) buff.flags |= 2u;
          if (buff.speed_multiplier < 0 && buff.speed_multiplier > -100) {
            buff.flags |= 4u;
          }
          if (buff.speed_multiplier > 0 || buff.hit_speed_multiplier > 0) {
            buff.flags |= 8u;
          }
          if (buff.shield_hp > 0) buff.flags |= 16u;
          if (buff.invisible != 0) buff.flags |= 32u;
          if (buff.damage_per_second > 0) buff.flags |= 64u;
          if (buff.heal_per_second > 0) buff.flags |= 128u;
          if (buff.damage_reduction != 0) buff.flags |= 256u;
          if (buff.switch_team != 0) buff.flags |= 512u;
          if (buff.lock_target != 0) buff.flags |= 1024u;
          if (buff.remaining_ms == -1) buff.flags |= 2048u;
          buffs.push_back(buff);
        }
      }
    }
    uint64_t target = 0;
    int32_t target_previous_x = 0, target_previous_y = 0;
    int32_t attack_progress_ms = 0, attack_load_timer_ms = 0;"""
assert old in s
s = s.replace(old, new, 1)

old = """        path_segment_direction_y, path_node_consumed,
        attack_component_valid, move_component_valid, path_nodes, {}});
  }"""
new = """        path_segment_direction_y, path_node_consumed,
        attack_component_valid, move_component_valid, path_nodes, {},
        buffs, buff_manager_count, buff_manager_vtable_rva});
  }"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print("ok")

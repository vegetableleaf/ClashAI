"""Patch step 3 for jni_bridge.cpp (v2): JSON emission of buffs + area_effects.
python re_patch_bridge_json.py <path to jni_bridge.cpp>
"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()

old = """    result.append(row);
    if (!entity.move_component_valid) {
      result.append("null}");
    } else {
      result.push_back('[');
      for (int32_t node = 0; node < entity.path_node_count; ++node) {
        char value[32];
        std::snprintf(
            value, sizeof(value), "%s%d", node == 0 ? "" : ",",
            entity.path_nodes[static_cast<size_t>(node)]);
        result.append(value);
      }
      result.append("]}");
    }
    ++emitted;"""
new = """    result.append(row);
    if (!entity.move_component_valid) {
      result.append("null");
    } else {
      result.push_back('[');
      for (int32_t node = 0; node < entity.path_node_count; ++node) {
        char value[32];
        std::snprintf(
            value, sizeof(value), "%s%d", node == 0 ? "" : ",",
            entity.path_nodes[static_cast<size_t>(node)]);
        result.append(value);
      }
      result.push_back(']');
    }
    // v2 (full observe only): buffs. Not part of state_hash.
    {
      char manager_json[96];
      std::snprintf(
          manager_json, sizeof(manager_json),
          ",\\"buff_manager_count\\":%d,\\"buff_manager_vtable_rva\\":\\"0x%llx\\","
          "\\"buffs\\":[",
          entity.buff_manager_count,
          static_cast<unsigned long long>(entity.buff_manager_vtable_rva));
      result.append(manager_json);
      size_t emitted_buffs = 0;
      for (const ObservedBuff& buff : entity.buffs) {
        char buff_row[640];
        std::snprintf(
            buff_row, sizeof(buff_row),
            "%s{\\"name\\":\\"%s\\",\\"data_id\\":%d,\\"remaining_ms\\":%d,"
            "\\"total_ms\\":%d,\\"level\\":%d,\\"instigator_side\\":%d,"
            "\\"shield_hp\\":%d,\\"flags\\":%u,\\"hit_speed_multiplier\\":%d,"
            "\\"speed_multiplier\\":%d,\\"spawn_speed_multiplier\\":%d,"
            "\\"damage_reduction\\":%d,\\"hitpoint_multiplier\\":%d,"
            "\\"damage_per_second\\":%d,\\"heal_per_second\\":%d,"
            "\\"data_shield\\":%d,\\"invisible\\":%d,\\"lock_target\\":%d,"
            "\\"switch_team\\":%d,\\"enable_stacking\\":%d}",
            emitted_buffs == 0 ? "" : ",", buff.name.c_str(), buff.data_id,
            buff.remaining_ms, buff.total_ms, buff.level,
            buff.instigator_side, buff.shield_hp, buff.flags,
            buff.hit_speed_multiplier, buff.speed_multiplier,
            buff.spawn_speed_multiplier, buff.damage_reduction,
            buff.hitpoint_multiplier, buff.damage_per_second,
            buff.heal_per_second, buff.data_shield,
            static_cast<int32_t>(buff.invisible),
            static_cast<int32_t>(buff.lock_target),
            static_cast<int32_t>(buff.switch_team),
            static_cast<int32_t>(buff.enable_stacking));
        result.append(buff_row);
        ++emitted_buffs;
      }
      result.append("]}");
    }
    ++emitted;"""
assert old in s
s = s.replace(old, new, 1)

old = """  result.append(",\\"effects_classified\\":");
  result.append(
      observed_effects.size() == projectile_count ? "true" : "false");
  } else {"""
new = """  result.append(",\\"effects_classified\\":");
  result.append(
      observed_effects.size() == projectile_count ? "true" : "false");
  // v2 (full observe only): area effect objects. Not part of state_hash.
  result.append(",\\"area_effects\\":[");
  for (size_t index = 0; index < observed_area_effects.size(); ++index) {
    const ObservedAreaEffect& area = observed_area_effects[index];
    char row[1024];
    std::snprintf(
        row, sizeof(row),
        "%s{\\"id\\":\\"0x%llx\\",\\"name\\":\\"%s\\",\\"data_id\\":%d,"
        "\\"data_ptr\\":\\"0x%llx\\",\\"vtable_rva\\":\\"0x%llx\\","
        "\\"category\\":%d,\\"kind\\":%d,\\"side\\":%d,\\"x\\":%d,\\"y\\":%d,"
        "\\"z\\":%d,\\"card_id\\":%d,\\"level\\":%d,\\"elapsed_ms\\":%d,"
        "\\"life_override_ms\\":%d,\\"life_base_ms\\":%d,"
        "\\"life_per_level_ms\\":%d,\\"life_per_level_over_cap_ms\\":%d,"
        "\\"life_ms\\":%d,\\"remaining_ms\\":%d,\\"radius\\":%d,"
        "\\"max_radius\\":%d,\\"current_radius\\":%d,\\"grows\\":%d,"
        "\\"buff_time_base_ms\\":%d,\\"buff_time_per_level_ms\\":%d,"
        "\\"damage\\":%d,\\"hit_speed_ms\\":%d,\\"controls_buff\\":%d,"
        "\\"has_buff\\":%d,\\"hits_air\\":%d,\\"hits_ground\\":%d,"
        "\\"only_enemies\\":%d,\\"only_own_troops\\":%d,"
        "\\"follow_behaviour\\":%d,\\"owner_slot_a\\":%d,\\"owner_slot_b\\":%d}",
        index == 0 ? "" : ",", static_cast<unsigned long long>(area.id),
        area.name.c_str(), area.data_id,
        static_cast<unsigned long long>(area.data_ptr),
        static_cast<unsigned long long>(area.vtable_rva), area.category,
        area.kind, area.side, area.x, area.y, area.z, area.card_id,
        area.level, area.elapsed_ms, area.life_override_ms,
        area.life_base_ms, area.life_per_level_ms,
        area.life_per_level_over_cap_ms, area.life_ms, area.remaining_ms,
        area.radius, area.max_radius, area.current_radius,
        static_cast<int32_t>(area.grows), area.buff_time_base_ms,
        area.buff_time_per_level_ms, area.damage, area.hit_speed_ms,
        area.controls_buff, static_cast<int32_t>(area.has_buff),
        static_cast<int32_t>(area.hits_air),
        static_cast<int32_t>(area.hits_ground),
        static_cast<int32_t>(area.only_enemies),
        static_cast<int32_t>(area.only_own_troops),
        static_cast<int32_t>(area.follow_behaviour), area.owner_slot_a,
        area.owner_slot_b);
    result.append(row);
  }
  result.append("],\\"area_effect_count\\":");
  result.append(std::to_string(observed_area_effects.size()));
  result.append(",\\"class_histogram\\":[");
  for (size_t index = 0; index < class_histogram.size(); ++index) {
    if (index != 0) {
      result.push_back(',');
    }
    result.append(std::to_string(class_histogram[index]));
  }
  result.append("],\\"area_effect_vtable_histogram\\":[");
  for (size_t index = 0; index < area_effect_vtable_histogram.size();
       ++index) {
    if (index != 0) {
      result.push_back(',');
    }
    result.append(std::to_string(area_effect_vtable_histogram[index]));
  }
  result.append("],\\"bridge_ext\\":\\"buffs_area_effects_v2_unverified\\"");
  } else {"""
assert old in s
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print("ok")

"""Offline synthetic tests. Never runs ADB, a target, debugger or network client."""
import copy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import qualify as q
from review import summarize, validate_result


class FakeReader:
    def __init__(self, cells, maps=None):
        self.cells = cells
        self.maps = maps or [{'lo': 1, 'hi': 1000000, 'perms': 'rw-p'}]
    def scalar(self, address, kind):
        value = self.cells[address]
        if isinstance(value, list):
            return value.pop(0)
        return value
    def read(self, address, size):
        value = self.cells[address]
        if isinstance(value, bytes):
            return value[:size]
        raise AssertionError('unprepared fake read')


def synthetic_binding():
    # Arbitrary synthetic layouts, unrelated to private target values.
    keys = ('manager.current_state', 'manager.current_state_type', 'manager.pending_state_type',
            'manager.replay_data', 'battle_state.battle', 'battle_state.core_accumulator',
            'battle.tick', 'battle.logic')
    fields = {k: {'offset': (i + 1) * 16} for i, k in enumerate(keys)}
    fields['loading_state_vtable'] = {'rva': 8500}
    entries = {'manager_global': {'rva': 100},
               'skip_core_and_presentation_flag': {'locator': {'global_pointer_rva': 200, 'member_offset': 16, 'width': 1}},
               'state_factory': {'battle_type': 71, 'vtable_rva': 7500, 'update_slot': 5},
               'battle_state_update': {'rva': 9100}, 'game_main_init': {'rva': 9200}}
    extension = {'manager_parent_offset': 152, 'control_owner_offset': 0, 'state_type_offset': 152,
                 'game_main_global_rva': 300, 'game_main_vtable_rva': 8000,
                 'game_main_context_offset': 16, 'game_main_init_slot': 5}
    return {'entries': entries, 'fields': fields}, extension


class Tests(unittest.TestCase):
    def test_maps_and_nonzero_segment_bias(self):
        maps = q.parse_maps('5000-6000 r--p 00002000 01:02 7 /data/app/a/libg.so\n'
                            '7000-8000 r-xp 00004000 01:02 7 /data/app/a/libg.so\n')
        # ELF PT_LOADs deliberately have different virtual and file offsets.
        headers = [(1, 4, 8192, 12288, 0, 4096, 4096, 4096),
                   (1, 5, 16384, 20480, 0, 4096, 4096, 4096)]
        self.assertEqual(q.module_base(maps, headers, 'unused.apk', None), 8192)
        for row in maps:
            row['offset'] += 65536
            row['path'] = '/data/app/a/split.apk'
        self.assertEqual(q.module_base(maps, headers, 'split.apk', 65536), 8192)
        with self.assertRaises(q.Blocked):
            q.module_base(maps, headers, 'split.apk', 65537)
        duplicate = [dict(m, lo=m['lo'] + 100000, hi=m['hi'] + 100000) for m in maps]
        with self.assertRaises(q.Blocked):
            q.module_base(maps + duplicate, headers, 'split.apk', 65536)

    def test_pid_stat_parentheses(self):
        # Linux stat tail starts at field 3; starttime is field 22.
        text = '123 (app name ) with parens) ' + ' '.join(str(i) for i in range(3, 53))
        self.assertEqual(q.start_time(text), '22')

    def test_pointer_chain_and_battle(self):
        b, x = synthetic_binding()
        base, manager, control, state, battle, game = 1000, 20000, 30000, 40000, 50000, 60000
        cells = {base + 100: manager, base + 200: control, base + 300: game,
                 manager + 152: 70000, control: 70000, control + 16: 1,
                 state: base + 7500, state + 152: 71, base + 7500 + 40: base + 9100,
                 game: base + 8000, game + 16: 80000, base + 8000 + 40: base + 9200}
        for k, value in {'manager.current_state': state, 'manager.current_state_type': 71,
                         'manager.pending_state_type': 0, 'manager.replay_data': 90000,
                         'battle_state.battle': battle, 'battle_state.core_accumulator': 0.025,
                         'battle.tick': 40, 'battle.logic': 95000}.items():
            root = manager if k.startswith('manager.') else state if k.startswith('battle_state.') else battle
            cells[root + b['fields'][k]['offset']] = value
        s = q.snapshot(FakeReader(copy.deepcopy(cells)), base, b, x)
        self.assertEqual(s['values']['scheduling_flag']['address'], control + 16)
        self.assertTrue(s['values']['scheduling_owner_matches_parent'])
        self.assertTrue(s['values']['battle_update_slot_matches'])
        self.assertTrue(s['values']['game_main_init_slot_matches'])
        self.assertEqual(s['values']['battle.tick']['value'], 40)
        changed = copy.deepcopy(cells)
        changed[base + 100] = [manager, manager + 1]
        with self.assertRaisesRegex(q.Blocked, 'ROOT_CHANGED'):
            q.snapshot(FakeReader(changed), base, b, x)
        with self.assertRaisesRegex(q.Blocked, 'SCHEDULING_NOT_RW'):
            q.snapshot(FakeReader(cells, [{'lo': 1, 'hi': 1000000, 'perms': 'rwxp'}]), base, b, x)

    def test_null_roots_are_not_zero_samples(self):
        b, x = synthetic_binding()
        s = q.snapshot(FakeReader({1100: 0, 1200: 0, 1300: 0}), 1000, b, x)
        self.assertNotIn('scheduling_flag', s['values'])
        self.assertNotIn('battle.tick', s['values'])

    def test_loading_state_and_native_readiness(self):
        b, x = synthetic_binding()
        extra = ('loading_update_vtable_slot', 'loading_complete_vtable_slot', 'loading_phase',
                 'loading_ready_latch', 'loading_future_primary', 'loading_future_secondary',
                 'loading_task', 'data_task.tables', 'data_task.resources', 'data_task.phase',
                 'data_task.range_cursor', 'data_tables.ready', 'resource_collection.count')
        for i, key in enumerate(extra):
            b['fields'][key] = {'offset': 256 + i * 16}
        b['fields']['resource_gate_global'] = {'rva': 400}
        b['entries']['loading_state_update'] = {'rva': 9300}
        b['entries']['loading_state_complete'] = {'rva': 9400}
        x['resource_gate_phase_offset'] = 16
        base, manager, state, task, tables, resources, gate = 1000, 20000, 40000, 50000, 60000, 70000, 80000
        cells = {1100: manager, 1200: 0, 1300: 0, 1400: gate,
                 manager + 152: 90000, state: base + 8500, state + 152: 72,
                 gate + 16: 7}
        values = {'manager.current_state': (manager, state), 'manager.current_state_type': (manager, 72),
                  'manager.pending_state_type': (manager, 0), 'manager.replay_data': (manager, 0),
                  'loading_update_vtable_slot': (base + 8500, base + 9300),
                  'loading_complete_vtable_slot': (base + 8500, base + 9400),
                  'loading_phase': (state, 5), 'loading_ready_latch': (state, 1),
                  'loading_future_primary': (state, 91000), 'loading_future_secondary': (state, 92000),
                  'loading_task': (state, task), 'data_task.tables': (task, tables),
                  'data_task.resources': (task, resources), 'data_task.phase': (task, 2),
                  'data_task.range_cursor': (task, 42), 'data_tables.ready': (tables, 1),
                  'resource_collection.count': (resources, 43)}
        for k, (root, value) in values.items():
            cells[root + b['fields'][k]['offset']] = value
        s = q.snapshot(FakeReader(cells), base, b, x)
        self.assertTrue(s['values']['loading_update_slot_matches'])
        self.assertTrue(s['values']['loading_complete_slot_matches'])
        self.assertEqual(s['values']['data_tables.ready']['value'], 1)
        self.assertEqual(s['values']['resource_gate.phase']['value'], 7)
        self.assertNotIn('battle.tick', s['values'])

    def test_result_safety_and_coverage(self):
        r = q.new_result('a' * 64)
        validate_result(r)
        for name in ('target_writes', 'software_breakpoints', 'patches_qualified'):
            bad = copy.deepcopy(r)
            bad[name] = 1
            with self.assertRaises(q.Blocked):
                validate_result(bad)
        bad = copy.deepcopy(r)
        bad['probes'][1] = bad['probes'][0]
        with self.assertRaises(q.Blocked):
            validate_result(bad)
        bad = copy.deepcopy(r)
        bad['sites'][0]['patch_qualified'] = True
        with self.assertRaises(q.Blocked):
            validate_result(bad)

    def test_result_invalid_hash_and_boolean_number(self):
        bad = q.new_result('not-a-hash')
        with self.assertRaises(q.Blocked):
            validate_result(bad)
        bad = q.new_result('a' * 64)
        bad['patches_qualified'] = False
        with self.assertRaises(q.Blocked):
            validate_result(bad)

    def test_no_pid_yet_is_not_command_failure(self):
        device = object.__new__(q.Device)
        device.argv = ['never-run-adb']
        completed = q.subprocess.CompletedProcess([], 1, stdout=b'', stderr=b'')
        with patch.object(q.subprocess, 'run', return_value=completed):
            self.assertEqual(device.pids(), [])
        completed = q.subprocess.CompletedProcess([], 1, stdout=b'error', stderr=b'')
        with patch.object(q.subprocess, 'run', return_value=completed):
            with self.assertRaises(q.Blocked):
                device.pids()

    def test_transitions_do_not_cross_generations(self):
        def sample(tick, accumulator, flag, generation=1):
            return {'atomic': False, 'values': {k: {'value': v} for k, v in
                    {'manager': generation, 'manager.current_state': 3, 'battle_state.battle': 5,
                     'scheduling_control': 7, 'battle.tick': tick,
                     'battle_state.core_accumulator': accumulator, 'scheduling_flag': flag}.items()}}
        result = summarize([sample(1, 0.04, 0), sample(2, 0.01, 1), sample(100, 0.03, 0, 2)])
        self.assertEqual(result['flag_changes'], 1)
        self.assertEqual(result['tick_increases'], 1)
        self.assertEqual(result['accumulator_changes'], 1)
        self.assertEqual(result['generation_changes'], 1)
        self.assertFalse(result['function_entry_proven'])

    def test_read_mapping_and_short_read_checks(self):
        reader = object.__new__(q.Reader)
        reader.maps = [{'lo': 100, 'hi': 108, 'perms': 'r--p'}]
        reader.command = lambda _: b'1234'
        self.assertEqual(reader.read(100, 4), b'1234')
        with self.assertRaises(q.Blocked):
            reader.read(104, 8)
        with self.assertRaises(q.Blocked):
            reader.read(100, 8)

    def test_network_gate(self):
        with patch.object(q.sys, 'platform', 'linux'), patch.object(q.subprocess, 'check_output',
                return_value=json.dumps([{'ifname': 'lo'}, {'ifname': 'eth0'}]).encode()):
            with self.assertRaisesRegex(q.Blocked, 'NETWORK_NOT_ISOLATED'):
                q.isolated()

    def test_elf_rejects_non_target(self):
        with self.assertRaises(q.Blocked):
            q.elf_headers(bytes(64))

    def test_live_named_jni_lookup(self):
        base, dyn, strings, symbols, table = 100000, 200, 3000, 4000, 5000
        name = b'JNI_OnLoad'
        hv = 5381
        for c in name:
            hv = (hv * 33 + c) & ((1 << 32) - 1)
        cells = {base + dyn + i * 16: struct.pack('<qQ', k, v) for i, (k, v) in enumerate(
            [(5, strings), (6, symbols), (10, 200), (11, 24), (1879047925, table), (0, 0)])}
        cells.update({base + table: struct.pack('<IIII', 1, 1, 1, 0),
                      base + table + 24: 1, base + table + 28: hv | 1,
                      base + symbols + 24: struct.pack('<IBBHQQ', 1, 18, 0, 1, 1234, 80),
                      base + strings + 1: name + b'\0'})
        reader = FakeReader(cells, [{'lo': base, 'hi': base + 10000}])
        headers = [(2, 4, dyn, dyn, 0, 96, 96, 8)]
        self.assertEqual(q.live_jni(reader, base, headers), 1234)
        cells[base + strings + 1] = b'not_the_JNI\0'
        with self.assertRaises(q.Blocked):
            q.live_jni(reader, base, headers)


if __name__ == '__main__':
    outcome = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    print('QUALIFY_OFFLINE_TESTS_OK')

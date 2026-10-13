"""Synthetic offline safety/receipt tests. No libg, emulator, ADB or network."""
import copy
import json
from pathlib import Path
import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import jsonschema
from common import HERE, ROOT, STAGES, BOUNDARY, SITES, Blocked, digest, verify_network, verify_emulator_command, verify_hashes
from build import deny_callbacks, UPSTREAM, DENY_CLASSES
from run import new_result, events_from, select_installed_libg
import run as worker_run
from review import assess, complete_sequence
from verify import observer_safe, leaked


def success():
    r = new_result('a' * 32)
    r.update(status='collected', returncode=0, last_completed='create_game_main',
             isolation_before={'namespace': 'fixture'}, isolation_after={'namespace': 'fixture'},
             identity={'expected_jni_delta': '128'})
    def row(stage, event, value=None):
        r['events'].append(dict(schema_version=1, token=r['token'], pid=123, stage=stage, event=event, value=value))
    for stage in STAGES:
        row(stage, 'before'); row(stage, 'after')
        if stage not in ('observer_load', 'package_context'):
            row(stage, 'observation', dict(module_base='4096', jni_delta='128', game_main=None, game_main_status='absent', atomic=False))
    row(BOUNDARY, 'before'); row(BOUNDARY, 'boundary', 'normal minimal init stop')
    return r


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.out = HERE.parents[2] / '.local/jnihost-ro-tests' / uuid.uuid4().hex
        self.out.mkdir(parents=True)
        self.r = success()

    # Retain tiny synthetic receipts under the existing ignored local tree.

    def evaluate(self, finding=None): return assess(self.r, self.out, finding)

    def evidence(self, text='libg reported an explicit refusal'):
        p = self.out / 'host.stderr'
        p.write_text(text + '\n', encoding='utf-8')
        self.r.update(returncode=2, failure_stage='create_game_main', host_output={'stderr': p.name})
        self.r['events'] = self.r['events'][:-4]
        self.r['receipts'] = {p.name: digest(p)}
        (self.out / 'result.json').write_text(json.dumps(self.r), encoding='utf-8')
        return dict(kind='libg_refusal', origin='libg', reviewer='offline fixture', rationale='synthetic explicit libg evidence',
                    result_sha256=digest(self.out / 'result.json'), stage='create_game_main',
                    evidence=dict(file=p.name, sha256=digest(p), line_start=1, line_end=1, excerpt=text))

    def test_success_absent_object_stays_absent(self):
        self.assertEqual(self.evaluate()['classification'], 'a')
        self.assertIsNone(self.r['events'][3]['value'])

    def test_identified_object(self):
        obs = next(e['value'] for e in self.r['events'] if e['event'] == 'observation')
        obs.update(game_main='8192', game_main_status='identified')
        self.assertEqual(self.evaluate()['classification'], 'a')

    def test_unverified_pointer_not_promoted(self):
        obs = next(e['value'] for e in self.r['events'] if e['event'] == 'observation')
        obs.update(game_main='8192', game_main_status='unverified_pointer')
        self.assertFalse(complete_sequence(self.r))

    def test_order_required(self):
        self.r['events'][0:2] = reversed(self.r['events'][0:2])
        self.assertEqual(self.evaluate()['classification'], 'unclassified')

    def test_jni_delta_mismatch(self):
        self.r['identity']['expected_jni_delta'] = '129'
        self.assertEqual(self.evaluate()['classification'], 'unclassified')

    def test_generic_crash_is_not_refusal(self):
        self.evidence('Fatal signal')
        self.assertEqual(self.evaluate()['classification'], 'unclassified')

    def test_timeout_is_not_rendering(self):
        self.r.update(returncode=137, timeout=True)
        self.assertEqual(self.evaluate()['classification'], 'unclassified')

    def test_explicit_refusal_stops(self):
        answer = self.evaluate(self.evidence())
        self.assertEqual(answer['classification'], 'b')
        self.assertTrue(answer['stop_required'])
        self.assertEqual(answer['patches_qualified'], 0)

    def test_rendering_needs_site_attribution(self):
        f = self.evidence('renderer unavailable in native init')
        f.update(kind='rendering_dependency', site_group='game_main_init',
                 site_ids=['renderer_bootstrap_call'], site_mapping_basis='synthetic source/runtime attribution')
        a = self.evaluate(f)
        self.assertEqual(a['classification'], 'c')
        self.assertEqual(a['required_sites'], ['renderer_bootstrap_call'])
        self.assertFalse(a['target_site_requirement_proven'])

    def test_invalid_site_mapping_rejected(self):
        f = self.evidence()
        f.update(kind='rendering_dependency', site_group='game_main_init', site_ids=['loading_platform_ui_call'], site_mapping_basis='bad')
        with self.assertRaises(Blocked): self.evaluate(f)

    def test_fake_excerpt_rejected(self):
        f = self.evidence(); f['evidence']['excerpt'] = 'invented'
        with self.assertRaises(Blocked): self.evaluate(f)

    def test_result_drift_rejected(self):
        f = self.evidence(); f['result_sha256'] = 'b' * 64
        with self.assertRaises(Blocked): self.evaluate(f)

    def test_receipt_tampering_rejected(self):
        self.evidence(); (self.out / 'host.stderr').write_text('changed')
        with self.assertRaises(Blocked): self.evaluate()

    def test_swallowed_host_callback_is_blocked(self):
        self.evidence('HOST_UNSUPPORTED_CALLBACK:QuagoManager.enable')
        self.r['returncode'] = 0
        self.assertEqual(self.evaluate()['classification'], 'blocked')

    def test_missing_isolation_blocks(self):
        self.r['isolation_after'] = None
        self.assertEqual(self.evaluate()['classification'], 'blocked')

    def test_policy_violation_rejected(self):
        self.r['policy']['code_patches'] = 1
        with self.assertRaises(Blocked): self.evaluate()

    def test_event_token_and_pid(self):
        text = '\n'.join('ORACLE_V5 ' + json.dumps(e) for e in self.r['events'])
        self.assertEqual(events_from(text, self.r['token']), self.r['events'])
        with self.assertRaises(Blocked): events_from(text, 'b' * 32)
        self.r['events'][-1]['pid'] = 124
        text = '\n'.join('ORACLE_V5 ' + json.dumps(e) for e in self.r['events'])
        with self.assertRaises(Blocked): events_from(text, self.r['token'])

    def test_loopback_only_ipv4_ipv6(self):
        verify_network([{'ifname': 'lo'}], [{'dev': 'lo'}])
        for links, routes in (([{'ifname': 'lo'}, {'ifname': 'eth0'}], []),
                              ([{'ifname': 'lo'}], [{'dev': 'eth0', 'dst': 'default'}]),
                              ([{'ifname': 'lo'}], [{'dst': '::/0'}])):
            with self.assertRaises(Blocked): verify_network(links, routes)

    def test_emulator_identity(self):
        argv = ['/sdk/qemu-system-x86_64', '-avd', 'oracle_fixture', '-port', '5554']
        verify_emulator_command(argv, 'emulator-5554')
        with self.assertRaises(Blocked): verify_emulator_command(argv, 'emulator-5556')
        with self.assertRaises(Blocked): verify_emulator_command(argv + ['-http-proxy', 'proxy'], 'emulator-5554')

    def test_hash_traversal_rejected(self):
        with self.assertRaises(Blocked): verify_hashes({'../escape': 'a' * 64}, self.out)

    def test_callback_contract_fails_closed(self):
        for name in DENY_CLASSES:
            raw = (UPSTREAM / ('java/com/supercell/titan/' + name + '.java')).read_text()
            result = deny_callbacks(raw, name)
            self.assertIn('throw royale.nativehost.JniHost.unsupportedCallback(', result)
            self.assertEqual(raw.count('native void'), result.count('native void'))
        self.assertNotIn('return false;', deny_callbacks((UPSTREAM / 'java/com/supercell/titan/ApplicationUtilBase.java').read_text(), 'ApplicationUtilBase'))

    def test_source_audits_with_negative_controls(self):
        source = (HERE / 'observer.cpp').read_text()
        self.assertTrue(observer_safe(source))
        self.assertFalse(observer_safe(source + 'pwrite();'))
        self.assertTrue(leaked('0' + 'x12345'))

    def test_schema_accepts_results_rejects_patch(self):
        schema = json.loads((HERE / 'results.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(self.r, schema)
        jsonschema.validate(new_result('b' * 32), schema)
        self.r['policy']['code_patches'] = 1
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(self.r, schema)

    def test_native_file_and_apk_member_selection(self):
        class Fake:
            present, hash = 0, 'a' * 64
            def capture(self, *args, **kwargs): return self.present, '', ''
            def call(self, *args): return self.hash + '  file'
        d = Fake()
        b = {'libg_sha256': 'a' * 64}
        manifest = {'native_libraries': [{'member': 'lib/x86_64/libg.so', 'apk': 'split.apk'}],
                    'apks': [{'name': 'split.apk', 'sha256': 'b' * 64}]}
        installed = [{'path': '/data/app/fixture/split.apk', 'sha256': 'b' * 64}]
        info = '  legacyNativeLibraryDir=/data/app/fixture/lib\n'
        self.assertEqual(select_installed_libg(d, manifest, b, installed, info)[3], 'package_manager_native_file')
        d.hash = 'c' * 64
        with self.assertRaises(Blocked): select_installed_libg(d, manifest, b, installed, info)
        d.present = 1
        self.assertEqual(select_installed_libg(d, manifest, b, installed, info)[0], '/data/app/fixture/split.apk!/lib/x86_64/libg.so')

    def test_all_site_ids_unique(self):
        flat = [s for group in SITES.values() for s in group]
        self.assertEqual(len(flat), 11)
        self.assertEqual(len(set(flat)), 11)

    def test_worker_launch_contract_and_attempt_latch(self):
        build = self.out / 'build'
        build.mkdir()
        (build / 'build.json').write_text('{}')
        calls = []
        token = 'c' * 32
        class FakeDevice:
            def __init__(self, serial, out): self.out = out
            def check(self): return {'api': '32'}
            def call(self, *args, **kwargs):
                calls.append(args)
                if args[:2] == ('shell', 'ps'): return 'NAME\ninit\n'
                if args[:3] == ('shell', 'dumpsys', 'package'): return 'legacyNativeLibraryDir=/data/app/fixture/lib'
                if args[:2] == ('shell', 'sha256sum'): return 'a' * 64 + '  file'
                return ''
            def capture(self, args, **kwargs):
                calls.append(tuple(args))
                if args[0] == 'shell':
                    rows = success()['events']
                    for row in rows: row['token'] = token
                    return 0, '\n'.join('ORACLE_V5 ' + json.dumps(e) for e in rows), 'fixture'
                return 0, '', 'log'
        built = {'inputs': {}, 'libg_sha256': 'a' * 64, 'artifacts': {'jnihost-ro.jar': 'a' * 64, 'libjnihost_ro.so': 'a' * 64},
                 'sources': {}, 'upstream': {}, 'jni_delta': '128'}
        args = SimpleNamespace(build_dir=build, serial='emulator-5554', emulator_pid=42)
        with patch.object(worker_run, 'load_inputs', return_value=({'libg_sha256': 'a' * 64}, {}, [], {})), \
             patch.object(worker_run, 'read_json', return_value=built), \
             patch.object(worker_run, 'verify_hashes'), \
             patch.object(worker_run, 'isolation', return_value={'namespace': 'fixture'}), \
             patch.object(worker_run, 'RecordingDevice', FakeDevice), \
             patch.object(worker_run, 'installed_check', return_value=[]), \
             patch.object(worker_run, 'select_installed_libg', return_value=('/data/app/fixture/lib/x86_64/libg.so', '/data/app/fixture/lib/x86_64/libg.so', 'a' * 64, 'package_manager_native_file')):
            r = new_result(token)
            worker_run.run_once(args, self.out, r)
            self.assertEqual(r['last_completed'], 'create_game_main')
            self.assertEqual(r['returncode'], 0)
            self.assertTrue((build / 'ATTEMPT.json').exists())
            launch = [c for c in calls if len(c) == 2 and '/system/bin/app_process' in c[1]]
            self.assertEqual(len(launch), 1)
            self.assertIn('timeout -s KILL 45', launch[0][1])
            self.assertIn('royale.nativehost.JniHost', launch[0][1])
            self.assertNotIn('am start', str(calls))
            with self.assertRaises(FileExistsError): worker_run.run_once(args, self.out, new_result(token))
            self.assertEqual(len([c for c in calls if len(c) == 2 and '/system/bin/app_process' in c[1]]), 1)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful(): print('JNIHOST_RO_TESTS_OK')
    raise SystemExit(0 if result.wasSuccessful() else 1)

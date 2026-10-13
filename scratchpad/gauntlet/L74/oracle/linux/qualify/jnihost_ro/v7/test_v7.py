"""Synthetic lifecycle/receipt tests; no device, libg or network execution."""
import copy
import json
import shlex
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from common import HERE, ROOT, LIMITS, STAGES, BOUNDARY, Blocked, digest, selected_stages, load_inputs
from binding import project, header, number, validate_recipe
from run import new_result, events_from, calls_from, run_once
import run as worker
from review import assess, FIXED_CALLS
from verify import observer_safe, leaked


def fixture(limit='load-only', failure=None, message='Fatal signal', hang=False):
    r = new_result('a' * 32)
    r.update(status='collected', stage_limit=limit, returncode=137 if hang else 2 if failure else 0,
             timeout=hang, isolation_before={'namespace': 'fixture'}, isolation_after={'namespace': 'fixture'},
             identity={'expected_jni_delta': '128', 'loader': {'apk_paths': ['/data/app/fixture/base.apk'],
             'native_search_paths': ['/data/app/fixture/lib/x86_64']}, 'preload_enabled': False, 'preloads': []},
             host_output={'stdout': 'host.stdout', 'stderr': 'host.stderr'})
    rows = []; clock = 1000
    def emit(stage, event, value=None, call=None):
        nonlocal clock
        clock += 10
        row = dict(schema_version=7, token=r['token'], pid=123, stage=stage, event=event,
                   monotonic_ns=str(clock), elapsed_ns='10')
        if call: row['call'] = call
        else: row['value'] = value
        rows.append(row)
    def obs(identified=False):
        return dict(module_base='4096', jni_delta='128', game_main='8192' if identified else None,
                    game_main_status='identified' if identified else 'absent', context='9000',
                    manager='9100', loading_state='9200', loading_phase=0, task='9300', tables='9400',
                    tables_ready=True if identified else None, task_phase=0, resource_count=10,
                    tables_from_saved_receiver=False, atomic=False, location='9500', primary_payload='9600',
                    secondary_payload='9700', cache='9800', battlefield='9900', instance_id=0)
    for stage in selected_stages(limit):
        emit(stage, 'before')
        if stage in LIMITS[1:]:
            emit(stage, 'observation_before', obs(stage != 'create_game_main'))
            if stage == 'create_game_main': emit(stage, 'arguments', {'activity': None, 'asset_source': 'verified_installed_apks'})
            calls = FIXED_CALLS.get(stage, ['DataLoadTask::start', 'DataLoadTask::complete'] if stage == 'data_load_tasks'
                                    else ['LoadingState::update', 'LoadingState::complete'])
            for name in calls:
                emit(stage, 'before', call=name)
                if failure == stage: break
                emit(stage, 'after', call=name)
        if failure == stage:
            if not hang: emit(stage, 'error', message)
            r['failure_stage'] = stage
            break
        if stage in LIMITS[1:]:
            emit(stage, 'native_return'); emit(stage, 'observation', obs(True))
        value = {'success': True} if stage in LIMITS[1:] else None
        if stage == 'class_loader': value = {'stub_loader_verified': True, 'apk_paths': '/data/app/fixture/base.apk',
                                            'native_search_path': '/data/app/fixture/lib/x86_64', 'preload': False}
        if stage == 'dependency_preload': value = 0
        emit(stage, 'after', value)
        if stage == 'jni_on_load': emit(stage, 'observation', obs())
        r['last_completed'] = stage
    if not failure:
        emit(BOUNDARY, 'before'); emit(BOUNDARY, 'boundary', limit)
    return r, rows


def text_of(rows):
    return ''.join(('ORACLE_V7_CALL ' if 'call' in row else 'ORACLE_V7 ') + json.dumps(row) + '\n' for row in rows)


class Tests(unittest.TestCase):
    def setUp(self):
        self.out = HERE.parents[3] / '.local/jnihost-v7-tests' / uuid.uuid4().hex
        self.out.mkdir(parents=True)

    def persist(self, r, rows, stderr=''):
        text = text_of(rows)
        (self.out / 'host.stdout').write_text(text, encoding='utf-8')
        (self.out / 'host.stderr').write_text(stderr, encoding='utf-8')
        r['events'] = events_from(text, r['token']); r['calls'] = calls_from(text, r['token'])
        r['receipts'] = {name: digest(self.out / name) for name in ('host.stdout', 'host.stderr')}
        (self.out / 'result.json').write_text(json.dumps(r), encoding='utf-8')
        return r

    def evaluate(self, limit='load-only', **kw):
        r, rows = fixture(limit, **kw)
        return assess(self.persist(r, rows), self.out)

    def test_all_inclusive_limits(self):
        for limit in LIMITS:
            with self.subTest(limit=limit):
                a = self.evaluate(limit)
                self.assertEqual(a['classification'], 'a', a)
                self.assertEqual(a['last_completed'], 'jni_on_load' if limit == 'load-only' else limit)
                self.assertIsNone(a['blocking_stage'])

    def test_default_is_load_only(self):
        self.assertEqual(new_result('a'*32)['stage_limit'], 'load-only')
        self.assertEqual(selected_stages('load-only'), STAGES)
        self.assertNotIn('nativeStage', text_of(fixture()[1]))

    def test_invalid_limit_rejected(self):
        for value in ('all', 'replay', '', None):
            with self.assertRaises(Blocked): selected_stages(value)

    def test_every_first_failure_is_retained(self):
        for stage in selected_stages('manager_update'):
            with self.subTest(stage=stage):
                a = self.evaluate('manager_update', failure=stage)
                self.assertEqual(a['classification'], 'unclassified', a)
                self.assertEqual(a['blocking_stage'], stage)
                self.assertTrue(a['stop_required'])
                self.assertFalse(a['attributed_sites'])

    def test_timeout_is_not_presentation_proof(self):
        a = self.evaluate('manager_update', failure='game_main_init', hang=True)
        self.assertEqual(a['classification'], 'unclassified', a)
        self.assertEqual(a['interrupted_call'], 'GameMain::init')
        self.assertIn('renderer_bootstrap_call', a['candidate_sites'])
        self.assertFalse(a['target_site_requirement_proven'])

    def test_host_prerequisite_not_libg_refusal(self):
        a = self.evaluate('manager_update', failure='map_resources', message='HOST_LOCATION_RECIPE_MISSING')
        self.assertEqual(a['classification'], 'blocked', a)
        self.assertEqual(a['blocking_stage'], 'map_resources')

    def finding(self, kind='rendering_dependency', stage='game_main_init'):
        r, rows = fixture('manager_update', failure=stage)
        self.persist(r, rows, 'Explicit native renderer diagnostic\n')
        f = dict(kind=kind, origin='libg', reviewer='synthetic test', rationale='receipt-backed synthetic fixture',
                 result_sha256=digest(self.out / 'result.json'), stage=stage,
                 evidence=dict(file='host.stderr', sha256=digest(self.out / 'host.stderr'),
                               line_start=1, line_end=1, excerpt='Explicit native renderer diagnostic'))
        if kind == 'rendering_dependency': f.update(site_group='game_main_init', site_ids=['renderer_bootstrap_call'], site_mapping_basis='fixture mapping')
        return r, f

    def test_receipt_bound_presentation_attribution(self):
        r, f = self.finding(); a = assess(r, self.out, f)
        self.assertEqual(a['classification'], 'c', a)
        self.assertEqual(a['attributed_sites'], ['renderer_bootstrap_call'])
        self.assertFalse(a['target_site_requirement_proven'])

    def test_receipt_bound_refusal_stops(self):
        r, f = self.finding('libg_refusal', 'create_game_main'); a = assess(r, self.out, f)
        self.assertEqual(a['classification'], 'b', a); self.assertTrue(a['stop_required'])

    def test_wrong_stage_site_attribution_rejected(self):
        r, f = self.finding(); f['site_group']='manager_home'; f['site_ids']=['home_graphics_create_call']
        self.assertEqual(assess(r, self.out, f)['classification'], 'blocked')

    def test_tampered_finding_rejected(self):
        for key, value in [('result_sha256','f'*64), ('stage','loading_state'), ('site_ids',[])]:
            r, f = self.finding(); f[key]=value
            self.assertEqual(assess(r,self.out,f)['classification'],'blocked')
        for key, value in [('sha256','f'*64),('line_start',0),('excerpt','not in receipt')]:
            r,f=self.finding(); f['evidence'][key]=value
            self.assertEqual(assess(r,self.out,f)['classification'],'blocked')

    def test_outcome_c_cannot_override_host_error(self):
        r,f=self.finding(); r['host_error']='POST_APK_DRIFT'
        self.assertEqual(assess(r,self.out,f)['classification'],'blocked')

    def test_transcript_tampering_rejected(self):
        r,rows=fixture('game_main_init'); self.persist(r,rows)
        r['events'][-1]['value']='manager_update'
        self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_receipt_hash_tampering_rejected(self):
        r,rows=fixture(); self.persist(r,rows)
        (self.out/'host.stderr').write_text('changed')
        self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_mixed_process_or_token_rejected(self):
        r,rows=fixture('game_main_init'); rows[-1]['pid']=555
        with self.assertRaises(Blocked): self.persist(r,rows)
        rows[-1]['token']='b'*32
        with self.assertRaises(Blocked): events_from(text_of(rows),r['token'])

    def test_old_version_rejected(self):
        r,rows=fixture(); self.persist(r,rows); r['schema_version']=2
        self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_ceiling_escalation_rejected(self):
        r,rows=fixture('game_main_init'); self.persist(r,rows); r['stage_limit']='load-only'
        self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_reordered_or_duplicate_call_rejected(self):
        r,rows=fixture('map_resources')
        calls=[i for i,row in enumerate(rows) if row.get('call')=='ResourceRequest::load']
        rows[calls[0]],rows[calls[1]]=rows[calls[1]],rows[calls[0]]
        self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_missing_call_cannot_succeed(self):
        r,rows=fixture('game_main_init'); rows=[row for row in rows if row.get('call')!='GameMain::init']
        self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_event_after_failure_rejected(self):
        r,rows=fixture('game_main_init',failure='create_game_main'); rows.append(dict(rows[-1]))
        self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_nonempty_create_result_cannot_succeed(self):
        r,rows=fixture('create_game_main')
        next(row for row in rows if row['event']=='native_return')['value']='native refusal'
        self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_unready_tables_cannot_succeed(self):
        for value in (None,False):
            r,rows=fixture('data_tables_range')
            next(row for row in rows if row['stage']=='data_tables_range' and row['event']=='observation')['value']['tables_ready']=value
            self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_map_and_cache_need_observed_payloads(self):
        for stage,field,value in [('map_resources','primary_payload','0'),
                                  ('battlefield_cache','battlefield','0'),
                                  ('battlefield_cache','instance_id',-1)]:
            r,rows=fixture(stage)
            next(row for row in rows if row['stage']==stage and row['event']=='observation')['value'][field]=value
            self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_timing_required_and_monotonic(self):
        for field,value in [('monotonic_ns','0'),('elapsed_ns','-1')]:
            r,rows=fixture(); rows[-1][field]=value
            self.persist(r,rows); self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_isolation_change_invalidates_success(self):
        r,rows=fixture(); r['isolation_after']['namespace']='other'; self.persist(r,rows)
        self.assertEqual(assess(r,self.out)['classification'],'blocked')

    def test_invalid_binding_number(self):
        for value in (-1, True, 2**32, None):
            with self.assertRaises((Blocked,TypeError)): number(value)

    def test_runtime_projection_matches_private_binding(self):
        b,_,_,_=load_inputs(); r=project(b)
        self.assertEqual(r['values'][r['keys'].index('game_main_init')],int(b['entries']['game_main_init']['rva'],0))
        self.assertIsNone(r['location_recipe'])
        self.assertNotIn(str(r['values'][0]),header())

    def test_recipe_requires_evidence_and_rejects_escape(self):
        with self.assertRaises(Blocked): validate_recipe({})
        r=dict(global_rva=1,vtable_rva=2,offsets=[0],evidence={},rationale='test')
        with self.assertRaises(Blocked): validate_recipe(r)
        r['evidence']={'../../../README.md':'f'*64}
        with self.assertRaises(Blocked): validate_recipe(r)

    def test_negative_detectors_have_positive_controls(self):
        source=(HERE/'observer.cpp').read_text()
        self.assertTrue(observer_safe(source)); self.assertFalse(observer_safe(source+'\npwrite();'))
        self.assertFalse(leaked('ordinary public text')); self.assertTrue(leaked('0'+'x1234'))

    def test_attempt_latch_blocks_before_device(self):
        build=self.out/'build'; build.mkdir(); (build/'ATTEMPT.json').write_text('{}')
        args=SimpleNamespace(build_dir=build,stage_limit='manager_update')
        with patch.object(worker,'RecordingDevice') as device:
            with self.assertRaises(Blocked): run_once(args,self.out,new_result('a'*32))
            device.assert_not_called()

    def test_invalid_limit_blocks_before_device(self):
        args=SimpleNamespace(build_dir=self.out,stage_limit='replay')
        with patch.object(worker,'RecordingDevice') as device:
            with self.assertRaises(Blocked): run_once(args,self.out,new_result('a'*32))
            device.assert_not_called()

    def test_collector_passes_ceiling_and_runtime_binding_once(self):
        self.collector_contract(False)

    def test_collector_never_retries_failed_native_stage(self):
        self.collector_contract(True)

    def collector_contract(self, failure):
        b,manifest,values,inputs=load_inputs()
        runtime=project(b)
        build=self.out/'build'; build.mkdir(); (build/'build.json').write_text('{}')
        names=('jnihost-ro.jar','jnihost-loader.jar','libjnihost_ro.so','runtime-binding.json')
        built=dict(schema_version=7,profile='staged_no_patches',client_shells_compiled=False,
                   inputs=inputs,libg_sha256=b['libg_sha256'],jni_delta=str(values[0]),
                   artifacts={name:'a'*64 for name in names},sources={'run.py':'a'*64})
        calls=[]
        class FakeDevice:
            def __init__(self,serial,out): self.out=out
            def check(self): return {'api':'32'}
            def call(self,*args,**kw):
                calls.append(args)
                if args[:2]==('shell','ps'): return 'NAME\ninit\n'
                if args[:3]==('shell','dumpsys','package'): return 'legacyNativeLibraryDir=/data/app/fixture/lib'
                if args[:2]==('shell','sha256sum'): return 'a'*64+'  artifact'
                return ''
            def capture(self,args,**kw):
                calls.append(tuple(args))
                if args[0]=='shell' and len(args)==2 and '/system/bin/app_process' in args[1]:
                    argv=shlex.split(args[1]); host=argv[argv.index('royale.nativehost.JniHost')+1:]
                    r,rows=fixture(host[6],failure='create_game_main' if failure else None)
                    for row in rows: row['token']=host[2]
                    rows[1]['value'].update(apk_paths=host[3],native_search_path=host[4])
                    text=text_of(rows)
                    (self.out/'launch.stdout').write_text(text)
                    (self.out/'launch.stderr').write_text('')
                    return r['returncode'],text,'launch'
                return 0,'','diagnostic'
        args=SimpleNamespace(build_dir=build,stage_limit='game_main_init',emulator_pid=123,
                             serial='emulator-5554',preload_dependencies=False)
        installed=[{'path':'/data/app/fixture/base.apk','sha256':'a'*64}]
        with patch.object(worker,'load_inputs',return_value=(b,manifest,values,inputs)), \
             patch.object(worker,'read_json',side_effect=lambda p: built if p.name=='build.json' else runtime), \
             patch.object(worker,'verify_hashes'), patch.object(worker,'digest',return_value='a'*64), \
             patch.object(worker,'isolation',return_value={'namespace':'fixture'}), \
             patch.object(worker,'RecordingDevice',FakeDevice), \
             patch.object(worker,'installed_check',return_value=installed), \
             patch.object(worker,'select_installed_libg',return_value=('/data/app/fixture/lib/x86_64/libg.so',
                 '/data/app/fixture/lib/x86_64/libg.so','a'*64,'package_manager_native_file')):
            r=new_result('a'*32); run_once(args,self.out,r)
            launch=[c for c in calls if len(c)==2 and '/system/bin/app_process' in c[1]]
            self.assertEqual(len(launch),1)
            self.assertIn('timeout -s KILL 45',launch[0][1])
            host=shlex.split(launch[0][1]); host=host[host.index('royale.nativehost.JniHost')+1:]
            self.assertEqual(host[5:],['off','game_main_init'])
            self.assertEqual(r['failure_stage'],'create_game_main' if failure else None)
            self.assertEqual(r['last_completed'],'jni_on_load' if failure else 'game_main_init')
            self.assertTrue(any(c[0]=='push' and c[1].endswith('runtime-binding.json') for c in calls))
            self.assertEqual(json.loads((build/'ATTEMPT.json').read_text())['stage_limit'],'game_main_init')
            with self.assertRaises(Blocked): run_once(args,self.out,new_result('a'*32))
            self.assertEqual(len([c for c in calls if len(c)==2 and '/system/bin/app_process' in c[1]]),1)


if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if result.wasSuccessful(): print('ORACLE_V7_TESTS_OK')
    raise SystemExit(0 if result.wasSuccessful() else 1)

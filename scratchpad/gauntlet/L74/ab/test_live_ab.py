"""Offline acceptance checks. Every scenario uses the production Runner and file tailer."""
import contextlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import shutil
import uuid
import unittest
from unittest.mock import patch

from ab_dryrun import FakeSupervisor, decision, emit
from live_ab import Abort, Arm, Match, RealControl, Runner, guard, project, statistics, wilson


class FixtureDirectory:
    """Use workspace directories; Python 3.13's Windows mode-700 temp ACL is sandbox-incompatible."""
    def __init__(self):
        self.base = Path(__file__).resolve().parent / '.dryrun'
        self.path = self.base / uuid.uuid4().hex
        self.path.mkdir(parents=True)
        self.name = str(self.path)

    def cleanup(self):
        assert self.path.resolve().parent == self.base.resolve()
        shutil.rmtree(self.path)

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()


class Cases(unittest.TestCase):
    def scenario(self, name='normal', block=3, total=7, noise=False, absent=False, prepare=None):
        tmp = FixtureDirectory()
        self.addCleanup(tmp.cleanup)
        fake = FakeSupervisor(tmp.name, name, noise=noise, absent=absent)
        r = Runner(fake.arms, fake, live=fake.live, logs=fake.logs, output=fake.output,
                   block=block, total=total, poll=1, stall=8, grace=1,
                   stop_timeout=3, clock=fake, now=fake.time)
        if prepare:
            prepare(fake, r)
        with contextlib.redirect_stdout(io.StringIO()):
            code = r.execute()
        fake.assert_restored()
        return fake, r, code

    def test_count_blocks(self):
        f, r, code = self.scenario(noise=True)
        self.assertEqual(code, 0)
        self.assertEqual(f.starts, ['A', 'B', 'A', 'B', 'A', 'B'])
        self.assertEqual([r.count(a) for a in r.arms], [7, 7])
        self.assertEqual(f.sequence, list('AAABBBAAABBBAB'))
        self.assertEqual(f.stop_seen_while_active, 6)
        self.assertFalse(any('_noise' in x['match_file'] or '_short' in x['match_file'] for x in r.rows))
        self.assertEqual(len({x['match_file'] for x in r.rows}), 14)
        self.assertEqual(len(r.rows), len((f.output/'results.jsonl').read_text().splitlines()))

    def test_count_existing_and_append(self):
        def prepare(f, r):
            f.arm = f.arms[0]
            emit(f.filename('_preexisting'), f.header(), decision(), decision(3000), dict(event='end'))
            (f.output/'results.jsonl').write_text('{"previous_run":true}\n')
        f, r, code = self.scenario(prepare=prepare)
        self.assertEqual(code, 0)
        self.assertTrue((f.output/'results.jsonl').read_text().startswith('{"previous_run":true}\n'))
        self.assertFalse(any('preexisting' in x['match_file'] for x in r.rows))

    def _prior_run(self, f, rid='RID', a=3, b=1, sha=None):
        rows = [dict(run_id=rid, block=0, match_file=f'C:/old/live_play_2026010{i}_000000.jsonl', arm=k, label='x',
                     ckpt_sha256=sha or next(x.sha for x in f.arms if x.key == k), fast=False, counted=True, result='W')
                for i, k in enumerate(['A'] * a + ['B'] * b)]
        (f.output/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        bk = f.output/'backups'/rid
        bk.mkdir(parents=True)
        for name, data in f.originals.items():
            (bk/name).write_bytes(data)
        (bk/'manifest.json').write_text(json.dumps({n: True for n in f.originals}))
        # Foreign values written after the runner died: the end-of-run restore must use the backup, not these.
        (f.live/'CKPT_OVERRIDE').write_bytes(b'C:/someone else.pt\n')
        (f.live/'LIVE_FAST').write_bytes(b'on\n')

    def test_resume_continues_counts_and_restores_original_backup(self):
        def prepare(f, r):
            self._prior_run(f)
            r.resume('RID')
        f, r, code = self.scenario(prepare=prepare)              # scenario asserts the ORIGINAL settings were restored
        self.assertEqual(code, 0)
        self.assertEqual([r.count(a) for a in r.arms], [7, 7])
        self.assertEqual(f.starts[0], 'B')                       # B had fewer counted matches
        self.assertEqual(sum(1 for x in r.rows if 'C:/old/' in x['match_file']), 4)
        self.assertTrue(all(json.loads(x)['run_id'] == 'RID' for x in (f.output/'results.jsonl').read_text().splitlines()))

    def test_resume_refuses_changed_checkpoint(self):
        tmp = FixtureDirectory()
        self.addCleanup(tmp.cleanup)
        f = FakeSupervisor(tmp.name, 'normal')
        self._prior_run(f, sha='0' * 64)
        r = Runner(f.arms, f, live=f.live, logs=f.logs, output=f.output, block=3, total=7, poll=1, stall=8, grace=1,
                   stop_timeout=3, clock=f, now=f.time)
        with self.assertRaises(Abort):
            r.resume('RID')

    def test_count_partial(self):
        f, r, code = self.scenario('partial', block=1, total=2)
        self.assertEqual(code, 0)
        self.assertEqual(len(r.rows), 4)
        self.assertTrue(all(x['result'] == 'W' for x in r.rows))

    def test_count_terminal_and_projection(self):
        with FixtureDirectory() as d:
            p = Path(d)/'match.jsonl'
            emit(p, dict(event='start'), decision(), decision(900, own=0),
                 dict(event='stop', why='battle_over_hands_visible'), dict(event='end'))
            m = Match(p); m.read()
            self.assertEqual(m.outcome()['result'], 'L')
            self.assertEqual(m.outcome()['tower_diff'], -3)
            m.reason = 'reader_silent'
            self.assertIsNone(m.outcome())
            m.last['tick'] = 3000
            self.assertEqual(m.outcome()['result'], 'L')
            m.closed = False
            self.assertIsNone(m.outcome())
            j = decision(); j['public']['opponent_hand'] = ['secret']
            self.assertNotIn('secret', json.dumps(project(j)))
            guard(project(decision(side=0)))

    def test_count_arm_parse(self):
        with FixtureDirectory() as d:
            p = Path(d)/'with spaces.pt'; p.write_bytes(b'checkpoint')
            a = Arm.parse(f'A:NEWSIM base:{p}:off')
            self.assertFalse(a.fast)
            self.assertEqual(a.ckpt, p.resolve())

    def test_count_drain_and_overflow(self):
        def prepare(f, r):
            old_step = f.step
            def step():
                was_active = f.current is not None
                old_step()
                if was_active and f.current is None:
                    # A second completed log arrives before the poll observes STOP.
                    emit(f.filename('_drain'), f.header(), decision(), decision(3000, enemy=2), dict(event='end'))
            f.step = step
        f, r, code = self.scenario(total=1, block=1, prepare=prepare)
        self.assertEqual(code, 0)
        self.assertEqual([r.count(a) for a in r.arms], [1, 1])
        self.assertEqual(len(r.rows), 4)
        self.assertEqual(sum(not x['counted'] for x in r.rows), 2)

    def test_safety_guard(self):
        for name in ('wrong_account',):
            with self.subTest(name=name):
                f, r, code = self.scenario(name)
                self.assertEqual(code, 1)
                self.assertEqual(f.starts, ['A'])
                self.assertEqual(r.rows, [])
                self.assertTrue(any('ACCOUNT GUARD' in p for p in f.posts))

    def test_safety_stop_ab(self):
        f, r, code = self.scenario('stop_ab', block=3)
        self.assertEqual(code, 0)
        self.assertEqual(f.starts, ['A'])
        self.assertEqual(len(r.rows), 3)
        self.assertTrue((f.output/'STOP_AB').exists())

    def test_safety_signal(self):
        def prepare(f, r):
            old_step = f.step
            def step():
                old_step()
                r.boundary_stop = True
            f.step = step
        f, r, code = self.scenario(prepare=prepare)
        self.assertEqual(code, 0)
        self.assertEqual(f.starts, ['A'])
        self.assertEqual(len(r.rows), 3)

    def test_safety_restart_limit(self):
        for name in ('dead', 'stall'):
            with self.subTest(name=name):
                f, r, code = self.scenario(name)
                self.assertEqual(code, 1)
                self.assertEqual(f.starts, ['A']*4)
                self.assertEqual(r.restarts, 3)
                self.assertTrue(any('Restart limit reached' in p for p in f.posts))

    def test_safety_recovery_and_backup_absence(self):
        f, r, code = self.scenario('dies_once', absent=True)
        self.assertEqual(code, 0)
        self.assertEqual(r.restarts, 1)
        self.assertEqual([r.count(a) for a in r.arms], [7, 7])

    def test_safety_check_failure(self):
        f, r, code = self.scenario('check_fail')
        self.assertEqual(code, 1)
        self.assertEqual(f.starts, [])
        self.assertTrue(any('LIVE_CHECK_PASS' in p for p in f.posts))

    def test_safety_slow_stop(self):
        f, r, code = self.scenario('slow_stop', block=1, total=1)
        self.assertEqual(code, 1)
        self.assertTrue(any('STOP wait exceeded' in p for p in f.posts))
        self.assertEqual(f.starts, ['A'])

    def test_safety_checkpoint_mutation(self):
        def prepare(f, r):
            f.arms[0].ckpt.write_bytes(b'changed')
        f, r, code = self.scenario(prepare=prepare)
        self.assertEqual(code, 1)
        self.assertEqual(f.starts, [])

    def test_safety_lock_and_prestop(self):
        with FixtureDirectory() as d:
            f = FakeSupervisor(d)
            r = Runner(f.arms, f, live=f.live, logs=f.logs, output=f.output)
            lock = f.output/'RUNNING.lock'; lock.write_text('existing owner')
            with self.assertRaises(Abort):
                r.execute()
            self.assertEqual(lock.read_text(), 'existing owner')
            lock.unlink()
            (f.output/'STOP_AB').touch()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(r.execute(), 0)
            self.assertEqual(f.starts, [])
            self.assertFalse((f.live/'STOP').exists())
            self.assertFalse(lock.exists())

    def test_safety_real_command_contract(self):
        c = RealControl.__new__(RealControl); c.emotes = 'on'
        with FixtureDirectory() as d:
            f = FakeSupervisor(d)
            cmd = c.command(f.arms[0], True)
            self.assertEqual(cmd[-4:], ['icebow', '--no-fast-plays', '--emotes', '--check'])
            self.assertNotIn('--no-fast-plays', c.command(f.arms[1]))

    def test_safety_real_check_receipt(self):
        c = RealControl.__new__(RealControl); c.emotes = 'off'; c.env = {}
        with FixtureDirectory() as d:
            f = FakeSupervisor(d); a = f.arms[0]
            for rc, receipt, expected in [
                (0, dict(check='LIVE_CHECK_PASS', sha256=a.sha), True),
                (1, dict(check='LIVE_CHECK_PASS', sha256=a.sha), False),
                (0, dict(check='LIVE_CHECK_PASS', sha256='wrong'), False),
                (0, dict(check='LIVE_CHECK_FAIL', sha256=a.sha), False),
            ]:
                with patch('subprocess.run', return_value=SimpleNamespace(returncode=rc, stdout=json.dumps(receipt).encode())) as run:
                    self.assertEqual(c.check(a), expected)
                    self.assertNotIn('timeout', run.call_args.kwargs)  # timeout-based run kills children

    def test_safety_real_setting_preconditions(self):
        with FixtureDirectory() as d:
            f = FakeSupervisor(d)
            with patch('live_ab.LIVE', f.live), patch.dict('os.environ', {}, clear=True), patch.dict('sys.modules', psutil=SimpleNamespace()):
                c = RealControl(f.output)
                self.assertEqual(c.emotes, 'on')
                for value in (b'bait\n', b'icebow\r\n'):
                    (f.live/'LIVE_DECK').write_bytes(value)
                    with self.assertRaises(Abort):
                        RealControl(f.output)
                (f.live/'LIVE_DECK').write_bytes(b'icebow\n')
                with patch.dict('os.environ', {'CKPT':'foreign-model.pt'}):
                    with self.assertRaises(Abort):
                        RealControl(f.output)

    def test_safety_process_discovery(self):
        class PError(Exception):
            pass
        c = RealControl.__new__(RealControl); c.launcher = None
        def proc(name, cmd):
            return SimpleNamespace(info=dict(name=name, cmdline=cmd))
        ps = SimpleNamespace(Error=PError, NoSuchProcess=PError)
        c.psutil = ps
        ps.process_iter = lambda attrs: iter([
            proc('bash.exe', ['bash', r'scratchpad\gauntlet\L70\live\run_live.sh']),
            proc('python.exe', ['python', 'live_play_hand_v4.py', '--ladder']),
            proc('python.exe', ['python', 'unrelated.py'])])
        self.assertEqual(c.running(), 2)
        ps.process_iter = lambda attrs: iter([proc('python.exe', None)])
        with self.assertRaises(Abort):
            c.running()
        ps.process_iter = lambda attrs: iter([])
        c.launcher = SimpleNamespace(poll=lambda: None)
        self.assertEqual(c.running(), 1)

    def test_safety_initial_live_drain(self):
        def prepare(f, r):
            f.alive = True
        f, r, code = self.scenario(prepare=prepare)
        self.assertEqual(code, 0)
        self.assertEqual([r.count(a) for a in r.arms], [7, 7])

    def test_safety_protected_setting_change(self):
        def prepare(f, r):
            old_step = f.step
            def step():
                old_step()
                (f.live/'LIVE_OPTIONS').write_bytes(b'external update')
                # The external value must survive; runner may not restore/change this file.
                f.protected['LIVE_OPTIONS'] = b'external update'
            f.step = step
        f, r, code = self.scenario(prepare=prepare)
        self.assertEqual(code, 1)
        self.assertEqual(f.starts, ['A'])
        self.assertEqual((f.live/'LIVE_OPTIONS').read_bytes(), b'external update')

    def test_safety_arm_extra_options(self):
        # B = same model + --no-ability: LIVE_OPTIONS is written per arm, the other arm's header never counts,
        # and the original LIVE_OPTIONS comes back (assert_restored).
        tmp = FixtureDirectory()
        self.addCleanup(tmp.cleanup)
        fake = FakeSupervisor(tmp.name, noise=True, extra={'B': '--no-ability'})
        r = Runner(fake.arms, fake, live=fake.live, logs=fake.logs, output=fake.output, block=3, total=7,
                   poll=1, stall=8, grace=1, stop_timeout=3, clock=fake, now=fake.time)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(r.execute(), 0)
        fake.assert_restored()
        base = b'{"untouched":true}'
        self.assertEqual({k: v for k, v in fake.options_seen}, {'A': base + b'\n', 'B': base + b' --no-ability\n'})
        self.assertEqual(r.count(fake.arms[0]), 7)
        self.assertEqual(r.count(fake.arms[1]), 7)

    def test_reporting_intervals(self):
        lo, hi = wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2365930905)
        self.assertAlmostEqual(hi, 0.7634069095)
        self.assertLess(wilson(0, 10)[1], .28)
        self.assertGreater(wilson(10, 10)[0], .72)
        self.assertIsNone(wilson(0, 0))
        rows = [dict(arm=k, result='W' if i < w else 'L') for k, w in [('A', 4), ('B', 6)] for i in range(10)]
        rows += [dict(arm='A', result='D')]
        s = statistics(rows)
        self.assertEqual(s['A']['win_rate'], .4)
        self.assertEqual(s['A']['D'], 1)
        diff = s['difference_B_minus_A']
        self.assertAlmostEqual(diff['value'], .2)
        self.assertLess(diff['ci95'][0], 0)
        self.assertGreater(diff['ci95'][1], .2)
        reverse = statistics([dict(r, arm='A' if r['arm']=='B' else 'B') for r in rows])['difference_B_minus_A']
        self.assertAlmostEqual(diff['ci95'][0], -reverse['ci95'][1])
        self.assertIsNone(statistics([])['difference_B_minus_A'])

    def test_reporting_cadence_and_trophies(self):
        f, r, code = self.scenario(total=20, block=5)
        self.assertEqual(code, 0)
        reports = [p for p in f.posts if 'reached' in p]
        self.assertEqual(len(reports), 4)
        self.assertTrue(all('B-A:' in p and 'Wilson/Newcombe' in p for p in reports))
        self.assertTrue(all(x['trophies'] is not None and x['trophy_source'].startswith('ladder_nav') for x in r.rows))
        self.assertEqual([r.count(a) for a in r.arms], [20, 20])

    def test_reporting_failure_is_local(self):
        f, r, code = self.scenario('post_fail', total=1)
        self.assertEqual(code, 0)
        self.assertIn('discord_failed', (f.output/'events.jsonl').read_text())


def run_suite(group='all'):
    names = unittest.defaultTestLoader.getTestCaseNames(Cases)
    prefix = {'counting': 'test_count_', 'safety': 'test_safety_', 'all': 'test_'}[group]
    suite = unittest.TestSuite(Cases(n) for n in names if n.startswith(prefix))
    # A fake dry-run must never reach production subprocess/network boundaries.
    with patch('subprocess.Popen', side_effect=AssertionError('dry-run attempted a process')):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print({'counting':'COUNTING_PASS', 'safety':'SAFETY_PASS', 'all':'DRYRUN_PASS'}[group],
              f'({result.testsRun} tests; fake supervisor, temporary files, zero subprocess/network calls)')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(run_suite(sys.argv[1] if len(sys.argv)>1 else 'all'))

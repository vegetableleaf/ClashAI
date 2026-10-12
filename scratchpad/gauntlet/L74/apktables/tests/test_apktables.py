"""Synthetic-only decoder and comparison regression tests; stdlib unittest."""
from __future__ import annotations

import csv
import contextlib
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import decoder
import compare
import check_build

TABLE = b'Name,Value\nString,Int\nSynthetic,7\n'


def sc_zlib(data):
    return b'SC' + struct.pack('>II', 1, 16) + hashlib.md5(data).digest() + zlib.compress(data)


def sc_lzma(data):
    standard = lzma.compress(data, format=lzma.FORMAT_ALONE)
    return standard[:5] + struct.pack('<I', len(data)) + standard[13:]


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        parent = HERE / 'out' / 'test_tmp'
        parent.mkdir(parents=True, exist_ok=True)
        # Python 3.13's Windows 0700 mkdir ACL excludes the sandbox's effective
        # write identity. Inherit the ignored parent directory's ACL for fixtures.
        if os.name == 'nt':
            mkdir = os.mkdir
            with patch('tempfile._os.mkdir', side_effect=lambda path, mode: mkdir(path, 0o777)):
                self.temp = tempfile.TemporaryDirectory(dir=parent)
        else:
            self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class DecodeTests(unittest.TestCase):
    def test_plain_utf8_and_bom(self):
        for data in (TABLE, b'\xef\xbb\xbf' + TABLE, 'Name\nString\nSynthetic \u2603\n'.encode()):
            with self.subTest(data=data):
                self.assertEqual(decoder.decode(data), (data, 'plain-utf8'))

    def test_standard_lzma_and_xz(self):
        for fmt in (lzma.FORMAT_ALONE, lzma.FORMAT_XZ):
            with self.subTest(format=fmt):
                self.assertEqual(decoder.decode(lzma.compress(TABLE, format=fmt)), (TABLE, 'lzma-standard'))

    def test_supercell_nine_byte_lzma(self):
        self.assertEqual(decoder.decode(sc_lzma(TABLE)), (TABLE, 'sc-lzma-9'))

    def test_sc_v1_zlib_md5(self):
        self.assertEqual(decoder.decode(sc_zlib(TABLE)), (TABLE, 'sc-v1-zlib'))
        corrupt = bytearray(sc_zlib(TABLE))
        corrupt[10] ^= 1
        with self.assertRaisesRegex(ValueError, 'MD5'):
            decoder.decode(bytes(corrupt))

    def test_truncated_and_unsupported_wrappers(self):
        cases = [b'SC', b'SC' + struct.pack('>II', 2, 16) + b'x' * 16,
                 sc_zlib(TABLE)[:-2], sc_lzma(TABLE)[:-5], lzma.compress(TABLE)[:-4]]
        for data in cases:
            with self.subTest(header=data[:12]), self.assertRaises(ValueError):
                decoder.decode(data)

    def test_unknown_binary_and_control_bytes(self):
        for data in (b'\xff\xfe\xfa', b'Name\x00Value', b'Name\x01Value'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decoder.decode(data)

    def test_input_and_decoded_size_limits(self):
        with self.assertRaisesRegex(ValueError, 'input size'):
            decoder.decode(TABLE, limit=4)
        data = b'x' * 10000
        for compressed in (lzma.compress(data), sc_lzma(data), sc_zlib(data)):
            with self.subTest(header=compressed[:10]), self.assertRaises(ValueError):
                decoder.decode(compressed, limit=200)

    def test_trailing_compressed_bytes_are_rejected(self):
        for compressed in (lzma.compress(TABLE), sc_lzma(TABLE), sc_zlib(TABLE)):
            with self.subTest(header=compressed[:10]), self.assertRaises(ValueError):
                decoder.decode(compressed + b'junk')

    def test_nine_byte_size_mismatch(self):
        compressed = sc_lzma(TABLE)
        wrong = compressed[:5] + struct.pack('<I', len(TABLE) + 1) + compressed[9:]
        with self.assertRaises(ValueError):
            decoder.decode(wrong)


class ExtractTests(TemporaryCase):
    def apk(self, name, members):
        with zipfile.ZipFile(self.root / name, 'w') as archive:
            for path, data in members.items():
                info = zipfile.ZipInfo(path)
                # Keep malicious spelling: ZipInfo's Windows constructor normally
                # normalizes backslashes before our extraction code can inspect it.
                info.filename = path
                archive.writestr(info, data)

    def test_multiple_splits_duplicates_and_conflicts(self):
        path = 'assets/csv_logic/synthetic.csv'
        self.apk('a.apk', {path: TABLE, 'assets/csv_client/client.csv': TABLE})
        self.apk('b.apk', {path: lzma.compress(TABLE)})
        self.apk('c.apk', {path: TABLE.replace(b',7', b',8')})
        dest = self.root / 'decoded'
        result = decoder.extract(self.root, dest)
        self.assertEqual(len(result['apks']), 3)
        self.assertEqual(len(result['files']), 2)
        self.assertEqual(len(result['files']['csv_logic/synthetic.csv']['duplicates']), 1)
        self.assertEqual(len(result['conflicts']), 1)
        self.assertEqual(result['conflicts'][0]['path'], 'csv_logic/synthetic.csv')
        self.assertEqual((dest / 'csv_logic/synthetic.csv').read_bytes(), TABLE)
        self.assertEqual(result['failures'], [])

    def test_zip_traversal_is_reported_and_not_written(self):
        self.apk('base.apk', {
            'assets/csv_logic/../../escape.csv': TABLE,
            'assets/csv_logic/back\\slash.csv': TABLE,
            'assets/csv_logic/drive:bad.csv': TABLE,
            'assets/csv_logic/good.csv': TABLE,
            'assets/texture/ignored.csv': TABLE,
        })
        dest = self.root / 'decoded'
        result = decoder.extract(self.root, dest)
        self.assertEqual(len(result['failures']), 3)
        self.assertTrue(all('unsafe archive path' in f['error'] for f in result['failures']))
        self.assertEqual(list(result['files']), ['csv_logic/good.csv'])
        self.assertFalse((self.root / 'escape.csv').exists())

    def test_decode_failure_does_not_hide_good_member(self):
        self.apk('base.apk', {'assets/csv_logic/good.csv': TABLE,
                             'assets/csv_logic/bad.csv': b'\xff\xfe'})
        result = decoder.extract(self.root, self.root / 'decoded')
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(len(result['failures']), 1)
        self.assertEqual(result['failures'][0]['member'], 'assets/csv_logic/bad.csv')

    def test_empty_apk_directory_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no APKs'):
            decoder.extract(self.root, self.root / 'decoded')


class CsvTests(unittest.TestCase):
    def test_continuation_rows_preserve_blank_cells(self):
        data = b'Name,Value,Labels\nString,Int,StringArray\nSynthetic,7,a\n,,b\n,9,\nOther,0,c\n'
        rows = decoder.csv_records(data)
        self.assertEqual([r['Value'] for r in rows['Synthetic']], [7, None, 9])
        self.assertEqual([r['Labels'] for r in rows['Synthetic']], ['a', 'b', None])
        self.assertEqual(rows['Other'][0]['Value'], 0)

    def test_orphan_duplicate_and_extra_columns_rejected(self):
        for data in (b'Name,Value\nString,Int\n,3\n',
                     b'Name,Value\nString,Int\nA,1\nA,2\n',
                     b'Name,Value\nString,Int\nA,1,extra\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decoder.csv_records(data)


class CompareTests(unittest.TestCase):
    def test_missing_null_and_zero_are_distinct(self):
        self.assertEqual(compare.diff_values({}, {'damage': None}),
                         [{'field': 'damage', 'before': compare.MISSING, 'after': None}])
        self.assertEqual(compare.diff_values({'damage': None}, {'damage': 0}),
                         [{'field': 'damage', 'before': None, 'after': 0}])
        self.assertEqual(compare.diff_values({'damage': 0}, {'damage': 0}), [])

    def test_nested_projectile_and_level_scaling_exact_values(self):
        before = {'name': 'Synthetic', 'damage': 7,
                  'projectile': {'speed': 600, 'spawn_projectile': {'speed': 800, 'radius_milli': 90}},
                  'level_scaling': {'relative_level': 2, 'multiplier_percent_by_level': [100, 110]}}
        after = json.loads(json.dumps(before))
        after['projectile']['spawn_projectile']['speed'] = 801
        after['level_scaling']['multiplier_percent_by_level'][1] = 111
        changes = compare.compare_cards({'cards': [after]}, {'cards': [before]}, ['Synthetic'])[0]
        self.assertEqual(changes['status'], 'mismatch')
        self.assertEqual(changes['differences'], [
            {'field': 'level_scaling.multiplier_percent_by_level', 'before': [100, 110], 'after': [100, 111]},
            {'field': 'projectile.spawn_projectile.speed', 'before': 800, 'after': 801},
        ])

    def test_missing_card_is_not_equal(self):
        row = compare.compare_cards({'cards': []}, {'cards': [{'name': 'Synthetic'}]}, ['Synthetic'])[0]
        self.assertEqual(row['status'], 'missing_card')
        self.assertFalse(row['apk_present'])
        self.assertTrue(row['sim_present'])

    def test_all_card_sections_indexed(self):
        doc = {'cards': [{'name': 'A'}], 'evolutions': [{'name': 'B'}], 'hero_forms': [{'name': 'C'}]}
        self.assertEqual(set(compare.cards_by_name(doc)), {'A', 'B', 'C'})
        self.assertEqual(compare.compare_cards(doc, doc, ['A', 'B', 'C'])[2]['status'], 'equal')

    def test_future_build_changes_new_removed_and_changed(self):
        old = {'manifest': {'fingerprint': 'old', 'files': {
            'changed.csv': {'sha256': '1'}, 'removed.csv': {'sha256': '2'}, 'same.csv': {'sha256': '3'}}},
            'card_stats': {'Changed': {'damage': 1}, 'Removed': {'damage': 2}, 'Same': {'damage': 3}}}
        new = {'manifest': {'fingerprint': 'new', 'files': {
            'changed.csv': {'sha256': '4'}, 'new.csv': {'sha256': '5'}, 'same.csv': {'sha256': '3'}}},
            'card_stats': {'Changed': {'damage': 4}, 'New': {'damage': 5}, 'Same': {'damage': 3}}}
        self.assertEqual(compare.build_changes(None, new)['status'], 'first_build')
        result = compare.build_changes(old, new)
        self.assertEqual(result['previous'], 'old')
        self.assertEqual([r['path'] for r in result['files']], ['changed.csv', 'new.csv', 'removed.csv'])
        self.assertEqual([r['card'] for r in result['cards']], ['Changed', 'New', 'Removed'])
        self.assertEqual(result['cards'][1]['differences'][0]['before'], compare.MISSING)
        self.assertEqual(result['cards'][2]['differences'][0]['after'], compare.MISSING)
        self.assertEqual(compare.build_changes(new, new)['cards'], [])

    def test_relative_rarity_level_caps_and_unknown_card(self):
        doc = {'cards': [{'name': n, 'rarity': 'SyntheticRare'} for n in ('Low', 'Min', 'Max', 'High')],
               'rarities': {'SyntheticRare': {'relative_level': 2, 'level_count': 4}}}
        result = {r['card']: r for r in compare.check_levels(
            '--foo 1 --card-levels Low=2 Min=3 Max=6 High=7 Missing=4 --bar 2 # note', doc)}
        self.assertEqual(result['Min']['minimum'], 3)
        self.assertEqual(result['Max']['cap'], 6)
        self.assertEqual([result[n]['status'] for n in ('Low', 'Min', 'Max', 'High')],
                         ['out_of_range', 'ok', 'ok', 'out_of_range'])
        self.assertEqual(result['Missing']['status'], 'unknown_cap')
        self.assertEqual(compare.check_levels('--card_levels=Min=3', doc)[0]['status'], 'ok')


class OpponentTests(TemporaryCase):
    def fixture(self, weight=99):
        census = self.root / 'census.json'
        census.write_text(json.dumps({'decks': [
            {'slugs': ['alpha-hero', 'beta-ev1'], 'engine': ['Alpha@hero', 'Beta@evolution'],
             'sides': weight, 'sides_census': 3},
            {'slugs': ['alpha', 'gamma'], 'engine': ['Alpha', 'Gamma'], 'sides': 2},
        ]}), encoding='utf-8')
        pro2 = self.root / 'battles.csv'
        with pro2.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['team_deck', 'opponent_deck'])
            writer.writeheader()
            writer.writerow({'team_deck': 'alpha,beta,gamma,delta,epsilon,zeta,eta,theta',
                             'opponent_deck': 'alpha,beta,gamma,delta,epsilon,zeta,eta,iota'})
        docs = [{'cards': [{'name': name, 'display_name': name} for name in ('Alpha', 'Beta', 'Gamma')],
                 'hero_forms': [{'name': 'Alpha_hero', 'form_of': 'Alpha'}],
                 'evolutions': [{'name': 'Beta_EV1', 'form_of': 'Beta'}]}]
        return census, pro2, docs

    def test_original_weights_both_seats_and_variant_counts(self):
        result = compare.opponent_counts(*self.fixture(), top=3)
        self.assertEqual(result['census_selected_sides'], 5)
        self.assertEqual(result['pro2_rows'], 1)
        self.assertEqual([(r['card'], r['census'], r['pro2'], r['total']) for r in result['top']],
                         [('Alpha', 5, 2, 7), ('Beta', 3, 2, 5), ('Gamma', 2, 2, 4)])
        self.assertEqual({r['card']: r['count'] for r in result['variants']}, {'Alpha_hero': 3, 'Beta_EV1': 3})

    def test_bad_census_weight_rejected(self):
        census, pro2, docs = self.fixture()
        data = json.loads(census.read_text())
        data['decks'][0]['sides_census'] = -1
        census.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'invalid census weight'):
            compare.opponent_counts(census, pro2, docs)

    def test_incomplete_pro2_deck_rejected(self):
        census, pro2, docs = self.fixture()
        pro2.write_text('team_deck,opponent_deck\nalpha,beta\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'incomplete PRO2 deck'):
            compare.opponent_counts(census, pro2, docs)


class IntegrationTests(TemporaryCase):
    fixture = OpponentTests.fixture
    apk = ExtractTests.apk

    def test_cli_two_builds_and_failed_decode_preserve_baseline(self):
        census, pro2, _ = self.fixture()
        source_doc = {'cards': [{'name': 'Alpha', 'damage': 7, 'rarity': 'SyntheticRare'}],
                      'rarities': {'SyntheticRare': {'relative_level': 2, 'level_count': 4}}}
        old = self.root / 'old.json'
        old.write_text(json.dumps(source_doc), encoding='utf-8')
        levels = self.root / 'LIVE_OPTIONS'
        levels.write_text('--card-levels Alpha=3', encoding='utf-8')
        out = self.root / 'runs'
        argv = [str(self.root), '--out', str(out), '--old-table', str(old),
                '--selected-table', str(old), '--census', str(census), '--pro2', str(pro2),
                '--live-options', str(levels), '--label', 'SyntheticFixture']

        def synthetic_normalize(tables, repo, ref, destination):
            doc = json.loads(json.dumps(source_doc))
            doc['cards'][0]['damage'] = decoder.csv_records((tables / 'synthetic.csv').read_bytes())['Synthetic'][0]['Value']
            return doc, {'sources': {}, 'refusals': []}

        self.apk('base.apk', {'assets/csv_logic/synthetic.csv': TABLE})
        with patch.object(check_build, 'normalize', side_effect=synthetic_normalize), \
                patch.object(check_build, 'git_blob', side_effect=AssertionError('unexpected Git access')), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_build.main(argv), 0)
            first = json.loads((out / 'latest.json').read_text())
            first_snapshot = json.loads(Path(first['snapshot']).read_text())
            self.assertEqual(first_snapshot['card_stats']['Alpha']['damage'], 7)
            self.apk('base.apk', {'assets/csv_logic/synthetic.csv': TABLE.replace(b',7', b',8')})
            self.assertEqual(check_build.main(argv), 0)
            second = json.loads((out / 'latest.json').read_text())
            report = json.loads((Path(second['snapshot']).parent / 'report.json').read_text())
            self.assertEqual(report['changes']['status'], 'compared')
            self.assertEqual(report['changes']['cards'][0]['differences'],
                             [{'field': 'damage', 'before': 7, 'after': 8}])
            self.assertNotEqual(first['snapshot'], second['snapshot'])
            self.assertTrue(Path(second['report']).is_file())
            self.assertEqual(check_build.main(argv), 0)
            second = json.loads((out / 'latest.json').read_text())
            repeated = json.loads((Path(second['snapshot']).parent / 'changes.json').read_text())
            self.assertEqual(repeated['files'], [])
            self.assertEqual(repeated['cards'], [])
            self.apk('base.apk', {'assets/csv_logic/synthetic.csv': b'\xff\xfe'})
            self.assertEqual(check_build.main(argv), 1)
            self.assertEqual(json.loads((out / 'latest.json').read_text()), second)


class RelatedStatsTests(unittest.TestCase):
    @staticmethod
    def spell(unit_name='SyntheticBody', hp=100, damage=7):
        return {'cards': [{'name': 'SyntheticSpell', 'kind': 'spell',
                           'spell': {'projectile': {'spawn_character': unit_name}}}],
                'units': {unit_name: {'name': unit_name, 'hitpoints': hp, 'damage': damage}}}

    def test_spawned_spell_body_hitpoints_and_damage_compared(self):
        before = check_build.with_related(self.spell())
        after = check_build.with_related(self.spell(hp=101, damage=8))
        row = compare.compare_cards(after, before, ['SyntheticSpell'])[0]
        self.assertEqual(row['status'], 'mismatch')
        self.assertEqual(row['differences'], [
            {'field': 'related_units.spell.projectile.spawn_character.damage', 'before': 7, 'after': 8},
            {'field': 'related_units.spell.projectile.spawn_character.hitpoints', 'before': 100, 'after': 101},
        ])

    def test_linked_unit_rename_preserves_role_and_does_not_imply_stat_drift(self):
        before = check_build.with_related(self.spell('SyntheticOld'))
        after = check_build.with_related(self.spell('SyntheticNew'))
        self.assertEqual(list(after['cards'][0]['related_units']), ['spell.projectile.spawn_character'])
        self.assertEqual(compare.compare_cards(after, before, ['SyntheticSpell'])[0]['status'], 'equal')

    def test_primary_summon_stats_are_not_duplicated(self):
        doc = {'cards': [{'name': 'SyntheticTroop', 'summon_character': 'Primary', 'hitpoints': 100,
                          'summon_resolution': {'character': 'Primary'},
                          'second_summon': {'character': 'Secondary'}}],
               'units': {'Primary': {'hitpoints': 100}, 'Secondary': {'hitpoints': 50}}}
        card = check_build.with_related(doc)['cards'][0]
        self.assertEqual(card['related_units'], {'second_summon.character': {'hitpoints': 50}})
        self.assertEqual(card['hitpoints'], 100)

    def test_hero_local_tables_override_shared_unit_and_effect(self):
        doc = {'hero_forms': [{'name': 'Synthetic_hero', 'projectile': {'spawn_character': 'Child'},
                              'deploy_area_effect': 'Aura',
                              'tables': {'units': {'Child': {'hitpoints': 222, 'damage': 22}},
                                         'area_effect_objects': {'Aura': {'radius_milli': 2222}}}}],
               'units': {'Child': {'hitpoints': 111, 'damage': 11}},
               'area_effect_objects': {'Aura': {'radius_milli': 1111}}}
        card = check_build.with_related(doc)['hero_forms'][0]
        self.assertEqual(card['related_units']['projectile.spawn_character']['hitpoints'], 222)
        self.assertEqual(card['related_effects']['deploy_area_effect']['radius_milli'], 2222)

    def test_unresolved_unit_is_explicit_in_projection(self):
        doc = self.spell('MissingBody')
        doc['units'] = {}
        card = check_build.with_related(doc)['cards'][0]
        unresolved = {'status': 'unresolved_unit', 'name': 'MissingBody'}
        self.assertEqual(compare.projection(card)['related_units.spell.projectile.spawn_character.hitpoints'], unresolved)

    def test_hero_auxiliary_spawner_is_outside_base_stat_scope(self):
        hero = {'name': 'Synthetic_hero', 'spawner': {'character': 'Auxiliary'},
                'projectile': {'spawn_character': 'OrdinaryChild'}}
        self.assertEqual(check_build.unit_references(hero), {'projectile.spawn_character': 'OrdinaryChild'})
        hero['name'] = 'SyntheticBase'
        self.assertEqual(check_build.unit_references(hero)['spawner.character'], 'Auxiliary')

    def test_unit_reference_lists_spawn_type_and_excluded_metadata(self):
        obj = {'effects': [{'spawn_type': 'CharacterType', 'spawn': 'Body'},
                           {'spawn_type': 'AreaEffectType', 'spawn': 'Aura'},
                           {'character': 'Second'}],
               'tables': {'character': 'ExcludedTable'}, 'raw': {'character': 'ExcludedRaw'},
               'ability': {'character': 'ExcludedAbility'}, 'related_units': {'character': 'ExcludedPrior'}}
        self.assertEqual(check_build.unit_references(obj),
                         {'effects[0].spawn': 'Body', 'effects[2].character': 'Second'})

    def test_build_changes_marks_parser_or_projection_drift(self):
        baseline = {'manifest': {'fingerprint': 'same-apk', 'files': {}},
                    'card_stats': {'Synthetic': {'damage': 7}}, 'projection_version': 1,
                    'normalization': {'sources': {'extract_cards.py': 'parser-one'}}}
        self.assertFalse(compare.build_changes(baseline, baseline)['interpretation_changed'])
        for key in ('parser', 'projection'):
            current = json.loads(json.dumps(baseline))
            current['card_stats']['Synthetic']['damage'] = 8
            if key == 'parser':
                current['normalization']['sources']['extract_cards.py'] = 'parser-two'
            else:
                current['projection_version'] = 2
            with self.subTest(change=key):
                changes = compare.build_changes(baseline, current)
                self.assertTrue(changes['interpretation_changed'])
                self.assertEqual(changes['files'], [])
                self.assertEqual(changes['cards'][0]['differences'],
                                 [{'field': 'damage', 'before': 7, 'after': 8}])


if __name__ == '__main__':
    unittest.main()

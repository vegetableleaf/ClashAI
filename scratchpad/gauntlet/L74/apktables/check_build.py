#!/usr/bin/env python3
"""Offline APK table audit. Python 3.11+ and local Git; no SIM imports or writes."""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from decoder import extract, sha
from compare import (ICEBOW, cards_by_name, projection, compare_cards, opponent_counts,
                     check_levels, build_changes)

PARSER_REF = 'cacb7005f0e441797c533e91ab4f44820f9919d4'
SELECTED = 'data/derived/cards-160402017-20261006.json'


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def git_blob(repo, ref, path):
    return subprocess.check_output(['git', '-C', str(repo), 'show', f'{ref}:{path}'], stderr=subprocess.PIPE)


def unit_references(obj, path=''):
    """Use reference roles as keys so unit renames do not fabricate stat drift."""
    refs = {}
    if isinstance(obj, dict):
        for k, value in obj.items():
            if k in ('raw', 'tables', 'related_units', 'ability'):
                continue
            if k == 'spawner' and not path and str(obj.get('name', '')).endswith('_hero'):
                continue  # Auxiliary hero spawners require the ability interpreter.
            p = f'{path}.{k}' if path else k
            if isinstance(value, str) and (k in ('spawn_character', 'character') or
                    (k == 'spawn' and obj.get('spawn_type') == 'CharacterType')):
                refs[p] = value
            elif isinstance(value, (dict, list)):
                refs.update(unit_references(value, p))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            refs.update(unit_references(value, f'{path}[{i}]'))
    return refs


def normalize(tables: Path, repo: Path, ref: str, out: Path) -> tuple[dict, dict]:
    """Reuse the pinned SIM joins, but feed only this APK's decoded assets.

    Mechanics validation refusals are retained; hero base stats are read apart
    from the release's ability interpreter. This proves table parity, not runtime parity.
    """
    evidence = dict(parser_ref=ref, sources={}, refusals=[], hero_scope='base/deploy stats only; ability mechanics and auxiliary hero spawners not interpreted')
    folder = out / 'parser' / 'tools'
    folder.mkdir(parents=True)
    for name in ('extract_cards.py', 'mechanic_register.py'):
        data = git_blob(repo, ref, 'tools/' + name)
        (folder / name).write_bytes(data)
        evidence['sources'][name] = sha(data)
    sys.path.insert(0, str(folder))
    # Separate processes are normal, but unit callers may invoke twice.
    for name in ('extract_cards', 'mechanic_register'):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location('extract_cards', folder / 'extract_cards.py')
    e = importlib.util.module_from_spec(spec)
    sys.modules['extract_cards'] = e
    spec.loader.exec_module(e)
    v = dataclasses.replace(e.VINTAGES['160402017'], key='apktables', raw=tables,
        update=None, additions=False, version='local-apk-tables',
        warning='Packaged APK data only; no content updates. SIM parser interpretation, not runtime proof.',
        source='local APK extraction; see extraction.json', vintage='supplied APK', roster_dating='not inferred')
    heroes = dict(e.HERO_FORMS)
    e.HERO_FORMS = {}
    e.CENSUS = []
    with (out / 'normalization.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
        t = e.load_tables(v)
        doc = e.build(t)
        # Recover ordinary card stats when only a release-specific evolution
        # mechanic interpreter refused the form. Keep its refusal in evidence.
        recovered = []
        built = {c['name'] for c in doc['evolutions']}
        for name in e.EVOLUTIONS:
            s = t['spells_evolved'].get(name)
            if name in built or s is None or e.flag(s, 'NotInUse'):
                continue
            try:
                links = e.hero_file_links(v)
                bases = [(kind, b) for key, kind in e.EVOLVED_BASE_TABLES for b in t[key].records.values()
                         if (b['EvolvedSpells'] == name or name in links.get(b['Name'], [])) and not b['NotInUse']]
                if len(bases) != 1:
                    raise ValueError('evolution base link is ambiguous')
                kind, b = bases[0]
                c = e.spell_card(t, doc['rarities'], s) if kind == 'spell' else e.summon_card(t, doc['rarities'], kind, 'spells_evolved', s)
                c['form_of'] = b['Name']
                doc['evolutions'].append(c)
                recovered.append(name)
            except (Exception, SystemExit) as ex:
                evidence['refusals'].append([name, 'basic stats also refused: ' + str(ex)])
        evidence['recovered_basic_stats'] = recovered
        for form, (base, stem) in heroes.items():
            if not all(p.exists() for p in e.hero_files(v, stem)):
                evidence['refusals'].append([form, 'hero files absent from APK'])
                continue
            try:
                h = e.load_tables(v, hero={form: (base, stem)})
                s = h['spells_hero'].get(form)
                if s is None or s['CardForm'] != 'HeroForm' or form not in h.hero_links.get(base, []):
                    raise ValueError('hero card/link not resolved')
                s = e.Row(s.columns, {**s, 'Name': form})
                key = next((k for k in ('spells_characters', 'spells_buildings', 'spells_other') if h[k].get(base) is not None), None)
                if key is None:
                    raise ValueError('non-troop/building hero requires separate mechanics parser')
                if s['Rarity'] is None or key == 'spells_other':
                    b = h[key].get(base)
                    s = e.Row(set(b.columns) | set(s.columns), {**b, **{k: val for k, val in s.items() if val is not None}, 'Name': form})
                group = e.tomb_group(h, form, s) if key != 'spells_other' else None
                if group is not None:
                    s = e.Row(s.columns, {**s, 'SummonCharacter': group['tomb'], 'SummonNumber': 1, 'IsAGroup': None})
                c = (e.spell_card(h, e.rarity_table(h), s) if key == 'spells_other' else
                     e.summon_card(h, e.rarity_table(h), 'troop' if key == 'spells_characters' else 'building', 'spells_hero', s))
                c.update(form_of=base, display_name='Hero ' + e.display_name(base))
                c['tables'] = {'area_effect_objects': {}, 'units': {}}
                for unit in (c.get('summon_character'), s.get('LinkedChampionCharacter')):
                    if unit:
                        c['tables']['units'][unit] = e.norm_unit(h, unit, with_raw=True)
                for field in ('deploy_area_effect', 'death_area_effect'):
                    if c.get(field):
                        c['tables']['area_effect_objects'][c[field]] = e.norm_aeo(h, c[field])
                for unit in set(unit_references(c).values()):
                    if unit not in c['tables']['units']:
                        c['tables']['units'][unit] = e.norm_unit(h, unit, with_raw=True)
                doc['hero_forms'].append(c)
            except (Exception, SystemExit) as ex:
                evidence['refusals'].append([form, str(ex)])
    evidence['refusals'] += e.CENSUS
    # Identify unhandled future forms as coverage gaps rather than pretending
    # the pinned parser knows every new release roster.
    known = set(heroes)
    for path in v.glob('characters/hero_form', '*_spell.toml'):
        for name in e.client_toml(path).get('SPELL_HERO', {}):
            if name not in known:
                evidence['refusals'].append([name, 'new hero outside pinned parser roster'])
    for n, r in t['spells_evolved'].records.items():
        if n not in e.EVOLUTIONS and not e.flag(r, 'NotInUse'):
            evidence['refusals'].append([n, 'new evolution outside pinned parser roster'])
    return doc, evidence


def with_related(doc):
    """Include deploy/death effects and explicitly spawned/second-summon units."""
    for c in cards_by_name(doc).values():
        related = {}
        for field in ('deploy_area_effect', 'death_area_effect'):
            name = c.get(field)
            if isinstance(name, str):
                row = c.get('tables', {}).get('area_effect_objects', {}).get(name) or doc.get('area_effect_objects', {}).get(name)
                if row is not None:
                    related[field] = row
        c['related_effects'] = related
        c['related_units'] = {}
        for role, name in sorted(unit_references(c).items()):
            if name == c.get('summon_character'):
                continue  # Already represented by the card's primary stats.
            unit = c.get('tables', {}).get('units', {}).get(name) or doc.get('units', {}).get(name)
            if unit is not None:
                unit = dict(unit)
                rarity = doc.get('rarities', {}).get(unit.get('rarity'))
                if rarity:
                    unit['level_scaling'] = dict(rarity=unit['rarity'], ladder_rarity=unit['rarity'],
                        base_level=rarity['relative_level']+1, level_count=rarity['level_count'],
                        relative_level=rarity['relative_level'], multiplier_percent_by_level=rarity['multiplier_percent_by_level'])
                c['related_units'][role] = unit
            else:
                c['related_units'][role] = {'hitpoints': {'status':'unresolved_unit', 'name':name}}
    return doc


def fmt(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('|', '\\|')


def report_markdown(report):
    lines = ['# APKTABLES private report', '',
        f"Build label: `{report['label']}`; APK set SHA256 `{report['manifest']['fingerprint']}`.",
        f"Decoded {len(report['manifest']['files'])} CSV/TOML assets; failures {len(report['manifest']['failures'])}; conflicts {len(report['manifest']['conflicts'])}.",
        '', 'Exact values: milliseconds, millitiles, raw table speeds, unified level-1 stats where the object ladder says base_level=1. Null is not zero. Missing is not equality.',
        'Equal means equal stored projections, not measured behavior. Null spell deploy times have no explicit card override; any engine/global default remains outside this comparison. Crown-tower percentages reflect the parser interpretation of raw damage encodings.',
        'Only packaged data was inspected; installed/downloaded content updates and engine behavior are outside this comparison.',
        'Normalization uses the pinned SIM source joins, so shared interpretation errors remain possible. Hero ability mechanics and auxiliary hero spawners are not interpreted.',
        '', '## Opponent selection', '', report['opponents']['basis'], '',
        f"{report['opponents']['census_decks']} census decks, {report['opponents']['census_selected_sides']} weighted sides; {report['opponents']['pro2_rows']} PRO2 replay rows.", '',
        '|Rank|Card|Census deck sides|PRO2 deck sides|Combined|', '|---:|---|---:|---:|---:|']
    for r in report['opponents']['top']:
        lines.append(f"|{r['rank']}|{r['card']}|{r['census']}|{r['pro2']}|{r['total']}|")
    for label, results in report['comparisons'].items():
        lines += ['', f'## {label}: icebow and top 60', '',
                  '|Card|Status|SIM value → APK value (exact field)|', '|---|---|---|']
        for r in results:
            if r['card'] not in report['main_names']:
                continue
            detail = '; '.join(f"`{x['field']}`: `{fmt(x['before'])}` → `{fmt(x['after'])}`" for x in r['differences'])
            if r['status'] == 'missing_card':
                detail = f"APK present={r['apk_present']}, SIM present={r['sim_present']}"
            lines.append(f"|{r['card']}|{r['status']}|{detail or 'All projected fields equal'}|")
        variants = [r for r in results if r['card'] not in report['main_names'] and r['status'] != 'equal']
        lines += ['', '### Observed opponent forms: mismatches / missing', '', '|Form|Status|SIM → APK|', '|---|---|---|']
        for r in variants:
            detail = '; '.join(f"`{x['field']}`: `{fmt(x['before'])}` → `{fmt(x['after'])}`" for x in r['differences'])
            lines.append(f"|{r['card']}|{r['status']}|{detail or ('APK present='+str(r.get('apk_present'))+', SIM present='+str(r.get('sim_present')))}|")
    lines += ['', '## Configured level caps', '', '|Card|Configured|Min|Cap|Status|', '|---|---:|---:|---:|---|']
    for r in report['levels']:
        lines.append(f"|{r['card']}|{r['level']}|{r.get('minimum','?')}|{r.get('cap','?')}|{r['status']}|")
    lines += ['', 'Only explicit LIVE_OPTIONS overrides are listed; unspecified levels depend on the live entry default, which this tool does not execute.',
              '', '## Changes since previous build', '', f"Status: {report['changes']['status']}; {len(report['changes']['files'])} changed/added/removed table files; {len(report['changes']['cards'])} changed card projections."]
    if report['changes'].get('interpretation_changed'):
        lines.append('Parser/projection changed since the baseline: normalized card changes may reflect interpretation changes, not changed APK bytes.')
    for r in report['changes']['files']:
        lines.append(f"- `{r['path']}`: `{r['before']}` → `{r['after']}`")
    if not report['changes'].get('interpretation_changed'):
        for r in report['changes']['cards']:
            lines.append(f"- {r['card']}: " + '; '.join(f"{x['field']}: {fmt(x['before'])} → {fmt(x['after'])}" for x in r['differences']))
    else:
        lines.append('Exact cross-interpretation deltas are retained in changes.json; they are not listed as game balance changes here.')
    lines += ['', '## Decoding failures', '', fmt(report['manifest']['failures']), '', '## Normalization limitations', '']
    for name, error in report['normalization']['refusals']:
        lines.append(f'- `{name}`: {error}')
    lines += ['', '## Provenance', '', '```json', json.dumps(report['sources'], indent=2), '```']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('apk_dir', type=Path)
    ap.add_argument('--selected-table', type=Path, help='JSON exported from selected_card_data() on the pod, if desired')
    ap.add_argument('--sim-repo', type=Path, default=ROOT/'research/ext/Royale/RoyaleSim')
    ap.add_argument('--parser-ref', default=PARSER_REF, help='local Git commit with reviewed parser and selected data; never fetched')
    ap.add_argument('--old-table', type=Path, action='append', help='repeatable; default cards*.json in old pin')
    ap.add_argument('--census', type=Path, default=ROOT/'scratchpad/gauntlet/L70/pool_forms/loadable_decks.json')
    ap.add_argument('--pro2', type=Path, default=ROOT/'scratchpad/gauntlet/L74/pro2/output/battles.csv')
    ap.add_argument('--live-options', type=Path, default=ROOT/'scratchpad/gauntlet/L70/live/LIVE_OPTIONS')
    ap.add_argument('--label', help='descriptive build label; APK fingerprint is authoritative')
    ap.add_argument('--previous', type=Path, help='explicit prior snapshot.json; default latest successful local extraction')
    ap.add_argument('--out', type=Path, default=HERE/'out/builds', help='must be inside this tool\'s ignored out directory')
    args = ap.parse_args(argv)
    out = args.out.resolve()
    if not out.is_relative_to(HERE/'out'):
        ap.error('--out must stay within apktables/out to keep private tables ignored')
    out.mkdir(parents=True, exist_ok=True)
    run = out / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + f'-{os.getpid()}')
    run.mkdir()
    latest = out/'latest.json'
    previous_path = args.previous
    if previous_path is None and latest.exists():
        previous_path = Path(json.loads(latest.read_text())['snapshot'])
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path else None
    try:
        manifest = extract(args.apk_dir.resolve(), run/'tables')
        write_json(run/'extraction.json', manifest)
        if manifest['failures'] or manifest['conflicts']:
            raise ValueError('incomplete extraction or conflicting splits; see extraction.json; baseline preserved')
        doc, norm = normalize(run/'tables/csv_logic', args.sim_repo, args.parser_ref, run)
        doc = with_related(doc)
        write_json(run/'cards.json', doc)
        write_json(run/'normalization.json', norm)
        sources = dict(parser=norm['sources'], parser_ref=args.parser_ref, apk_dir=str(args.apk_dir.resolve()), tables={},
                       tool={n:sha((HERE/n).read_bytes()) for n in ('check_build.py','compare.py','decoder.py')})
        sims = {}
        old_paths = args.old_table or sorted((args.sim_repo/'data/derived').glob('cards*.json'))
        for path in old_paths:
            data = path.read_bytes()
            label = ('old/' if path.name in ('cards.json', 'cards-15.535.json', 'cards-2018.json') else 'reference/') + path.name
            sims[label] = with_related(json.loads(data))
            sources['tables'][label] = dict(path=str(path.resolve()), sha256=sha(data))
        data = args.selected_table.read_bytes() if args.selected_table else git_blob(args.sim_repo, args.parser_ref, SELECTED)
        sims['selected-0.1.33'] = with_related(json.loads(data))
        sources['tables']['selected-0.1.33'] = dict(path=str(args.selected_table) if args.selected_table else f'git:{args.parser_ref}:{SELECTED}', sha256=sha(data),
            evidence='exported JSON supplied by caller' if args.selected_table else 'local release source table; installed wheel payload not independently verified')
        for name, path in [('census',args.census),('pro2',args.pro2),('live_options',args.live_options)]:
            sources[name] = dict(path=str(path.resolve()), sha256=sha(path.read_bytes()))
        opponents = opponent_counts(args.census, args.pro2, [doc, *sims.values()])
        main_names = list(dict.fromkeys(ICEBOW + [x['card'] for x in opponents['top']]))
        names = list(dict.fromkeys(main_names + [x['card'] for x in opponents['variants']]))
        snapshot = dict(manifest=manifest, projection_version=4, card_stats={n: projection(c) for n,c in cards_by_name(doc).items()},
                        normalization=norm, label=args.label or args.apk_dir.parent.name)
        changes = build_changes(previous, snapshot)
        report = dict(label=snapshot['label'], manifest=manifest, normalization=norm, sources=sources,
                      main_names=main_names, opponents=opponents, changes=changes,
                      comparisons={label: compare_cards(doc, sim, names) for label, sim in sims.items()},
                      levels=check_levels(args.live_options.read_text(encoding='utf-8-sig'), doc))
        write_json(run/'snapshot.json', snapshot)
        write_json(run/'report.json', report)
        (run/'REPORT.md').write_text(report_markdown(report), encoding='utf-8')
        write_json(run/'changes.json', changes)
        write_json(out/'latest.tmp', dict(snapshot=str(run/'snapshot.json'), report=str(run/'REPORT.md')))
        (out/'latest.tmp').replace(latest)
        print(f"Decoded {len(manifest['files'])} tables; normalization limitations: {len(norm['refusals'])}")
        for label, rows in report['comparisons'].items():
            print(label + ': ' + ', '.join(f'{s}={sum(r["status"]==s for r in rows)}' for s in ('equal','mismatch','missing_card')))
        print('Levels:', json.dumps(report['levels']))
        if changes.get('interpretation_changed'):
            print('Build changes:', json.dumps({k:v for k,v in changes.items() if k != 'cards'}))
            print('Parser/projection changed: cross-interpretation card deltas are in', run/'changes.json')
        else:
            print('Build changes:', json.dumps(changes))
        print('Report:', run/'REPORT.md')
        print('APKTABLES_REPORT_WRITTEN')
        return 0 if all(r['status']=='ok' for r in report['levels']) else 2
    except (Exception, SystemExit) as e:
        write_json(run/'ERROR.json', dict(error=str(e), type=type(e).__name__, previous=str(previous_path)))
        print(f'APKTABLES INCOMPLETE: {e}; evidence {run}; baseline preserved', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

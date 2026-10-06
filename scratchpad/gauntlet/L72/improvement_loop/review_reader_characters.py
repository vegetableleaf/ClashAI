"""Outside one-shot identity/receipt review; no probe, model or test replay."""
import collections,copy,hashlib,json,math,sys
from pathlib import Path
LOOP=Path(__file__).resolve().parent;ROOT=LOOP.parents[3];H=LOOP/'reader_character_identity'
sys.path.insert(0,str(H));from adapter import adapt
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text())
def parent_valid(cube,objects):
    if cube.get('native_name')!='IceWizardHeroFloatingCube' or cube.get('native_name_status')!='ok' or not cube.get('attached_owner_read_ok'):return False
    parent=objects.get(cube.get('attached_owner'))
    return bool(parent and parent is not cube and parent.get('native_name')=='IceWizardHero' and parent.get('native_name_status')=='ok'
        and parent['card_id']==cube['card_id']==203000023 and parent['side']==cube['side'])
def main():
    assert not (H/'reviewed.json').exists()
    r=load(H/'verified.json');assert r['complete']
    for path,digest in r['sources'].items():assert sha(ROOT/path)==digest
    for path,digest in r['generated'].items():assert sha(H/path)==digest
    details=load(H/'details.json');decoded=[json.loads(s) for s in (H/'decoder.out').read_text().splitlines()]
    lookup={(x['batch_index'],x['address']):x for x in decoded};assert len(lookup)==len(decoded)==1215
    counts=collections.Counter()
    for row in details:
        d=lookup[row['batch_index'],row['address']]
        for k in ('native_name','status','attached_owner'):assert row[k]==d[k]
        counts[row['native_name'] or row['status']]+=1
    assert dict(counts)==r['classes'] and len(details)==r['raw_object_records']==1202
    p=load(H/'passive_v2.json');assert p['complete'] and p['engineering_pass']
    for path,digest in p['sources'].items():assert sha(ROOT/path)==digest
    assert sha(H/'passive_v2_raw.jsonl')==p['raw_sha256']
    frames=[json.loads(s) for s in (H/'passive_v2_raw.jsonl').read_text().splitlines()]
    assert len(frames)==120 and [x['sequence'] for x in frames]==list(range(120))
    allnames=collections.Counter();coherentnames=collections.Counter();qualified=unknown=0
    for f in frames:
        assert f['character_identity']=={'schema':1,'build':160402012}
        coherent=f['battle_active'] and f['coherent']
        objects={x['address']:x for x in f['entities']}
        for e in f['entities']:
            if e['card_id']!=203000023:continue
            assert e['native_name_status']=='ok'
            allnames[e['native_name']]+=1
            if coherent:coherentnames[e['native_name']]+=1
            if coherent and e['native_name']=='IceWizardHeroFloatingCube':
                if parent_valid(e,objects):qualified+=1
                else:unknown+=1
        adapted=adapt(f)
        assert len(adapted['entities'])+len(adapted['excluded_public_objects'])==len(f['entities'])
    assert allnames==coherentnames==collections.Counter(p['names'])
    assert coherentnames['IceWizardHero']>0 and coherentnames['IceWizardHeroFloatingCube']>0
    read=sorted(f['read_us'] for f in frames)
    assert (read[59]+read[60])/2==p['read_us']['median']<=5000
    assert read[math.ceil(.95*len(read))-1]==p['read_us']['p95']<=20000 and read[-1]==p['read_us']['maximum']
    # Current-parent checks reject false joins; these never drive filtering.
    sample=next(f for f in frames if any(e.get('native_name')=='IceWizardHeroFloatingCube' for e in f['entities']))
    objects={e['address']:e for e in sample['entities']}
    cube=next(e for e in sample['entities'] if e.get('native_name')=='IceWizardHeroFloatingCube')
    assert parent_valid(cube,objects)
    bad=0
    for field,value in [('attached_owner','0x0'),('native_name','IceWizardHero'),('native_name_status','read_error'),('attached_owner_read_ok',False),('side',1-cube['side'])]:
        changed=copy.deepcopy(cube);changed[field]=value;assert not parent_valid(changed,objects);bad+=1
    changed=copy.deepcopy(objects);changed[cube['attached_owner']]['native_name']='IceWizardHero_IceCube'
    assert not parent_valid(cube,changed);bad+=1
    receipts={}
    expected={'l72-reader-character-identity':0,'l72-reader-character-adapter':1,'l72-reader-character-lifecycle-v2':0,
        'l72-reader-character-passive':1,'l72-reader-character-passive-v2':0,'l72-reader-character-entry':0,'l72-reader-character-entry-check':0}
    checks=ROOT/'scratchpad/gauntlet/L71/integration/checks'
    for name,code in expected.items():
        path=checks/(name+'.json');value=load(path);assert value['exit_code']==code
        assert sha_text(checks/(name+'.out'))==value['output_sha256']
        if code==0:assert value['matched']
        receipts[name]=dict(sha256=sha(path),**value)
    failed=(checks/'l72-reader-character-adapter.out').read_text()
    assert '1 failed, 19 passed' in failed
    assert '1 passed' in (checks/'l72-reader-character-lifecycle-v2.out').read_text()
    assert '4 passed' in (checks/'l72-reader-character-entry.out').read_text()
    settings=[json.loads(s) for s in (checks/'l72-reader-character-entry-check.out').read_text().splitlines() if s.startswith('{"check":')]
    assert len(settings)==1
    st=settings[0];assert st['sha256']=='76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd'
    assert st['device']=='cpu' and st['tau']==.35 and not st['anti_leak'] and st['public_audit']
    assert st['decision_options']['card_choice']=='argmax' and st['decision_options']['spell_aim']=='argmax'
    sourcefiles=[Path(__file__),*H.glob('*.py'),*H.glob('*.c'),*H.glob('*.h'),H/'ENTRY_PLAN.md',H/'LIFECYCLE_RECOVERY.md']
    output=dict(complete=True,original_byte_records=len(details),original_counts=dict(counts),passive_coherent_frames=sum(f['battle_active'] and f['coherent'] for f in frames),
        passive_coherent_names=dict(coherentnames),current_floating_parent_joined=qualified,current_floating_parent_unknown=unknown,
        parent_controls=dict(positive=1,negative=bad),adapter_completed_tests=20,entry_completed_tests=4,
        failed_originals_preserved=['test_adapter.py final canonical-slug assertion','passive.py segment-base uniqueness assertion'],
        source_bindings={str(x.relative_to(ROOT)):sha(x) for x in sourcefiles},receipts=receipts,entry_check=st,
        production_sources_unchanged=True,owner_worker_transition='PENDING',decision_capture='PENDING',policy_benefit='UNMEASURED',ice_cube_mechanics='UNQUALIFIED')
    (H/'reviewed.json').write_text(json.dumps(output,indent=2));print(json.dumps({k:v for k,v in output.items() if k not in ('source_bindings','receipts','entry_check')}));print('READER_CHARACTER_REVIEWED')
def sha_text(p):return hashlib.sha256(Path(p).read_text().encode()).hexdigest()
if __name__=='__main__':main()

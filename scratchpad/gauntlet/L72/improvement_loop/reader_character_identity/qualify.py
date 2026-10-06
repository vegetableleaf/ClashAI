"""New offline original-byte identity census and separately compiled C decoder."""
import collections, hashlib, io, json, re, struct, subprocess, sys, time
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE))
from build_successor import build, ORIGINAL

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def linux(path):return '/mnt/c/'+str(Path(path).resolve()).replace('\\','/').split(':/',1)[1]
def command(args, **kwargs):
    p=subprocess.run(args,capture_output=True,timeout=120,**kwargs)
    if p.returncode:raise RuntimeError((args,p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace')))
    return p.stdout
def integer(data,offset=0,size=8,signed=False):
    return int.from_bytes(data[offset:offset+size],'little',signed=signed) if len(data)>=offset+size else 0
def reader(blocks):
    def read(address,size):
        for base,b in reversed(blocks):
            if base==address and len(b)>=size:return b[:size]
        for base,b in reversed(blocks):
            if base<=address and address+size<=base+len(b):return b[address-base:address-base+size]
        return None
    return read
def reference(blocks,address):
    read=reader(blocks); touched=[]
    def get(a,n):
        b=read(a,n)
        if b is not None:touched.append((a,b))
        return b
    ownerbytes=get(address+0x180,8) if address and address+0x187<2**64 else None
    owner=integer(ownerbytes) if ownerbytes is not None else 0
    out=dict(address=hex(address),native_name=None,status='read_error',attached_owner=hex(owner) if owner else None,
             attached_owner_read_ok=ownerbytes is not None)
    def pointer(base,offset,size):
        return bool(base and 0<=base+offset<=base+offset+size-1<2**64)
    if not pointer(address,0x48,8):out['status']='invalid_pointer';return out,touched
    b=get(address+0x48,8)
    if b is None:return out,touched
    dp=integer(b)
    if not pointer(dp,0x2c,4):out['status']='invalid_pointer';return out,touched
    b=get(dp+0x2c,4)
    if b is None:return out,touched
    length=integer(b,size=4)
    if not 1<=length<=128:out['status']='invalid_name';return out,touched
    if length<8:chars=dp+0x30
    else:
        if not pointer(dp,0x30,8):out['status']='invalid_pointer';return out,touched
        b=get(dp+0x30,8)
        if b is None:return out,touched
        chars=integer(b)
    if not pointer(chars,0,length):out['status']='invalid_pointer';return out,touched
    b=get(chars,length)
    if b is None:return out,touched
    if not re.fullmatch(rb'[A-Za-z0-9_]{1,128}',b):out['status']='invalid_name';return out,touched
    out.update(native_name=b.decode('ascii'),status='ok');return out,touched
def write_batch(dest,blocks,addresses):
    dest.write(struct.pack('<I',len(blocks)))
    for a,b in blocks:dest.write(struct.pack('<QI',a,len(b))+b)
    dest.write(struct.pack('<I',len(addresses)))
    for a in addresses:dest.write(struct.pack('<Q',a))
def main():
    assert not (HERE/'started.json').exists()
    paths=[ROOT/'scratchpad/gauntlet/L70/reader'/n for n in ['capture_a.jsonl','capture_b.jsonl']]
    sources=[*paths,ORIGINAL,*[HERE/n for n in ['PLAN.md','qualify.py','adapter.py','test_adapter.py','build_successor.py','character_name.h','decoder_test.c']],
        ROOT/'scratchpad/gauntlet/L72/improvement_loop/native_elite_form_probe_v5.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    (HERE/'started.json').write_text(json.dumps(dict(time=time.time(),sources=hashes,live_started=False,model_calls=0),indent=2))
    successor=build()
    for source,binary in [(HERE/'decoder_test.c',HERE/'decoder_test'),(successor,HERE/'live_sampler3')]:
        command(['wsl.exe','--exec','gcc','-O2','-static','-o',linux(binary),linux(source)])
    stream=io.BytesIO(); expected=[]; metadata=[]; framecounts=collections.Counter(); classes=collections.Counter(); links=collections.Counter(); batch=0
    for path in paths:
        libbase=None
        for line in path.open():
            row=json.loads(line)
            if row['event']=='meta':libbase=row['libg_base'];continue
            framecounts['all_batches']+=1
            blocks=[(a,bytes.fromhex(h)) for a,n,h,e in row['blocks'] if h is not None]
            read=reader(blocks)
            def ptr(a):return integer(read(a,8) or b'')
            root=ptr(libbase+0x1aeef98); ctx=ptr(root+0x18); battle=ptr(ctx+0x90)
            ticks=[integer(bytes.fromhex(h),size=4,signed=True) for a,n,h,e in row['blocks'] if a==battle+0x60 and h is not None]
            if len(ticks)!=2 or ticks[0]!=ticks[1]:framecounts['incoherent_or_unbracketed']+=1;continue
            framecounts['coherent']+=1
            ps=ptr(battle+0xa8); registry=ptr(ps+8); collection=ptr(registry+0x40); data=ptr(collection+8)
            n=integer(read(collection+0x14,4) or b'',size=4,signed=True)
            if not 0<=n<=2048:framecounts['bad_registry_count']+=1;continue
            array=read(data,n*8)
            if array is None:
                framecounts['partial_registry']+=1
                exact=[b for a,b in blocks if a==data];array=(exact[-1] if exact else b'')[:n*8]
                framecounts['uncaptured_registry_suffix']+=n-len(array)//8
            objects={}
            for j in range(len(array)//8):
                address=integer(array,j*8); raw=read(address,0x128)
                if raw is None:framecounts['missing_object_bytes']+=1;continue
                card=integer(raw,0xac,4,True);cat=integer(raw,8,4,True);vt=integer(raw)-libbase
                if card!=203000023 or not (5000000<=cat<6000000 and 0<vt<0x3000000):continue
                ref,touched=reference(blocks,address)
                objects[address]=(ref,touched,integer(raw,0x78,4,True),cat)
            if not objects:continue
            selected={a:b for ref,touched,side,cat in objects.values() for a,b in touched}
            write_batch(stream,list(selected.items()),list(objects))
            for address,(ref,touched,side,cat) in objects.items():
                expected.append(dict(batch_index=batch,**ref));classes[ref['native_name'] or ref['status']]+=1
                owner=int(ref['attached_owner'],16) if ref['attached_owner'] else 0
                parent=objects.get(owner)
                qualified=bool(ref['native_name']=='IceWizardHeroFloatingCube' and parent and parent[0]['native_name']=='IceWizardHero' and parent[2]==side)
                if ref['native_name']=='IceWizardHeroFloatingCube':links['floating_total']+=1;links['qualified_parent' if qualified else 'unresolved_parent']+=1
                metadata.append(dict(capture=path.name,seq=row['seq'],tick=ticks[0],address=hex(address),category=cat,side=side,batch_index=batch,
                    native_name=ref['native_name'],status=ref['status'],attached_owner=ref['attached_owner'],qualified_floating_parent=qualified))
            batch+=1
    # Original current-block byte decoding plus synthetic boundary controls.
    fixtures=[]
    def fixture(name,declared=None,drop=False,pointer=0x3000,obj=0x1000,dp=0x2000,owner=True):
        length=len(name) if declared is None else declared
        blocks=[(obj+0x48,struct.pack('<Q',dp))] if obj+0x4f<2**64 else []
        if owner and obj+0x187<2**64:blocks.append((obj+0x180,bytes(8)))
        if dp:
            blocks.append((dp+0x2c,struct.pack('<I',length%(2**32))))
            if 0<length<8:blocks.append((dp+0x30,name))
            else:
                blocks.append((dp+0x30,struct.pack('<Q',pointer)))
                if not drop and name and pointer and pointer+len(name)<2**64:blocks.append((pointer,name))
        return blocks,obj
    for args in [(b'Knight',{}),(b'IceWizardHero',{}),(b'IceWizardHeroFloatingCube',{'owner':False}),
        (b'A'*128,{}),(b'',{'declared':0}),(b'A'*129,{}),(b'bad-name',{}),(b'bad\x00name',{}),
        (b'IceWizardHero',{'drop':True}),(b'IceWizardHero',{'pointer':0}),(b'IceWizardHero',{'dp':0}),
        (b'IceWizardHero',{'declared':-1}),(b'A',{'obj':2**64-16})]:
        blocks,obj=fixture(args[0],**args[1]);ref,_=reference(blocks,obj)
        fixtures.append(ref);write_batch(stream,blocks,[obj]);expected.append(dict(batch_index=batch,**ref));batch+=1
    data=stream.getvalue();(HERE/'public_name_fixtures.bin').write_bytes(data)
    output=command(['wsl.exe','--exec',linux(HERE/'decoder_test')],input=data)
    (HERE/'decoder.out').write_bytes(output)
    actual=[json.loads(s) for s in output.splitlines()];assert actual==expected
    assert set(('IceWizardHero','IceWizardHeroFloatingCube','IceWizardHero_IceCube'))<=classes.keys()
    assert sum(f['status']=='ok' for f in fixtures)==4 and len(fixtures)==13
    malformed=[b'\x00',struct.pack('<I',4097),struct.pack('<I',1)+struct.pack('<QI',0x1000,0),data[:-1]]
    for value in malformed:
        run=subprocess.run(['wsl.exe','--exec',linux(HERE/'decoder_test')],input=value,capture_output=True,timeout=30)
        assert run.returncode==2
    # The original and successor emit exactly the same legacy entity JSON when opt-in is off.
    fmt='''\nint main(void) {\n EntityFrame e={.address=0x1234,.category=5000001,.kind=15,.side=1,.x=3000,.y=17000,.card_id=203000023,.level=14,.hp=753,.max_hp=911,.behavior=2};\n emit_extended_entity(&e); putchar('\\n');\n e.card_id=13000043; emit_extended_entity(&e); putchar('\\n');\n e.card_id=26000000; emit_extended_entity(&e); putchar('\\n');return 0;\n}\n'''
    formats=[]
    for label,source in [('original',ORIGINAL),('successor',successor)]:
        harness=HERE/f'format_{label}.c';binary=HERE/f'format_{label}'
        harness.write_text('#define main original_sampler_main\n#include "'+linux(source)+'"\n#undef main\n'+fmt)
        command(['wsl.exe','--exec','gcc','-O2','-static','-o',linux(binary),linux(harness)])
        formats.append(command(['wsl.exe','--exec',linux(binary)]))
    assert formats[0]==formats[1]
    for p,h in zip(sources,hashes.values()):assert sha(p)==h
    (HERE/'details.json').write_text(json.dumps(metadata,indent=2))
    report=dict(complete=True,frames=dict(framecounts),classes=dict(classes),attachments=dict(links),raw_object_records=len(metadata),
        exact_c_decodes=len(actual),positive_name_fixtures=4,malformed_name_fixtures=9,malformed_streams=4,
        legacy_formatter_cases=3,legacy_formatter_exact=True,decoder_fixture_bytes=len(data),
        sources=hashes,generated={str(p.relative_to(HERE)):sha(p) for p in [successor,HERE/'live_sampler3',HERE/'decoder_test',HERE/'public_name_fixtures.bin',HERE/'decoder.out',HERE/'details.json']},
        live_started=False,reader_installed=False,active_sources_edited=False,model_calls=0,optimizer_steps=0,
        activation='PENDING current build/passive runtime qualification and owner-worker transition',cube_mechanics='UNQUALIFIED')
    (HERE/'verified.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('sources','generated')}));print('READER_CHARACTER_IDENTITY_VERIFIED')
if __name__=='__main__':main()

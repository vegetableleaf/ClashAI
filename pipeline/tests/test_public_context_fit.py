"""Synthetic fitter integration only; never a real C2 completion artifact."""
import hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
import pytest
from pipeline.rocket_context import load_weight_artifact,require_weight_artifact

@pytest.fixture
def workspace_tmp():
    # pytest's mode-0700 Windows temp directory is inaccessible to this
    # restricted runner. Ordinary workspace directories retain inherited ACLs.
    import uuid
    path=Path(__file__).resolve().parents[2]/'.foreman/codex_autopilot/runs/r6'/('fit_fixture_'+uuid.uuid4().hex)
    path.mkdir(parents=True)
    return path

def module():
    path=Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31/fit_public_context.py'
    spec=importlib.util.spec_from_file_location('public_fit_fixture',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture(tmp_path):
    m=module();tags=np.array(['synthetic-fixture-'+str(i) for i in range(100)])
    n=len(tags)*6;sc=np.zeros((n,70),np.float32);sc[:,6]=1
    rng=np.random.default_rng(17);sc[:,0]=rng.random(n)
    card=np.tile([1,1,1,1,2,2],len(tags));rep=np.repeat(np.arange(len(tags)),6)
    arrays=dict(sc=sc,hand_card=np.tile([1,2,3,4],(n,1)),rep=rep,split=np.zeros(n,np.int8),
                tick=np.tile(np.arange(6),len(tags)),side=np.zeros(n,np.int8),y_gate=np.ones(n),y_card=card)
    meta=dict(feature_version=4,card_vocab=['<pad>','rocket','x-bow','tornado','the-log'],corpora=['synthetic/public_preflight_remaining'])
    data=tmp_path/'synthetic.npz';np.savez(data,tags=tags,meta=json.dumps(meta),**arrays)
    calibration=tmp_path/'calibration.json';calibration.write_text(json.dumps(dict(status='R1_REVISED_CALIBRATION_PASS',modal_offensive=True,
        overlap=0,balanced_overlap=0,reach_milli=13038.4)))
    events=[]
    for i in range(n):
        kind='rocket' if card[i]==1 else 'x-bow'
        events.append(dict(tag=str(tags[rep[i]]),side=0,tick=int(arrays['tick'][i]),card=kind,
            tower_rocket=i%6==0,defensive_rocket=i%6==1,rocket_then_tornado=i%6==2,tornado_then_rocket=i%6==3,
            offensive_xbow=i%6==4,defensive_xbow=i%6==5,lane_state='alive'))
    labels=tmp_path/'labels.jsonl';labels.write_text(''.join(json.dumps(e)+'\n' for e in events))
    (tmp_path/'manifest.json').write_text(json.dumps(dict(xbow_calibration_sha256=m.C.sha(calibration))))
    rulings=tmp_path/'rulings.md';rulings.write_text('Synthetic test authority; not a real artifact.')
    return m,data,labels,calibration,rulings,arrays,tags,meta,events

def test_six_target_fitter_and_provenance_negative_control(workspace_tmp,monkeypatch):
    tmp_path=workspace_tmp
    m,data,labels,calibration,rulings,arrays,tags,meta,events=fixture(tmp_path)
    out=tmp_path/'synthetic-output'
    monkeypatch.setattr(sys,'argv',['fit','--data',str(data),'--labels',str(labels),'--rulings',str(rulings),
        '--xbow-validation',str(calibration),'--out',str(out)])
    m.main()
    p,e=load_weight_artifact(out/'artifact.json',data)
    require_weight_artifact(dict(y_gate=arrays['y_gate'],rocket_context_probability=p),dict(rocket_context=e),2.)
    assert len(e['context_targets'])==6 and np.all((1+p>=1)&(1+p<=2))
    assert all(set(e[a+'_tags']).isdisjoint(e[b+'_tags']) for a,b in [('fit','tune'),('fit','test'),('tune','test')])
    p._mmap.close()
    probability=out/'probability.npy';probability.write_bytes(probability.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='provenance'):load_weight_artifact(out/'artifact.json',data)

def test_rejected_calibration_and_duplicate_event_refused(workspace_tmp,monkeypatch):
    tmp_path=workspace_tmp
    m,data,labels,calibration,rulings,arrays,tags,meta,events=fixture(tmp_path)
    with pytest.raises(ValueError,match='Duplicate label'):m.labels(arrays,tags,meta,events+[events[0]])
    with pytest.raises(ValueError,match='lack labels'):m.labels(arrays,tags,meta,events[1:])
    calibration.write_text(json.dumps(dict(status='STOP_TELL_LEAD')))
    monkeypatch.setattr(sys,'argv',['fit','--data',str(data),'--labels',str(labels),'--rulings',str(rulings),
        '--xbow-validation',str(calibration),'--out',str(tmp_path/'should-not-exist')])
    with pytest.raises(ValueError,match='lead gate'):m.main()
    assert not (tmp_path/'should-not-exist').exists()

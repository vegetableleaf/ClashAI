"""Qualified reader entry, explicitly selected by owner; current startup stays unchanged."""
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from adapter import adapt,extend_elite_names,extend_elite_forms
from pipeline.live_gen_v2 import GenPilot as ExistingPilot


class IdentityPilot(ExistingPilot):
    def observe(self,frame):
        return super().observe(adapt(frame))

    def row(self,frame):
        normalized=adapt(frame)
        batch,info=super().row(normalized)
        if getattr(self,'public_audit',False):
            fields=('side','x','y','card_id','hp','max_hp','kind','address','category',
                    'native_name','native_name_status','attached_owner','attached_owner_read_ok')
            self._public_audit_snapshot['raw_bodies']=[{k:e[k] for k in fields if k in e} for e in frame.get('entities',[])]
            self._public_audit_snapshot['character_identity']=dict(frame['character_identity'])
            self._public_audit_snapshot['excluded_public_objects']=[dict(role=x['role'],entity={k:x['entity'][k] for k in fields if k in x['entity']}) for x in normalized['excluded_public_objects']]
        return batch,info


def install_catalog():
    from pipeline import obs_contract as O
    names=O._catalog_names()
    O.catalog_card_form(26000043)
    forms=O.catalog_card_form.table
    O._CATALOG_NAMES=extend_elite_names(names)
    O.catalog_card_form.table=extend_elite_forms(forms)


def main():
    original=ROOT/'scratchpad/gauntlet/L68/live_reader/live_play.py'
    sys.path.insert(0,str(original.parent))
    spec=importlib.util.spec_from_file_location('live_identity_original_entry',original)
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    install_catalog()
    entry.GenPilot=IdentityPilot
    from pipeline import reader_config
    entry.READERS={'v3':reader_config.reader('v3')}   # local-only reader config
    if not any(x=='--reader' or x.startswith('--reader=') for x in sys.argv[1:]):
        sys.argv.extend(['--reader','v3'])
    print('[reader] isolated character identity entry; production startup unchanged',flush=True)
    return entry.main()

if __name__=='__main__':raise SystemExit(main())

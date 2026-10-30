SME-REBUILD 10-30 (pod 33903 /workspace/smeR): gate rebuilt from tracked tree 18f614a (sme/recon/rebuild_gate.sh),
run with sme/recon/runR.sh (= f1fix/runH.sh's env, lib 5e8089a4 tickprobe, tables 16.635.3 sha 1243a2df, SME_BANNER_GIVEN=1),
byte-identity runs with SME_HIDDEN_ASSIGN=0 (as the reference runs).
id4 = FRESH4 151109 vs F4_fe, id5 = FRESH5 021310 vs F5_main, id6 = FRESH6 031310 vs F6_main.
Result (sme/recon/idcmp.py): every one of the 24 shared result fields equal (counts, first_div, first_detail,
repair log, plants, torn, overfit, deal_check, ...); only cls_ticks differs (field added after the reference runs).
151109 2767 + 264 div first 925; 021310 1660 + 105 first 1986; 031310 2102 + 40 first 3954. Wall ~40-65 s per match.

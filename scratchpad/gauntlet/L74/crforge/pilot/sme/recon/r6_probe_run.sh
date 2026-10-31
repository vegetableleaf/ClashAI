# usage: probe_run.sh LISTFILE  (pod): each line "tag match me runs frames" -> baseline and --noopp
cd /workspace/smeR5
one() {
  tag=$1; m=$2; me=$3; runs=$4; fr=$5
  cp $runs/$m/recon_plan.json diag/${m}_plan.json
  for v in base noopp; do
    extra=""; [ $v = noopp ] && extra="--noopp"
    R=/workspace/smeR5 SME_THREADS=3 CPUS=226-237 bash sme/recon/envR.sh python3 recon/form_diag.py /workspace/smeR5/diag/${m}_plan.json $fr/$m.jsonl $me $extra --out /workspace/smeR5/diag/o_${m}_$v > diag/${m}_$v.txt 2>&1
  done
}
while read tag m me runs fr; do one $tag $m $me $runs $fr & while [ $(jobs -r | wc -l) -ge 3 ]; do sleep 2; done; done < $1
wait
echo PROBE_DONE > diag/PROBE_DONE

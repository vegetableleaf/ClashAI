#!/bin/bash
# NEW-vs-main test classification on the VM: pipeline/tests + L68/live_reader tests in ~/threat/t_new (this branch,
# threat.tar) and ~/threat/t_main (main 808f4f4, threat_main.tar), same environment, plain archives (no telemetry
# patch). One process per tree, nice, CPU only.   bash vm_tests.sh
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
for t in t_new t_main; do
  D=~/threat/$t; rm -rf $D; mkdir -p $D; cd $D
  tar xf ~/threat/$([ $t = t_new ] && echo threat.tar || echo threat_main.tar)
  mkdir -p scratchpad/gauntlet
  ln -s ~/ClashBot/icebow icebow; ln -s ~/ClashBot/research research
  for g in ~/ClashBot/scratchpad/*; do b=$(basename "$g"); [ -e "scratchpad/$b" ] || ln -s "$g" "scratchpad/$b"; done
  for g in ~/ClashBot/scratchpad/gauntlet/*; do b=$(basename "$g"); [ -e "scratchpad/gauntlet/$b" ] || ln -s "$g" "scratchpad/gauntlet/$b"; done
  for L in L74; do
    for g in ~/ClashBot/scratchpad/gauntlet/$L/*; do b=$(basename "$g"); [ -e "scratchpad/gauntlet/$L/$b" ] || ln -s "$g" "scratchpad/gauntlet/$L/$b"; done
  done
  find pipeline scratchpad/gauntlet/L74/threat -name "*.py" -type f -print0 2>/dev/null | xargs -0 sed -i 's/\r$//'
  nice timeout 5400 ~/venv/bin/python -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors \
    pipeline/tests scratchpad/gauntlet/L68/live_reader > ~/threat/pytest_$t.out 2>&1 &
done
wait
echo DONE >> ~/threat/pytest_t_new.out

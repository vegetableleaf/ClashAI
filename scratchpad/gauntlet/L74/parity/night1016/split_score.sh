# split_score.sh RUNDIR : score fully-captured matches (phase-3 capture exists) and the rest separately (never pool them)
R=$1; A=/c/Users/benpe/AppData/Local/Temp/claude/parity1016/attacks.json; P=/c/Users/benpe/ClashBot/research/ext/Royale/.venv/Scripts/python.exe
F=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/parity/fights.py
rm -rf $R/_cap $R/_old; mkdir -p $R/_cap/matches $R/_old/matches
caps=$($P -c "import json,sys; print(' '.join(k[:-6] for k in json.load(open(sys.argv[1]))))" $A)
for f in $R/matches/*.json; do s=$(basename $f .json); case " $caps " in *" $s "*) cp $f $R/_cap/matches/;; *) cp $f $R/_old/matches/;; esac; done
echo "captured $(ls $R/_cap/matches | wc -l)  old $(ls $R/_old/matches | wc -l)"
for d in _cap _old; do $P $F score --out $R/$d > $R/$d/score.out 2>&1; done

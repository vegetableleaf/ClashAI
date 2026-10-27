#!/usr/bin/env bash
# A2c-BP4: fork patch 0004 is instrumentation only: core tests, then SmeRun traces of every bp4R0 plan on lib_bp3 vs lib_bp4
cd /workspace/pilot/bp3/crforge && ./gradlew --offline :core:test > /workspace/pilot/bp4/coretest_bp4.log 2>&1; echo "gradle rc=$?" >> /workspace/pilot/bp4/coretest_bp4.log
python3 /workspace/pilot/bp2/junit_sum.py /workspace/pilot/bp3/crforge/core/build/test-results/test >> /workspace/pilot/bp4/coretest_bp4.log 2>&1
bash /workspace/pilot/bp3/tools/trace_ident.sh /workspace/pilot/sme_live/bp4R0 /workspace/pilot/bp3/lib_bp3 /workspace/pilot/bp4/lib_bp4 > /workspace/pilot/bp4/trace_ident_bp4.txt 2>&1
echo verify done >> /workspace/pilot/bp4/trace_ident_bp4.txt

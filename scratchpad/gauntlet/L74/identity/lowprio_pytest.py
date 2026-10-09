"""pytest at below-normal priority, GPU hidden, one BLAS thread (live play runs on this laptop).
  python lowprio_pytest.py <pytest args...>"""
import os, sys
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import pytest
sys.exit(pytest.main(sys.argv[1:]))

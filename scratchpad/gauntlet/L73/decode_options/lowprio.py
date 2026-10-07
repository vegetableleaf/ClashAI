"""Run a module or script at below-normal priority, CPU only, <=4 threads.
Usage: lowprio.py -m pytest ...   |   lowprio.py script.py args"""
import ctypes, os, runpy, sys
os.environ.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
if sys.argv[1] == '-m':
    sys.argv = sys.argv[2:]
    runpy.run_module(sys.argv[0], run_name='__main__', alter_sys=True)
else:
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name='__main__')

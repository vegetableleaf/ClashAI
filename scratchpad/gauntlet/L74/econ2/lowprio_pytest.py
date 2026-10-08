"""pytest at below-normal priority, single process (the laptop is shared with live play).  python lowprio_pytest.py <pytest args>"""
import sys
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import pytest

sys.exit(pytest.main(sys.argv[1:]))

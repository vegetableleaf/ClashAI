# LOOP-OPP test harness (not pipeline code), active only under LOOPOPP_CHECK=outdir in spawned actor processes (argv[0]
# '-c'): once pipeline.e1_eval is imported, opp_check installs the fast-loop opponent comparison on the actor path.
# Chains D2-T2's obs check (d2g/d2t2/hook) when D2T2_OBSCHECK is also set (its hook dir on PYTHONPATH after this one).
import os
import sys

if os.environ.get("LOOPOPP_CHECK") and sys.argv[:1] == ["-c"]:
    import importlib.abc
    import importlib.machinery

    class _After(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name != "pipeline.e1_eval":
                return None
            sys.meta_path.remove(self)
            spec = importlib.machinery.PathFinder.find_spec(name, path)
            run = spec.loader.exec_module

            def exec_module(mod):
                run(mod)
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                if os.environ.get("D2T2_OBSCHECK"):
                    import actor_obscheck
                    actor_obscheck.install(mod)
                import opp_check
                opp_check.install(mod)
            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _After())

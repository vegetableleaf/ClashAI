# LOOP-IW test harness (not pipeline code), active only under LIW_OUT=outdir in spawned actor processes (argv[0] '-c'):
# once pipeline.royale_env is imported, actor_abil installs the CfAbil comparison on the env's ability calls.
import os
import sys

if os.environ.get("LIW_OUT") and sys.argv[:1] == ["-c"]:
    import importlib.abc
    import importlib.machinery

    class _After(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name != "pipeline.royale_env":
                return None
            sys.meta_path.remove(self)
            spec = importlib.machinery.PathFinder.find_spec(name, path)
            run = spec.loader.exec_module

            def exec_module(mod):
                run(mod)
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import actor_abil
                actor_abil.install(mod)
            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _After())

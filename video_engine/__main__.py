import os
import sys
import importlib

repo_dir = os.path.dirname(__file__)
base_dir = os.path.dirname(repo_dir)
src_dir = os.path.join(base_dir, "src")

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Remove the current wrapper package so that importing 'video_engine' resolves to src package
try:
    if "video_engine" in sys.modules:
        del sys.modules["video_engine"]
except Exception:
    pass

if __name__ == "__main__":
    # If MoviePy is unavailable in this interpreter, try re-exec using a local venv Python.
    try:
        import moviepy  # type: ignore
    except Exception:
        # Try VIRTUAL_ENV first
        venv = os.environ.get("VIRTUAL_ENV")
        candidates = []
        if venv:
            candidates.append(os.path.join(venv, "Scripts", "python.exe"))
            candidates.append(os.path.join(venv, "bin", "python"))
        # Fallback: project-local .venv
        candidates.append(os.path.join(base_dir, ".venv", "Scripts", "python.exe"))
        candidates.append(os.path.join(base_dir, ".venv", "bin", "python"))

        for py in candidates:
            if py and os.path.isfile(py):
                # Re-exec with the same module and args under venv python
                args = [py, "-m", "video_engine"] + sys.argv[1:]
                os.execv(py, args)
                break
        # If no candidate found, continue and let import fail inside CLI

    mod = importlib.import_module("video_engine.cli")
    raise SystemExit(mod.main())

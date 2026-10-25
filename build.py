"""Builds every lesson, or only those whose file name contains the first argument:

    python build.py              all of them
    python build.py hello        1.1 hello_window and 2.1 hello_triangle

Each lesson is one .rasm file that imports everything it needs (a unity
build), so building it is one `rin asm`: it writes build/rasm/<name>.s (the
code) and build/rasm/<name>_data.c (the data and its types), assembles and
compiles them with clang and links build/<name>.exe with its .pdb.

The assembler is `rin asm`, inside the rin compiler: RIN names it, or else
C:\\devel\\rin\\build\\rin.exe, or else `rin` on PATH. Anything the build prints
besides its "built" line counts as a warning, and fails the build.
"""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
LIBS = ["d3d11", "d3dcompiler", "dxguid", "ole32", "windowscodecs"]   # kernel32 and user32 always


def find_rin():
    if os.environ.get("RIN"):
        return os.environ["RIN"]
    default = pathlib.Path(r"C:\devel\rin\build\rin.exe")
    if default.exists():
        return str(default)
    found = shutil.which("rin")
    if not found:
        sys.exit("build.py: no rin compiler: set RIN to rin.exe, or put it on PATH")
    return found


def main():
    rin = find_rin()
    pattern = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    lessons = sorted((ROOT / "src").rglob("*.rasm"))
    failed = []
    for src in lessons:
        if pattern not in src.stem.lower():
            continue
        exe = ROOT / "build" / f"{src.stem}.exe"
        cmd = [rin, "asm", str(src.relative_to(ROOT)), "-o", str(exe.relative_to(ROOT))]
        for lib in LIBS:
            cmd += ["-l", lib]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not l.startswith("rin asm: built")]
        if r.returncode != 0 or out:
            failed.append(src.stem)
            print(f"{src.stem}: FAILED" if r.returncode else f"{src.stem}: warnings")
            for line in out:
                print("    " + line)
        else:
            print(src.stem)
    if failed:
        print(f"{len(failed)} failed: {' '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

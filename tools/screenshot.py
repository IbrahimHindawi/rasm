"""Pictures of the built lessons, for checking them unattended.

    python tools/screenshot.py                       every lesson in build/
    python tools/screenshot.py camera textures       those whose names contain one of these
    python tools/screenshot.py lighting:2@0.5        mode 2 at 0.5 seconds

A lesson from 3.1 on is run as `lesson.exe --shot shots/<name>.png [--time t]
[--mode n]` (includes/learn/window.rasm): it renders with the clock stopped,
saves its backbuffer and exits, with the window hidden. 1.1 and 2.1 write
their window out by hand and take no --shot, as in masm64-dx11, so they are
launched, given a moment, and captured from outside with PrintWindow, which
needs Pillow. name[:mode][@seconds]; a mode tags the picture shots/<name>_<mode>.png.
"""
import ctypes
import ctypes.wintypes as wt
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
OUT = ROOT / "shots"
BY_HAND = {"hello_window", "hello_triangle"}   # no --shot of their own


def capture_window(name, wait):
    from PIL import Image
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.SetProcessDPIAware()
    proc = subprocess.Popen([str(BUILD / f"{name}.exe")], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    enum_proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def find_window():
        found = []

        def cb(hwnd, _):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True
        user32.EnumWindows(enum_proc(cb), 0)
        return found[0] if found else None

    hwnd, deadline = None, time.time() + 30
    while hwnd is None and time.time() < deadline and proc.poll() is None:
        time.sleep(0.1)
        hwnd = find_window()
    if hwnd is None:
        proc.kill()
        return "no window"
    time.sleep(wait)
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right, rect.bottom
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 3)           # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    header = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, header, 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(OUT / f"{name}.png")
    user32.PostMessageW(hwnd, 0x10, 0, 0)      # WM_CLOSE
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
    return None


def shoot(spec):
    name, mode, at = spec, None, None
    if "@" in name:
        name, at = name.split("@")
    if ":" in name:
        name, mode = name.split(":")
    if not (BUILD / f"{name}.exe").exists():
        return f"{name}: not built"
    if name in BY_HAND:
        err = capture_window(name, float(at) if at else 1.5)
        return f"{name}: {err}" if err else None
    tag = name + (f"_{mode}" if mode is not None else "")
    cmd = [str(BUILD / f"{name}.exe"), "--shot", str(OUT / f"{tag}.png")]
    if at:
        cmd += ["--time", at]
    if mode is not None:
        cmd += ["--mode", mode]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return f"{tag}: exit {r.returncode} {r.stdout.strip()[:300]}"
    return None


def main():
    OUT.mkdir(exist_ok=True)
    built = [p.stem for p in sorted(BUILD.glob("*.exe"))]
    args = sys.argv[1:]
    if not args:
        specs = built
    else:
        specs = []
        for a in args:
            base = a.split(":")[0].split("@")[0]
            if base in built:
                specs.append(a)
            else:
                specs += [n + a[len(base):] for n in built if base in n]
    failed = 0
    for spec in specs:
        err = shoot(spec)
        print(f"FAIL {err}" if err else f"ok   {spec}")
        failed += err is not None
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

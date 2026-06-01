#!/usr/bin/env python3
"""
web-snap — capturas de pantalla de URLs web en Windows usando Chrome + Pillow.

Sin Selenium, Playwright ni ChromeDriver. Solo subprocess + Win32 API + PIL.

Uso:
    python web_snap.py <filename> <url> [--wait SECONDS] [--out DIR] [--browser chrome|edge]
    python web_snap.py --batch <jsonfile> [--out DIR]
    python web_snap.py --list                # lista capturas en --out

Ejemplo single:
    python web_snap.py 01-dashboard.png "https://console.aws.amazon.com/" --wait 8

Ejemplo batch (jobs.json):
    [
      {"file": "01-cluster.png", "url": "https://...", "wait": 8},
      {"file": "02-tasks.png",   "url": "https://...", "wait": 6}
    ]
    python web_snap.py --batch jobs.json --out ./img

Requisitos:
    pip install pillow

Limitaciones:
    - Solo Windows con sesion interactiva (necesita acceso al frame buffer y a user32.dll).
    - Captura toda la pantalla — incluye la barra de tareas. Maximizar Chrome ayuda.
    - El --wait es heuristico; si la pagina tarda mas, sale a medio renderizar.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from PIL import ImageGrab
except ImportError:
    sys.exit("ERROR: requiere Pillow. Instala con: pip install pillow")

# -------------------------------------------------------------------- browsers

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

_BROWSER_TITLE_SUFFIX = {
    "chrome": "Google Chrome",
    "edge": "- Microsoft​Edge",  # Edge usa a veces un caracter invisible
}


def find_browser(name: str) -> str:
    candidates = _CHROME_CANDIDATES if name == "chrome" else _EDGE_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            return path
    sys.exit(f"ERROR: no se encontro {name}. Rutas probadas: {candidates}")


# -------------------------------------------------------------------- win32

def _get_user32():
    if not sys.platform.startswith("win"):
        sys.exit("ERROR: web-snap solo funciona en Windows (requiere user32.dll).")
    return ctypes.windll.user32


def _activate_window(title_suffix: str) -> bool:
    """Trae al frente la primera ventana visible cuyo titulo termine en title_suffix.

    Usa SetWindowPos con HWND_TOPMOST -> NOTOPMOST para forzar foreground en Win11.
    """
    user32 = _get_user32()
    wndenumproc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    found: list[int] = []

    def cb(hwnd: int, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value.strip().lower()
            if title.endswith(title_suffix.strip().lower()):
                found.append(hwnd)
        return True

    user32.EnumWindows(wndenumproc(cb), 0)
    if not found:
        return False

    hwnd = found[0]
    SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040
    HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
    SW_RESTORE = 9

    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)
    return True


# -------------------------------------------------------------------- core

def snap(filename: str, url: str, *, wait: int = 6, out_dir: Path,
         browser: str = "chrome") -> Path:
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    browser_exe = find_browser(browser)
    title_suffix = _BROWSER_TITLE_SUFFIX[browser]

    print(f"==> {filename}")
    print(f"    URL: {url}")
    subprocess.Popen([browser_exe, "--new-tab", url])
    time.sleep(wait)

    if not _activate_window(title_suffix):
        print(f"    !! No se pudo activar ventana de {browser}; capturando lo que haya en pantalla")

    img = ImageGrab.grab()
    img.save(out_path, "PNG")
    size_bytes = out_path.stat().st_size
    print(f"    Saved: {out_path}  ({size_bytes} bytes, {img.size})")
    return out_path


def snap_batch(jobs: list[dict], *, out_dir: Path, browser: str = "chrome") -> list[Path]:
    results: list[Path] = []
    for job in jobs:
        file = job["file"]
        url = job["url"]
        wait = int(job.get("wait", 6))
        try:
            results.append(snap(file, url, wait=wait, out_dir=out_dir, browser=browser))
        except Exception as e:
            print(f"    !! ERROR en {file}: {e}")
    print(f"\nBatch completo: {len(results)}/{len(jobs)} capturas en {out_dir}")
    return results


# -------------------------------------------------------------------- CLI

def main() -> int:
    p = argparse.ArgumentParser(
        prog="web-snap",
        description="Capturas de pantalla de URLs en Windows (Chrome/Edge + Pillow).",
    )
    p.add_argument("filename", nargs="?", help="Nombre de archivo PNG (modo single)")
    p.add_argument("url", nargs="?", help="URL a capturar (modo single)")
    p.add_argument("--wait", type=int, default=6,
                   help="Segundos de espera antes de capturar (default 6)")
    p.add_argument("--out", type=Path, default=Path.cwd() / "img",
                   help="Directorio de salida (default ./img)")
    p.add_argument("--browser", choices=("chrome", "edge"), default="chrome",
                   help="Browser a usar (default chrome)")
    p.add_argument("--batch", type=Path, metavar="JSONFILE",
                   help="Modo batch: ejecuta lista de jobs desde JSON")
    p.add_argument("--list", action="store_true",
                   help="Lista PNGs en --out y sale")
    args = p.parse_args()

    if args.list:
        out = args.out.resolve()
        if not out.exists():
            print(f"(directorio no existe: {out})")
            return 0
        pngs = sorted(out.glob("*.png"))
        if not pngs:
            print(f"(sin PNGs en {out})")
            return 0
        for p_ in pngs:
            kb = p_.stat().st_size // 1024
            print(f"  {p_.name:50s} {kb:>6d} KB")
        return 0

    if args.batch:
        if not args.batch.exists():
            sys.exit(f"ERROR: no existe {args.batch}")
        jobs = json.loads(args.batch.read_text(encoding="utf-8"))
        if not isinstance(jobs, list):
            sys.exit("ERROR: el JSON debe ser una lista de objetos {file,url,wait?}")
        snap_batch(jobs, out_dir=args.out, browser=args.browser)
        return 0

    if not args.filename or not args.url:
        p.print_help()
        sys.exit("\nERROR: en modo single requiere <filename> y <url>")

    snap(args.filename, args.url, wait=args.wait, out_dir=args.out, browser=args.browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
nombre-del-skill — Una frase de propósito.

Uso:
  python main.py [--flag]

Trabaja siempre desde Path.cwd().
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

REPO = Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description="nombre-del-skill")
    parser.add_argument("--flag", action="store_true", help="...")
    args = parser.parse_args()

    print(f"Trabajando en: {REPO}")
    # ... lógica ...
    return 0


if __name__ == "__main__":
    sys.exit(main())

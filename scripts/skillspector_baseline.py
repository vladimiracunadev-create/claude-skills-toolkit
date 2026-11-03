#!/usr/bin/env python3
"""
Genera el baseline de SkillSpector de cada skill con la razón del triaje.

`skillspector baseline` sólo acepta un `--reason` único para todo el fichero.
Aquí se genera el baseline por skill y luego se reescribe la razón de cada
huella según la regla que la disparó, leyendo los veredictos de
`docs/security/skillspector-triage.yaml`.

La huella (`hash`) la calcula el scanner y se conserva tal cual: este script no
inventa supresiones, sólo las etiqueta.

Guard: si el scanner dispara una regla que no figura en el triaje, el script
falla. Un hallazgo de una clase nueva no se puede suprimir sin que alguien
escriba antes su veredicto.

Uso:
    python scripts/skillspector_baseline.py            # escribe los baselines
    python scripts/skillspector_baseline.py --check     # sólo verifica el triaje
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skillspector_scan import (  # noqa: E402
    BASELINE_DIR,
    SECURITY_DIR,
    discover_skills,
    find_binary,
    scanner_version,
)

TRIAGE_FILE = SECURITY_DIR / "skillspector-triage.yaml"


def load_triage() -> dict[str, dict]:
    if not TRIAGE_FILE.is_file():
        sys.exit(f"falta el triaje: {TRIAGE_FILE}")
    data = yaml.safe_load(TRIAGE_FILE.read_text(encoding="utf-8")) or {}
    rules = data.get("rules") or {}
    if not rules:
        sys.exit(f"{TRIAGE_FILE} no declara ninguna regla")
    return rules


def generate(binary: str, skill: Path) -> dict | None:
    proc = subprocess.run(
        [binary, "baseline", str(skill), "--no-llm", "--output", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(
            f"  ! {skill.name}: el scanner no devolvió baseline "
            f"({(proc.stderr or proc.stdout or '').strip()[:160]})"
        )
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Baselines de SkillSpector con triaje.")
    ap.add_argument(
        "--check",
        action="store_true",
        help="no escribe: sólo comprueba que toda regla disparada esté triada",
    )
    args = ap.parse_args()

    triage = load_triage()
    binary = find_binary()
    version = scanner_version(binary)
    skills = discover_skills()

    untriaged: dict[str, set[str]] = {}
    written: list[str] = []
    empty: list[str] = []

    for n, skill in enumerate(skills, 1):
        print(f"[{n}/{len(skills)}] {skill.name}", flush=True)
        baseline = generate(binary, skill)
        if baseline is None:
            return 2
        fingerprints = baseline.get("fingerprints") or []
        if not fingerprints:
            empty.append(skill.name)
            target = BASELINE_DIR / f"{skill.name}.yaml"
            if not args.check and target.exists():
                # El skill dejó de disparar hallazgos: el baseline sobra y
                # mantenerlo escondería un hallazgo futuro de esa misma clase.
                target.unlink()
                print(f"  - baseline eliminado (sin hallazgos): {target.name}")
            continue
        for fp in fingerprints:
            rule_id = fp.get("rule_id")
            rule = triage.get(rule_id)
            if not rule:
                untriaged.setdefault(rule_id or "(sin id)", set()).add(skill.name)
                continue
            fp["reason"] = f"[{rule['verdict']}] {' '.join(rule['reason'].split())}"
        if not args.check:
            BASELINE_DIR.mkdir(parents=True, exist_ok=True)
            target = BASELINE_DIR / f"{skill.name}.yaml"
            header = (
                f"# Baseline de SkillSpector para el skill `{skill.name}`.\n"
                f"# Generado por scripts/skillspector_baseline.py con "
                f"SkillSpector v{version}.\n"
                "# Las razones vienen de docs/security/skillspector-triage.yaml;\n"
                "# no editar a mano: edita el triaje y regenera.\n"
            )
            target.write_text(
                header + yaml.safe_dump(baseline, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            written.append(skill.name)

    print()
    if untriaged:
        print("FALLO: reglas disparadas sin veredicto en el triaje:")
        for rule_id, skill_names in sorted(untriaged.items()):
            print(f"  - {rule_id}: {', '.join(sorted(skill_names))}")
        print(f"\nAñade su veredicto en {TRIAGE_FILE.name} y vuelve a correr.")
        return 1

    if args.check:
        print("OK: toda regla disparada tiene veredicto en el triaje.")
        return 0

    print(f"OK: {len(written)} baseline(s) escritos en "
          f"{BASELINE_DIR.relative_to(SECURITY_DIR.parent.parent).as_posix()}/")
    if empty:
        print(f"Sin hallazgos (sin baseline): {', '.join(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

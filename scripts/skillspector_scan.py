#!/usr/bin/env python3
"""
Escanea cada skill del toolkit con SkillSpector y agrega los resultados.

Por qué skill por skill y no `skillspector scan skills/ --recursive`: el modo
recursivo choca con el límite de runtime del propio scanner y entrega cobertura
parcial (~70%). Una invocación por skill da cobertura 100% en cada una, permite
baseline por skill y deja el gate por skill en vez de un único máximo global.

Salidas:
  - Informe Markdown fechado en docs/security/
  - Resumen JSON estable en docs/security/skillspector-latest.json
    (lo consume el test de coherencia del badge del README)

Uso:
    python scripts/skillspector_scan.py                 # scan + informe
    python scripts/skillspector_scan.py --check         # no escribe, solo gate
    python scripts/skillspector_scan.py --max-score 50  # umbral del gate
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
SECURITY_DIR = REPO / "docs" / "security"
BASELINE_DIR = SECURITY_DIR / "skillspector-baselines"
SUMMARY_JSON = SECURITY_DIR / "skillspector-latest.json"

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def find_binary() -> str:
    for name in ("skillspector", "skillspector.exe"):
        found = shutil.which(name)
        if found:
            return found
    env = os.environ.get("SKILLSPECTOR_BIN")
    if env and Path(env).exists():
        return env
    sys.exit(
        "skillspector no está en PATH. Instálalo con:\n"
        "  pip install git+https://github.com/vladimiracunadev-create/SkillSpector.git\n"
        "o exporta SKILLSPECTOR_BIN con la ruta al binario."
    )


def scanner_version(binary: str) -> str:
    try:
        out = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "desconocida"
    return out.split()[-1].lstrip("v") if out else "desconocida"


def discover_skills() -> list[Path]:
    return sorted(
        p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    )


def scan_one(binary: str, skill: Path, use_llm: bool, raw_dir: Path | None = None) -> dict:
    cmd = [binary, "scan", str(skill), "--format", "json"]
    if not use_llm:
        cmd.append("--no-llm")
    baseline = BASELINE_DIR / f"{skill.name}.yaml"
    if baseline.is_file():
        cmd += ["--baseline", str(baseline)]
    # El scanner rechaza --output en Windows ("safe file output unsupported"),
    # así que el JSON se recoge por stdout en vez de por fichero.
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "name": skill.name,
            "error": (proc.stderr or proc.stdout or "sin salida").strip()[:500],
        }
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{skill.name}.json").write_text(proc.stdout, encoding="utf-8")
    risk = data.get("risk_assessment") or {}
    completeness = data.get("analysis_completeness") or {}
    issues = data.get("issues") or []
    by_severity: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for issue in issues:
        sev = (issue.get("severity") or "LOW").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "name": skill.name,
        "score": risk.get("score"),
        "severity": risk.get("severity"),
        "recommendation": risk.get("recommendation"),
        "findings": len(issues),
        "by_severity": by_severity,
        "suppressed": data.get("suppressed_count", 0),
        "coverage_percent": completeness.get("coverage_percent"),
        "coverage_status": completeness.get("status"),
        "execution_successful": data.get("execution_successful", False),
        "baseline": baseline.name if baseline.is_file() else None,
        "issues": [
            {
                "rule_id": i.get("id"),
                "severity": i.get("severity"),
                "category": i.get("category"),
                "pattern": i.get("pattern"),
                "confidence": i.get("confidence"),
                "explanation": i.get("explanation"),
                "file": (i.get("location") or {}).get("file"),
                "line": (i.get("location") or {}).get("start_line"),
                "column": (i.get("location") or {}).get("start_column"),
            }
            for i in issues
        ],
    }


# Severidad SARIF: `error` rompe el code scanning, `warning` lo deja como aviso.
SARIF_LEVEL = {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning", "LOW": "note"}
SARIF_SECURITY_SEVERITY = {"CRITICAL": "9.0", "HIGH": "7.5", "MEDIUM": "5.5", "LOW": "3.0"}


def render_sarif(results: list[dict], version: str) -> dict:
    """Un único run SARIF con los hallazgos de todos los skills.

    Se sintetiza del JSON en vez de pedirle `--format sarif` al scanner por
    skill: así basta una pasada, y las rutas quedan relativas al repo
    (`skills/<skill>/SKILL.md`) en lugar de relativas a cada skill, que es lo
    que el code scanning de GitHub necesita para anclar la anotación. Además
    GitHub acepta como máximo 20 runs por envío y aquí hay 22 skills.
    """
    rules: dict[str, dict] = {}
    sarif_results = []
    for r in results:
        if "error" in r:
            continue
        for i in r["issues"]:
            rule_id = i["rule_id"] or f"{i['category']}/{i['pattern']}"
            sev = (i["severity"] or "LOW").upper()
            rules.setdefault(
                rule_id,
                {
                    "id": rule_id,
                    "shortDescription": {"text": i["pattern"] or rule_id},
                    "fullDescription": {"text": i["explanation"] or i["pattern"] or ""},
                    "properties": {
                        "security-severity": SARIF_SECURITY_SEVERITY.get(sev, "3.0"),
                        "tags": [i["category"]] if i["category"] else [],
                    },
                },
            )
            uri = f"skills/{r['name']}/{i['file']}" if i["file"] else f"skills/{r['name']}/"
            region = {}
            if i["line"]:
                region["startLine"] = i["line"]
                region["startColumn"] = max(1, (i["column"] or 0) + 1)
            location = {"physicalLocation": {"artifactLocation": {"uri": uri}}}
            if region:
                location["physicalLocation"]["region"] = region
            sarif_results.append(
                {
                    "ruleId": rule_id,
                    "level": SARIF_LEVEL.get(sev, "note"),
                    "message": {
                        "text": f"[{r['name']}] {i['category']} · {i['pattern']}"
                    },
                    "locations": [location],
                    "properties": {
                        "skill": r["name"],
                        "severity": sev,
                        "confidence": i["confidence"],
                    },
                }
            )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skillspector",
                        "version": version,
                        "informationUri": "https://github.com/vladimiracunadev-create/SkillSpector",
                        "rules": list(rules.values()),
                    }
                },
                "automationDetails": {"id": "skillspector/skills/"},
                "columnKind": "unicodeCodePoints",
                "results": sarif_results,
            }
        ],
    }


def render_markdown(results: list[dict], version: str, stamp: str, max_score: int) -> str:
    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]
    active = sum(r["findings"] for r in ok)
    suppressed = sum(r["suppressed"] for r in ok)
    gated = [r for r in ok if (r["score"] or 0) > max_score]
    min_cov = min((r["coverage_percent"] or 0) for r in ok) if ok else 0

    lines = [
        f"# Escaneo de skills — SkillSpector — {stamp}",
        "",
        f"Generado por `scripts/skillspector_scan.py` sobre **SkillSpector v{version}** "
        "([fork](https://github.com/vladimiracunadev-create/SkillSpector) de "
        "[NVIDIA/skillspector](https://github.com/NVIDIA/skillspector)), capa estática "
        "(`--no-llm`): patrones de prompt injection, exfiltración, supply chain, "
        "escalada de privilegios y abuso de herramientas, más reglas YARA y taint "
        "tracking.",
        "",
        "## Qué afirma este informe y qué no",
        "",
        "Afirma que cada skill del toolkit pasó por el scanner y que los hallazgos "
        "activos son los que se listan abajo. **No es un certificado de calidad ni de "
        "ausencia de bugs**: dice que no aparecen los patrones que el scanner conoce, "
        "con la cobertura declarada en la tabla.",
        "",
        "Los hallazgos suprimidos viven en `docs/security/skillspector-baselines/` "
        "con su veredicto, uno por skill, y su análisis **caso a caso** en "
        "[`skillspector-hallazgos.md`](skillspector-hallazgos.md): qué disparó cada "
        "regla, cómo se resolvería y por qué el skill cumple igual. Un baseline no "
        "borra el hallazgo: lo deja fuera del score y documentado.",
        "",
        "## Resumen",
        "",
        f"- **Skills escaneados:** {len(ok)} de {len(results)}",
        f"- **Scanner:** SkillSpector v{version}, capa estática (sin LLM)",
        f"- **Hallazgos activos:** {active}",
        f"- **Hallazgos suprimidos con justificación:** {suppressed}",
        f"- **Cobertura mínima observada:** {min_cov:.1f}%",
        f"- **Skills sobre el umbral de score {max_score}:** {len(gated)}"
        + (f" — {', '.join(r['name'] for r in gated)}" if gated else ""),
        "",
        "## Resultado por skill",
        "",
        "| Skill | Score | Severidad | Recomendación | Activos | Suprimidos | Cobertura |",
        "|---|--:|:-:|:-:|--:|--:|--:|",
    ]
    for r in sorted(ok, key=lambda x: (-(x["score"] or 0), x["name"])):
        lines.append(
            f"| `{r['name']}` | {r['score']} | {r['severity']} | {r['recommendation']} "
            f"| {r['findings']} | {r['suppressed']} | {r['coverage_percent']}% |"
        )

    if errs:
        lines += ["", "## Skills no escaneados", ""]
        for r in errs:
            lines.append(f"- `{r['name']}` — {r['error']}")

    detail = [r for r in ok if r["findings"]]
    if detail:
        lines += ["", "## Hallazgos activos", ""]
        for r in sorted(detail, key=lambda x: x["name"]):
            lines += [f"### `{r['name']}` — score {r['score']} ({r['severity']})", ""]
            for i in r["issues"]:
                loc = f"{i['file']}:{i['line']}" if i["file"] else "—"
                lines.append(
                    f"- `{i['severity']}` · **{i['category']}** · {i['pattern']} — `{loc}`"
                )
            lines.append("")

    lines += [
        "## Cómo reproducir",
        "",
        "```bash",
        "pip install git+https://github.com/vladimiracunadev-create/SkillSpector.git",
        "python scripts/skillspector_scan.py",
        "```",
        "",
        "El job `Skill scan` del CI lo corre en cada push sobre un checkout limpio.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Escaneo de skills con SkillSpector.")
    ap.add_argument("--max-score", type=int, default=50, help="umbral del gate por skill")
    ap.add_argument(
        "--llm",
        action="store_true",
        help="habilita la capa LLM (envía el contenido de los skills al proveedor)",
    )
    ap.add_argument(
        "--check", action="store_true", help="no escribe informes, solo evalúa el gate"
    )
    ap.add_argument(
        "--sarif",
        metavar="PATH",
        help="escribe un SARIF 2.1.0 unificado (para el code scanning de GitHub)",
    )
    ap.add_argument(
        "--raw-dir",
        metavar="PATH",
        help="guarda el JSON crudo del scanner por skill (para triar hallazgos)",
    )
    args = ap.parse_args()

    binary = find_binary()
    version = scanner_version(binary)
    skills = discover_skills()
    if not skills:
        sys.exit(f"no se encontraron skills con SKILL.md en {SKILLS_DIR}")

    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    results = []
    for n, skill in enumerate(skills, 1):
        print(f"[{n}/{len(skills)}] {skill.name}", flush=True)
        results.append(scan_one(binary, skill, args.llm, raw_dir))

    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]
    gated = [r for r in ok if (r["score"] or 0) > args.max_score]

    print()
    print(f"{'Skill':<34}{'Score':>6} {'Severidad':<10}{'Activos':>8}{'Cobertura':>11}")
    print("-" * 70)
    for r in sorted(ok, key=lambda x: (-(x["score"] or 0), x["name"])):
        print(
            f"{r['name']:<34}{r['score']:>6} {r['severity']:<10}"
            f"{r['findings']:>8}{str(r['coverage_percent']) + '%':>11}"
        )
    for r in errs:
        print(f"{r['name']:<34} ERROR: {r['error'][:60]}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = {
        "generated_at": stamp,
        "scanner": "SkillSpector",
        "scanner_version": version,
        "llm_layer": args.llm,
        "max_score_gate": args.max_score,
        "skills_total": len(results),
        "skills_scanned": len(ok),
        "skills_over_gate": [r["name"] for r in gated],
        "active_findings": sum(r["findings"] for r in ok),
        "suppressed_findings": sum(r["suppressed"] for r in ok),
        "max_score": max((r["score"] or 0) for r in ok) if ok else None,
        "min_coverage_percent": min((r["coverage_percent"] or 0) for r in ok) if ok else None,
        "skills": [{k: v for k, v in r.items() if k != "issues"} for r in results],
    }

    if args.sarif:
        sarif_path = Path(args.sarif)
        sarif_path.parent.mkdir(parents=True, exist_ok=True)
        sarif_path.write_text(
            json.dumps(render_sarif(results, version), indent=1) + "\n", encoding="utf-8"
        )
        print(f"\nSARIF: {sarif_path.as_posix()}")

    if not args.check:
        SECURITY_DIR.mkdir(parents=True, exist_ok=True)
        report = SECURITY_DIR / f"SKILLSPECTOR_{datetime.now(timezone.utc):%Y-%m-%d}.md"
        report.write_text(
            render_markdown(results, version, stamp, args.max_score), encoding="utf-8"
        )
        SUMMARY_JSON.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nInforme: {report.relative_to(REPO).as_posix()}")
        print(f"Resumen: {SUMMARY_JSON.relative_to(REPO).as_posix()}")

    if errs:
        print(f"\nFALLO: {len(errs)} skill(s) no se pudieron escanear.")
        return 2
    if gated:
        print(f"\nFALLO: score > {args.max_score} en: {', '.join(r['name'] for r in gated)}")
        return 1
    print(f"\nOK: {len(ok)} skills escaneados, ninguno sobre el umbral {args.max_score}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Escaneo de skills — SkillSpector — 2026-11-03 03:34 UTC

Generado por `scripts/skillspector_scan.py` sobre **SkillSpector v2.12.0** ([fork](https://github.com/vladimiracunadev-create/SkillSpector) de [NVIDIA/skillspector](https://github.com/NVIDIA/skillspector)), capa estática (`--no-llm`): patrones de prompt injection, exfiltración, supply chain, escalada de privilegios y abuso de herramientas, más reglas YARA y taint tracking.

## Qué afirma este informe y qué no

Afirma que cada skill del toolkit pasó por el scanner y que los hallazgos activos son los que se listan abajo. **No es un certificado de calidad ni de ausencia de bugs**: dice que no aparecen los patrones que el scanner conoce, con la cobertura declarada en la tabla.

Los hallazgos suprimidos viven en `docs/security/skillspector-baselines/` con su veredicto, uno por skill, y su análisis **caso a caso** en [`skillspector-hallazgos.md`](skillspector-hallazgos.md): qué disparó cada regla, cómo se resolvería y por qué el skill cumple igual. Un baseline no borra el hallazgo: lo deja fuera del score y documentado.

## Resumen

- **Skills escaneados:** 23 de 23
- **Scanner:** SkillSpector v2.12.0, capa estática (sin LLM)
- **Hallazgos activos:** 0
- **Hallazgos suprimidos con justificación:** 93
- **Cobertura mínima observada:** 33.3%
- **Skills sobre el umbral de score 50:** 0

## Resultado por skill

| Skill | Score | Severidad | Recomendación | Activos | Suprimidos | Cobertura |
|---|--:|:-:|:-:|--:|--:|--:|
| `_template` | 0 | LOW | CAUTION | 0 | 1 | 66.7% |
| `bitcoin-custody-audit` | 0 | LOW | CAUTION | 0 | 6 | 66.7% |
| `clone-repo` | 0 | LOW | CAUTION | 0 | 1 | 50.0% |
| `docker-cleanup` | 0 | LOW | SAFE | 0 | 4 | 100.0% |
| `docker-compose-doctor` | 0 | LOW | CAUTION | 0 | 2 | 33.3% |
| `functional-user-flow-tester` | 0 | LOW | SAFE | 0 | 1 | 100.0% |
| `git-push` | 0 | LOW | SAFE | 0 | 5 | 100.0% |
| `md-lint-fix` | 0 | LOW | SAFE | 0 | 5 | 100.0% |
| `md-to-doc` | 0 | LOW | CAUTION | 0 | 3 | 66.7% |
| `pre-commit-guard` | 0 | LOW | CAUTION | 0 | 11 | 33.3% |
| `pre-push-guard` | 0 | LOW | CAUTION | 0 | 9 | 33.3% |
| `preliminary-product-tester` | 0 | LOW | CAUTION | 0 | 1 | 50.0% |
| `python-deps-pinning` | 0 | LOW | CAUTION | 0 | 1 | 33.3% |
| `python-lint-guard` | 0 | LOW | CAUTION | 0 | 2 | 66.7% |
| `python-version-control` | 0 | LOW | CAUTION | 0 | 3 | 33.3% |
| `release-evidence-auditor` | 0 | LOW | SAFE | 0 | 1 | 100.0% |
| `repo-coherence-audit` | 0 | LOW | CAUTION | 0 | 3 | 75.0% |
| `security-audit` | 0 | LOW | CAUTION | 0 | 21 | 66.7% |
| `software-resilience-state-tester` | 0 | LOW | SAFE | 0 | 1 | 100.0% |
| `sync-fork` | 0 | LOW | CAUTION | 0 | 1 | 50.0% |
| `version-bump` | 0 | LOW | SAFE | 0 | 3 | 100.0% |
| `web-snap` | 0 | LOW | SAFE | 0 | 3 | 100.0% |
| `yaml-control` | 0 | LOW | SAFE | 0 | 5 | 100.0% |
## Cómo reproducir

```bash
pip install git+https://github.com/vladimiracunadev-create/SkillSpector.git
python scripts/skillspector_scan.py
```

El job `Skill scan` del CI lo corre en cada push sobre un checkout limpio.

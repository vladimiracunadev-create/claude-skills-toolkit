"""
Coherencia entre el escaneo de SkillSpector y lo que el repo AFIRMA en el README.

El badge del README es una afirmación verificable: si dice "23/23 escaneados",
el resumen del último scan tiene que decir lo mismo, y los skills escaneados
tienen que ser los que existen en disco. Sin este test el badge se queda stale
en cuanto se añade un skill — exactamente el drift que `repo-coherence-audit`
persigue en los repos de los demás.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
SUMMARY = REPO / "docs" / "security" / "skillspector-latest.json"
SKILLS_DIR = REPO / "skills"

REQUIRED_KEYS = {
    "generated_at",
    "scanner",
    "scanner_version",
    "llm_layer",
    "max_score_gate",
    "skills_total",
    "skills_scanned",
    "skills_over_gate",
    "active_findings",
    "suppressed_findings",
    "max_score",
    "min_coverage_percent",
    "skills",
}

# El badge del README: .../badge/SkillSpector-<escaneados>%2F<total>%20escaneados-...
BADGE_RE = re.compile(r"SkillSpector-(\d+)%2F(\d+)%20skills%20escaneados")


def load_summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def skills_on_disk() -> set[str]:
    return {
        p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    }


class TestSkillSpectorSummary(unittest.TestCase):
    def test_summary_exists(self):
        self.assertTrue(
            SUMMARY.is_file(),
            f"{SUMMARY.relative_to(REPO).as_posix()} no existe — corre "
            "`python scripts/skillspector_scan.py`",
        )

    def test_summary_has_required_keys(self):
        data = load_summary()
        missing = REQUIRED_KEYS - set(data)
        self.assertEqual(set(), missing, f"faltan claves en el resumen: {sorted(missing)}")

    def test_every_skill_on_disk_was_scanned(self):
        data = load_summary()
        scanned = {s["name"] for s in data["skills"]}
        on_disk = skills_on_disk()
        self.assertEqual(
            on_disk,
            scanned,
            "el resumen no cubre los mismos skills que hay en disco; "
            f"sin escanear: {sorted(on_disk - scanned)} · "
            f"sobran en el resumen: {sorted(scanned - on_disk)}",
        )

    def test_counts_match_the_skill_list(self):
        data = load_summary()
        self.assertEqual(len(data["skills"]), data["skills_total"])
        self.assertEqual(
            data["skills_scanned"],
            sum(1 for s in data["skills"] if "error" not in s),
            "skills_scanned no coincide con los skills sin error",
        )

    def test_no_skill_was_left_unscanned(self):
        data = load_summary()
        failed = [s["name"] for s in data["skills"] if "error" in s]
        self.assertEqual([], failed, f"skills que el scanner no pudo procesar: {failed}")


class TestReadmeBadgeCoherence(unittest.TestCase):
    def setUp(self):
        self.readme = README.read_text(encoding="utf-8")
        self.data = load_summary()

    def test_badge_present(self):
        self.assertRegex(
            self.readme,
            BADGE_RE,
            "el README no lleva el badge de SkillSpector con el formato "
            "`SkillSpector-<n>%2F<total>%20skills%20escaneados`",
        )

    def test_badge_numbers_match_summary(self):
        match = BADGE_RE.search(self.readme)
        assert match is not None  # cubierto por test_badge_present
        scanned, total = int(match.group(1)), int(match.group(2))
        self.assertEqual(
            self.data["skills_scanned"],
            scanned,
            "el badge del README y el resumen del scan no dicen lo mismo",
        )
        self.assertEqual(self.data["skills_total"], total)

    def test_scanner_version_claimed_in_readme_matches(self):
        version = self.data["scanner_version"]
        self.assertIn(
            f"v{version}",
            self.readme,
            f"el README no menciona la versión del scanner realmente usada (v{version})",
        )

    def test_clean_claim_requires_clean_scan(self):
        """Si el README afirma que no hay hallazgos activos, tiene que ser cierto."""
        claims_clean = "sin hallazgos activos" in self.readme.lower()
        if claims_clean:
            self.assertEqual(
                0,
                self.data["active_findings"],
                "el README afirma «sin hallazgos activos» pero el scan reporta "
                f"{self.data['active_findings']}",
            )

    def test_gate_claim_matches(self):
        """Nadie sobre el umbral: si hay skills gated, el README no puede callarlo."""
        over = self.data["skills_over_gate"]
        if over:
            for name in over:
                self.assertIn(
                    name,
                    self.readme,
                    f"`{name}` supera el umbral de score y el README no lo menciona",
                )


if __name__ == "__main__":
    unittest.main()

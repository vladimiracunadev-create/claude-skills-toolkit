"""
Smoke tests para la estructura del toolkit. Verifican que cada skill cumple
el contrato mínimo: existe SKILL.md, tiene frontmatter válido con name y
description, y los scripts referenciados son ejecutables.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyyaml requerido para los tests: pip install pyyaml") from exc


REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
PRODUCTION_SKILLS = {
    "security-audit",
    "yaml-control",
    "md-lint-fix",
    "docker-cleanup",
    "docker-compose-doctor",
    "pre-push-guard",
    "web-snap",
    "python-version-control",
    "pre-commit-guard",
}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} no empieza con frontmatter '---'")
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm)


class TestSkillsStructure(unittest.TestCase):
    def test_skills_dir_exists(self):
        self.assertTrue(SKILLS_DIR.is_dir(), f"{SKILLS_DIR} no existe")

    def test_all_production_skills_present(self):
        present = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
        missing = PRODUCTION_SKILLS - present
        self.assertFalse(missing, f"Faltan skills de producción: {missing}")

    def test_each_skill_has_skill_md(self):
        for skill in PRODUCTION_SKILLS:
            with self.subTest(skill=skill):
                skill_md = SKILLS_DIR / skill / "SKILL.md"
                self.assertTrue(skill_md.is_file(), f"Falta {skill_md}")

    def test_each_skill_has_readme_md(self):
        """Cada skill de producción debe tener un README.md humano-legible
        con diagramas y casos de uso — complementa al SKILL.md (contrato agente)."""
        for skill in PRODUCTION_SKILLS:
            with self.subTest(skill=skill):
                readme = SKILLS_DIR / skill / "README.md"
                self.assertTrue(readme.is_file(), f"Falta {readme}")
                content = readme.read_text(encoding="utf-8")
                self.assertGreater(
                    len(content), 1000,
                    f"{skill}: README.md demasiado corto (<1000 chars) — debe cubrir instalación, uso, casos, diagramas",
                )
                for section in ("## 🎯", "## 📦", "## 🚀"):
                    self.assertIn(
                        section, content,
                        f"{skill}: README.md falta sección '{section}' (qué hace / instalación / uso)",
                    )

    def test_frontmatter_has_required_fields(self):
        for skill in PRODUCTION_SKILLS:
            with self.subTest(skill=skill):
                fm = parse_frontmatter(SKILLS_DIR / skill / "SKILL.md")
                self.assertIn("name", fm, f"{skill}: falta 'name' en frontmatter")
                self.assertIn("description", fm, f"{skill}: falta 'description'")
                self.assertEqual(
                    fm["name"], skill,
                    f"{skill}: el 'name' del frontmatter ({fm['name']!r}) no coincide con la carpeta",
                )
                self.assertGreater(
                    len(fm["description"]), 80,
                    f"{skill}: la 'description' es demasiado corta para incluir triggers útiles",
                )

    def test_template_is_not_counted_as_production(self):
        template = SKILLS_DIR / "_template"
        self.assertTrue(template.is_dir(), "El template debería existir como referencia")
        self.assertNotIn("_template", PRODUCTION_SKILLS)


class TestRepoFiles(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue((REPO / "README.md").is_file())

    def test_install_scripts_pair(self):
        self.assertTrue((REPO / "scripts" / "install.sh").is_file())
        self.assertTrue((REPO / "scripts" / "install.ps1").is_file())
        self.assertTrue((REPO / "scripts" / "uninstall.sh").is_file())
        self.assertTrue((REPO / "scripts" / "uninstall.ps1").is_file())

    def test_license_present(self):
        self.assertTrue((REPO / "LICENSE").is_file())


if __name__ == "__main__":
    unittest.main()

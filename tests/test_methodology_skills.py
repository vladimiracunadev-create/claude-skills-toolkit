"""
Tests de los skills de metodología — los que entregan criterio en prosa en vez
de un script ejecutable: preliminary-product-tester, functional-user-flow-tester,
software-resilience-state-tester y release-evidence-auditor.

Un skill sin script no tiene salida que aserción pueda comparar, así que lo que
se protege es lo que sí puede romperse en silencio: que no se cuele un script
sin reclasificar el skill, que los enlaces relativos (incluidas las referencias
que el SKILL.md manda leer) apunten a ficheros reales, y que cada uno siga
declarando sus límites.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"

METHODOLOGY_SKILLS = {
    "preliminary-product-tester",
    "functional-user-flow-tester",
    "software-resilience-state-tester",
    "release-evidence-auditor",
}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


class TestMethodologySkills(unittest.TestCase):
    def test_no_executable_script(self):
        """Son skills de criterio: la lógica vive en la prosa. Si alguno gana un
        script, deja de pertenecer a esta categoría y hay que documentarlo como
        skill ejecutable (deps, exit codes, flags) en vez de colarlo aquí."""
        for skill in METHODOLOGY_SKILLS:
            with self.subTest(skill=skill):
                scripts = [
                    p.name
                    for p in (SKILLS / skill).rglob("*")
                    if p.suffix in {".py", ".sh", ".ps1"}
                ]
                self.assertEqual(
                    scripts, [],
                    f"{skill}: aparecieron scripts {scripts} — reclasifícalo como skill ejecutable",
                )

    def test_relative_links_resolve(self):
        """El SKILL.md de varios de estos skills manda leer un fichero de
        references/. Un enlace roto convierte esa instrucción en un callejón."""
        for skill in METHODOLOGY_SKILLS:
            for md in sorted((SKILLS / skill).rglob("*.md")):
                text = md.read_text(encoding="utf-8")
                for href in LINK_RE.findall(text):
                    if href.startswith(("http://", "https://", "#", "mailto:")):
                        continue
                    target = (md.parent / href.split("#")[0]).resolve()
                    with self.subTest(file=md.relative_to(REPO).as_posix(), href=href):
                        self.assertTrue(
                            target.exists(),
                            f"{md.relative_to(REPO)}: enlace roto → {href}",
                        )

    def test_references_are_not_empty(self):
        for skill in METHODOLOGY_SKILLS:
            refs = SKILLS / skill / "references"
            if not refs.is_dir():
                continue
            for ref in sorted(refs.glob("*.md")):
                with self.subTest(ref=ref.relative_to(REPO).as_posix()):
                    self.assertGreater(
                        len(ref.read_text(encoding="utf-8")), 300,
                        f"{ref.relative_to(REPO)}: referencia demasiado corta para guiar una prueba",
                    )

    def test_declares_its_limits(self):
        """Regla de honestidad del toolkit: un skill que no dice qué NO hace es
        peor que un skill que no existe."""
        for skill in METHODOLOGY_SKILLS:
            with self.subTest(skill=skill):
                skill_md = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
                readme = (SKILLS / skill / "README.md").read_text(encoding="utf-8")
                self.assertTrue(
                    "Límites" in skill_md or "Limitaciones" in skill_md,
                    f"{skill}: el SKILL.md no declara sus límites",
                )
                self.assertIn(
                    "## ⚠️ Limitaciones", readme,
                    f"{skill}: el README.md no declara sus limitaciones",
                )


if __name__ == "__main__":
    unittest.main()

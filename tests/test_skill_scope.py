"""
Cada skill declara su alcance, y lo que declara cuadra con lo que su código hace.

Este test cierra el hallazgo `LP3` de SkillSpector («el skill no declara su scope
de herramientas, pero se detectaron capacidades en el código») de forma que no
pueda reabrirse en silencio: un skill nuevo sin declaración de alcance, o con una
declaración que se queda corta respecto a su propio script, rompe la suite.

La regla sobre `allowed-tools` es deliberada y también se verifica: ese campo
*preaprueba* herramientas —se salta la confirmación del usuario durante el turno
que invoca el skill— en vez de limitarlas, así que ningún SKILL.md lo declara. El
techo real es `disallowed-tools`, que sí retira herramientas del pool.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyyaml requerido para los tests: pip install pyyaml") from exc


REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"

CAPABILITY_VOCABULARY = {"shell", "file_read", "file_write", "network", "env"}

# Firmas con las que se detecta cada capacidad en el código del skill. Son las
# mismas que se usaron para construir las declaraciones, para que el test
# compare declaración contra código y no declaración contra declaración.
CAPABILITY_PATTERNS = {
    "shell": r"\bsubprocess\.|os\.system\(",
    "file_write": r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]|shutil\.(copy|move|rmtree)|\.unlink\(|\.mkdir\(",
    "file_read": r"\.read_text\(|\.read_bytes\(|open\([^)]*['\"]r|\.rglob\(|\.glob\(|\.iterdir\(",
    "network": r"urllib\.request|urlopen\(|requests\.(get|post)|http\.client",
    "env": r"os\.environ|os\.getenv\(",
}

SCOPE_HEADINGS = ("## Alcance y permisos", "## Scope and permissions")


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def scripts_of(skill: Path) -> list[Path]:
    return [p for p in skill.rglob("*") if p.is_file() and p.suffix in (".py", ".sh")]


def detected_capabilities(skill: Path) -> set[str]:
    found: set[str] = set()
    for script in scripts_of(skill):
        text = script.read_text(encoding="utf-8", errors="replace")
        for cap, pattern in CAPABILITY_PATTERNS.items():
            if re.search(pattern, text):
                found.add(cap)
        if script.suffix == ".sh":
            found.add("shell")
    return found


class TestSkillScopeDeclared(unittest.TestCase):
    def test_every_skill_declares_capabilities(self):
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                meta = frontmatter(skill / "SKILL.md").get("metadata") or {}
                self.assertIn(
                    "capabilities",
                    meta,
                    f"`{skill.name}` no declara `metadata.capabilities` en su "
                    "frontmatter (cierra el hallazgo LP3 de SkillSpector)",
                )
                self.assertIsInstance(meta["capabilities"], list)

    def test_declared_capabilities_use_the_vocabulary(self):
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                declared = set(frontmatter(skill / "SKILL.md")["metadata"]["capabilities"])
                unknown = declared - CAPABILITY_VOCABULARY
                self.assertEqual(
                    set(),
                    unknown,
                    f"`{skill.name}` declara capacidades fuera del vocabulario: "
                    f"{sorted(unknown)}",
                )

    def test_declaration_covers_what_the_code_does(self):
        """Lo declarado no puede quedarse corto respecto al script."""
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                declared = set(frontmatter(skill / "SKILL.md")["metadata"]["capabilities"])
                missing = detected_capabilities(skill) - declared
                self.assertEqual(
                    set(),
                    missing,
                    f"el script de `{skill.name}` usa capacidades que su "
                    f"`metadata.capabilities` no declara: {sorted(missing)}",
                )

    def test_every_skill_has_a_scope_section(self):
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(
                    any(h in text for h in SCOPE_HEADINGS),
                    f"`{skill.name}` no tiene sección de alcance "
                    f"(una de {SCOPE_HEADINGS})",
                )


class TestNoPreapprovedTools(unittest.TestCase):
    def test_no_skill_declares_allowed_tools(self):
        """`allowed-tools` preaprueba, no limita: ningún skill debe declararlo."""
        offenders = [
            skill.name
            for skill in skill_dirs()
            if "allowed-tools" in frontmatter(skill / "SKILL.md")
        ]
        self.assertEqual(
            [],
            offenders,
            "estos skills declaran `allowed-tools`, que *preaprueba* herramientas "
            "y quita la confirmación del usuario en vez de limitarlas; para "
            f"acotar de verdad usa `disallowed-tools`: {offenders}",
        )

    def test_disallowed_tools_is_a_list_of_strings(self):
        for skill in skill_dirs():
            disallowed = frontmatter(skill / "SKILL.md").get("disallowed-tools")
            if disallowed is None:
                continue
            with self.subTest(skill=skill.name):
                self.assertIsInstance(disallowed, list)
                for tool in disallowed:
                    self.assertIsInstance(tool, str)
                    self.assertTrue(tool.strip(), "nombre de herramienta vacío")

    def test_scope_section_lists_the_removed_tools(self):
        """Si el frontmatter retira herramientas, la sección tiene que decirlo."""
        for skill in skill_dirs():
            disallowed = frontmatter(skill / "SKILL.md").get("disallowed-tools") or []
            if not disallowed:
                continue
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                for tool in disallowed:
                    self.assertIn(
                        f"`{tool}`",
                        text,
                        f"`{skill.name}` retira `{tool}` en el frontmatter pero no "
                        "lo menciona en su sección de alcance",
                    )


if __name__ == "__main__":
    unittest.main()

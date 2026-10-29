# Auditoría de seguridad — `claude-skills-toolkit` — 2026-10-29 22:44 UTC

Generado por skill `security-audit` v2 (multi-layer). Cruza dependencias y código contra fuentes oficiales: OSV.dev (NVD + GHSA + PyPA + Go vuln DB + RustSec + etc.) · CISA KEV (explotación activa) · EPSS (probabilidad de exploit) · Bandit SAST · trivy/grype (container) · zizmor (GHA workflows) · hadolint (Dockerfile) · gitleaks/detect-secrets · typosquat heuristic.

## Resumen ejecutivo

- **Ecosistemas auditados:** ninguno detectado
- **Dependencias revisadas:** 0 únicas (total entradas: 0)
- **Cobertura del scan de deps:** completa — todas las dependencias declaradas tienen versión exacta resuelta
- **Vulnerabilidades en deps (OSV):** 0 (critical: 0, high: 0, medium: 0, low: 0, unknown: 0)
- **En CISA KEV (explotación activa):** 0
- **Hallazgos en capas extra:** 59 (sast: 59)

## ✅ Sin vulnerabilidades en dependencias (capa OSV)

Continúa con los hallazgos de capas extra abajo.

## 🧠 Capa SAST — Bandit (vulnerabilidades en TU código)

### `LOW` — try_except_pass

- **Ubicación:** `skills/_template/main.py:18`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — blacklist

- **Ubicación:** `skills/bitcoin-custody-audit/bitcoin_custody_audit.py:34`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/bitcoin-custody-audit/bitcoin_custody_audit.py:211`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/bitcoin-custody-audit/bitcoin_custody_audit.py:211`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — blacklist

- **Ubicación:** `skills/md-lint-fix/fix-md-lint.py:36`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/md-lint-fix/fix-md-lint.py:80`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/md-lint-fix/fix-md-lint.py:91`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/md-lint-fix/fix-md-lint.py:91`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/md-lint-fix/fix-md-lint.py:284`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — blacklist

- **Ubicación:** `skills/md-to-doc/md_to_doc.py:38`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/md-to-doc/md_to_doc.py:180`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/md-to-doc/md_to_doc.py:208`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — blacklist

- **Ubicación:** `skills/pre-commit-guard/pre_commit_guard.py:28`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/pre-commit-guard/pre_commit_guard.py:59`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — blacklist

- **Ubicación:** `skills/pre-push-guard/pre_push_guard.py:24`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/pre-push-guard/pre_push_guard.py:55`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — blacklist

- **Ubicación:** `skills/python-lint-guard/python_lint_guard.py:32`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/python-lint-guard/python_lint_guard.py:132`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — try_except_pass

- **Ubicación:** `skills/python-version-control/scan.py:26`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — try_except_continue

- **Ubicación:** `skills/python-version-control/scan.py:134`
- **Detalle:** Try, Except, Continue detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html

### `LOW` — blacklist

- **Ubicación:** `skills/repo-coherence-audit/scripts/coherence_probe.py:18`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/repo-coherence-audit/scripts/coherence_probe.py:163`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — assert_used

- **Ubicación:** `skills/repo-coherence-audit/scripts/mojibake_probe.py:113`
- **Detalle:** Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b101_assert_used.html

### `LOW` — blacklist

- **Ubicación:** `skills/security-audit/security_audit.py:27`
- **Detalle:** Consider possible security implications associated with the subprocess module.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess

### `LOW` — try_except_pass

- **Ubicación:** `skills/security-audit/security_audit.py:40`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — try_except_pass

- **Ubicación:** `skills/security-audit/security_audit.py:489`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:572`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — try_except_pass

- **Ubicación:** `skills/security-audit/security_audit.py:576`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:599`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:653`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:708`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:708`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:742`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:742`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:777`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:777`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:817`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:817`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — try_except_continue

- **Ubicación:** `skills/security-audit/security_audit.py:829`
- **Detalle:** Try, Except, Continue detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html

### `LOW` — try_except_pass

- **Ubicación:** `skills/security-audit/security_audit.py:931`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:975`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:975`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — try_except_pass

- **Ubicación:** `skills/security-audit/security_audit.py:990`
- **Detalle:** Try, Except, Pass detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html

### `LOW` — try_except_continue

- **Ubicación:** `skills/security-audit/security_audit.py:1032`
- **Detalle:** Try, Except, Continue detected.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:1507`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:1518`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:1593`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:1628`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

### `LOW` — subprocess_without_shell_equals_true

- **Ubicación:** `skills/security-audit/security_audit.py:1628`
- **Detalle:** subprocess call - check for execution of untrusted input.
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html

### `LOW` — start_process_with_partial_path

- **Ubicación:** `skills/security-audit/security_audit.py:1636`
- **Detalle:** Starting a process with a partial executable path
- **Referencia:** https://bandit.readthedocs.io/en/1.9.4/plugins/b607_start_process_with_partial_path.html

_…y 9 hallazgos más en esta capa (truncado)._

## Cómo reproducir

```bash
python ~/.claude/skills/security-audit/security_audit.py
```

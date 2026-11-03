# Hallazgos de SkillSpector, caso a caso

> Qué disparó cada regla, por qué el escáner tiene razón en mirarlo, qué pasa
> realmente en este repo, **cómo se resolvería** y por qué el skill cumple su
> función igual. Un veredicto de una línea en un YAML sirve para que una
> herramienta decida; no sirve para que una persona entienda.

Datos de este análisis: **SkillSpector v2.12.0** (capa estática, `--no-llm`) sobre los 23 skills del repo, checkout limpio. Informe con las cifras: [`SKILLSPECTOR_2026-11-03.md`](SKILLSPECTOR_2026-11-03.md). Los veredictos que consume el generador de baselines viven en [`skillspector-triage.yaml`](skillspector-triage.yaml) — ese fichero es **datos**, este documento es la explicación.

| | |
|---|---|
| Hallazgos de la primera pasada | **95** |
| Corregidos de verdad | **2** (`YR4`, `RP1`) |
| Riesgo real asumido y declarado | **1 clase** (`LP3`, ×14) |
| Falsos positivos y límites del escáner | **9 clases**, 91 hallazgos |

**Por qué hay tantos.** SkillSpector está diseñado para contestar una pregunta concreta: *¿instalo este skill que me encontré en internet?* Con esa pregunta, toda capacidad peligrosa es sospechosa por defecto, y hace bien. Este repo es el caso que rompe ese supuesto: es una caja de herramientas de desarrollo cuyo trabajo **es** invocar `git`, `docker` y `pytest`, escribir en ficheros del repo y consultar bases de CVE por HTTPS. El escáner no se equivoca al marcarlo; el trabajo está en decidir, caso por caso, si el riesgo existe.

---

## 1 · `YR4` — carácter invisible en el fuente · **CORREGIDO**

**Severidad:** HIGH · **×1** · `web-snap`

**Qué disparó.** Una regla YARA sobre `web_snap.py:61`. El fichero contenía un **U+200B** (espacio de ancho cero) literal, incrustado dentro de una cadena:

```python
"edge": "- Microsoft<U+200B>Edge",  # Edge usa a veces un caracter invisible
```

**Qué veía el escáner.** Texto oculto en un manifiesto o script de skill — el vector clásico para colar instrucciones que una persona no ve al revisar el diff.

**Qué pasaba realmente.** Era intencional y estaba comentado: el título de ventana de Edge trae ese carácter, y el skill lo necesita para reconocer la ventana. Pero el escáner acertó de pleno en el fondo del asunto: **el carácter era invisible en el diff, en el blame y en la revisión de código**. Que esta vez fuera benigno es suerte, no diseño — nadie revisando ese fichero habría podido distinguirlo de uno hostil.

**Cómo se resolvió.**

```python
"edge": "- Microsoft" + chr(0x200B) + "Edge",
```

El byte que llega al runtime es idéntico (verificado: `'- Microsoft​Edge'`), pero ahora el carácter está **escrito**, no escondido. Un `grep` lo encuentra y un diff lo muestra.

**Lección.** Un carácter no imprimible en el fuente se escribe siempre con su escape, aunque sea legítimo. El coste es cero y la diferencia es que la próxima vez que aparezca uno, destacará.

---

## 2 · `RP1` — dependencia sin pin de versión · **CORREGIDO**

**Severidad:** MEDIUM · **×1** · `md-lint-fix`

**Qué disparó.** `md-lint-fix/SKILL.md:81` referenciaba `npx markdownlint-cli2` sin versión.

**Qué veía el escáner.** Un *rug pull*: la referencia flotante resuelve a lo último publicado, así que quien controle ese paquete controla lo que se ejecuta mañana, sin que cambie ni una línea del repo.

**Qué pasaba realmente.** Exactamente eso, y peor: al buscarlo apareció que **el propio CI** tenía el mismo defecto (`pnpm add -g markdownlint-cli2`, sin versión). El repo tiene un documento entero —[`supply-chain-security.md`](../supply-chain-security.md)— sobre por qué usa `pnpm` en vez de `npm` para defenderse de ataques tipo Shai-Hulud, y dejaba la puerta abierta en el paso de instalación.

**Cómo se resolvió.** Pin a `markdownlint-cli2@0.24.0` en los cuatro sitios (`SKILL.md` ×3 variantes de gestor + `ci.yml`, este último con la versión en `env:`). El segundo beneficio es que el conteo de errores de lint deja de cambiar bajo los pies cuando el linter cambia de criterio.

---

## 3 · `LP3` — ningún skill declara su scope de herramientas · **ABIERTO, asumido**

**Severidad:** MEDIUM · **×14** · `bitcoin-custody-audit`, `docker-compose-doctor`, `md-lint-fix`, `md-to-doc`, `pre-commit-guard`, `pre-push-guard`, `python-deps-pinning`, `python-lint-guard`, `python-version-control`, `repo-coherence-audit`, `security-audit`, `version-bump`, `web-snap`, `yaml-control`

**Qué disparó.** El frontmatter de cada `SKILL.md` no declara `allowed-tools` ni `permissions`, mientras el analizador detecta en el código capacidades de `shell`, `file_write`, `file_read`, `network` y `env`.

**Qué veía el escáner.** Lo dice sin adornos: sin permisos declarados, *la intención del skill es opaca y no se puede validar*. Quien lee el `SKILL.md` no tiene forma de saber, sin leer el script, qué va a tocar.

**Este es el hallazgo real del escaneo**, y conviene ser preciso sobre qué lo resolvería y qué no. La propia remediación de SkillSpector avisa de la trampa: en los Agent Skills de Claude Code, `allowed-tools` **registra herramientas preaprobadas, no un techo de permisos**, y advierte de añadir una herramienta sólo cuando esté aprobada como necesaria, *no para silenciar el hallazgo*.

Eso cambia el cálculo por completo:

- **Añadir `allowed-tools` a los 22 skills no es un control de seguridad.** No impide que el skill use otra herramienta; preaprueba las que liste, es decir, **quita confirmaciones al usuario**. Hecho a la ligera, el resultado neto sería *menos* fricción ante una acción destructiva, no más — y el hallazgo se marcaría como resuelto. Es el peor desenlace posible: la métrica en verde y la postura peor.
- **Lo que sí resuelve el problema de fondo** es lo que el hallazgo nombra: la opacidad. Que cada `SKILL.md` diga qué toca y con qué alcance, de forma que quien lo instala lo sepa antes de ejecutarlo.

**Cómo se resolverá.** Declarar el scope skill por skill, revisando las 22 superficies una a una y comprobando dos cosas en cada una: que la lista no deja fuera una herramienta que el skill necesita (lo rompería), y que no preaprueba ninguna que el usuario querría confirmar a mano (`docker-cleanup` borra todo sin preguntar por diseño; `security-audit --apply` reescribe manifests). No es un cambio mecánico de 22 líneas de frontmatter: es una decisión por skill.

**Por qué el skill cumple igual, mientras.** Ninguno de los 22 oculta lo que hace: cada `SKILL.md` documenta qué hace, qué **no** hace y sus riesgos —es una de las reglas del repo—, cada uno trae un `README.md` para humanos, y los casos destructivos están marcados como tales en [`SECURITY.md`](../../SECURITY.md). La opacidad que el escáner penaliza es la del **campo del frontmatter**, no la del skill: la información existe, no está donde una herramienta pueda leerla. Queda [declarado como riesgo asumido](../../SECURITY.md) y [pendiente en el ROADMAP](../../ROADMAP.md), con severidad media, no como falso positivo.

---

## 4 · `AST4` — llamadas a `subprocess`

**Severidad:** MEDIUM · **×26** · 10 skills

**Qué disparó.** Cada `subprocess.run([...])` del repo. Por ejemplo `bitcoin_custody_audit.py:211`:

```python
subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
```

**Qué veía el escáner.** Ejecución de comandos externos: sin validar la entrada, es la vía de la inyección de comandos.

**Qué pasa realmente.** La remediación que pide el escáner es *«usa `subprocess.run()` con `shell=False` y una lista explícita de argumentos»* — y eso es exactamente lo que el código ya hace, en las 26 ocurrencias. No hay un solo `shell=True` en el repo, los argumentos van en lista (nunca concatenados en una cadena) y lo que se invoca son binarios fijos: `git`, `gh`, `docker`, `pytest`, `ruff`, `markdownlint-cli2`. Es la misma clase que Bandit reporta como `B404`/`B603`/`B607` y que está aceptada en [`.bandit-baseline.json`](../../.bandit-baseline.json) por esta razón.

**Cómo se "resolvería".** No hay nada que resolver: la alternativa a invocar `git` por `subprocess` es no automatizar tareas de git. El hallazgo es inherente al propósito del toolkit, no a su implementación. Lo que sí hay que mantener —y el gate de Bandit `MEDIUM+` del CI lo verifica en cada push— es que no aparezca nunca un `shell=True` ni una cadena concatenada.

**Veredicto:** `by_design`. El skill cumple porque la capacidad que se marca *es* su función, ejecutada con el patrón que el propio escáner recomienda.

---

## 5 · `TM1` — abuso de parámetros de herramienta

**Severidad:** HIGH · **×22** · `docker-cleanup`, `git-push`, `pre-commit-guard`, `pre-push-guard`, `version-bump`

**Qué disparó.** Cadenas como `rm TODOS`, `git push --force`, `git push --no-verify`, `git reset --hard`. El escáner busca parámetros peligrosos (`--force`, `-rf /`, `shell=True`) usados para esquivar comprobaciones de seguridad.

**Qué pasa realmente.** Aquí es donde el pattern matching se ve con más claridad, porque **tres de los casos son literalmente lo contrario de lo que la regla busca**:

- **`version-bump/SKILL.md:175`** — el escáner marcó `git push --force`. El texto completo dice `git push --force-with-lease`: la coincidencia es un **prefijo de la variante segura**, la que no sobreescribe el trabajo de otro. Y está dentro de una recomendación de seguridad sobre no commitear datos personales en repos públicos.
- **`git-push/SKILL.md:189`** — el escáner marcó `git reset --hard`. La línea está en la sección **«Reglas de seguridad (no se saltan)»** y dice: *«Nunca `git reset --hard` sin avisar antes de lo que se pierde»*. Se marcó una **prohibición** como si fuera una instrucción.
- **`docker-cleanup/README.md:20-23`** — `rm TODOS` / `rm TODAS` es la tabla del README que advierte al usuario de qué borra el skill. Es la advertencia, no el comando.

Queda un caso que sí merece una respuesta y no un encogimiento de hombros:

- **`pre_push_guard.py:219` y `:248`** — aquí `git push --no-verify` está **en el código**, no en la documentación: es el comentario de la plantilla del hook y el mensaje que se imprime tras instalarlo (*«Saltar con: `git push --no-verify`»*). Un gate que te enseña a saltarlo, dicho así, suena mal. Dos razones por las que es correcto: **(1)** `--no-verify` es una bandera de git, no del skill — un hook local es saltable por diseño y por definición, con o sin aviso, así que ocultarlo no añade seguridad, sólo confusión cuando el push falle en medio de una urgencia; **(2)** el hook lo instala el usuario a mano con `--install-hook`, que es opt-in y nunca automático. Decirle cómo desactivar temporalmente algo que él activó es documentación honesta, y es lo que hace cualquier framework de hooks. El gate que **no** se salta es el del CI, que corre en el servidor.

**Cómo se resolvería.** Reescribir la documentación para que no contenga las cadenas que el escáner busca. Es decir: dejar de advertir que `docker-cleanup` borra todo, y quitar de `git-push` la regla que prohíbe `git reset --hard`. **Sería peor en todos los sentidos** — se degradaría la seguridad real del usuario para mejorar una métrica. No se hace.

**Veredicto:** `false_positive`. La única acción que esta clase deja abierta es la de siempre: que la prosa diga lo que el código hace.

---

## 6 · `E1` — transmisión a destino externo

**Severidad:** MEDIUM · **×16** · 11 skills

**Qué disparó.** El bloque de instalación que cada `README.md` trae:

```bash
curl -L -o docker-cleanup.zip \
  https://github.com/vladimiracunadev-create/claude-skills-toolkit/releases/...
```

**Qué veía el escáner.** Datos saliendo hacia una URL externa, que puede ser telemetría legítima o exfiltración. Pide verificar el destino y asegurarse de que no se transmiten secretos ni PII.

**Qué pasa realmente.** La dirección del flujo es la inversa: `curl -L -o <fichero>` **descarga** desde GitHub al disco del usuario. No hay cuerpo de petición, no hay datos del usuario en la URL, no hay destino que no sea el repo de releases del propio toolkit. El escáner detecta «URL externa en contexto de transferencia» sin distinguir subida de bajada.

**Cómo se resolvería.** Nada que resolver sin quitar las instrucciones de instalación del README. Lo que sí es obligación permanente, y aquí se cumple, es que esas URL apunten al repo oficial: si una apuntara a otro dominio, este hallazgo sería el que lo delataría. Por eso se revisa el destino antes de suprimirlo, en vez de suprimir la clase entera a ciegas.

**Veredicto:** `false_positive`.

---

## 7 · `RA2` — persistencia entre sesiones

**Severidad:** MEDIUM · **×7** · `clone-repo`, `functional-user-flow-tester`, `git-push`, `preliminary-product-tester`, `release-evidence-auditor`, `software-resilience-state-tester`, `sync-fork`

**Qué disparó.** `mkdir -p ~/.claude` y `curl -L -o ~/.claude/skills/<skill>/SKILL.md ...` en los READMEs.

**Qué veía el escáner.** Un skill que se instala solo en el directorio del agente es el patrón exacto de la persistencia: sobrevivir más allá de la sesión actual sin que el usuario lo pida. Pide *eliminar cualquier mecanismo de persistencia*.

**Qué pasa realmente.** Es el **procedimiento de instalación documentado**, en el README, bajo un encabezado que dice que instala. `~/.claude/skills/` es el destino que el runtime define para los skills; escribir ahí es lo que significa instalar uno. La diferencia con el ataque es quién inicia la acción: aquí el usuario lee el README y ejecuta el comando. No hay cron, no hay script de arranque, no hay fichero de estado, y nada de esto ocurre como efecto colateral de invocar un skill.

**Cómo se resolvería.** Sólo dejando de documentar cómo instalar los skills. El hallazgo es inseparable de ser un repo de skills instalables.

**Veredicto:** `false_positive`. Vale la pena notar que la regla es útil precisamente porque es ruidosa aquí: en un skill que *no* fuera un instalador, escribir en `~/.claude/skills/` sería grave.

---

## 8 · `PE3` — acceso a ficheros de credenciales

**Severidad:** HIGH · **×5** · `bitcoin-custody-audit`, `version-bump`

**Qué disparó.** Las cadenas literales `".env"` y `".env.local"`, por ejemplo en `bitcoin_custody_audit.py:99`, dentro de una lista de sufijos de fichero:

```python
TEXT_SUFFIXES = SOURCE_SUFFIXES | {
    ".md", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".conf", ".txt",
    ".env", ".sh", ".ps1", ".cmd", ".bat", ".html",
}
```

**Qué veía el escáner.** Código que accede a ficheros de credenciales — posible robo de credenciales. Pide eliminar las referencias a rutas de credenciales y usar rutas de ejemplo en la documentación.

**Qué pasa realmente.** Es la inversión más limpia del escaneo: el trabajo de `bitcoin-custody-audit` es **buscar secretos filtrados** en el repo auditado y reportarlos; `version-bump` recorre sufijos de texto buscando marcadores de versión. Nombrar `.env` es lo que permite *detectar* que hay uno donde no debería. El skill no lee credenciales para usarlas: avisa de que existen. Un escáner de secretos que no mencionara `.env` sería un escáner roto — y, por construcción, todo escáner de secretos dispara esta regla.

**Lo que sí hay que sostener**, porque aquí es donde estaría el problema real: ese contenido no sale del proceso. `bitcoin-custody-audit` tiene como regla central no pedir, leer ni aceptar material secreto (semillas, claves privadas, passphrases), y su informe reporta *la existencia y la ubicación* del hallazgo, nunca el valor. Eso es lo que hace que la mención sea benigna, no el hecho de ser un escáner.

**Veredicto:** `false_positive`.

---

## 9 · `AR2` — declaración anti-rechazo

**Severidad:** HIGH · **×1** · `yaml-control`

**Qué disparó.** La cadena `no warnings` en `yaml-control/SKILL.md:131`. La línea completa:

> Si hay errores (no warnings), exit 1 → bloquea el push si se usa en pre-push hook.

**Qué veía el escáner.** Un skill que instruye al agente a omitir advertencias o descargos — preámbulo habitual de jailbreak, porque esconde el riesgo al usuario.

**Qué pasa realmente.** `no warnings` aquí no es «sin advertencias»: es la aclaración de **cuál de los dos niveles** decide el código de salida. Errores sí bloquean el push; warnings no. La frase hace lo contrario de ocultar: precisa el criterio del gate. El escáner buscó una subcadena en inglés dentro de una frase en español donde funciona como paréntesis.

**Cómo se resolvería.** Reformular a *«Si hay errores —los warnings no cuentan— exit 1»*. Es un cambio de una línea, pero reescribir prosa correcta para esquivar un patrón de un escáner es poner la herramienta por encima del lector. La regla es buena; la coincidencia, no.

**Veredicto:** `false_positive`.

---

## 10 · `AE1` — análisis incompleto de un artefacto referenciado

**Severidad:** HIGH · **×1** · `python-version-control`

**Qué disparó.** `python-version-control/SKILL.md:62` referencia su `README.md`, y el escáner no pudo inspeccionarlo por completo (`static_parse_limit`: una expresión relevante excedió el límite de su parser).

**Qué veía el escáner.** Un artefacto referenciado pero no inspeccionado del todo es, en su modelo, un sitio donde esconder algo. Su propia remediación lo matiza con honestidad: *un análisis incompleto no es prueba de evasión maliciosa*, y pide conservar las referencias necesarias.

**Qué pasa realmente.** No es un hallazgo sobre el skill: es el escáner declarando su propio límite de cobertura. Es la misma clase de dato que la columna «Cobertura» del informe, donde se ve que la mínima observada es **33,3 %** — y por eso ese número se publica en el README junto al «0 hallazgos activos», en vez de dejar que el cero se lea como más de lo que es.

**Cómo se resolvería.** No desde este repo: el límite es del parser del escáner, sobre Markdown largo. Lo que está en nuestra mano es no esconderlo, y el informe publica la cobertura por skill.

**Veredicto:** `scanner_limit`.

---

## 11 · `TM3` — valores por defecto inseguros

**Severidad:** MEDIUM · **×1** · `security-audit`

**Qué disparó.** `verify=False` en `security_audit.py:1534`.

**Qué veía el escáner.** Verificación TLS desactivada — un clásico, y de los graves: deja la conexión expuesta a un intermediario. Pide forzar `verify=True`.

**Qué pasa realmente.** No es `requests`. Es la firma de una función del propio skill:

```python
def apply_fixes(findings, deps, verify: bool = False, test_cmd: str = "", ...):
    """Si verify=True: tras cada bump corre pip install + tests; si falla revierte."""
```

El parámetro significa «¿corro los tests después de subir la versión?», y su valor por defecto es `False`. La coincidencia es con el nombre del parámetro, no con una llamada HTTP. **Comprobado en todo el repo**, porque esta es la clase de hallazgo que no se descarta por intuición: no hay un solo `verify=False` de `requests`, ni `ssl._create_unverified_context`, ni `CERT_NONE`, ni `check_hostname = False`.

**Un matiz que el hallazgo acierta sin querer.** Que `verify` sea `False` por defecto sí es una decisión discutible — significa que `--apply` bumpea versiones sin correr tests a menos que se pida `--verify`. No es un problema de TLS, pero es un default que puede romper un build, y por eso figura explícitamente en la tabla de **riesgos conocidos** de [`SECURITY.md`](../../SECURITY.md) desde antes de este escaneo.

**Veredicto:** `false_positive` en cuanto a TLS; el default en sí está documentado como riesgo conocido.

---

## Qué sostiene todo esto

Un baseline que suprime 93 hallazgos vale lo que valga el mecanismo que impide que se convierta en un cajón de sastre. El de aquí es:

1. **Cada regla suprimida tiene veredicto escrito** en [`skillspector-triage.yaml`](skillspector-triage.yaml) — y su explicación, en este documento.
2. **Una regla nueva no se puede suprimir.** [`scripts/skillspector_baseline.py`](../../scripts/skillspector_baseline.py) falla si el escáner dispara algo que no figura en el triaje. Para silenciar un hallazgo hay que escribir antes por qué.
3. **La supresión es por huella, no por clase.** La calcula el escáner; el script sólo la etiqueta. Un `subprocess` nuevo en un sitio nuevo es un hallazgo nuevo.
4. **Si un skill deja de disparar hallazgos, su baseline se borra** — mantenerlo escondería un hallazgo futuro de esa misma clase.
5. **El gate es por skill** (score > 50 rompe el build), no un máximo global que un skill limpio pueda diluir.
6. **La cobertura se publica, no se promedia.** 33,3 % mínima, declarada en el informe y en el README.

Y el resultado honesto del escaneo no es el cero final: son los dos defectos reales que encontró —un carácter invisible en el fuente y una dependencia sin pin, ambos en sitios donde el repo creía tener la política cubierta— y el riesgo que dejó nombrado y abierto.

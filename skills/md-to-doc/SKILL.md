---
name: md-to-doc
description: >-
  Renderiza cualquier árbol de Markdown (docs/, ADRs, runbooks, notas, specs) a
  un documento HTML autocontenido con portada e índice — y opcionalmente a PDF.
  El núcleo funciona con Python stdlib y embebe cada imagen como data URI, así
  que el resultado es UN solo fichero que se puede mover o adjuntar sin
  arrastrar carpetas de assets. Capas opt-in que degradan con aviso si falta la
  herramienta — `images` (Pillow, optimiza y convierte a gris en perfil de
  impresión), `highlight` (pygments), `diagrams` (mmdc, convierte fences mermaid
  a PNG con caché por hash, los diagramas que GitHub renderiza pero un PDF no),
  `exec` (ejecuta bloques marcados y captura su salida REAL en vez de una
  inventada), `pdf` (xhtml2pdf). Úsalo cuando el usuario diga "genera un PDF de
  la documentación", "exporta los docs a HTML", "compila el manual", "un solo
  fichero con toda la doc", "los diagramas no salen en el PDF", o "documentación
  offline". Trabaja sobre `Path.cwd()` — funciona en cualquier repo.
---

# md-to-doc

Convierte una colección de ficheros Markdown en **un documento**: HTML
autocontenido, o PDF.

## Por qué existe

Todo repo con documentación seria acaba necesitando lo mismo — juntar los `.md`
en algo que se pueda leer de corrido, imprimir o adjuntar. Y casi siempre se
resuelve con un script ad-hoc que solo sirve para ese repo.

Los dos fallos que este skill ataca:

1. **Documentos que no son autocontenidos.** Un HTML que referencia
   `./img/diagrama.png` deja de funcionar en cuanto se mueve. Aquí las imágenes
   van embebidas como data URI: el fichero viaja solo.
2. **Diagramas que desaparecen.** GitHub renderiza los fences ` ```mermaid `
   de forma nativa, así que se escriben sin pensar. Al exportar a PDF no
   renderiza nadie: el diagrama sale como un bloque de texto plano o no sale.
   La capa `diagrams` los convierte a imagen antes de componer.

---

## Cuándo invocar este skill

Triggers explícitos:

- "genera un PDF de la documentación"
- "exporta los docs a HTML"
- "compila el manual"
- "quiero un solo fichero con toda la doc"
- "los diagramas no salen en el PDF"
- "documentación offline"
- "export docs to PDF"

Triggers proactivos:

- Al preparar una entrega o release que incluya documentación
- Cuando el usuario necesita revisar los docs sin acceso al repo

---

## Cómo se invoca

```bash
# Núcleo: cero dependencias
python ~/.claude/skills/md-to-doc/md_to_doc.py --src docs --out manual.html

# Con diagramas y resaltado
python ~/.claude/skills/md-to-doc/md_to_doc.py --src docs --layer diagrams --layer highlight

# Listo para imprimir
python ~/.claude/skills/md-to-doc/md_to_doc.py --src docs --profile print \
    --layer images --layer diagrams --layer pdf --out manual.pdf
```

| Flag | Efecto |
|---|---|
| `--src DIR` | Directorio con los `.md` (por defecto: `cwd`) |
| `--out FICHERO` | Salida `.html` o `.pdf` |
| `--title` / `--subtitle` | Portada |
| `--profile color\|print` | `print`: paleta monocroma + imágenes en gris |
| `--layer NOMBRE` | Capa opcional, repetible |
| `--order FICHERO` | Orden explícito, un path por línea |
| `--cache DIR` | Caché de diagramas renderizados |
| `--exec-timeout N` | Segundos máximos por bloque ejecutado (default 10) |

---

## Arquitectura por capas

El núcleo **nunca** depende de nada externo. Cada capa se pide explícitamente y,
si su herramienta no está, el documento se genera igual con un aviso en la
sección "Avisos de generación" del propio documento.

| Capa | Herramienta | Qué añade | Si falta |
|---|---|---|---|
| *(núcleo)* | stdlib | Parseo Markdown, portada, índice, imágenes como data URI | — |
| `images` | `pillow` | Reescala y optimiza; convierte a gris en perfil `print` | Imágenes sin optimizar |
| `highlight` | `pygments` | Resaltado de sintaxis | Código sin colorear |
| `diagrams` | `mmdc` | Fences ` ```mermaid ` → PNG, cacheado por hash del diagrama | Quedan como texto |
| `exec` | — | Ejecuta bloques ` ```lang run ` y captura su salida real | Capa inactiva |
| `pdf` | `xhtml2pdf` | HTML → PDF | Se emite solo HTML |

### Orden de los documentos

1. El fichero de `--order`, si se pasa.
2. `SUMMARY.md` en el directorio origen (convención mdBook/GitBook).
3. Prefijo numérico (`01-`, `02-`…) y después alfabético.

### La capa `diagrams` y su caché

Los diagramas se cachean por `sha256` de su contenido. Un diagrama que no
cambió entre dos ejecuciones no se vuelve a renderizar — que importa cuando
`mmdc` arranca un Chromium por invocación.

### La capa `exec`

Solo ejecuta bloques marcados explícitamente:

~~~markdown
```python run
print(sum(range(1, 11)))
```
~~~

La salida capturada se inserta debajo del código como bloque de consola. El
valor es que la documentación muestra **lo que el código hace de verdad**, no
lo que alguien recordaba que hacía cuando lo escribió.

> ⚠️ **Ejecuta código del Markdown de origen.** Está detrás de `--layer exec`,
> avisa por `stderr` al arrancar, corre con `python -I` (aislado de
> `PYTHONPATH` y del `site` del usuario) y con timeout. Aun así: úsala solo
> sobre fuentes en las que confías. Por defecto está desactivada.

---

## Qué NO hace / limitaciones

- **No es un renderizador CommonMark completo.** Cubre encabezados, párrafos,
  énfasis, código inline y en bloque, listas, tablas, citas, reglas, enlaces e
  imágenes. No cubre listas anidadas de varios niveles, notas al pie,
  definiciones ni HTML crudo embebido.
- **No descarga imágenes remotas.** Una `![](https://…)` se deja como enlace:
  el documento deja de ser autocontenido en ese punto y así se reporta.
- **Solo ejecuta Python** en la capa `exec`. Otros lenguajes se ignoran con aviso.
- **El PDF hereda los límites de `xhtml2pdf`**: soporte CSS parcial y fuentes
  del sistema. Para tipografía compleja o emoji, revisa el resultado.
- **No modifica los `.md` de origen.** Solo lee.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida u opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida |
| `pillow` | `pip install pillow` | opcional — capa `images` |
| `pygments` | `pip install pygments` | opcional — capa `highlight` |
| `@mermaid-js/mermaid-cli` | `pnpm add -g @mermaid-js/mermaid-cli` | opcional — capa `diagrams` |
| `xhtml2pdf` | `pip install xhtml2pdf` | opcional — capa `pdf` |

Ver [docs/supply-chain-security.md](../../docs/supply-chain-security.md) sobre
por qué `pnpm` en lugar de `npm`.

---

## Ejemplo de salida

```text
✓ HTML autocontenido generado: /repo/manual.html
  documentos procesados: 40
  perfil: color · capas: diagrams, highlight
  ⚠ imagen no encontrada: ./img/archivo.png (desde web-snap)
```

# RepoForge

Read this in: [English](README.md) · [Español](README.es.md)

Análisis de código con IA para generar documentación técnica, skills de agentes, escaneos de seguridad, grafos de código, diagramas de arquitectura y exportaciones del repo listas para LLM.

[![PyPI version](https://img.shields.io/pypi/v/repoforge-ai?label=PyPI&color=blue)](https://pypi.org/project/repoforge-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo](https://repoforge.javierzader.com) · [PyPI](https://pypi.org/project/repoforge-ai/) · [GitHub](https://github.com/JNZader/repoforge) · [Issues](https://github.com/JNZader/repoforge/issues)

## Qué es

RepoForge escanea un repositorio una sola vez y produce varias salidas a partir del mismo análisis: un sitio de documentación listo para Docsify, skills de agentes multi-herramienta, diagramas Mermaid/SVG, grafos de código, escaneos de seguridad y exportaciones de contexto para LLM en un único archivo.

La idea central: combinar **análisis determinístico** (detección de stack, grafos, scoring, escaneo, parseo de coverage, generación de diagramas) con **generación de texto por LLM opcional**, en lugar de fingir que el modelo entiende el repo por arte de magia. El LLM escribe la prosa; todo lo estructural se computa.

Usalo cuando necesites:

- incorporar ingenieros a un código desconocido rápido
- generar documentación interna sin escribir cada capítulo a mano
- crear instrucciones de agente para Claude Code, OpenCode, Cursor, Codex, Gemini y Copilot desde una sola fuente
- aplanar un repositorio en un único archivo de contexto apto para LLM
- auditar el markdown generado en busca de secretos, prompt injection o comandos peligrosos
- entender el radio de impacto arquitectónico antes de refactorizar
- publicar un sitio de docs en GitHub Pages sin armar un pipeline de documentación propio

## Inicio rápido

```bash
pip install repoforge-ai

# Generar docs listas para Docsify (necesita una API key de LLM)
repoforge docs -w /path/to/repo --lang English

# Generar skills multi-herramienta (necesita una API key de LLM)
repoforge skills -w /path/to/repo --targets all

# Exportar el contexto del repo para un LLM (sin API key)
repoforge export -w /path/to/repo -o context.md

# Escaneo de seguridad determinístico (sin API key)
repoforge scan -w /path/to/repo
```

Notas:

- Comando de CLI: `repoforge`
- Nombre del paquete en PyPI: `repoforge-ai` (`repoforge` ya estaba tomado)
- Recomendado para velocidad: instalar `ripgrep`

## Índice

- [Instalación](#instalación)
- [Resumen de comandos](#resumen-de-comandos)
- [Configuración del modelo](#configuración-del-modelo)
- [Inicio rápido técnico](#inicio-rápido-técnico)
- [Comando `docs`](#comando-docs)
- [Comando `skills`](#comando-skills)
- [Comando `export`](#comando-export)
- [Comando `score`](#comando-score)
- [Comando `scan`](#comando-scan)
- [Comando `compress`](#comando-compress)
- [Comando `graph`](#comando-graph)
- [Comando `diagram`](#comando-diagram)
- [Comandos de análisis de código](#comandos-de-análisis-de-código)
- [Servidor MCP](#servidor-mcp)
- [Despliegue en GitHub Pages](#despliegue-en-github-pages)
- [Soporte de monorepos](#soporte-de-monorepos)
- [`repoforge.yaml` - Configuración por repo](#repoforgeyaml---configuración-por-repo)
- [API de Python](#api-de-python)
- [Cómo funciona](#cómo-funciona)
- [Costo](#costo)
- [Stacks soportados](#stacks-soportados)
- [Licencia](#licencia)
- [Inspiraciones](#inspiraciones)

## Instalación

```bash
pip install repoforge-ai
```

### Extras opcionales

Algunos comandos necesitan dependencias extra. Instalá solo lo que uses:

```bash
pip install "repoforge-ai[intelligence]"  # análisis AST multi-lenguaje (tree-sitter) para `analyze`, `slice`
pip install "repoforge-ai[search]"        # índice de búsqueda semántica (faiss) para `index`/`query`
pip install "repoforge-ai[pdf]"           # ingesta de PDF para `skills-from-docs`
pip install "repoforge-ai[youtube]"       # ingesta de transcripciones de YouTube para `skills-from-docs`
pip install "repoforge-ai[all]"           # todo lo anterior
```

`ripgrep` es muy recomendable para acelerar el escaneo:

```bash
brew install ripgrep
sudo apt install ripgrep
scoop install ripgrep
```

## Resumen de comandos

### Comandos de generación (necesitan una API key de LLM)

| Comando | Qué hace |
|---|---|
| `repoforge docs` | Genera documentación técnica lista para Docsify |
| `repoforge skills` | Genera skills y agentes para herramientas de coding |
| `repoforge skills-from-docs` | Genera `SKILL.md` desde docs externas (URL, repo de GitHub, directorio local, PDF, YouTube, notebook) |
| `repoforge index` | Construye un índice de búsqueda semántica a partir de las entidades del código |

### Comandos determinísticos (sin API key)

| Comando | Qué hace |
|---|---|
| `repoforge export` | Aplana un repo en un único archivo optimizado para LLM |
| `repoforge score` | Puntúa los `SKILL.md` generados en 7 dimensiones |
| `repoforge scan` | Escanea la seguridad del markdown generado |
| `repoforge compress` | Optimiza tokens del markdown generado |
| `repoforge graph` | Construye grafos de dependencias/llamadas y vistas de radio de impacto |
| `repoforge diagram` / `diagrams` | Genera diagramas Mermaid, SVG, ERD, K8s y OpenAPI |
| `repoforge check` | Valida referencias a código en las docs generadas |
| `repoforge diff` | Diff semántico a nivel de entidad entre dos refs de git |
| `repoforge audit` | Corre todos los chequeos de análisis de una sola vez |
| `repoforge analyze` | Análisis multicapa: AST + grafo de llamadas + CFG + DFG + PDG |
| `repoforge search` | Búsqueda semántica de código por comportamiento |
| `repoforge query` | Busca en un índice ya construido |
| `repoforge blast-radius` | Radio de impacto transitivo de un cambio |
| `repoforge change-impact` | Identifica qué tests correr para un cambio |
| `repoforge co-change` | Detecta archivos que siempre cambian juntos |
| `repoforge ownership` | Calcula ownership de archivos/módulos y bus factor |
| `repoforge dead-code` | Detecta código potencialmente muerto vía análisis de grafo |
| `repoforge slice` | Program slice para una línea específica |
| `repoforge decisions` | Registro de decisiones desde el historial de git y marcadores inline |
| `repoforge context-prune` | Poda de contexto consciente del grafo para review con LLM |
| `repoforge prompts` | Genera prompts de análisis reutilizables desde un escaneo |
| `repoforge import-docs` | Importa docs de dependencias externas para enriquecer el contexto |
| `repoforge validate-skills` | Valida archivos `SKILL.md` contra el formato estándar |
| `repoforge registry` | Registro de grafos de código cross-repo (`add`/`remove`/`list`/`build`/`search`) |

Corré `repoforge <command> --help` para ver la lista completa de opciones de cualquier comando.

### Flags comunes

- `-w`, `--working-dir` / `--workspace`: ruta del repo
- `-o`, `--output` / `--output-dir`: archivo o directorio de salida
- `--model`: modelo de LLM
- `--dry-run`: solo planifica, sin llamadas al LLM
- `-q`, `--quiet`: salida más silenciosa

## Configuración del modelo

RepoForge autodetecta proveedores a partir de variables de entorno, pero la configuración explícita importa porque el comportamiento de cada proveedor NO es el mismo.

### GitHub Models

La mejor opción de baja fricción si ya usás el tooling de GitHub.

```bash
export GITHUB_TOKEN=$(gh auth token)
repoforge docs -w . --model github/gpt-4o-mini
```

Para GitHub Actions, el `GITHUB_TOKEN` incorporado no alcanza para GitHub Models. Necesitás un PAT con scope `models:read`, normalmente guardado como `GH_MODELS_TOKEN`.

### Groq

```bash
export GROQ_API_KEY=gsk_...
repoforge docs -w . --model groq/llama-3.3-70b-versatile
```

### Ollama

```bash
ollama pull qwen2.5-coder:14b
repoforge docs -w . --model ollama/qwen2.5-coder:14b
```

### Claude Haiku

```bash
export ANTHROPIC_API_KEY=sk-ant-...
repoforge docs -w . --model claude-haiku-3-5
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
repoforge docs -w . --model gpt-4o-mini
```

### Notas prácticas sobre modelos

- `github/gpt-4o-mini`: el default más fácil para docs y skills si ya usás GitHub
- `claude-haiku-3-5`: barato y normalmente suficiente para generación
- `ollama/...`: local y gratis, pero la calidad depende mucho del modelo que bajes
- `groq/...`: rápido y amigable con el free tier, pero los rate limits importan
- `gpt-4o-mini`: una base sólida si ya tenés OpenAI configurado

## Inicio rápido técnico

```bash
# Docs
repoforge docs -w /path/to/repo --lang English -o docs

# Servir docs localmente
repoforge docs -w . --serve

# Generar skills para Claude + OpenCode + Cursor + Codex
repoforge skills -w /path/to/repo --targets claude,opencode,cursor,codex

# Generar skills y de inmediato puntuarlas, escanearlas y comprimirlas
repoforge skills -w /path/to/repo --score --scan --compress

# Exportar el contexto del repo
repoforge export -w /path/to/repo -o context.md

# Construir grafo de dependencias
repoforge graph -w /path/to/repo --format mermaid

# Generar diagrama de dependencias
repoforge diagram -w /path/to/repo --type dependency

# Docs incrementales
repoforge docs -w /path/to/repo --incremental

# Solo planificar
repoforge docs -w /path/to/repo --dry-run
repoforge skills -w /path/to/repo --dry-run
```

## Comando `docs`

Genera un sitio de documentación técnica listo para Docsify, adaptado al tipo de proyecto.

| Tipo de proyecto | Capítulos típicos |
|---|---|
| Web service | Data Models, API Reference |
| Frontend SPA | Components, State Management |
| CLI tool | Commands, Configuration |
| Data science | Data Pipeline, Models and Training, Experiments |
| Library o SDK | Public API, Integration Guide |
| Mobile app | Screens and Navigation, Native Integrations |
| Infra o DevOps | Resources, Variables, Deployment Guide |
| Monorepo | Capítulos globales más subdocs por capa |

```text
repoforge docs [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: docs]
  --model TEXT              LLM model
  --lang LANGUAGE           Documentation language  [default: English]
  --name TEXT               Project name override
  --complexity LEVEL        auto|small|medium|large
  --theme THEME             vue|dark|buble|pure
  --serve                   Generate and open local docs
  --serve-only              Skip generation, serve existing docs
  --port INT                Local server port  [default: 8000]
  --chunked                 Use chunked generation mode
  --verify / --no-verify    Enable or disable Stage C verification
  --verify-model TEXT       Verification model override
  --no-verify-docs          Disable verification and deterministic corrections
  --facts-only              Emit factual extraction without prose
  --incremental             Regenerate only stale chapters
  --semantic-dedup          Skip semantically unchanged chapters in incremental mode
  --semantic-threshold FLOAT
  --watch                   Regenerate docs when files change
  --watch-interval FLOAT
  --link-style STYLE        backtick|wiki
  --diagrams                Embed Mermaid diagrams in architecture docs
  --max-workers INT         Parallel chapter workers
  --model-heavy TEXT        Heavy-tier model when --model auto
  --model-standard TEXT     Standard-tier model when --model auto
  --model-light TEXT        Light-tier model when --model auto
  --dry-run
  -q, --quiet
```

Idiomas soportados: English, Spanish, French, German, Portuguese, Chinese, Japanese, Korean, Russian, Italian, Dutch.

### Salida

Hasta 8 capítulos más el andamiaje de Docsify:

- `index.md`
- `01-overview.md`
- `02-quickstart.md`
- `03-architecture.md`
- `04-core-mechanisms.md`
- `05-data-models.md` cuando corresponde
- `06-api-reference.md` cuando corresponde
- `07-dev-guide.md`
- `index.html`, `_sidebar.md` y `.nojekyll` para Docsify y GitHub Pages

### Modo incremental

Con `--incremental`, RepoForge rastrea las dependencias de cada capítulo en un manifest y usa `git diff` para decidir qué capítulos quedaron desactualizados. Eso importa en repos grandes, porque regenerar todo es simplemente quemar tokens al pedo.

`--semantic-dedup` va un paso más allá: usa similitud de embeddings para saltear capítulos cuyo significado no cambió materialmente, aunque hayan cambiado archivos.

### Niveles de complejidad

| Nivel | Comportamiento |
|---|---|
| `auto` | Detecta a partir de la cantidad de archivos y capas |
| `small` | Menos archivos, cobertura más densa por archivo |
| `medium` | Profundidad equilibrada |
| `large` | Más resumen arquitectónico, menos ruido archivo por archivo |

### Vista previa local

```bash
repoforge docs -w . --serve
```

O serví vos mismo la carpeta generada:

```bash
python3 -m http.server 8000 --directory docs
```

## Comando `skills`

Genera artefactos `SKILL.md` y `AGENT.md` para seis targets de agentes de coding a partir de un único escaneo.

```text
repoforge skills [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: .claude]
  --model TEXT              LLM model
  --complexity LEVEL        auto|small|medium|large
  --targets TARGETS         claude|opencode|cursor|codex|gemini|copilot|all
  --disclosure MODE         tiered|full
  --with-hooks              Generate HOOKS.md
  --plugin                  Generate plugin.json + commands/
  --score                   Score skills after generation
  --compress                Compress skills after generation
  --aggressive              Stronger compression mode
  --scan                    Run security scan after generation
  --no-opencode             Skip mirror to .opencode/
  --serve                   Open skills browser
  --serve-only              Open existing skills browser
  --port INT                Browser port  [default: 8765]
  --dry-run
  -q, --quiet
```

### Targets de salida

| Target | Salida | Formato |
|---|---|---|
| `claude` | `.claude/skills/`, `.claude/agents/` | `SKILL.md` y `AGENT.md` |
| `opencode` | `.opencode/` | Espejo de la salida de Claude |
| `cursor` | `.cursor/rules/*.mdc` | Reglas de Cursor |
| `codex` | `AGENTS.md` | Instrucciones consolidadas |
| `gemini` | `GEMINI.md` | Instrucciones de Gemini CLI |
| `copilot` | `.github/copilot-instructions.md` | Instrucciones de Copilot |

También se produce la salida del registry de agent-teams-lite (`.atl/skill-registry.md`).

### Ejemplo de layout

```text
.claude/
├── skills/
│   ├── backend/SKILL.md
│   ├── backend/auth/SKILL.md
│   └── frontend/SKILL.md
├── agents/
│   ├── orchestrator/AGENT.md
│   ├── backend-agent/AGENT.md
│   └── frontend-agent/AGENT.md
├── commands/
├── plugin.json
├── HOOKS.md
├── DISCOVERY_INDEX.md
└── SKILLS_INDEX.md
```

### Cosas que vale la pena saber

- `--targets all` es la forma más rápida de producir un set de salida multi-agente completo.
- `--disclosure tiered` agrega marcadores de disclosure progresivo y archivos de índice.
- `--score --scan --compress` te deja tratar la generación de skills como un pipeline en lugar de un volcado de una sola pasada.

## Comando `export`

Aplana un repo en un único archivo apto para LLM. No requiere API key.

```text
repoforge export [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output FILE         Output file, or stdout if omitted
  --max-tokens INT          Token budget cap
  --no-contents             Tree plus definitions only
  --format FORMAT           markdown|xml
  --compress                API-surface-focused export
  -q, --quiet
```

```bash
repoforge export -w .
repoforge export -w . -o context.md
repoforge export -w . --max-tokens 100000
repoforge export -w . --no-contents
repoforge export -w . --format xml
repoforge export -w . --compress
```

## Comando `score`

Puntúa las skills generadas en 7 dimensiones: completeness, clarity, specificity, examples, format, safety y agent readiness. No requiere API key.

```text
repoforge score [OPTIONS]

  -w, --working-dir DIR     Repo root  [default: .]
  -d, --skills-dir DIR      Skills directory override
  --format FORMAT           table|json|markdown
  --min-score FLOAT         Exit 1 if a skill falls below threshold
  -q, --quiet
```

```bash
repoforge score -w .
repoforge score -w . --format json
repoforge score -w . --min-score 0.7
repoforge score -d /path/to/skills
```

## Comando `scan`

Escáner de seguridad para el markdown generado. No requiere API key. Trae 37 reglas en 5 categorías:

- prompt injection
- secretos hardcodeados
- exposición de PII
- comandos destructivos
- patrones de código inseguro

Es consciente del contexto: los ejemplos de antipatrones se degradan en lugar de tratarse igual que secretos de producción.

```text
repoforge scan [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Specific directory override
  --format FORMAT           table|json|markdown
  --allowlist IDS           Comma-separated rule IDs
  --fail-on SEVERITY        critical|high|medium|low
  -q, --quiet
```

```bash
repoforge scan -w .
repoforge scan -w . --format json
repoforge scan -w . --fail-on critical
repoforge scan -w . --allowlist SEC-020,SEC-022
repoforge scan --target-dir ./my-skills
```

## Comando `compress`

Compresión determinística de markdown para bajar el costo en tokens. No requiere API key.

Las pasadas de compresión incluyen normalización de espacios, remoción de relleno, compactación de tablas, limpieza de bloques de código, consolidación de bullets y abreviación agresiva opcional.

```text
repoforge compress [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Directory override
  --aggressive              Stronger abbreviation mode
  --dry-run                 Show compression stats only
  -q, --quiet
```

```bash
repoforge compress -w .
repoforge compress -w . --aggressive
repoforge compress -w . --dry-run
repoforge compress --target-dir ./my-skills
```

## Comando `graph`

Construye un grafo de conocimiento del código a partir de la estructura del repositorio. No requiere API key.

Soporta grafos de dependencias a nivel de archivo, grafos de llamadas a nivel de símbolo, consultas estructuradas del grafo, detección de comunidades y análisis de radio de impacto.

```text
repoforge graph [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  -o, --output FILE         Output file or stdout
  --format FORMAT           mermaid|json|dot|summary
  --type TYPE               deps|calls
  --blast-radius MODULE     Show impact of a module change
  --v2                      Use extractor-based graph builder
  --depth INT               BFS depth for v2 blast radius
  --max-files INT           Max files in blast-radius result
  --include-tests / --no-include-tests
  --query MODE              callers|callees|imports
  --symbol TEXT             Symbol for callers or callees query
  --file PATH               File path for imports query
  --communities             Detect related module clusters
  --incremental             Use file-hash graph caching
  -q, --quiet
```

```bash
repoforge graph -w .
repoforge graph -w . --format mermaid
repoforge graph -w . --format json -o graph.json
repoforge graph -w . --format dot -o graph.dot
repoforge graph -w . --blast-radius repoforge/cli.py
repoforge graph -w . --type calls
repoforge graph --query callers --symbol build_graph
repoforge graph --query imports --file repoforge/cli.py
repoforge graph -w . --communities --format summary
```

## Comando `diagram`

Genera diagramas de arquitectura a partir del código o de specs externas. No requiere API key.

```text
repoforge diagram [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  -o, --output FILE         Output file or stdout
  --type TYPE               dependency|directory|callflow|erd|k8s|openapi|svg|all
  --max-nodes INT           Dependency diagram node cap
  --max-depth INT           Directory or call-flow depth
  --entry FILE              Entry point for call-flow diagrams
  --input FILE              Required for erd, k8s, and openapi
  -q, --quiet
```

```bash
repoforge diagram -w .
repoforge diagram -w . --type dependency
repoforge diagram -w . --type callflow --entry src/main.py
repoforge diagram -w . --type erd --input schema.sql
repoforge diagram -w . --type k8s --input k8s/deployment.yaml
repoforge diagram -w . --type openapi --input openapi.json
repoforge diagram -w . --type svg -o architecture.svg
repoforge diagram -w . -o diagrams.md
```

También existe un comando `repoforge diagrams` que escribe un archivo markdown combinado con varios bloques Mermaid.

## Comandos de análisis de código

Más allá de docs y skills, RepoForge expone un conjunto de comandos de análisis de código determinísticos (sin API key salvo que se indique). Sirven para planificar refactors, delimitar el alcance de un review y hacer arqueología del código.

```bash
# Análisis multicapa: AST + grafo de llamadas + CFG + DFG + PDG (necesita el extra [intelligence])
repoforge analyze -w .

# Radio de impacto transitivo de un cambio
repoforge blast-radius -w . --files repoforge/cli.py

# Qué tests correr para un cambio
repoforge change-impact -w .

# Archivos que siempre cambian juntos
repoforge co-change -w .

# Ownership y bus factor
repoforge ownership -w .

# Código potencialmente muerto vía análisis de grafo
repoforge dead-code -w .

# Program slice para una línea específica
repoforge slice -w . --file repoforge/cli.py --line 100

# Registro de decisiones desde el historial de git y marcadores inline
repoforge decisions -w .

# Poda de contexto consciente del grafo para review con LLM
repoforge context-prune -w . --files repoforge/cli.py

# Búsqueda semántica de código por comportamiento
repoforge search -w . "where do we validate the API key"

# Correr todos los chequeos de análisis de una sola vez
repoforge audit -w .
```

Para trabajo cross-repo, `repoforge registry` mantiene un registro de repositorios y te deja hacer `add`, `remove`, `list`, `build` y `search` de grafos en todos ellos.

## Servidor MCP

RepoForge trae un servidor MCP (Model Context Protocol) que expone su análisis determinístico a agentes compatibles con MCP. Provee estas tools:

- `repoforge_generate_docs`
- `repoforge_score`
- `repoforge_graph`
- `repoforge_scan`
- `repoforge_drift`

más recursos de contexto (documentación generada, `LLMs.txt`, el grafo de conocimiento del código, los scores de calidad y la superficie de API pública).

Agregalo a la configuración de tu cliente MCP (por ejemplo `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "repoforge": {
      "command": "uv",
      "args": ["--directory", "/path/to/repoforge", "run", "python", "-m", "repoforge.mcp_server"]
    }
  }
}
```

## Despliegue en GitHub Pages

RepoForge incluye un workflow de docs con modos de deploy seguros. El default es solo-generar. Ese es el default correcto, porque pisar un sitio de Pages existente sería una jugada de amateur.

### Modos de deploy

| Modo | Comportamiento |
|---|---|
| `none` | Solo genera docs, no publica |
| `auto` | Si no existe un sitio en vivo, deploya en la raíz de Pages; si no, deploya en un subpath |
| `main` | Fuerza el deploy en la raíz de Pages |
| `subpath` | Publica bajo `/<prefix>/` en `gh-pages` preservando los archivos existentes |

### Paso a paso: setup seguro de GitHub Pages

1. Copiá o reutilizá `.github/workflows/docs.yml` en tu repositorio.
2. Creá un PAT de GitHub con scope `models:read`.
3. Guardá ese PAT como el secret de repositorio `GH_MODELS_TOKEN`.
4. Decidí si querés solo-generar, deploy en raíz o deploy en subpath.
5. Si querés publicar, definí variables de repositorio:
   - `REPOFORGE_DOCS_DEPLOY_MODE=auto` o `main` o `subpath`
   - `REPOFORGE_DOCS_CONFIRM_DEPLOY=true`
   - opcional `REPOFORGE_DOCS_SUBPATH_PREFIX=docs`
6. Revisá la configuración de GitHub Pages:
   - para `main`: Pages debería usar GitHub Actions
   - para `subpath`: Pages debería deployar desde la rama `gh-pages` en `/ (root)`
7. Pusheá a `main`, o disparalo con `workflow_dispatch` pasando `deploy_mode`, `confirm_deploy` y `subpath_prefix`.
8. Abrí la URL publicada que reporta el resumen del workflow.

### Configuración de Pages requerida por modo

| `deploy_mode` | Mecanismo de despliegue | Configuración de Pages requerida |
|---|---|---|
| `none` | Solo genera | Cualquiera |
| `main` | `actions/deploy-pages@v4` | GitHub Actions |
| `subpath` | `peaceiris/actions-gh-pages@v4` con `keep_files` | Deploy desde la rama `gh-pages` |
| `auto` | Elige `main` o `subpath` | Debe coincidir con el target real |

### Ejemplo: agregar docs sin romper un sitio de Pages existente

```bash
gh variable set REPOFORGE_DOCS_DEPLOY_MODE --body "auto" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_CONFIRM_DEPLOY --body "true" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_SUBPATH_PREFIX --body "docs" --repo youruser/yourrepo
gh secret set GH_MODELS_TOKEN --repo youruser/yourrepo
```

Si tu repo ya sirve `https://youruser.github.io/yourrepo/`, el modo auto va a preferir un deploy preservado en subpath cuando detecte un sitio en vivo existente.

### Usar la GitHub Action reutilizable

RepoForge también trae una action compuesta (`action.yml`). Cuando la referencias desde otro workflow, fijá un tag publicado en lugar de `@main` para que los workflows aguas abajo queden reproducibles:

```yaml
uses: JNZader/repoforge@v0.6.0  # fijá un tag publicado — mirá la página de Releases
```

### Flujo manual de Pages

Sigue soportado si no querés el workflow:

```bash
repoforge docs -w . -o docs --lang English
git add docs
git commit -m "docs: generate documentation"
git push
```

Después configurá GitHub Pages para servir `/docs` desde `main` si ese es el modelo que elegiste.

## Soporte de monorepos

RepoForge autodetecta las capas y genera docs jerárquicas.

```text
docs/
├── index.md
├── 01-overview.md
├── 03-architecture.md
├── 06b-service-map.md
├── frontend/
│   ├── index.md
│   ├── 05-components.md
│   └── 06-state.md
└── backend/
    ├── index.md
    ├── 05-data-models.md
    └── 06-api-reference.md
```

Eso significa que obtenés una vista de arquitectura global más capítulos específicos por capa, en vez de una única pared de prosa aplanada e inútil.

## `repoforge.yaml` - Configuración por repo

Creá `repoforge.yaml` en la raíz del repo para sobrescribir los defaults.

```yaml
# Core identity
project_name: "My App"
project_type: web_service
language: English

# Model selection
model: github/gpt-4o-mini

# If you want per-tier routing, set model: auto and configure tiers
models:
  heavy: claude-haiku-3-5
  standard: github/gpt-4o-mini
  light: github/gpt-4o-mini

# Generation depth
complexity: auto
disclosure: tiered

# Multi-tool output
targets: [claude, opencode, cursor, codex]
generate_hooks: true
generate_plugin: true

# Monorepo layer overrides
layers:
  frontend: apps/web
  backend: apps/api
  shared: packages/shared

# Docs generation defaults
parallel:
  max_workers: 4

# Optional chapter-level customization
pages:
  - file: "03-architecture.md"
    sections:
      - type: intro
        order: 1
        content: "This project follows a layered architecture."
      - type: diagram
        enabled: true
        order: 2
      - type: custom
        title: "Deployment Notes"
        order: 3
        content: "Production deploys through GitHub Actions."

# Optional project-type template overrides
templates:
  - name: "custom-web-service"
    project_type: web_service
    chapters:
      - file: "08-ops.md"
        title: "Operations"
        description: "Runbooks, observability, and deployment notes"
        prompt_key: dev_guide
        order: 80
```

### Notas sobre el comportamiento de la config

- Los flags de CLI ganan sobre los valores de config.
- Si `model` no es `auto`, se usa el mismo modelo para los tiers heavy, standard y light.
- Si `model: auto`, RepoForge lee `models.heavy`, `models.standard` y `models.light`.
- `targets` puede ser una lista YAML y mapea directo a la salida multi-herramienta.
- `pages` personaliza secciones dentro de los capítulos generados.
- `templates` te deja sobrescribir o extender los templates de capítulos por tipo de proyecto.

## API de Python

RepoForge no es solo un wrapper de CLI. Podés llamar la librería subyacente directamente.

```python
from repoforge import (
    generate_artifacts,
    generate_docs,
    export_llm_view,
    SkillScorer,
    SkillCompressor,
    SecurityScanner,
    scan_generated_output,
    build_graph,
    build_graph_from_workspace,
    build_graph_v2,
    get_blast_radius_v2,
    generate_dependency_diagram,
    generate_directory_diagram,
    generate_call_flow_diagram,
    generate_all_diagrams,
    Manifest,
    ChapterEntry,
    load_manifest,
    save_manifest,
    get_changed_files,
    build_chapter_deps,
    get_stale_chapters,
    DependencyHealthReport,
    analyze_dependency_health,
    CoverageReport,
    auto_detect_and_parse,
    render_coverage_markdown,
    adapt_for_cursor,
    adapt_for_codex,
    adapt_for_gemini,
    adapt_for_copilot,
    resolve_targets,
    ALL_TARGETS,
)

# Generate skills and agents
generate_artifacts(
    working_dir="/path/to/repo",
    output_dir=".claude",
    model="github/gpt-4o-mini",
    targets="claude,cursor,codex",
    complexity="auto",
    with_hooks=True,
    with_plugin=True,
    disclosure="tiered",
    compress=True,
)

# Generate documentation
generate_docs(
    working_dir="/path/to/repo",
    output_dir="docs",
    model="claude-haiku-3-5",
    language="English",
    complexity="auto",
    incremental=True,
    embed_diagrams=True,
)

# Export repo context
context = export_llm_view(
    workspace="/path/to/repo",
    output_path="context.md",
    max_tokens=100000,
    fmt="markdown",
)

# Score skills
scorer = SkillScorer()
scores = scorer.score_directory(".claude/skills")
print(scorer.report(scores, fmt="table"))

# Scan generated output
scan_result = scan_generated_output("/path/to/repo")
scanner = SecurityScanner()
print(scanner.report(scan_result, fmt="table"))

# Graph and blast radius
graph = build_graph_from_workspace("/path/to/repo")
print(graph.to_mermaid())
graph_v2 = build_graph_v2("/path/to/repo")
blast = get_blast_radius_v2(graph_v2, "repoforge/cli.py")

# Diagrams
print(generate_dependency_diagram(graph_v2, max_nodes=40))

# Incremental docs helpers
manifest = load_manifest("docs")
changed = get_changed_files("/path/to/repo")

# Dependency health and coverage
health = analyze_dependency_health("/path/to/repo")
reports = auto_detect_and_parse("/path/to/repo")
markdown = render_coverage_markdown(reports)
```

### Áreas de la API que vale la pena conocer

- generación de docs: `generate_docs`
- generación de skills: `generate_artifacts`
- exportación del repo: `export_llm_view`
- escaneo y scoring: `SecurityScanner`, `SkillScorer`
- análisis de grafo: `build_graph_from_workspace`, `build_graph_v2`, `get_blast_radius_v2`
- diagramas: `generate_dependency_diagram`, `generate_all_diagrams`
- docs incrementales: helpers de manifest y de capítulos desactualizados
- adaptadores: `adapt_for_cursor`, `adapt_for_codex`, `adapt_for_gemini`, `adapt_for_copilot`

## Cómo funciona

```text
1. SCAN     (deterministic)  Detect stack, layers, files, symbols, and structure
2. PLAN     (deterministic)  Choose chapters, rank modules, route by complexity
3. GENERATE (LLM)            Produce prose for docs or skills
4. ADAPT    (deterministic)  Convert output to Cursor, Codex, Gemini, Copilot, OpenCode formats
5. ENRICH   (deterministic)  Add scans, compression, plugin manifests, diagrams, dependency health, coverage
6. WRITE                     Emit Docsify docs, skills, agents, exports, and reports
```

Distinción importante: el LLM genera el texto, pero el análisis estructural, el grafo, el scoring, el escaneo, el parseo de coverage y la generación de diagramas son determinísticos.

## Costo

El único paso pago es la generación de texto por LLM (`docs`, `skills`, `skills-from-docs`, `index`). Todos los demás comandos son gratis de correr.

| Modelo | Costo |
|---|---|
| GitHub Models | Gratis con el setup de token correcto |
| Groq | Free tier, con rate limit |
| Ollama | Runtime local gratis |
| Claude Haiku 3.5 / GPT-4o-mini | Costo bajo por corrida |
| Claude Sonnet / modelos más grandes | Costo más alto por corrida |

El costo real depende del tamaño del repo, la cantidad de capítulos y el pricing del modelo. Usá `--dry-run` para ver el plan de generación antes de gastar tokens.

## Stacks soportados

Escaneo agnóstico del lenguaje, con análisis profundo a nivel de AST (el pipeline `analyze`/`slice`) en 13 lenguajes: Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust, Ruby, PHP, C, C++, C# y Swift.

Los extractores de grafo (`graph --v2`, radio de impacto) cubren un subconjunto central — Python, TypeScript, JavaScript, Go, Java y Rust — más monorepos mixtos.

## Licencia

MIT

## Inspiraciones

- [CodeViewX](https://github.com/dean2021/codeviewx)
- [Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills)
- [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [repomix](https://github.com/yamadashy/repomix)
- [rendergit](https://github.com/nicobytes/rendergit)
- [aider](https://github.com/Aider-AI/aider)
- [semgrep](https://github.com/semgrep/semgrep)

# Skill Discovery Index


> Load this file FIRST. Then load full skills only when needed.
> Each skill supports tiered loading: L1 (discovery) → L2 (quick ref) → L3 (full).

| Name | Description | Trigger | Complexity | ~Tokens | Priority | Path |
|------|-------------|---------|------------|---------|----------|------|
| backend-layer | The backend layer (apps/server) owns the FastAPI server, asy… |  | low | 350 | high | `backend/SKILL.md` |
| add-auth-endpoints | >- Implements GitHub OAuth login/callback and JWT validation… | when auth routes are needed | low | 340 | high | `backend/auth/SKILL.md` |
| encrypt-api-keys | This skill covers AES-256-GCM encryption for provider API ke… | Load this skill when handling crypto operations fo… | — | 462 | — | `backend/crypto/SKILL.md` |
| manage-database-session | This skill covers patterns for managing database sessions an… | Load when working with database interactions | — | 537 | — | `backend/database/SKILL.md` |
| start-generation | This skill covers the generation routes for starting, stream… | When generating content | — | 457 | — | `backend/generate/SKILL.md` |
| add-generation-event | This skill covers the creation and management of Generation … | When working with generation data in the backend | — | 571 | — | `backend/generation/SKILL.md` |
| exchange-github-oauth-code | This skill covers the implementation of GitHub OAuth helper … | Load this skill when handling GitHub OAuth process… | — | 487 | — | `backend/github_oauth/SKILL.md` |
| configure-main-middleware | Sets up core FastAPI middleware and health endpoints for the… | when the `main` FastAPI app is initialized | low | 350 | high | `backend/main/SKILL.md` |
| add-schemas-model | Pydantic v2 schemas for RepoForge API requests and responses… | when working with schemas in the backend | low | 350 | high | `backend/schemas/SKILL.md` |
| example-layer | This layer encapsulates the core business logic for the exam… | When working in example/ — adding, modifying, or d… | — | 376 | — | `build_modules/SKILL.md` |
| build-graph-context | Generates concise graph‑based context for LLM prompts. | when graph_context is needed for code analysis | low | 350 | high | `build_modules/graph_context/SKILL.md` |
| add-harness-modules | Provides patterns to generate module scaffolds and evaluate … | when working with the `harness` module in eval lay… | low | 350 | high | `build_modules/harness/SKILL.md` |
| add-incremental-manifest | Manage incremental build state for repoforge projects. | when working with incremental manifests | low | 350 | high | `build_modules/incremental/SKILL.md` |
| frontend-layer | The frontend layer owns the React UI, routing, and client‑si… | When working in frontend/ directory — adding, modi… | low | 1200 | high | `frontend/SKILL.md` |
| manage-api | Provides patterns for robust API interaction in the frontend… | load when any `api` function or hook is imported | low | 350 | high | `frontend/api/SKILL.md` |
| add-auth-provider | Patterns for integrating authentication context in a React f… | when auth utilities are imported or used | low | 340 | high | `frontend/auth/SKILL.md` |
| add-types-definitions | Provides core TypeScript type definitions for generation wor… | when working with `types` in the web frontend | low | 350 | high | `frontend/types/SKILL.md` |
| usegenerationstream-hook | This skill covers patterns for managing generation streams i… | Load when using `useGenerationStream` for state ma… | — | 519 | — | `frontend/useGenerationStream/SKILL.md` |
| main-layer | This layer encompasses the core functionality of the project… | When working in main/ — adding, modifying, or debu… | — | 481 | — | `main/SKILL.md` |
| add-cli-options | This skill covers the creation of shared options for CLI com… | When defining command-line interfaces using the `c… | — | 381 | — | `main/cli/SKILL.md` |
| get-chapter-prompts | This skill covers the generation of chapter prompts for docu… | When integrating shared system prompts in document… | — | 498 | — | `main/docs_prompts/SKILL.md` |
| add-harness-parent-path | This skill covers adding the parent directory to the path wh… | When using the harness module in a standalone cont… | — | 469 | — | `main/harness/SKILL.md` |
| add-prompts-endpoint | This skill covers the integration of various prompt types in… | When working with prompts in the application | — | 368 | — | `main/prompts/SKILL.md` |
| check-ripgrep-availability | This skill covers patterns for checking the availability of … | When verifying if ripgrep is installed and accessi… | — | 364 | — | `main/ripgrep/SKILL.md` |
| add-scenarios-real-endpoint | This skill covers adding endpoints for scenarios in the real… | When integrating new functionality into the scenar… | — | 375 | — | `main/scenarios_real/SKILL.md` |
| test-adapters-strip-yaml-frontmatter | This skill covers testing the _strip_yaml_frontmatter helper… | test_adapters | — | 365 | — | `main/test_adapters/SKILL.md` |
| test-compressor-fixtures | This skill covers patterns for creating fixtures to test com… | Load this skill when working with test_compressor | — | 465 | — | `main/test_compressor/SKILL.md` |
| mock-repomaps-fixtures | This skill covers patterns for mocking RepoMaps in tests. | Load this skill when working with test_graph fixtu… | — | 496 | — | `main/test_graph/SKILL.md` |
| test-plugins-build-commands | This skill covers testing plugins for various repository typ… | Load this skill when working with test_plugins | — | 433 | — | `main/test_plugins/SKILL.md` |
| add-test-ripgrep-endpoint | This skill covers adding endpoints for user management in th… | When implementing user management features in the … | — | 538 | — | `main/test_ripgrep/SKILL.md` |
| add-test-scorer-endpoint | This skill covers patterns for creating and managing test sc… | Load this skill when working with the test_scorer … | — | 450 | — | `main/test_scorer/SKILL.md` |
| test-security-fixtures | This skill covers patterns for testing security using crafte… | Load this skill when working with test_security sc… | — | 422 | — | `main/test_security/SKILL.md` |

**Total skills**: 32
**Index tokens**: ~1535

## How to Use

1. Scan this index to find relevant skills by trigger or description
2. Load the skill at L1 or L2 level first (if tiered markers present)
3. Only load full L3 content when you need deep examples or anti-patterns


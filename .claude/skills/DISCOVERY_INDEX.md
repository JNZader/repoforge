# Skill Discovery Index


> Load this file FIRST. Then load full skills only when needed.
> Each skill supports tiered loading: L1 (discovery) → L2 (quick ref) → L3 (full).

| Name | Description | Trigger | Complexity | ~Tokens | Priority | Path |
|------|-------------|---------|------------|---------|----------|------|
| backend-layer | Python FastAPI backend layer for RepoForge Web. Handles HTTP… | When working in backend/ directory and its main re… | — | 816 | — | `backend/SKILL.md` |
| add-auth-routes | Authentication routes: GitHub OAuth login/callback, JWT vali… | when initializing auth layer in FastAPI applicatio… | — | 1477 | — | `backend/auth/SKILL.md` |
| encrypt-api-keys | This skill covers AES-256-GCM encryption for provider API ke… | Load this skill when handling crypto operations fo… | — | 462 | — | `backend/crypto/SKILL.md` |
| manage-database-session | This skill covers patterns for managing database sessions an… | Load when working with database interactions | — | 537 | — | `backend/database/SKILL.md` |
| start-generation | This skill covers the generation routes for starting, stream… | When generating content | — | 457 | — | `backend/generate/SKILL.md` |
| add-generation-event | This skill covers the creation and management of Generation … | When working with generation data in the backend | — | 571 | — | `backend/generation/SKILL.md` |
| exchange-github-oauth-code | This skill covers the implementation of GitHub OAuth helper … | Load this skill when handling GitHub OAuth process… | — | 487 | — | `backend/github_oauth/SKILL.md` |
| add-main-endpoints | Middleware and health endpoints for RepoForge Web applicatio… | when initializing or extending the FastAPI main ap… | low | 450 | high | `backend/main/SKILL.md` |
| add-schemas-endpoint | Pydantic v2 request/response schemas for RepoForge Web API. | when defining or validating schemas in apps/server… | low | 450 | high | `backend/schemas/SKILL.md` |
| build_modules-layer | Builds and evaluates Python module layers for the Gentleman-… | When working in `build_modules/` — adding, modifyi… | — | 730 | — | `build_modules/SKILL.md` |
| add-graph-context-endpoint | Build and format graph context for codebase analysis. | When loading graph_context module for codebase ana… | medium | 1200 | high | `build_modules/graph_context/SKILL.md` |
| extend-harness-module | Add parent directory to path when running eval scripts direc… | when executing eval/harness | — | 933 | — | `build_modules/harness/SKILL.md` |
| add-incremental-endpoint | Incremental data model operations for chapter dependencies a… | incremental or manifest operations | — | 549 | — | `build_modules/incremental/SKILL.md` |
| frontend-layer | Frontend layer for the Gentleman-Skills project. Handles the… |  | — | 1039 | — | `frontend/SKILL.md` |
| add-api-endpoint | Centralized API client for the web frontend with React Query… | when fetching or mutating data from the backend AP… | medium | 450 | high | `frontend/api/SKILL.md` |
| add-auth-endpoint | Adding authentication endpoints and managing auth state acro… | when adding new auth-protected routes or API calls | — | 443 | — | `frontend/auth/SKILL.md` |
| add-types-endpoint | Type-safe frontend types for generation workflows and SSE ev… | when adding new generation types or SSE events to … | — | 609 | — | `frontend/types/SKILL.md` |
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
**Index tokens**: ~1542

## How to Use

1. Scan this index to find relevant skills by trigger or description
2. Load the skill at L1 or L2 level first (if tiered markers present)
3. Only load full L3 content when you need deep examples or anti-patterns


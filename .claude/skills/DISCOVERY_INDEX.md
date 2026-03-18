# Skill Discovery Index


> Load this file FIRST. Then load full skills only when needed.
> Each skill supports tiered loading: L1 (discovery) → L2 (quick ref) → L3 (full).

| Name | Description | Trigger | Complexity | ~Tokens | Priority | Path |
|------|-------------|---------|------------|---------|----------|------|
| backend-layer | This layer provides the backend functionality for the RepoFo… | When working in backend/ — adding, modifying, or d… | — | 524 | — | `backend/SKILL.md` |
| add-auth-endpoint | This skill covers the implementation of authentication route… | When setting up auth-related endpoints in the back… | — | 490 | — | `backend/auth/SKILL.md` |
| encrypt-api-keys | This skill covers AES-256-GCM encryption for provider API ke… | Load this skill when handling crypto operations fo… | — | 462 | — | `backend/crypto/SKILL.md` |
| manage-database-session | This skill covers patterns for managing database sessions an… | Load when working with database interactions | — | 537 | — | `backend/database/SKILL.md` |
| start-generation | This skill covers the generation routes for starting, stream… | When generating content | — | 457 | — | `backend/generate/SKILL.md` |
| add-generation-event | This skill covers the creation and management of Generation … | When working with generation data in the backend | — | 571 | — | `backend/generation/SKILL.md` |
| exchange-github-oauth-code | This skill covers the implementation of GitHub OAuth helper … | Load this skill when handling GitHub OAuth process… | — | 487 | — | `backend/github_oauth/SKILL.md` |
| add-main-endpoint | This skill covers adding main endpoints to the FastAPI appli… | When setting up the main entry point for the appli… | — | 523 | — | `backend/main/SKILL.md` |
| define-request-response-schemas | This skill covers the creation of Pydantic v2 request and re… | Load this skill when defining schemas for the Repo… | — | 488 | — | `backend/schemas/SKILL.md` |
| frontend-layer | This layer manages the user interface and user experience of… | When working in frontend/ — adding, modifying, or … | — | 510 | — | `frontend/SKILL.md` |
| fetch-api-data | This skill covers patterns for fetching and managing API dat… | When working with API interactions in the frontend | — | 566 | — | `frontend/api/SKILL.md` |
| use-auth-provider | This skill covers patterns for implementing authentication i… | Load this skill when managing user authentication | — | 474 | — | `frontend/auth/SKILL.md` |
| generate-request-types | This skill covers the creation and management of generation … | Load this skill when working with types related to… | — | 460 | — | `frontend/types/SKILL.md` |
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

**Total skills**: 28
**Index tokens**: ~1368

## How to Use

1. Scan this index to find relevant skills by trigger or description
2. Load the skill at L1 or L2 level first (if tiered markers present)
3. Only load full L3 content when you need deep examples or anti-patterns


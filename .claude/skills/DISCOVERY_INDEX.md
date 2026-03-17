# Skill Discovery Index


> Load this file FIRST. Then load full skills only when needed.
> Each skill supports tiered loading: L1 (discovery) → L2 (quick ref) → L3 (full).

| Name | Description | Trigger | Complexity | ~Tokens | Priority | Path |
|------|-------------|---------|------------|---------|----------|------|
| main-layer | This layer encompasses the core functionality and utilities … | When working in main/ — adding, modifying, or debu… | — | 449 | — | `main/SKILL.md` |
| add-cli-options | This skill covers the creation of shared options for CLI com… | When defining command-line interfaces using the `c… | — | 381 | — | `main/cli/SKILL.md` |
| get-chapter-prompts | This skill covers the generation of chapter prompts for docu… | Load this skill when working with docs_prompts | — | 454 | — | `main/docs_prompts/SKILL.md` |
| add-harness-parent-path | This skill covers adding the parent directory to the path wh… | When utilizing the harness module in a direct exec… | — | 487 | — | `main/harness/SKILL.md` |
| add-prompts-endpoint | This skill covers the integration of various prompt types in… | When working with prompts in the application | — | 368 | — | `main/prompts/SKILL.md` |
| check-ripgrep-availability | This skill covers patterns for checking the availability of … | When verifying if ripgrep is installed and accessi… | — | 364 | — | `main/ripgrep/SKILL.md` |
| add-scenarios-real-endpoint | This skill covers adding endpoints for scenarios in the real… | When integrating new functionality into the scenar… | — | 375 | — | `main/scenarios_real/SKILL.md` |
| test-adapters-strip-yaml-frontmatter | This skill covers testing the _strip_yaml_frontmatter helper… | test_adapters | — | 384 | — | `main/test_adapters/SKILL.md` |
| add-test-ripgrep-endpoint | This skill covers adding endpoints for user management in th… | When implementing user-related features in the tes… | — | 537 | — | `main/test_ripgrep/SKILL.md` |
| add-test-scorer-endpoint | This skill covers patterns for implementing scoring function… | Load this skill when working with the test_scorer … | — | 448 | — | `main/test_scorer/SKILL.md` |

**Total skills**: 10
**Index tokens**: ~540

## How to Use

1. Scan this index to find relevant skills by trigger or description
2. Load the skill at L1 or L2 level first (if tiered markers present)
3. Only load full L3 content when you need deep examples or anti-patterns


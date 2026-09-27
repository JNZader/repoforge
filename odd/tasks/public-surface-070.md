# Public surface 0.7.0

## Objective
Make the published docs, landing page, composite action text, and package metadata match what 0.7.0 actually is.

## Problem
PyPI `repoforge-ai` 0.7.0 has an empty Author field. README (EN/ES), the live landing, and `action.yml` still tell people to use GitHub Models and pin `v0.6.0`. GitHub Models was retired on 2026-07-30.

## Scope
- `pyproject.toml` author name
- `.github/workflows/publish.yml` project URL
- `README.md`, `README.es.md`
- `landing/index.html`
- `action.yml` descriptions and default model
- web form: drop the dead provider, the extra target, and the language the CLI rejects

## Out of scope
Server-side `github-models` validator and `AUTO_DETECT_ORDER` still know that provider. Removing them is a behavior change with its own tests.

## Checklist
- [x] Author metadata is Javier Zader, no email
- [x] Publish environment URL is `/project/repoforge-ai/`
- [x] Public copy no longer presents GitHub Models as a working free tier
- [x] Action pin example is `v0.7.0`
- [x] Landing badge is `v0.7.0` and target count is 6
- [x] Web form languages match the CLI list and targets match `ALL_TARGETS`

## Verification
`pytest tests/test_mcp_contract.py`: 2 passed, 1 skipped (MCP 2 runtime). Live site https://repoforge.javierzader.com/ still serves the previous landing until this branch reaches main and Deploy Pages runs. PyPI 0.7.0 keeps the README that was uploaded with that release until the next publish.

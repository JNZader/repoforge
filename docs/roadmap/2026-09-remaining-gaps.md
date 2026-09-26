# Remaining gaps

Two cuts left from the March 2026 roadmap. Everything else in that plan stays closed: it already exists in another shape, or it is a different product. The generation-truth plan is done. This file is what comes next.

## What these cuts close

1. `--incremental` regenerates a global chapter only when a file that entered its prompt changed.
2. A chapter that invents a port, endpoint, table, or env var gets one repair. If the repair still invents, the chapter is not written.

## Cuts

Both cuts are on `roadmap/generation-truth`. The checks run in CI without an API key. R1 does not call a model. R2 calls a fake model.

### R1 — Record the files the prompt actually used

`build_chapter_deps` gives `index.md`, `01-overview.md`, `02-quickstart.md`, `03-architecture.md`, and `07-dev-guide.md` every scanned file. The first manifest write stores that list. The next `--incremental` run treats the list as truth, so any change marks those chapters stale.

**Change:** when a chapter is generated, `source_files` in the manifest is the scanned paths cited in that chapter's graph context (`context_source`), not every path in the module catalog. The catalog lists every scanned file and would recreate the all-files guess. `recorded_consumed_files` still decides staleness from the stored list. A chapter regenerated on this run stores the paths its current graph context cites.

**Check:** `pytest tests/test_incremental.py`. A monorepo fixture with `apps/server/app/main.py` and `apps/web/src/lib/api.ts` gives overview a graph context that cites only the server file. The consumed list for `01-overview.md` is `apps/server/app/main.py`. Changing the web file does not mark overview stale. Changing the server file does.

**Status:** done on `roadmap/generation-truth`. `pytest tests/test_incremental.py tests/test_factuality.py tests/test_docs.py` — 79 passed.

### R2 — One repair after the factuality gate

`invented_claim_block` refuses the write. The chapter is then gone. `docs --verify` is a second model pass and does not see the invented-claim list. The March refinement loop (generate, score, rewrite, repeat until a threshold) is not this cut.

**Change:** when the block fires, call the model once. The prompt contains the rejected prose, the invented claims, and the extracted facts. Run `invented_claim_block` on the reply. If it is clean, write that reply. If it still invents, return the chapter error and do not write. The call count is one. There is no third try and no score threshold.

**Check:** `pytest tests/test_factuality.py` with a fake model. A reply that replaces port `8080` with the extracted `7437` is written. A reply that still says `8080` is not written. The fake model is called once in each case. No network.

**Status:** done on `roadmap/generation-truth`. The fake model in `tests/test_factuality.py` is called once. A reply that says `7437` is writable. A reply that still says `8080` returns the factuality error and is not written. A chapter that is already clean does not call the model.

## Out of scope

HTML, PDF, RST, and Docusaurus renderers. A persona package. LSP, a VS Code extension, and watch mode. Migration and security generators. A style enforcer, a review bot, and profiles. A TUI, telemetry, and the htmx dashboard. A DAG orchestrator, per-tag docs, compliance docs, and planner/reviewer agents. Homebrew and a plugin marketplace. Rewriting LiteLLM into a new `llm/` package. An AST chunker. Chunking waits until a real `docs` run shows the prompt is mostly function bodies. That measurement is not a cut in this plan.

## Order

R1, then R2. Opening a pull request for `roadmap/generation-truth` can happen after R2, or before it if the five generation-truth commits need a review boundary. A pull request does not replace either cut.

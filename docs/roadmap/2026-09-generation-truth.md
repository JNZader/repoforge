# Generation truth

`repoforge docs` and `repoforge skills` must describe the repo they scanned. The structural claims in that prose (ports, endpoints, tables, env vars, and which module imports which) have to match the facts and the file graph. A new command does not move that.

This is the plan to fulfill. The March 2026 wave list in `ROADMAP.md` is research history.

## What "functional" means

1. On a mixed Python/TypeScript tree, `docs` builds a graph that links internal app imports, including a package that does not sit at the repo root.
2. A factuality check fails when a chapter names a port, endpoint, table, or env var that the scanner did not extract, and passes when it names the one that was extracted.
3. The README and the MCP tool list describe the commands that actually run.

`analyze` staying a regex sketch is acceptable. Pretending it is a compiler is not.

## Already on other branches

Do not redo these. They are not this plan.

| Branch | What it is |
|---|---|
| `feat/graph-json-identity` | Optional identity fields on the v2 JSON graph |
| `fix/faiss-missing-contract` | FAISS-absent behavior of `index` |
| `fix/cli-search-test-contract` | CLI search import contract |
| `fix/ruff-safe-autofix` and `refactor/ruff-policy-cleanup-slice-3` | Lint policy |

## Cuts

Each cut is one branch, one work unit, and a check that can fail in CI without an API key. Start the next cut only after the previous check is green.

### S1 — The importer's language and package root

`pipeline/context.py` already feeds `build_graph_v2` to every docs run. Two resolution bugs make that context wrong:

- `from app.config` is looked up as `app/config.py` at the repo root. In this repo the file is `apps/server/app/config.py`, so the whole server has no edges. Files that only import third-party packages stay unlinked on purpose. `apps/web/src/lib/api.ts` → `./types` already links.
- A relative import tries every extension (`.ts`, `.py`, `.go`, `.java`, `.rs`). `./foo` from a TypeScript file can bind to `foo.py`.

**Change:** `repoforge/extractors/resolver.py`.

- Python absolute imports match a path whose segments end in the dotted module. Among several matches, pick the one that shares the longest directory prefix with the importer. If two matches tie, resolve nothing.
- Relative extension and index search stay inside the importer's language. The existing `.js` → `.ts` fallback stays for TypeScript and JavaScript.

**Check:** `pytest tests/test_extractors/test_resolver.py tests/test_graph_v2.py`. A graph built from `apps/server/app/main.py` importing `app.config`, with a decoy `apps/other/app/config.py`, edges only to `apps/server/app/config.py`. A TypeScript `./foo` with both `foo.ts` and `foo.py` edges to `foo.ts`.

**Status:** done on `roadmap/generation-truth`. `pytest tests/test_extractors/test_resolver.py tests/test_graph_v2.py` — 72 passed. The full-repo orphan count is not the gate: a file that only imports third-party packages stays unlinked.

### S2 — Signatures in the chapter context

The `[intelligence]` extra already parses signatures with tree-sitter. Python, TypeScript, and Go stay on regex even when that extra is installed. The chapter should see the real signature (name, parameters, route), not the function body.

**Change:** the structured graph context used by `docs`, behind the extra. Without the extra, keep today's regex and do not claim AST coverage.

**Check:** a fixture prompt for one Python route and one TypeScript function contains the signature text from the source file. No network.

**Status:** done on `roadmap/generation-truth`. `pytest tests/test_signature_context.py` — passed. `format_api_surface` keeps route decorators on the signature line (`@app.get("/health")` plus `def health(...)`). Without the intelligence extra the section stays empty and is not labeled as AST. The regex symbol extractor is unchanged.

### S3 — Factuality check

`eval/harness.py` scores skill shape (trigger, concreteness, patterns, multi-language). With no LLM it scores a fake paragraph. `post_process.py` rewrites a hardcoded list of ports (`8080`, `3000`, `5000`, `8000`, `4000`, `9090`). Neither one checks that the chapter agrees with the extracted facts.

**Change:** a pure function from facts plus markdown to a list of invented and missing values for `port`, `endpoint`, `db_table`, and `env_var`. Call it from the harness as its own score. Keep the port rewrite, but it is no longer the quality gate.

**Check:** markdown that says `8080` fails when the only port fact is `7437`. Markdown that says `7437` passes. No live model in CI.

**Status:** done on `roadmap/generation-truth`. `pytest tests/test_factuality.py` — 12 passed. The checker lives in `repoforge/factuality.py`. `eval/harness.py` appends a `factuality` score only when the caller passes the facts for that chapter. The port rewrite in `post_process.py` is unchanged.

### S4 — Say what the product does

**Change:** README and `mcp_server.py` module doc.

- `skills-from-docs` is a template. It does not spend an API key.
- `analyze` and `slice` do not need the `[intelligence]` extra. They are regex. The extra is the tree-sitter symbol path.
- The "up to 8x" line in `context_pruning.py` stays out of the README until something measures tokens.
- The MCP tools a client can call are `score`, `graph`, `changelog`, `drift`, `analyze`, `context`.

**Check:** a test asserts the names `list_tools` returns. The README sections above match those names and the cost table.

### S5 — Stale chapters

Only after S3 is green. Regenerating a false chapter faster is not a product.

**Change:** given a set of changed paths and the file list each chapter consumed, mark those chapters stale. Do not regenerate them in this cut.

**Check:** changing `apps/server/app/main.py` marks the chapter that included it, and leaves the others current.

## Out of scope

CFG, DFG, and PDG. New CLI commands. Packing parity with Repomix. A hosted wiki. The March waves 8 through 18.

## Order

S1, then S2 and S3 in either order, then S4, then S5. S4 can land earlier if a release is going out and the text is still wrong. It does not unblock S1.

# CI image for javi-forge's python runner (build-context target).
#
# javi-forge runs each CI phase in a fresh `docker run --rm` container, so a
# `setup:` install does not persist into the lint/test phases. Baking the
# project's third-party dependencies into the image here is what makes the
# lint/test phases able to import `repoforge` and its deps.
#
# The repo is bind-mounted at /home/runner/work at run time, so the package
# *code* comes from the live checkout (PYTHONPATH below makes it importable);
# only the deps need to live in the image.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Base tools the javi-forge python image would otherwise provide.
RUN pip install --no-cache-dir pytest ruff pylint poetry

# Runtime + intelligence deps required by repoforge and its AST symbol
# extractors (tree-sitter / tree-sitter-language-pack).
RUN pip install --no-cache-dir \
    "litellm>=1.82.6,!=1.82.8" \
    click \
    pyyaml \
    "mcp>=1.26.0" \
    tree-sitter \
    tree-sitter-language-pack

# Make the bind-mounted checkout importable as the `repoforge` package.
ENV PYTHONPATH=/home/runner/work

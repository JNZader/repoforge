FROM python:3.12-slim

WORKDIR /app

# Install system deps for tree-sitter compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Install repoforge with all extras
COPY pyproject.toml .
COPY repoforge/ repoforge/
RUN pip install --no-cache-dir -e ".[all]"

ENTRYPOINT ["repoforge"]
CMD ["--help"]

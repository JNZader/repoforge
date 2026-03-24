#!/usr/bin/env bash
set -euo pipefail

# Build script for Cloudflare Pages
# Replicates .github/workflows/deploy-pages.yml assembly logic
# Output: _site/ (landing + React dashboard + docs)

echo "==> Installing dependencies..."
npm ci --prefix apps/web

echo "==> Building React app..."
npm run build --prefix apps/web

echo "==> Assembling _site/..."
rm -rf _site
mkdir -p _site _site/app

# 1. Landing page → _site/ root
if [ -f landing/index.html ]; then
  cp landing/index.html _site/
fi
if [ -f landing/favicon.svg ]; then
  cp landing/favicon.svg _site/
fi

# 2. React dashboard → _site/app/
if [ -d apps/web/dist ]; then
  cp -r apps/web/dist/* _site/app/
else
  echo "WARNING: apps/web/dist not found — skipping app"
fi

# 3. Docs → _site/docs/ (if docs/ has content)
if [ -d docs ] && [ "$(ls -A docs/ 2>/dev/null)" ]; then
  mkdir -p _site/docs
  cp -r docs/* _site/docs/
fi

# 4. Prevent Jekyll processing
touch _site/.nojekyll

echo "==> Done! Output in _site/"
echo "    Contents:"
ls -la _site/

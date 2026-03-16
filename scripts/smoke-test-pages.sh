#!/usr/bin/env bash
# ============================================================
# RepoForge — Smoke test for safe Pages deploy modes
# ============================================================
#
# Validates that RepoForge docs workflow doesn't break an
# existing GitHub Pages site when using deploy_mode=auto.
#
# Usage:
#   ./scripts/smoke-test-pages.sh <owner/repo>
#
# Prerequisites:
#   - gh CLI authenticated
#   - Target repo must have GitHub Pages enabled with live content
#   - Target repo must have GH_MODELS_TOKEN secret configured
#
# What it does:
#   1. Snapshots existing Pages root (HTTP status + content hash)
#   2. Copies docs workflow to target repo
#   3. Triggers workflow with deploy_mode=auto, confirm_deploy=true
#   4. Waits for completion
#   5. Re-checks Pages root (must be unchanged)
#   6. Reports results
#
# The script is NON-DESTRUCTIVE to the main Pages site.
# Subpath content is deployed to gh-pages branch only.

set -euo pipefail

# --- Args ---
TARGET="${1:?Usage: $0 <owner/repo>}"
PREFIX="repoforge-smoke-$(date +%Y%m%d%H%M%S)"
OWNER="${TARGET%%/*}"
REPO="${TARGET##*/}"
PAGES_URL="https://${OWNER}.github.io/${REPO}/"

echo "============================================"
echo "RepoForge Smoke Test — Safe Pages Deploy"
echo "============================================"
echo "Target:  ${TARGET}"
echo "Prefix:  ${PREFIX}"
echo "URL:     ${PAGES_URL}"
echo ""

# --- Step 1: Snapshot existing Pages ---
echo "Step 1: Snapshot existing Pages root..."
BEFORE_HTTP=$(curl -sS -o /dev/null -w "%{http_code}" "${PAGES_URL}" || echo "000")
BEFORE_HASH=""
if [ "${BEFORE_HTTP}" = "200" ]; then
  BEFORE_HASH=$(curl -sS "${PAGES_URL}" | sha256sum | cut -d' ' -f1)
fi
echo "  HTTP: ${BEFORE_HTTP}"
echo "  Hash: ${BEFORE_HASH:-N/A}"
echo ""

if [ "${BEFORE_HTTP}" != "200" ]; then
  echo "WARNING: Pages root is not live (HTTP ${BEFORE_HTTP})."
  echo "         This test is most useful on repos with existing Pages content."
  echo "         Continuing anyway..."
  echo ""
fi

# --- Step 2: Trigger docs workflow ---
echo "Step 2: Triggering docs workflow (deploy_mode=auto)..."

# Check if workflow exists
if ! gh workflow list --repo "${TARGET}" | grep -q "Generate Docs"; then
  echo "ERROR: No 'Generate Docs' workflow found in ${TARGET}."
  echo "       Add .github/workflows/docs.yml first."
  exit 1
fi

gh workflow run docs.yml \
  --repo "${TARGET}" \
  --ref main \
  -f deploy_mode=auto \
  -f confirm_deploy=true \
  -f subpath_prefix="${PREFIX}"

echo "  Triggered. Waiting for run to appear..."
sleep 8

# --- Step 3: Find and watch run ---
echo "Step 3: Watching workflow run..."
RUN_ID=$(gh run list --repo "${TARGET}" --workflow docs.yml --limit 1 --json databaseId --jq '.[0].databaseId')

if [ -z "${RUN_ID}" ]; then
  echo "ERROR: Could not find workflow run."
  exit 1
fi

echo "  Run ID: ${RUN_ID}"
echo "  URL:    https://github.com/${TARGET}/actions/runs/${RUN_ID}"
echo ""

gh run watch "${RUN_ID}" --repo "${TARGET}" --exit-status || {
  echo ""
  echo "FAIL: Workflow run failed."
  echo "Check logs: gh run view ${RUN_ID} --repo ${TARGET} --log-failed"
  exit 1
}

# --- Step 4: Verify existing Pages unchanged ---
echo ""
echo "Step 4: Verify existing Pages root unchanged..."
AFTER_HTTP=$(curl -sS -o /dev/null -w "%{http_code}" "${PAGES_URL}" || echo "000")
AFTER_HASH=""
if [ "${AFTER_HTTP}" = "200" ]; then
  AFTER_HASH=$(curl -sS "${PAGES_URL}" | sha256sum | cut -d' ' -f1)
fi
echo "  HTTP: ${AFTER_HTTP}"
echo "  Hash: ${AFTER_HASH:-N/A}"
echo ""

# --- Step 5: Report ---
echo "============================================"
echo "Results"
echo "============================================"
echo "  Before: HTTP=${BEFORE_HTTP} Hash=${BEFORE_HASH:-N/A}"
echo "  After:  HTTP=${AFTER_HTTP}  Hash=${AFTER_HASH:-N/A}"
echo ""

PASS=true

if [ "${BEFORE_HTTP}" = "200" ] && [ "${AFTER_HTTP}" != "200" ]; then
  echo "FAIL: Pages root went from 200 to ${AFTER_HTTP}!"
  PASS=false
fi

if [ -n "${BEFORE_HASH}" ] && [ -n "${AFTER_HASH}" ] && [ "${BEFORE_HASH}" != "${AFTER_HASH}" ]; then
  echo "FAIL: Pages root content changed!"
  echo "  Before hash: ${BEFORE_HASH}"
  echo "  After hash:  ${AFTER_HASH}"
  PASS=false
fi

if [ "${PASS}" = "true" ]; then
  echo "PASS: Existing Pages site is unchanged."
  echo ""
  echo "Subpath URL (may need gh-pages source config):"
  echo "  ${PAGES_URL}${PREFIX}/"
fi

echo ""
echo "Workflow run: https://github.com/${TARGET}/actions/runs/${RUN_ID}"
echo "============================================"

if [ "${PASS}" = "false" ]; then
  exit 1
fi

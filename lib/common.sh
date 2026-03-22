#!/bin/bash
# =============================================================================
# lib/common.sh - Shared functions for project-starter-framework
# =============================================================================
# Source from scripts:   source "$(dirname "$0")/../lib/common.sh"
# Source from ci-local:  source "$(dirname "$0")/../lib/common.sh"
# Source from hooks:     source "$(dirname "$0")/../../lib/common.sh"
# =============================================================================

# Guard against double-sourcing
if [[ -n "${_COMMON_SH_LOADED:-}" ]]; then
    return 0 2>/dev/null || true
fi
_COMMON_SH_LOADED=1

# =============================================================================
# Colors (exported for callers via source)
# =============================================================================
# shellcheck disable=SC2034
RED='\033[0;31m'
# shellcheck disable=SC2034
GREEN='\033[0;32m'
# shellcheck disable=SC2034
YELLOW='\033[1;33m'
# shellcheck disable=SC2034
CYAN='\033[0;36m'
# shellcheck disable=SC2034
BLUE='\033[0;34m'
# shellcheck disable=SC2034
NC='\033[0m'

# =============================================================================
# Shared logging helpers
# =============================================================================
log_ok()   { echo -e "  ${GREEN}[OK]${NC}   $1"; }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
log_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "  ${CYAN}[INFO]${NC} $1"; }
log_step() { echo -e "${YELLOW}$1${NC}"; }

# =============================================================================
# sed_inplace - Portable sed -i (works on both GNU and BSD/macOS sed)
# =============================================================================
# Usage: sed_inplace "s/foo/bar/" file.txt
# =============================================================================
sed_inplace() {
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

# =============================================================================
# escape_sed - Escape special characters for safe use in sed replacement
# =============================================================================
# Usage: escaped=$(escape_sed "$raw_string")
# Note: This escapes replacement-side characters (backslash, ampersand, slash).
# =============================================================================
escape_sed() {
    printf '%s\n' "$1" | sed -e 's/[\\&/]/\\&/g'
}

# =============================================================================
# backup_if_exists - Create a .bak copy of a file before overwriting
# =============================================================================
# Usage: backup_if_exists "path/to/file"
# =============================================================================
backup_if_exists() {
    local file="$1"
    if [[ -f "$file" ]]; then
        cp "$file" "${file}.bak"
        echo -e "${YELLOW}  Backed up existing ${file}${NC}"
    fi
}

# =============================================================================
# detect_stack - Auto-detect project technology stack
# =============================================================================
# Sets: STACK_TYPE, BUILD_TOOL, JAVA_VERSION
# Detects: java-gradle, java-maven, node, python, go, rust
#
# Usage:
#   detect_stack                  # Detects from current directory
#   detect_stack "/path/to/project"  # Detects from given directory
#
# NOTE: Does NOT set LINT_CMD/COMPILE_CMD/TEST_CMD. Those are CI-specific
#       and should be configured by the caller (e.g., ci-local.sh).
# =============================================================================
# shellcheck disable=SC2034  # STACK_TYPE, BUILD_TOOL, JAVA_VERSION used by callers
detect_stack() {
    local project_dir="${1:-.}"

    STACK_TYPE="unknown"
    BUILD_TOOL=""
    JAVA_VERSION="21"

    # Java + Gradle
    if [[ -f "$project_dir/build.gradle" || -f "$project_dir/build.gradle.kts" ]]; then
        STACK_TYPE="java-gradle"
        BUILD_TOOL="gradle"

        # Detect Java version from build files (compatible with macOS and Linux)
        if [[ -f "$project_dir/build.gradle.kts" ]]; then
            JAVA_VERSION=$(grep -E 'languageVersion\s*=\s*JavaLanguageVersion\.of\(' "$project_dir/build.gradle.kts" 2>/dev/null | grep -o '[0-9]\+' | head -1 || echo "21")
        elif [[ -f "$project_dir/build.gradle" ]]; then
            JAVA_VERSION=$(grep -E 'sourceCompatibility\s*=' "$project_dir/build.gradle" 2>/dev/null | grep -o '[0-9]\+' | head -1 || echo "21")
        fi
        [[ -z "$JAVA_VERSION" ]] && JAVA_VERSION="21"
        return
    fi

    # Java + Maven
    if [[ -f "$project_dir/pom.xml" ]]; then
        STACK_TYPE="java-maven"
        BUILD_TOOL="maven"
        return
    fi

    # Node.js
    if [[ -f "$project_dir/package.json" ]]; then
        STACK_TYPE="node"
        if [[ -f "$project_dir/pnpm-lock.yaml" ]]; then
            BUILD_TOOL="pnpm"
        elif [[ -f "$project_dir/yarn.lock" ]]; then
            BUILD_TOOL="yarn"
        else
            BUILD_TOOL="npm"
        fi
        return
    fi

    # Python (detection order: uv > poetry > pipenv > pip)
    if [[ -f "$project_dir/pyproject.toml" || -f "$project_dir/setup.py" || -f "$project_dir/requirements.txt" ]]; then
        STACK_TYPE="python"
        if [[ -f "$project_dir/uv.lock" ]]; then
            BUILD_TOOL="uv"
        elif [[ -f "$project_dir/poetry.lock" ]]; then
            BUILD_TOOL="poetry"
        elif [[ -f "$project_dir/Pipfile" ]]; then
            BUILD_TOOL="pipenv"
        else
            BUILD_TOOL="pip"
        fi
        return
    fi

    # Go
    if [[ -f "$project_dir/go.mod" ]]; then
        STACK_TYPE="go"
        BUILD_TOOL="go"
        return
    fi

    # Rust
    if [[ -f "$project_dir/Cargo.toml" ]]; then
        STACK_TYPE="rust"
        BUILD_TOOL="cargo"
        return
    fi
}

# =============================================================================
# detect_framework - Locate the project-starter-framework directory
# =============================================================================
# Sets: FRAMEWORK_DIR (path to framework root, or empty string)
#       HAS_OPTIONAL  (true/false if optional/ dir exists)
#
# Usage: detect_framework
# =============================================================================
# shellcheck disable=SC2034  # FRAMEWORK_DIR, HAS_OPTIONAL used by callers
detect_framework() {
    FRAMEWORK_DIR=""
    HAS_OPTIONAL=false
    if [[ -d "templates" && -d ".ai-config" ]]; then
        FRAMEWORK_DIR="."
    elif [[ -d "../templates" && -d "../.ai-config" ]]; then
        FRAMEWORK_DIR=".."
    fi
    if [[ -n "$FRAMEWORK_DIR" && -d "$FRAMEWORK_DIR/optional" ]]; then
        HAS_OPTIONAL=true
    fi
}

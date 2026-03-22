#!/bin/bash
# =============================================================================
# CI-LOCAL: Universal CI Simulation for Any Project
# =============================================================================
# Detecta automáticamente: Java/Gradle, Java/Maven, Node, Python, Go, Rust
#
# Uso:
#   ./ci-local.sh              # CI completo
#   ./ci-local.sh quick        # Solo lint + compile
#   ./ci-local.sh shell        # Shell interactivo en entorno CI
#   ./ci-local.sh detect       # Mostrar stack detectado
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source shared library for colors and detect_stack
source "$SCRIPT_DIR/../lib/common.sh"

# =============================================================================
# CI COMMAND SETUP (extends shared detect_stack with CI-specific commands)
# =============================================================================
setup_ci_commands() {
    # detect_stack is from lib/common.sh - sets STACK_TYPE, BUILD_TOOL, JAVA_VERSION
    detect_stack

    DOCKERFILE=""
    LINT_CMD=""
    COMPILE_CMD=""
    TEST_CMD=""

    case "$STACK_TYPE" in
        java-gradle)
            DOCKERFILE="java.Dockerfile"
            LINT_CMD="./gradlew spotlessCheck --no-daemon"
            COMPILE_CMD="./gradlew classes testClasses --no-daemon"
            TEST_CMD="./gradlew test --no-daemon"
            ;;
        java-maven)
            DOCKERFILE="java.Dockerfile"
            LINT_CMD="./mvnw spotless:check"
            COMPILE_CMD="./mvnw compile test-compile"
            TEST_CMD="./mvnw test"
            ;;
        node)
            DOCKERFILE="node.Dockerfile"
            LINT_CMD="$BUILD_TOOL run lint"
            COMPILE_CMD="$BUILD_TOOL run build"
            TEST_CMD="$BUILD_TOOL test"
            ;;
        python)
            DOCKERFILE="python.Dockerfile"
            LINT_CMD="ruff check . && { pylint **/*.py 2>/dev/null || true; }"
            COMPILE_CMD=""
            TEST_CMD="pytest"
            ;;
        go)
            DOCKERFILE="go.Dockerfile"
            LINT_CMD="golangci-lint run"
            COMPILE_CMD="go build ./..."
            TEST_CMD="go test ./..."
            ;;
        rust)
            DOCKERFILE="rust.Dockerfile"
            LINT_CMD="cargo clippy -- -D warnings"
            COMPILE_CMD="cargo build"
            TEST_CMD="cargo test"
            ;;
        *)
            DOCKERFILE=""
            ;;
    esac
}

# Check if GHAGGA is available on the host
GHAGGA_AVAILABLE=false
if command -v ghagga >/dev/null 2>&1; then
    GHAGGA_AVAILABLE=true
fi

# =============================================================================
# DOCKER
# =============================================================================
get_image_name() {
    echo "ci-local-$STACK_TYPE"
}

create_dockerfile() {
    local docker_dir="$SCRIPT_DIR/docker"
    mkdir -p "$docker_dir"

    case "$STACK_TYPE" in
        java-gradle|java-maven)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
ARG JAVA_VERSION=21
FROM eclipse-temurin:${JAVA_VERSION}-jdk-noble
RUN apt-get update && apt-get install -y git curl unzip && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENV GRADLE_USER_HOME=/home/runner/.gradle
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
        node)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
FROM node:22-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN npm install -g pnpm
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
        python)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
FROM python:3.12-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pytest ruff pylint poetry
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
        go)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
FROM golang:1.23-bookworm
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN go install github.com/golangci/golangci-lint/cmd/golangci-lint@v1.62.0 && \
    mv /root/go/bin/golangci-lint /usr/local/bin/
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
        rust)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
FROM rust:1.83-slim
RUN apt-get update && apt-get install -y git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
RUN rustup component add clippy rustfmt
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
        *)
            cat > "$docker_dir/$DOCKERFILE" << 'DOCKERFILE'
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash runner
USER runner
WORKDIR /home/runner/work
ENTRYPOINT ["/bin/bash", "-c"]
DOCKERFILE
            ;;
    esac

    echo -e "${GREEN}Created $DOCKERFILE${NC}"
}

ensure_docker_image() {
    local image_name
    image_name=$(get_image_name)
    local dockerfile="$SCRIPT_DIR/docker/$DOCKERFILE"

    # Create Dockerfile if it does not exist yet
    if [[ ! -f "$dockerfile" ]]; then
        echo -e "${YELLOW}Creating Dockerfile for $STACK_TYPE...${NC}"
        create_dockerfile
    fi

    # Detect staleness: rebuild if the Dockerfile content has changed since last build
    local current_hash
    current_hash=$(sha256sum "$dockerfile" 2>/dev/null | cut -d' ' -f1)
    local image_hash
    image_hash=$(docker inspect --format='{{index .Config.Labels "dockerfile-hash"}}' "$image_name" 2>/dev/null || echo "")

    if [[ "$current_hash" != "$image_hash" ]]; then
        echo -e "${YELLOW}Building CI Docker image...${NC}"
        local -a build_args=("--label" "dockerfile-hash=$current_hash")
        if [[ -n "$JAVA_VERSION" && "$STACK_TYPE" == java-* ]]; then
            build_args+=("--build-arg" "JAVA_VERSION=$JAVA_VERSION")
        fi
        docker build "${build_args[@]}" -f "$dockerfile" -t "$image_name" "$SCRIPT_DIR/docker"
    fi
}

run_in_ci() {
    local image_name
    image_name=$(get_image_name)
    local -a docker_flags=(--rm)
    if [ -t 0 ]; then
        docker_flags+=(-it)
    fi
    local timeout="${CI_LOCAL_TIMEOUT:-600}"
    # Validate timeout is a positive integer
    if ! [[ "$timeout" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: CI_LOCAL_TIMEOUT must be a positive integer, got: $timeout${NC}"
        exit 1
    fi
    docker run "${docker_flags[@]}" \
        --stop-timeout 30 \
        -v "$PROJECT_DIR:/home/runner/work" \
        -e CI=true \
        "$image_name" timeout "$timeout" bash -c "$1"
}

# =============================================================================
# MAIN
# =============================================================================
echo -e "\n${YELLOW}=== CI-LOCAL ===${NC}"

setup_ci_commands

if [[ "$STACK_TYPE" == "unknown" ]]; then
    echo -e "${RED}Could not detect project type!${NC}"
    echo -e "${YELLOW}Supported: Java/Gradle, Java/Maven, Node, Python, Go, Rust${NC}"
    exit 1
fi

echo -e "${GREEN}Detected: $STACK_TYPE ($BUILD_TOOL)${NC}"
if [[ "$STACK_TYPE" == java-* ]]; then
    echo -e "${GREEN}Java version: $JAVA_VERSION${NC}"
fi

MODE="${1:-full}"

case "$MODE" in
    detect)
        echo -e "\n${CYAN}Stack details:${NC}"
        echo "  Type: $STACK_TYPE"
        echo "  Build tool: $BUILD_TOOL"
        echo "  Dockerfile: $DOCKERFILE"
        echo "  Lint: $LINT_CMD"
        echo "  Compile: $COMPILE_CMD"
        echo "  Test: $TEST_CMD"
        exit 0
        ;;

    quick)
        ensure_docker_image
        echo -e "\n${YELLOW}Running quick check...${NC}"

        if [[ -n "$LINT_CMD" ]]; then
            echo -e "${CYAN}Lint: $LINT_CMD${NC}"
            run_in_ci "cd /home/runner/work && $LINT_CMD"
        fi
        if [[ -n "$COMPILE_CMD" ]]; then
            echo -e "${CYAN}Compile: $COMPILE_CMD${NC}"
            run_in_ci "cd /home/runner/work && $COMPILE_CMD"
        fi
        ;;

    shell)
        ensure_docker_image
        echo -e "\n${YELLOW}Opening shell in CI environment...${NC}"
        image_name=$(get_image_name)
        docker run --rm -it \
            -v "$PROJECT_DIR:/home/runner/work" \
            -e CI=true \
            "$image_name" "cd /home/runner/work && bash"
        ;;

    full|*)
        ensure_docker_image
        echo -e "\n${YELLOW}Running full CI simulation...${NC}"

        step=1
        total=0
        [[ -n "$LINT_CMD" ]] && total=$((total + 1))
        [[ -n "$COMPILE_CMD" ]] && total=$((total + 1))
        [[ -n "$TEST_CMD" ]] && total=$((total + 1))
        if $GHAGGA_AVAILABLE; then total=$((total + 1)); fi

        if [[ -n "$LINT_CMD" ]]; then
            echo -e "\n${YELLOW}Step $step/$total: Lint${NC}"
            echo -e "  ${CYAN}$LINT_CMD${NC}"
            run_in_ci "cd /home/runner/work && $LINT_CMD"
            step=$((step + 1))
        fi

        if [[ -n "$COMPILE_CMD" ]]; then
            echo -e "\n${YELLOW}Step $step/$total: Compile${NC}"
            echo -e "  ${CYAN}$COMPILE_CMD${NC}"
            run_in_ci "cd /home/runner/work && $COMPILE_CMD"
            step=$((step + 1))
        fi

        if [[ -n "$TEST_CMD" ]]; then
            echo -e "\n${YELLOW}Step $step/$total: Test${NC}"
            echo -e "  ${CYAN}$TEST_CMD${NC}"
            run_in_ci "cd /home/runner/work && $TEST_CMD"
            step=$((step + 1))
        fi

        if $GHAGGA_AVAILABLE; then
            echo -e "\n${YELLOW}Step $step/$total: GHAGGA Review${NC}"
            echo -e "  ${CYAN}ghagga review --plain --exit-on-issues${NC}"
            if ! ghagga review --plain --exit-on-issues; then
                echo -e "${RED}GHAGGA review found issues!${NC}"
                exit 1
            fi
            step=$((step + 1))
        fi
        ;;
esac

echo -e "\n${GREEN}CI Local completed successfully!${NC}"
echo -e "${GREEN}  Safe to push - CI should pass.${NC}\n"

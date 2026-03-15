"""
eval/scenarios_real.py - Eval scenarios based on actual consorcio-canalero code.

These scenarios use real module data extracted from the repo so we can test
prompt quality against known patterns:
  - FastAPI + Supabase auth pattern (require_admin_or_operator dependency)
  - GEE integration (Google Earth Engine, long timeouts, celery tasks)
  - Frontend hooks + Zustand store pattern
  - Cross-layer: TypeScript types consumed by React + referenced by FastAPI schemas
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repoforge.prompts import skill_prompt, layer_skill_prompt, agent_prompt

# ---------------------------------------------------------------------------
# Real module snapshots (extracted from the actual repo)
# ---------------------------------------------------------------------------

REPO_MAP_CONSORCIO = {
    "root": "/consorcio-canalero",
    "tech_stack": [
        "Python", "Node.js", "React", "Vite", "Mantine UI",
        "Leaflet", "Zustand", "Supabase", "FastAPI", "Celery",
        "Google Earth Engine", "Redis", "Docker",
    ],
    "entry_points": ["gee-backend/app/main.py"],
    "config_files": [
        "docker-compose.yml", "docker-compose.prod.yml",
        "gee-backend/requirements.txt", "consorcio-web/package.json",
        "Makefile", "fly.toml",
    ],
    "layers": {
        "frontend": {
            "path": "consorcio-web/src",
            "modules": [
                {
                    "path": "consorcio-web/src/lib/api/reports.ts",
                    "name": "reports",
                    "language": "TypeScript",
                    "exports": ["reportsApi"],
                    "imports": ["./core", "../../types"],
                    "summary_hint": "Reports API module - Reports management and public reports.",
                },
                {
                    "path": "consorcio-web/src/hooks/useAuth.ts",
                    "name": "useAuth",
                    "language": "TypeScript",
                    "exports": ["useAuth", "UseAuthState"],
                    "imports": ["zustand", "@supabase/supabase-js", "../stores/authStore", "../lib/auth"],
                    "summary_hint": "Unified authentication hook for React components.",
                },
                {
                    "path": "consorcio-web/src/hooks/useGEELayers.ts",
                    "name": "useGEELayers",
                    "language": "TypeScript",
                    "exports": ["useGEELayers"],
                    "imports": ["react", "../lib/api/layers"],
                    "summary_hint": "Hook for managing Google Earth Engine layer state.",
                },
                {
                    "path": "consorcio-web/src/lib/api/core.ts",
                    "name": "core",
                    "language": "TypeScript",
                    "exports": [
                        "API_URL", "API_PREFIX", "DEFAULT_TIMEOUT", "LONG_TIMEOUT",
                        "GEE_TIMEOUT", "HEALTH_TIMEOUT", "getAuthToken", "apiFetch",
                    ],
                    "imports": ["../supabase"],
                    "summary_hint": "Core API module - Base fetch function, auth token handling, API configuration.",
                },
            ],
        },
        "backend": {
            "path": "gee-backend/app",
            "modules": [
                {
                    "path": "gee-backend/app/api/v1/endpoints/reports.py",
                    "name": "reports",
                    "language": "Python",
                    "exports": [
                        "router", "ReportStatus", "ReportPriority", "ReportUpdate",
                        "ReportAssign", "ResolveStatus", "ResolvePayload",
                        "ResolveReportRequest", "get_reports", "get_reports_stats",
                        "get_report", "update_report", "assign_report", "resolve_report",
                    ],
                    "imports": ["fastapi", "pydantic", "app.services.supabase_service", "app.auth"],
                    "summary_hint": "Reports Endpoints. Gestion de denuncias ciudadanas (admin).",
                },
                {
                    "path": "gee-backend/app/auth.py",
                    "name": "auth",
                    "language": "Python",
                    "exports": [
                        "User", "TokenPayload", "get_jwks", "get_signing_key_from_jwks",
                        "decode_jwt_header", "verify_supabase_token", "get_user_role",
                        "get_current_user", "get_current_user_required", "require_roles",
                        "require_admin", "require_admin_or_operator", "require_authenticated",
                    ],
                    "imports": ["fastapi", "jose", "pydantic", "httpx", "app.config"],
                    "summary_hint": "Authentication module. Implements JWT verification using Supabase tokens. Supports HS256 and ES256.",
                },
                {
                    "path": "gee-backend/app/services/gee_service.py",
                    "name": "gee_service",
                    "language": "Python",
                    "exports": [
                        "initialize_gee", "get_gee_layers", "get_sentinel2_tiles",
                        "get_flood_detection", "get_ndvi_tiles",
                    ],
                    "imports": ["ee", "app.config"],
                    "summary_hint": "Google Earth Engine Service. Provides access to GEE assets and satellite imagery.",
                },
                {
                    "path": "gee-backend/app/services/supabase_service.py",
                    "name": "supabase_service",
                    "language": "Python",
                    "exports": [
                        "get_supabase_service", "SupabaseService",
                        "get_reports", "get_report", "update_report",
                        "get_sugerencias", "create_sugerencia",
                    ],
                    "imports": ["httpx", "app.config"],
                    "summary_hint": "Supabase service for database operations via REST API.",
                },
            ],
        },
    },
    "stats": {"total_files": 261, "rg_available": False},
}


# Convenience shortcuts
FRONTEND_LAYER = REPO_MAP_CONSORCIO["layers"]["frontend"]
BACKEND_LAYER = REPO_MAP_CONSORCIO["layers"]["backend"]


def get_reports_backend_module():
    return BACKEND_LAYER["modules"][0], REPO_MAP_CONSORCIO

def get_auth_backend_module():
    return BACKEND_LAYER["modules"][1], REPO_MAP_CONSORCIO

def get_gee_service_module():
    return BACKEND_LAYER["modules"][2], REPO_MAP_CONSORCIO

def get_useauth_frontend_module():
    return FRONTEND_LAYER["modules"][1], REPO_MAP_CONSORCIO

def get_api_core_frontend_module():
    return FRONTEND_LAYER["modules"][3], REPO_MAP_CONSORCIO


# ---------------------------------------------------------------------------
# Scenario registry (plug into harness)
# ---------------------------------------------------------------------------

REAL_SCENARIOS = {
    "consorcio_reports_endpoint": lambda: ("module", *get_reports_backend_module()),
    "consorcio_auth_module":      lambda: ("module", *get_auth_backend_module()),
    "consorcio_gee_service":      lambda: ("module", *get_gee_service_module()),
    "consorcio_useauth_hook":     lambda: ("module", *get_useauth_frontend_module()),
    "consorcio_api_core":         lambda: ("module", *get_api_core_frontend_module()),
    "consorcio_backend_layer":    lambda: ("layer", "backend", BACKEND_LAYER, REPO_MAP_CONSORCIO),
    "consorcio_frontend_layer":   lambda: ("layer", "frontend", FRONTEND_LAYER, REPO_MAP_CONSORCIO),
}


# ---------------------------------------------------------------------------
# Quick preview: print the prompts that would be sent to the LLM
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="consorcio_reports_endpoint")
    parser.add_argument("--show-prompt", action="store_true")
    args = parser.parse_args()

    scenario_fn = REAL_SCENARIOS.get(args.scenario)
    if not scenario_fn:
        print(f"Unknown scenario. Available: {list(REAL_SCENARIOS)}")
        sys.exit(1)

    kind, *rest = scenario_fn()

    if kind == "module":
        module, repo_map = rest
        layer_name = "backend" if "gee-backend" in module["path"] else "frontend"
        system, user = skill_prompt(module, layer_name, repo_map)
        print(f"\n=== SKILL prompt for: {module['path']} ===")
        if args.show_prompt:
            print("\n--- SYSTEM ---")
            print(system[:600] + "...")
            print("\n--- USER ---")
            print(user)
    elif kind == "layer":
        layer_name, layer, repo_map = rest
        system, user = layer_skill_prompt(layer_name, layer, repo_map)
        print(f"\n=== LAYER SKILL prompt for: {layer_name} ===")
        if args.show_prompt:
            print("\n--- SYSTEM ---")
            print(system[:600] + "...")
            print("\n--- USER ---")
            print(user)

    print("\n✅ Scenario loaded OK. Pass --show-prompt to see the full prompt.")
    print(f"   Run with LLM: python -m eval.harness --model claude-haiku-3-5")

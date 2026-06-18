"""
CareerOS Backend — Lokal Smoke Test
Kør: python smoke_test.py (med aktiv .env og Supabase)

Tester:
  1. Backend starter (health check)
  2. Alle kritiske imports
  3. Config indlæses korrekt
  4. Supabase-forbindelsen kan etableres
  5. Alle Sprint 1 API-routes er registreret
"""
import sys
import os

# Sæt arbejdsmappe til backend-roden så .env findes
os.chdir(os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


def check(label: str, fn):
    try:
        result = fn()
        print(f"  {PASS} {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  {FAIL} {label} — {e}")
        return False


def main():
    errors = 0
    print("\n══════════════════════════════════════")
    print("  CareerOS Smoke Test")
    print("══════════════════════════════════════\n")

    # 1. Python version
    print("── Python ──────────────────────────────")
    v = sys.version_info
    if v >= (3, 12):
        print(f"  {PASS} Python {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"  {FAIL} Python {v.major}.{v.minor} — kræver 3.12+")
        errors += 1

    # 2. Kritiske imports
    print("\n── Imports ─────────────────────────────")
    imports = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("supabase", "supabase"),
        ("litellm", "litellm"),
        ("pdfplumber", "pdfplumber"),
        ("docx", "python-docx"),
        ("cryptography.fernet", "cryptography"),
        ("pydantic_settings", "pydantic-settings"),
        ("sse_starlette", "sse-starlette"),
    ]
    for module, pkg in imports:
        ok = check(f"import {pkg}", lambda m=module: __import__(m))
        if not ok:
            errors += 1

    # 3. App config
    print("\n── Config ──────────────────────────────")
    try:
        from app.core.config import settings
        print(f"  {PASS} Config indlæst")
        print(f"       DEBUG={settings.debug}")
        print(f"       SUPABASE_URL={settings.supabase_url}")
        has_openai = bool(settings.openai_api_key)
        has_anthropic = bool(settings.anthropic_api_key)
        if has_openai:
            print(f"  {PASS} OPENAI_API_KEY konfigureret")
        elif has_anthropic:
            print(f"  {PASS} ANTHROPIC_API_KEY konfigureret")
        else:
            print(f"  {WARN} Ingen AI-nøgle konfigureret — LLM-kald vil fejle")
            errors += 1

        if settings.encryption_key:
            print(f"  {PASS} ENCRYPTION_KEY konfigureret")
        else:
            print(f"  {FAIL} ENCRYPTION_KEY mangler")
            errors += 1
    except Exception as e:
        print(f"  {FAIL} Config fejl: {e}")
        errors += 1

    # 4. Supabase forbindelse
    print("\n── Supabase ────────────────────────────")
    try:
        from app.core.deps import get_supabase_admin
        db = get_supabase_admin()
        # Simpel tabel-forespørgsel (fejler hvis DB ikke kører)
        result = db.table("user_profiles").select("count", count="exact").limit(0).execute()
        print(f"  {PASS} Supabase forbundet")
    except Exception as e:
        print(f"  {FAIL} Supabase forbindelsesfejl: {e}")
        print(f"       Sørg for at `supabase start` er kørt")
        errors += 1

    # 5. FastAPI app + routes
    print("\n── API Routes ──────────────────────────")
    try:
        from app.main import app
        routes = {r.path for r in app.routes}

        expected = [
            "/api/v1/cv/upload",
            "/api/v1/cv/master",
            "/api/v1/discovery/start",
            "/api/v1/profile/experiences",
            "/api/v1/profile/skills",
            "/api/v1/profile/score",
            "/health",
        ]
        for path in expected:
            found = any(path in r for r in routes)
            if found:
                print(f"  {PASS} {path}")
            else:
                print(f"  {FAIL} {path} — IKKE REGISTRERET")
                errors += 1
    except Exception as e:
        print(f"  {FAIL} App-import fejl: {e}")
        errors += 1

    # 6. Sprint 1 services
    print("\n── Services ────────────────────────────")
    services = [
        ("CVService", "app.services.cv_service", "CVService"),
        ("ExperienceService", "app.services.experience_service", "ExperienceService"),
        ("DiscoveryService", "app.services.discovery_service", "DiscoveryService"),
        ("ProfileCompletenessService", "app.services.profile_completeness_service", "ProfileCompletenessService"),
        ("CVAgent", "app.agents.cv_agent", "CVAgent"),
    ]
    for label, module, cls in services:
        try:
            import importlib
            mod = importlib.import_module(module)
            getattr(mod, cls)
            print(f"  {PASS} {label}")
        except Exception as e:
            print(f"  {FAIL} {label}: {e}")
            errors += 1

    # 7. Migrations-tjek
    print("\n── Migrations ──────────────────────────")
    migration_dir = os.path.join(os.path.dirname(__file__), "..", "supabase", "migrations")
    migration_dir = os.path.normpath(migration_dir)
    if os.path.isdir(migration_dir):
        migrations = sorted(os.listdir(migration_dir))
        print(f"  {PASS} {len(migrations)} migration-filer fundet")
        for m in migrations:
            print(f"       · {m}")
    else:
        print(f"  {WARN} Migrations-mappe ikke fundet: {migration_dir}")

    # Resultat
    print("\n══════════════════════════════════════")
    if errors == 0:
        print(f"  {PASS} Alle checks bestået — klar til lokal test")
    else:
        print(f"  {FAIL} {errors} fejl fundet — ret dem før deployment")
    print("══════════════════════════════════════\n")
    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()

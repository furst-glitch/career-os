"""
CareerOS End-to-End Test
Kør: python -X utf8 e2e_test.py

Flow:
  1. Opret testbruger (Supabase Admin)
  2. Login og hent JWT
  3. Verificér /health
  4. Upload testCV (POST /cv/upload)
  5. Start Discovery Session (POST /discovery/start)
  6. Hent session status (GET /discovery/{id})
  7. Opdater Profile Score (POST /profile/score/recalculate)
  8. Hent Master CV (GET /cv/master)
  9. Start Master CV generering (POST /cv/master/generate) — timeout efter 5s
 10. Ryd op: slet testbruger
"""
import asyncio
import os
import sys
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import httpx
from supabase import create_client

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"
SKIP = "[SKIP]"

API_BASE = "http://127.0.0.1:8000/api/v1"
TEST_EMAIL = f"e2e-test-{int(time.time())}@careeros-test.invalid"
TEST_PASSWORD = "E2eTestPassword123!"

errors = 0
results = []


def log(symbol, label, detail=""):
    line = f"  {symbol} {label}" + (f" — {detail}" if detail else "")
    print(line)
    results.append((symbol, label, detail))


def step(title):
    print(f"\n── {title} {'─' * max(1, 40 - len(title))}")


async def main():
    global errors

    print("\n" + "=" * 46)
    print("  CareerOS End-to-End Test")
    print("=" * 46)
    print(f"  API:   {API_BASE}")
    print(f"  Email: {TEST_EMAIL}")

    # ─── Load config ─────────────────────────────────────────────────────────
    from app.core.config import settings
    supabase_admin = create_client(settings.supabase_url, settings.supabase_service_role_key)

    token = None
    user_id = None

    # ─── 1. Opret testbruger ─────────────────────────────────────────────────
    step("1. Opret testbruger")
    try:
        resp = supabase_admin.auth.admin.create_user({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "email_confirm": True,
        })
        user_id = resp.user.id
        log(PASS, "Bruger oprettet", f"id={user_id[:8]}...")
    except Exception as exc:
        log(FAIL, "Bruger oprettelse fejlede", str(exc))
        errors += 1
        return  # Kan ikke fortsætte uden bruger

    # ─── 2. Login og hent JWT ────────────────────────────────────────────────
    step("2. Login")
    try:
        session = supabase_admin.auth.sign_in_with_password({
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        })
        token = session.session.access_token
        log(PASS, "Login OK", f"token={token[:20]}...")
    except Exception as exc:
        log(FAIL, "Login fejlede", str(exc))
        errors += 1

    if not token:
        log(FAIL, "Ingen JWT — afbryder test", "")
        errors += 1
        await cleanup(supabase_admin, user_id)
        return

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:

        # ─── 3. Health check ─────────────────────────────────────────────────
        step("3. Health check")
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as hc:
                r = await hc.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
            log(PASS, "GET /health", r.json()["version"])
        except Exception as exc:
            log(FAIL, "GET /health fejlede", str(exc))
            errors += 1

        # ─── 4. Upload CV ────────────────────────────────────────────────────
        step("4. Upload CV (POST /cv/upload)")
        upload_id = None
        session_id_from_upload = None

        test_cv = """Lars Nielsen
lars.nielsen@example.com | +45 12 34 56 78 | Copenhagen, Denmark

EXPERIENCE
Senior Software Engineer - TechCorp A/S (2019-2024)
- Led team of 5 developers building microservices platform
- Reduced deployment time by 60% through CI/CD automation
- Increased test coverage from 40% to 85%

Software Developer - StartupX (2016-2019)
- Built RESTful API serving 100k daily requests
- Implemented real-time notification system using WebSockets

EDUCATION
BSc Computer Science - DTU (2013-2016)

SKILLS
Python, FastAPI, React, PostgreSQL, Docker, Kubernetes, AWS

CERTIFICATIONS
AWS Solutions Architect Associate (2022)
""".encode("utf-8")
        try:
            r = await client.post(
                "/cv/upload",
                headers=headers,
                files={"file": ("cv.txt", test_cv, "text/plain")},
            )
            if r.status_code == 200:
                data = r.json()
                upload_id = data.get("upload_id")
                session_id_from_upload = data.get("session_id")
                sections = data.get("parsed_sections", {})
                gaps = data.get("gaps", [])
                log(PASS, "CV uploadet og parset", f"upload={upload_id[:8] if upload_id else '?'}...")
                log(PASS, "Sections parsed", f"exp={sections.get('experiences',0)}, skills={sections.get('skills',0)}, edu={sections.get('educations',0)}")
                log(PASS if gaps else WARN, f"Gaps fundet", f"{len(gaps)} gaps")
            else:
                log(FAIL, f"CV upload fejlede HTTP {r.status_code}", r.text[:200])
                errors += 1
        except Exception as exc:
            log(FAIL, "CV upload exception", str(exc))
            errors += 1

        # ─── 5. Start Discovery Session ──────────────────────────────────────
        step("5. Start Discovery Session (POST /discovery/start)")
        session_id = session_id_from_upload
        try:
            payload = {"upload_id": upload_id} if upload_id else {}
            r = await client.post("/discovery/start", headers=headers, json=payload)
            if r.status_code == 200:
                data = r.json()
                session_id = data.get("session_id") or data.get("id") or session_id
                log(PASS, "Discovery session startet", f"id={str(session_id)[:8] if session_id else '?'}...")
            else:
                log(FAIL, f"Discovery start fejlede HTTP {r.status_code}", r.text[:200])
                errors += 1
        except Exception as exc:
            log(FAIL, "Discovery start exception", f"{type(exc).__name__}: {exc}")
            errors += 1

        # ─── 6. Hent session status ──────────────────────────────────────────
        step("6. Hent session status (GET /discovery/{id})")
        if session_id:
            try:
                r = await client.get(f"/discovery/{session_id}", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    log(PASS, "Session hentet", f"status={data.get('status')}, gaps={data.get('gaps_total',0)}")
                else:
                    log(FAIL, f"GET session fejlede HTTP {r.status_code}", r.text[:200])
                    errors += 1
            except Exception as exc:
                log(FAIL, "GET session exception", str(exc))
                errors += 1
        else:
            log(SKIP, "Ingen session_id — springer over")

        # ─── 7. Profile Score ────────────────────────────────────────────────
        step("7. Profile Score (POST /profile/score/recalculate)")
        try:
            r = await client.post("/profile/score/recalculate", headers=headers)
            if r.status_code == 200:
                data = r.json()
                overall = data.get("overall", 0)
                log(PASS, "Score beregnet", f"overall={overall}%")
            else:
                log(FAIL, f"Score fejlede HTTP {r.status_code}", r.text[:200])
                errors += 1
        except Exception as exc:
            log(FAIL, "Score exception", str(exc))
            errors += 1

        # ─── 8. Hent Master CV ───────────────────────────────────────────────
        step("8. GET /cv/master")
        try:
            r = await client.get("/cv/master", headers=headers)
            if r.status_code == 200:
                data = r.json()
                exp_count = len(data.get("experiences") or [])
                skill_count = len(data.get("skills") or [])
                log(PASS, "Master CV profil hentet", f"exp={exp_count}, skills={skill_count}")
            else:
                log(FAIL, f"GET /cv/master fejlede HTTP {r.status_code}", r.text[:200])
                errors += 1
        except Exception as exc:
            log(FAIL, "GET /cv/master exception", str(exc))
            errors += 1

        # ─── 9. Generer Master CV ────────────────────────────────────────────
        step("9. Generer Master CV (POST /cv/master/generate — timeout 8s)")
        try:
            async with client.stream("POST", "/cv/master/generate", headers=headers) as r:
                if r.status_code == 200:
                    chunks = []
                    deadline = time.time() + 8
                    async for line in r.aiter_lines():
                        if line.startswith("data:"):
                            chunks.append(line)
                        if time.time() > deadline:
                            break
                    log(PASS, "Master CV stream startet", f"{len(chunks)} chunks modtaget")
                else:
                    body = await r.aread()
                    log(FAIL, f"Generate fejlede HTTP {r.status_code}", body.decode()[:200])
                    errors += 1
        except Exception as exc:
            log(FAIL, "Generate exception", str(exc))
            errors += 1

    # ─── 10. Cleanup ─────────────────────────────────────────────────────────
    step("10. Cleanup")
    await cleanup(supabase_admin, user_id)

    # ─── Resultat ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 46)
    if errors == 0:
        print(f"  {PASS} Alle end-to-end checks bestået")
    else:
        print(f"  {FAIL} {errors} fejl fundet")
    print("=" * 46 + "\n")
    sys.exit(0 if errors == 0 else 1)


async def cleanup(supabase_admin, user_id: str | None):
    global errors
    if not user_id:
        return
    try:
        supabase_admin.auth.admin.delete_user(user_id)
        log(PASS, "Testbruger slettet", f"id={user_id[:8]}...")
    except Exception as exc:
        log(WARN, "Kunne ikke slette testbruger", str(exc))


if __name__ == "__main__":
    asyncio.run(main())

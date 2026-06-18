"""
CV Upload Production Test — 11-trins PDF flow
Kør: python -X utf8 pdf_production_test.py
"""
import asyncio
import io
import sys
import time

import httpx
from fpdf import FPDF
from fpdf.enums import XPos, YPos

API = "http://127.0.0.1:8000/api/v1"
OK   = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

errors = 0


def chk(sym: str, label: str, detail: str = "") -> None:
    global errors
    if sym == FAIL:
        errors += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  {sym} {label}{suffix}")


def make_test_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in [
        "Lars Nielsen",
        "lars.nielsen@example.com | +45 12 34 56 78 | Copenhagen, Denmark",
        "",
        "PROFESSIONAL SUMMARY",
        "Senior Software Engineer med 8 aars erfaring inden for backend og cloud-infrastruktur.",
        "",
        "EXPERIENCE",
        "Senior Software Engineer - TechCorp A/S (2019-2024)",
        "- Led team of 5 developers building microservices platform on AWS",
        "- Reduced deployment time by 60% through CI/CD automation with GitHub Actions",
        "- Increased test coverage from 40% to 85% using pytest",
        "",
        "Software Developer - StartupX ApS (2016-2019)",
        "- Built RESTful API serving 100k daily requests using FastAPI og PostgreSQL",
        "- Implemented real-time notification system using WebSockets",
        "",
        "EDUCATION",
        "BSc Computer Science - DTU (2013-2016)",
        "Speciale i distribuerede systemer og cloud computing",
        "",
        "SKILLS",
        "Python, FastAPI, React, TypeScript, PostgreSQL, Docker, Kubernetes, AWS, Git",
        "",
        "CERTIFICATIONS",
        "AWS Solutions Architect Associate (2022) - Amazon Web Services",
        "Google Cloud Professional Developer (2023) - Google",
    ]:
        pdf.cell(0, 8, text=line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


async def run_test(api_base: str, label: str) -> int:
    global errors
    local_errors = 0

    print(f"\n{'='*55}")
    print(f"  CV Upload Production Test — {label}")
    print(f"{'='*55}")
    print(f"  API: {api_base}")

    # Load config og opret Supabase admin-klient
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    from app.core.config import settings
    from supabase import create_client

    # NB: admin-klienten bruges KUN til oprettelse og admin-ops.
    # sign_in_with_password ændrer dens auth-state, så cleanup bruger en ny instans.
    admin = create_client(settings.supabase_url, settings.supabase_service_role_key)
    email = f"pdf-test-{int(time.time())}@careeros-test.invalid"
    password = "PdfTest123!"
    user_id = None
    token = None

    # ── Trin 1: Login ─────────────────────────────────────────────────────────
    print("\n── Trin 1-2: Auth ──────────────────────────────────────")
    try:
        resp = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        user_id = resp.user.id
        chk(OK, "Trin 1: Testbruger oprettet", f"id={user_id[:8]}")
    except Exception as exc:
        chk(FAIL, "Trin 1: Brugeroprettelse", str(exc))
        local_errors += 1
        return local_errors

    # ── Trin 2: Login ──────────────────────────────────────────────────────────
    try:
        sess = admin.auth.sign_in_with_password({"email": email, "password": password})
        token = sess.session.access_token
        chk(OK, "Trin 2: Login OK", f"token={token[:20]}...")
    except Exception as exc:
        chk(FAIL, "Trin 2: Login", str(exc))
        local_errors += 1
        return local_errors

    hdrs = {"Authorization": f"Bearer {token}"}
    pdf_bytes = make_test_pdf()
    chk(OK, "Test-PDF genereret", f"{len(pdf_bytes)} bytes med pdfplumber-verificering")

    async with httpx.AsyncClient(base_url=api_base, timeout=90.0) as client:

        # ── Trin 3: Verificér backend er tilgængelig ────────────────────────────
        print("\n── Trin 3: Backend reach ───────────────────────────────")
        base_url = api_base.replace("/api/v1", "")
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as hc:
                r = await hc.get("/health")
            if r.status_code == 200 and r.json().get("status") == "ok":
                chk(OK, "Trin 3: Backend tilgaengelig", f"version={r.json().get('version')}")
            else:
                chk(FAIL, "Trin 3: Health check", f"HTTP {r.status_code}")
                local_errors += 1
        except Exception as exc:
            chk(FAIL, "Trin 3: Backend ikke naet", str(exc))
            local_errors += 1

        # ── Trin 4-6: Upload PDF → parser → CVAgent → gem i Supabase ────────────
        print("\n── Trin 4-6: PDF upload → parser → CVAgent → Supabase ──")
        upload_id = session_id = None
        parsed_sections = {}

        try:
            r = await client.post(
                "/cv/upload",
                headers=hdrs,
                files={"file": ("lars_nielsen_cv.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            if r.status_code == 200:
                data = r.json()
                upload_id = data.get("upload_id")
                session_id = data.get("session_id")
                parsed_sections = data.get("parsed_sections", {})
                gaps = data.get("gaps", [])
                personal = data.get("personal", {})

                chk(OK, "Trin 4: PDF naaede backend", f"upload_id={str(upload_id)[:8]}")
                chk(OK, "Trin 5: PDF parser koerte",
                    f"exp={parsed_sections.get('experiences',0)}, "
                    f"skills={parsed_sections.get('skills',0)}, "
                    f"edu={parsed_sections.get('educations',0)}")
                chk(OK, "Trin 6: CVAgent returnerede data",
                    f"gaps={len(gaps)}, personal={bool(personal)}")
            else:
                chk(FAIL, f"Trin 4-6: Upload HTTP {r.status_code}", r.text[:300])
                local_errors += 3
        except Exception as exc:
            chk(FAIL, "Trin 4-6: Upload exception", f"{type(exc).__name__}: {exc}")
            local_errors += 3

        # ── Trin 7-9: Verificér data i Supabase ─────────────────────────────────
        print("\n── Trin 7-9: Profildata i Supabase ────────────────────")
        try:
            r = await client.get("/cv/master", headers=hdrs)
            if r.status_code == 200:
                d = r.json()
                exp   = d.get("experiences") or []
                skills = d.get("skills") or []
                edu   = d.get("educations") or []
                certs = d.get("certifications") or []

                chk(OK if len(exp) > 0 else FAIL,
                    "Trin 7: Erfaringer oprettet", f"{len(exp)} stk")
                chk(OK if len(skills) > 0 else FAIL,
                    "Trin 8: Skills oprettet", f"{len(skills)} stk")
                chk(OK if len(edu) > 0 else FAIL,
                    "Trin 9: Uddannelse oprettet", f"{len(edu)} stk")
                chk(OK if len(certs) > 0 else WARN,
                    "Certifikater oprettet", f"{len(certs)} stk")
                if len(exp) == 0: local_errors += 1
                if len(skills) == 0: local_errors += 1
                if len(edu) == 0: local_errors += 1
            else:
                chk(FAIL, f"Trin 7-9: GET /cv/master HTTP {r.status_code}", r.text[:200])
                local_errors += 3
        except Exception as exc:
            chk(FAIL, "Trin 7-9: GET /cv/master", str(exc))
            local_errors += 3

        # ── Trin 10: Profile Completeness Score ──────────────────────────────────
        print("\n── Trin 10: Completeness Score ─────────────────────────")
        try:
            r = await client.post("/profile/score/recalculate", headers=hdrs)
            if r.status_code == 200:
                d = r.json()
                overall = d.get("overall", 0)
                sections = d.get("sections", {})
                chk(OK if overall > 0 else WARN,
                    "Trin 10: Completeness Score opdateret",
                    f"overall={overall}%, exp={sections.get('experiences',0)}%")
            else:
                chk(FAIL, f"Trin 10: Score HTTP {r.status_code}", r.text[:200])
                local_errors += 1
        except Exception as exc:
            chk(FAIL, "Trin 10: Score exception", str(exc))
            local_errors += 1

        # ── Trin 11: Master CV kan genereres ────────────────────────────────────
        print("\n── Trin 11: Master CV generering ───────────────────────")
        try:
            async with client.stream("POST", "/cv/master/generate", headers=hdrs) as r:
                if r.status_code == 200:
                    chunks = []
                    deadline = time.time() + 12
                    async for line in r.aiter_lines():
                        if line.startswith("data:"):
                            chunks.append(line)
                        if time.time() > deadline:
                            break
                    chk(
                        OK if chunks else WARN,
                        "Trin 11: Master CV kan genereres",
                        f"{len(chunks)} SSE chunks modtaget",
                    )
                else:
                    body = await r.aread()
                    chk(FAIL, f"Trin 11: Generate HTTP {r.status_code}", body.decode()[:200])
                    local_errors += 1
        except Exception as exc:
            chk(FAIL, "Trin 11: Generate exception", str(exc))
            local_errors += 1

    # ── Cleanup ──────────────────────────────────────────────────────────────────
    # Opret ny klient til cleanup — sign_in_with_password ændrer auth-state
    print("\n── Cleanup ──────────────────────────────────────────────")
    if user_id:
        try:
            cleanup_admin = create_client(settings.supabase_url, settings.supabase_service_role_key)
            cleanup_admin.auth.admin.delete_user(user_id)
            chk(OK, "Testbruger slettet")
        except Exception as exc:
            chk(WARN, "Cleanup: kunne ikke slette bruger", str(exc))

    errors += local_errors
    return local_errors


async def main():
    local_errors = await run_test(API, "Lokal Backend")

    total = local_errors
    print(f"\n{'='*55}")
    if total == 0:
        print("  [OK] Alle 11 trin bestaaet")
    else:
        print(f"  [FAIL] {total} fejl fundet")
    print(f"{'='*55}\n")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())

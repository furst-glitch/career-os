"""
AI Arbejdsliv & Løncoach API

POST /labor-coach/salary-check          - Løntjek (JSON)
GET  /labor-coach/career-value          - Karriereværdi (fra memory)
POST /labor-coach/contract-analysis     - Kontraktanalyse (fil-upload)
POST /labor-coach/agreement-analysis    - Overenskomstanalyse (fil-upload)
POST /labor-coach/payslip-check         - Lønseddelkontrol (fil-upload)
POST /labor-coach/worktime-check        - Arbejdstidskontrol (fil-upload)
POST /labor-coach/salary-prep/chat      - Lønsamtale-interview (SSE)
POST /labor-coach/salary-prep/generate  - Generer lønsamtalepakke (SSE)
POST /labor-coach/salary-prep/export    - Eksporter pakke som PDF
POST /labor-coach/labor-rights          - Fagforeningsassistent (SSE)
GET  /labor-coach/analyses              - Liste seneste analyser
"""
import io
import json as _json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.core.rate_limit import LIMIT_COACH, limiter
from app.providers.litellm_provider import NoProviderKeyError
from app.services.memory_snapshot_service import MemorySnapshotService

logger = logging.getLogger("app.labor_coach")
router = APIRouter(prefix="/labor-coach", tags=["Labor Coach"])

DISCLAIMER = "\n\n---\nDette er vejledende analyse og ikke juridisk rådgivning."


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_text(file_bytes: bytes, filename: str) -> str:
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
            return "\n".join(pages)
        elif name.endswith(".docx"):
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            return file_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", filename, exc)
        return file_bytes.decode("utf-8", errors="replace")


def _save_analysis(supabase, user_id: str, analysis_type: str, title: str, input_data: dict, result_text: str) -> dict:
    row = supabase.table("coach_analyses").insert({
        "user_id": user_id,
        "analysis_type": analysis_type,
        "title": title,
        "input_data": input_data,
        "result_text": result_text,
    }).execute()
    return row.data[0] if row.data else {}


def _sse_stream(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class SalaryCheckRequest(BaseModel):
    title: str
    industry: str = ""
    location: str = ""
    company: str = ""
    experience_years: str = ""
    education: str = ""
    management_responsibility: bool = False
    budget_responsibility: str = ""
    team_size: str = ""
    current_salary: str = ""
    pension: str = ""
    bonus: str = ""
    benefits: str = ""


class CareerValueRequest(BaseModel):
    current_salary: str = ""


class SalaryPrepChatRequest(BaseModel):
    messages: list[dict] = []
    current_salary: str = ""
    target_salary: str = ""
    session_id: str | None = None


class SalaryPrepGenerateRequest(BaseModel):
    messages: list[dict] = []
    current_salary: str = ""
    target_salary: str = ""
    min_salary: str = ""
    market_salary: str = ""
    session_id: str | None = None


class LaborRightsRequest(BaseModel):
    messages: list[dict] = []


# ── Module 1: Løntjek ─────────────────────────────────────────────────────────

@router.post("/salary-check")
@limiter.limit(LIMIT_COACH)
async def salary_check(
    request: Request,
    body: SalaryCheckRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    from app.agents.salary_check_agent import SalaryCheckAgent
    agent = SalaryCheckAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run(body.model_dump())
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "salary_check",
                   f"Løntjek — {body.title}", body.model_dump(), result.content)
    return {"content": result.content, "analysis_type": "salary_check"}


# ── Module 7: Karriereværdi ───────────────────────────────────────────────────

@router.get("/career-value")
@limiter.limit(LIMIT_COACH)
async def career_value(
    request: Request,
    current_salary: str = "",
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    snap = MemorySnapshotService(supabase).snapshot(user["id"])
    text_summary = snap.get("text_summary", "")
    if not text_summary.strip():
        raise HTTPException(422, "Din karriereprofil er tom — upload dit CV og udfyld din profil først.")

    from app.agents.career_value_agent import CareerValueAgent
    agent = CareerValueAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({"snapshot_text": text_summary, "current_salary": current_salary})
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "career_value", "Karriereværdi", {}, result.content)
    return {
        "content": result.content,
        "analysis_type": "career_value",
        "profile_summary": {
            "target_title": (snap.get("profile") or {}).get("target_title"),
            "skills_count": len(snap.get("skills") or []),
            "experience_count": len(snap.get("experience") or []),
        },
    }


# ── Module 4: Kontraktanalyse ─────────────────────────────────────────────────

@router.post("/contract-analysis")
@limiter.limit(LIMIT_COACH)
async def contract_analysis(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Filen er for stor (max 10 MB)")

    extracted = _extract_text(file_bytes, file.filename or "")
    if len(extracted.strip()) < 100:
        raise HTTPException(422, "Kunne ikke udtrække tekst fra filen. Prøv et andet format.")

    from app.agents.contract_analysis_agent import ContractAnalysisAgent
    agent = ContractAnalysisAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({"contract_text": extracted, "file_name": file.filename})
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "contract_analysis",
                   f"Kontrakt — {file.filename}", {"file_name": file.filename}, result.content)
    return {"content": result.content, "analysis_type": "contract_analysis", "file_name": file.filename}


# ── Module 2+3: Overenskomstidentifikation og -analyse ───────────────────────

@router.post("/agreement-analysis")
@limiter.limit(LIMIT_COACH)
async def agreement_analysis(
    request: Request,
    contract_file: UploadFile = File(...),
    agreement_file: UploadFile | None = File(default=None),
    mode: str = Form(default="identify"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    contract_bytes = await contract_file.read()
    if len(contract_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Kontraktfilen er for stor (max 10 MB)")

    contract_text = _extract_text(contract_bytes, contract_file.filename or "")
    if len(contract_text.strip()) < 50:
        raise HTTPException(422, "Kunne ikke udtrække tekst fra kontrakten.")

    agreement_text = ""
    if agreement_file:
        agreement_bytes = await agreement_file.read()
        agreement_text = _extract_text(agreement_bytes, agreement_file.filename or "")

    from app.agents.agreement_analysis_agent import AgreementAnalysisAgent
    agent = AgreementAnalysisAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({
            "contract_text": contract_text,
            "agreement_text": agreement_text,
            "file_name": contract_file.filename,
            "mode": mode if mode in ("identify", "analyze") else "identify",
        })
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "agreement_analysis",
                   f"Overenskomst — {contract_file.filename}", {"mode": mode}, result.content)
    return {"content": result.content, "analysis_type": "agreement_analysis", "mode": mode}


# ── Module 5: Lønseddelkontrol ────────────────────────────────────────────────

@router.post("/payslip-check")
@limiter.limit(LIMIT_COACH)
async def payslip_check(
    request: Request,
    payslip_file: UploadFile = File(...),
    contract_file: UploadFile | None = File(default=None),
    agreement_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    payslip_bytes = await payslip_file.read()
    if len(payslip_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Lønseddelfilen er for stor (max 10 MB)")

    payslip_text = _extract_text(payslip_bytes, payslip_file.filename or "")
    if len(payslip_text.strip()) < 50:
        raise HTTPException(422, "Kunne ikke udtrække tekst fra lønsedlen.")

    contract_text = ""
    if contract_file:
        contract_bytes = await contract_file.read()
        contract_text = _extract_text(contract_bytes, contract_file.filename or "")

    agreement_text = ""
    if agreement_file:
        agreement_bytes = await agreement_file.read()
        agreement_text = _extract_text(agreement_bytes, agreement_file.filename or "")

    from app.agents.payslip_check_agent import PayslipCheckAgent
    agent = PayslipCheckAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({
            "payslip_text": payslip_text,
            "contract_text": contract_text,
            "agreement_text": agreement_text,
        })
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "payslip_check",
                   f"Lønseddel — {payslip_file.filename}", {}, result.content)
    return {"content": result.content, "analysis_type": "payslip_check"}


# ── Module 6: Arbejdstidskontrol ──────────────────────────────────────────────

@router.post("/worktime-check")
@limiter.limit(LIMIT_COACH)
async def worktime_check(
    request: Request,
    schedule_file: UploadFile = File(...),
    agreement_file: UploadFile | None = File(default=None),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    schedule_bytes = await schedule_file.read()
    if len(schedule_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Filen er for stor (max 10 MB)")

    schedule_text = _extract_text(schedule_bytes, schedule_file.filename or "")
    if len(schedule_text.strip()) < 30:
        raise HTTPException(422, "Kunne ikke udtrække tekst fra vagtplanen.")

    agreement_text = ""
    if agreement_file:
        agreement_bytes = await agreement_file.read()
        agreement_text = _extract_text(agreement_bytes, agreement_file.filename or "")

    from app.agents.worktime_check_agent import WorktimeCheckAgent
    agent = WorktimeCheckAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({"schedule_text": schedule_text, "agreement_text": agreement_text})
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_analyse_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Analyse fejlede — prøv igen")

    _save_analysis(supabase, user["id"], "worktime_check",
                   f"Arbejdstid — {schedule_file.filename}", {}, result.content)
    return {"content": result.content, "analysis_type": "worktime_check"}


# ── Module 8: Lønsamtale-interview (SSE chat) ────────────────────────────────

@router.post("/salary-prep/chat")
@limiter.limit(LIMIT_COACH)
async def salary_prep_chat(
    request: Request,
    body: SalaryPrepChatRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    import asyncio

    snap = MemorySnapshotService(supabase).snapshot(user["id"])
    snapshot_text = snap.get("text_summary", "")

    from app.agents.salary_prep_agent import SalaryPrepAgent
    agent = SalaryPrepAgent(user_id=user["id"], supabase=supabase)

    async def event_stream():
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                result = await agent.run_interview({
                    "snapshot_text": snapshot_text,
                    "messages": body.messages,
                    "current_salary": body.current_salary,
                    "target_salary": body.target_salary,
                })
                stream = result.metadata.get("stream")
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        await queue.put(("data", _json.dumps({"type": "chunk", "content": delta})))
            except NoProviderKeyError as exc:
                await queue.put(("data", _json.dumps({"type": "error", "code": "no_api_key", "content": str(exc)})))
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                await queue.put(("data", _json.dumps({"type": "error", "content": str(exc)})))
            finally:
                try:
                    queue.put_nowait(("done", ""))
                except asyncio.QueueFull:
                    pass

        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if kind == "done":
                    yield f"data: {_json.dumps({'type': 'done'})}\n\n"
                    break
                yield f"data: {payload}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return _sse_stream(event_stream())


# ── Module 8: Generer lønsamtalepakke ────────────────────────────────────────

@router.post("/salary-prep/generate")
@limiter.limit(LIMIT_COACH)
async def salary_prep_generate(
    request: Request,
    body: SalaryPrepGenerateRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    snap = MemorySnapshotService(supabase).snapshot(user["id"])
    snapshot_text = snap.get("text_summary", "")
    if not snapshot_text.strip():
        raise HTTPException(422, "Din karriereprofil er tom — udfyld din profil først.")

    conversation = "\n".join(
        f"{'Kandidat' if m.get('role') == 'user' else 'Coach'}: {m.get('content', '')}"
        for m in body.messages if m.get("role") in ("user", "assistant")
    )

    from app.agents.salary_prep_agent import SalaryPrepAgent
    agent = SalaryPrepAgent(user_id=user["id"], supabase=supabase)
    try:
        result = await agent.run({
            "snapshot_text": snapshot_text,
            "conversation": conversation,
            "current_salary": body.current_salary,
            "target_salary": body.target_salary,
            "min_salary": body.min_salary,
            "market_salary": body.market_salary,
        })
        a4_result = await agent.generate_a4({
            "package_text": result.content,
            "current_salary": body.current_salary,
            "target_salary": body.target_salary,
            "min_salary": body.min_salary,
        })
    except NoProviderKeyError as exc:
        raise HTTPException(402, {"error": "no_api_key", "message": str(exc)})
    except Exception as exc:
        logger.error("labor_coach_generate_failed user=%s error=%s", user["id"], exc, exc_info=True)
        raise HTTPException(500, "Generering fejlede — prøv igen")

    # Gem session
    session_data = {
        "user_id": user["id"],
        "messages": body.messages,
        "package_text": result.content,
        "package_a4_text": a4_result.content,
    }
    if body.session_id:
        supabase.table("salary_prep_sessions").update({
            k: v for k, v in session_data.items() if k != "user_id"
        }).eq("id", body.session_id).eq("user_id", user["id"]).execute()
        session_id = body.session_id
    else:
        row = supabase.table("salary_prep_sessions").insert(session_data).execute()
        session_id = row.data[0]["id"] if row.data else None

    return {
        "package_text": result.content,
        "package_a4_text": a4_result.content,
        "session_id": session_id,
    }


# ── Module 8: Eksporter pakke som PDF ────────────────────────────────────────

@router.get("/salary-prep/{session_id}/pdf")
async def salary_prep_export_pdf(
    session_id: str,
    doc: str = "package",
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    row = supabase.table("salary_prep_sessions").select("package_text, package_a4_text").eq("id", session_id).eq("user_id", user["id"]).limit(1).execute()
    if not row.data:
        raise HTTPException(404, "Session ikke fundet")

    session = row.data[0]
    text = session.get("package_a4_text" if doc == "a4" else "package_text") or ""
    if not text:
        raise HTTPException(404, "Indhold mangler — generer pakken først.")

    title = "Lønsamtale A4" if doc == "a4" else "Lønsamtalepakke"

    profile_row = supabase.table("user_profiles").select("display_name, full_name, email, phone, location, linkedin_url").eq("user_id", user["id"]).limit(1).execute()
    profile = profile_row.data[0] if profile_row.data else {}

    from app.services.export_service import export_text_as_pdf
    pdf_bytes = export_text_as_pdf(title, text, "corporate", profile=profile)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}.pdf"'},
    )


@router.get("/salary-prep/{session_id}/docx")
async def salary_prep_export_docx(
    session_id: str,
    doc: str = "package",
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    row = supabase.table("salary_prep_sessions").select("package_text, package_a4_text").eq("id", session_id).eq("user_id", user["id"]).limit(1).execute()
    if not row.data:
        raise HTTPException(404, "Session ikke fundet")

    session = row.data[0]
    text = session.get("package_a4_text" if doc == "a4" else "package_text") or ""
    if not text:
        raise HTTPException(404, "Indhold mangler — generer pakken først.")

    title = "Lønsamtale A4" if doc == "a4" else "Lønsamtalepakke"

    profile_row = supabase.table("user_profiles").select("display_name, full_name, email, phone, location, linkedin_url").eq("user_id", user["id"]).limit(1).execute()
    profile = profile_row.data[0] if profile_row.data else {}

    from app.services.export_service import export_text_as_docx
    docx_bytes = export_text_as_docx(title, text, "corporate", profile=profile)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}.docx"'},
    )


# ── Module 9: Fagforeningsassistent (SSE chat) ───────────────────────────────

@router.post("/labor-rights")
@limiter.limit(LIMIT_COACH)
async def labor_rights(
    request: Request,
    body: LaborRightsRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    import asyncio

    from app.agents.labor_rights_agent import LaborRightsAgent
    agent = LaborRightsAgent(user_id=user["id"], supabase=supabase)

    async def event_stream():
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                result = await agent.run({"messages": body.messages})
                stream = result.metadata.get("stream")
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        await queue.put(("data", _json.dumps({"type": "chunk", "content": delta})))
            except NoProviderKeyError as exc:
                await queue.put(("data", _json.dumps({"type": "error", "code": "no_api_key", "content": str(exc)})))
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                await queue.put(("data", _json.dumps({"type": "error", "content": str(exc)})))
            finally:
                try:
                    queue.put_nowait(("done", ""))
                except asyncio.QueueFull:
                    pass

        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if kind == "done":
                    yield f"data: {_json.dumps({'type': 'done'})}\n\n"
                    break
                yield f"data: {payload}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return _sse_stream(event_stream())


# ── Analysehistorik ───────────────────────────────────────────────────────────

@router.get("/analyses")
async def list_analyses(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
    limit: int = 20,
):
    rows = (
        supabase.table("coach_analyses")
        .select("id, analysis_type, title, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(min(limit, 50))
        .execute()
    )
    return {"analyses": rows.data or []}

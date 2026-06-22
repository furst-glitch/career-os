"""
Jobs API — Sprint 3.1

GET    /jobs                  — list alle jobs (saved_only param)
GET    /jobs/saved            — kun gemte jobs
POST   /jobs                  — tilføj job + beregn match score
POST   /jobs/paste            — importér job via URL eller råtekst
GET    /jobs/{id}             — hent job
PUT    /jobs/{id}             — opdater job
DELETE /jobs/{id}             — slet job
POST   /jobs/{id}/save        — toggle is_saved
GET    /jobs/{id}/match       — beregn frisk match score
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.services.automation_service import on_job_saved
from app.services.cache_service import TTL_MATCH, get_cache, key_match
from app.services.job_service import JobService
from app.services.memory_snapshot_service import MemorySnapshotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _svc(supabase) -> JobService:
    return JobService(supabase)


def _snapshot(user_id: str, supabase, force: bool = False) -> dict:
    """Henter karriere-snapshot til match-beregning. Returnerer tomt dict ved fejl."""
    try:
        return MemorySnapshotService(supabase).snapshot(user_id, force=force)
    except Exception:
        return {}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_jobs(
    saved_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return _svc(supabase).list_jobs(user["id"], saved_only=saved_only, limit=limit)


@router.get("/saved")
async def list_saved_jobs(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return _svc(supabase).list_jobs(user["id"], saved_only=True)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_job(
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    # Hvis title mangler men der er en beskrivelse, udtrækker AI metadata
    description = body.get("description") or ""
    if not body.get("title", "").strip() and len(description) >= 100:
        meta = await _extract_job_metadata(description, user["id"])
        if meta.get("title"):
            body["title"] = meta["title"]
        if meta.get("company") and not body.get("company", "").strip():
            body["company"] = meta["company"]
        if meta.get("location") and not body.get("location"):
            body["location"] = meta["location"]
        if meta.get("job_type") in ("full_time", "part_time", "contract", "freelance", "internship"):
            body.setdefault("job_type", meta["job_type"])
        if meta.get("remote_type") in ("onsite", "hybrid", "remote"):
            body.setdefault("remote_type", meta["remote_type"])
        if meta.get("deadline"):
            body["_extracted_deadline"] = meta["deadline"]

    # Sæt fallback-titel hvis AI heller ikke fandt noget
    if not body.get("title", "").strip():
        body["title"] = "Indsat stillingsopslag"
    if not body.get("company", "").strip():
        body["company"] = "Ukendt virksomhed"

    svc = _svc(supabase)
    job = svc.create_job(user["id"], {k: v for k, v in body.items() if not k.startswith("_")})

    # Gem deadline på pipeline-entry hvis udtrukket (oprettes af automation_service ved is_saved)
    extracted_deadline = body.get("_extracted_deadline")
    if extracted_deadline:
        job["extracted_deadline"] = extracted_deadline

    # Beregn og gem match score (fejler stille)
    try:
        snap = _snapshot(user["id"], supabase)
        if snap:
            result = await svc.compute_match_score(job, snap)
            svc.store_match_score(job["id"], result["total"])
            job["match_score"] = result["total"]
            job["match_breakdown"] = result
    except Exception:
        pass

    return job


# ── Paste / Import ────────────────────────────────────────────────────────────

async def _extract_job_metadata(full_description: str, user_id: str) -> dict:
    """
    Bruger LLM til at udtrække strukturerede metadata fra en jobannonce-tekst.
    Returnerer dict med title, company, location, job_type, remote_type, deadline.
    Fejler stille — returnerer tomt dict ved fejl.
    """
    import json as _json

    from app.providers.litellm_provider import LiteLLMProvider
    if not full_description or len(full_description) < 100:
        return {}
    try:
        llm = LiteLLMProvider(user_id)
        response = await llm.complete(
            "cv_agent",  # brug generisk agent-konfiguration
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du er en assistent der udtrækker metadata fra jobopslag. "
                        "Returner KUN gyldig JSON med disse felter:\n"
                        "  title: stillingsbetegnelse (string)\n"
                        "  company: virksomhedens navn (string)\n"
                        "  location: arbejdssted, by eller 'Remote' (string eller null)\n"
                        "  job_type: 'full_time' | 'part_time' | 'contract' | 'freelance' | 'internship'\n"
                        "  remote_type: 'onsite' | 'hybrid' | 'remote'\n"
                        "  deadline: ansøgningsfrist i ISO-format YYYY-MM-DD (string eller null)\n"
                        "Gæt aldrig — brug kun oplysninger der fremgår direkte af teksten. "
                        "Returner null for felter du ikke kan finde."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Udtrjek metadata fra dette jobopslag:\n\n{full_description[:4000]}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=300,
        )
        raw = response.choices[0].message.content or "{}"
        return _json.loads(raw)
    except Exception as exc:
        logger.warning("paste_job metadata extraction failed: %s", exc)
        return {}


@router.post("/paste", status_code=201)
async def paste_job(
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Importér job ved at indsætte URL eller råtekst.
    Titel, firma, lokation og deadline udtrækkes automatisk af AI — ingen manuel udfyldning nødvendig.

    Body:
      url         — job-URL: hentes og scrapes automatisk
      text        — råtekst: bruges direkte som full_description
      (alle øvrige felter ignoreres — AI udtrækker dem fra indholdet)

    Returnerer det gemte job med match score, matched_skills og missing_requirements.
    """
    from app.services.job_scraper import scrape_jobs_batch

    url = (body.get("url") or "").strip()
    text = (body.get("text") or "").strip()

    if not url and not text:
        raise HTTPException(400, "Angiv enten 'url' eller 'text'")

    job_dict: dict = {
        "url": url or None,
        "title": "Analyserer...",
        "company": "Ukendt",
        "location": None,
        "job_type": "full_time",
        "remote_type": "hybrid",
        "source": "paste",
        "description": None,
        "full_description": text or None,
        "requirements": [],
    }

    # Scrape URL if provided (mutates job_dict with full_description + ats_url)
    if url:
        try:
            await scrape_jobs_batch([job_dict], max_concurrent=1, total_timeout=20.0)
        except Exception as exc:
            logger.warning("paste_job scraping failed for %s: %s", url, exc)

    # AI-udtræk af metadata fra den scrapede/indsatte tekst
    full_text = job_dict.get("full_description") or ""
    if full_text:
        meta = await _extract_job_metadata(full_text, user["id"])
        if meta.get("title"):
            job_dict["title"] = meta["title"]
        if meta.get("company"):
            job_dict["company"] = meta["company"]
        if meta.get("location"):
            job_dict["location"] = meta["location"]
        if meta.get("job_type") in ("full_time", "part_time", "contract", "freelance", "internship"):
            job_dict["job_type"] = meta["job_type"]
        if meta.get("remote_type") in ("onsite", "hybrid", "remote"):
            job_dict["remote_type"] = meta["remote_type"]
        # deadline gemmes som note indtil application_pipeline er oprettet
        if meta.get("deadline"):
            job_dict["_extracted_deadline"] = meta["deadline"]

    # Fallback til "Indsat jobopslag" hvis AI ikke fandt en titel
    if not job_dict["title"] or job_dict["title"] == "Analyserer...":
        job_dict["title"] = "Indsat jobopslag"

    svc = _svc(supabase)
    snap = _snapshot(user["id"], supabase)

    # Compute match score on scraped/pasted text
    match_result: dict = {}
    if snap:
        try:
            match_result = await svc.compute_match_score(job_dict, snap)
        except Exception as exc:
            logger.warning("paste_job match scoring failed: %s", exc)

    # Save to DB (strip private underscore keys added during processing)
    payload = {k: v for k, v in job_dict.items() if not k.startswith("_")}
    payload["is_saved"] = True
    job = svc.create_job(user["id"], payload)

    # Attach match data to response
    if match_result:
        try:
            svc.store_match_score(job["id"], match_result["total"])
            job["match_score"] = match_result["total"]
            job["match_breakdown"] = match_result.get("breakdown", {})
            job["matched_skills"] = match_result.get("matched_skills", [])
            job["missing_requirements"] = match_result.get("missing_requirements", [])
        except Exception:
            pass

    # Inkludér udtrukket deadline i svaret (til pipeline-oprettelse i frontend)
    if job_dict.get("_extracted_deadline"):
        job["extracted_deadline"] = job_dict["_extracted_deadline"]

    return job


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    job = _svc(supabase).get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    return job


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{job_id}")
async def update_job(
    job_id: str,
    body: dict,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    svc = _svc(supabase)
    job = svc.update_job(job_id, user["id"], body)

    # Genberegn match score hvis beskrivelse/krav ændret
    if any(k in body for k in ("title", "description", "requirements")):
        try:
            snap = _snapshot(user["id"], supabase)
            if snap:
                result = await svc.compute_match_score(job, snap)
                svc.store_match_score(job_id, result["total"])
                job["match_score"] = result["total"]
        except Exception:
            pass

    return job


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    _svc(supabase).delete_job(job_id, user["id"])


# ── Save toggle ───────────────────────────────────────────────────────────────

@router.post("/{job_id}/save")
async def toggle_save(
    job_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    try:
        result = _svc(supabase).toggle_save(job_id, user["id"])
        # Auto-create draft pipeline entry when job is saved
        if result.get("is_saved"):
            background_tasks.add_task(on_job_saved, user["id"], job_id, supabase)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Match score ───────────────────────────────────────────────────────────────

@router.get("/{job_id}/match")
async def get_match_score(
    job_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    cache = get_cache()
    ck = key_match(user["id"], job_id)

    cached = await cache.get(ck)
    if cached:
        return cached

    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job ikke fundet")
    snap = _snapshot(user["id"], supabase)
    result = await svc.compute_match_score(job, snap)
    svc.store_match_score(job_id, result["total"])
    await cache.set(ck, result, ttl=TTL_MATCH)
    return result


# ── Quick Generate (CV eller ansøgning direkte fra job-card) ──────────────────

class QuickGenRequest(BaseModel):
    doc_type: str = "cover_letter"  # "cover_letter" | "cv"
    language: str = "da"
    writing_style: str = "professional"
    focus_areas: str | None = None


@router.post("/{job_id}/quickgen")
async def quickgen(
    job_id: str,
    body: QuickGenRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Generer et dokument (CV eller ansøgning) direkte fra et job-kort.
    Returnerer SSE-stream med keep-alive pings og et enkelt 'done'-event til sidst.

    SSE events:
      : ping                                    (keep-alive mens AI tænker)
      data: {"type": "done",   "document_id": ..., "content": ..., ...}
      data: {"type": "error",  "message": ..., "code"?: "no_api_key"}
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    from app.agents.generation_pipeline import GenerationPipeline
    from app.providers.litellm_provider import NoProviderKeyError
    from app.services.application_service import ApplicationService

    if body.doc_type not in ("cover_letter", "cv"):
        raise HTTPException(400, "doc_type skal være 'cover_letter' eller 'cv'")

    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(404, "Job ikke fundet")

    app_svc = ApplicationService(supabase)
    pipeline_id = job.get("pipeline_id")
    if not pipeline_id:
        new_entry = app_svc.create_pipeline(user["id"], job_id, {"status": "gemt", "priority": "medium"})
        pipeline_id = new_entry["id"]

    snapshot = _snapshot(user["id"], supabase, force=True)
    candidate_summary = snapshot.get("text_summary", "")

    is_cv = body.doc_type == "cv"
    new_status = "cv_genereret" if is_cv else "ansoegning_genereret"
    title = (
        f"CV — {job.get('title')} hos {job.get('company')}"
        if is_cv
        else f"Ansøgning — {job.get('title')} hos {job.get('company')}"
    )

    # Hent brugerens valgte template fra Indstillinger → Layout
    try:
        prefs_row = supabase.table("user_profiles").select(
            "default_cv_template, default_app_template"
        ).eq("user_id", user["id"]).limit(1).execute()
        prefs = prefs_row.data[0] if prefs_row.data else {}
    except Exception:
        prefs = {}
    user_template = prefs.get("default_cv_template" if is_cv else "default_app_template") or (
        "nordic_executive" if is_cv else "corporate"
    )

    async def process():
        queue: asyncio.Queue = asyncio.Queue()

        async def run_agent():
            try:
                pipeline = GenerationPipeline(user_id=user["id"], supabase=supabase)
                full_desc = job.get("full_description") or job.get("description") or ""
                gen_input = {
                    "job_title": job.get("title", ""),
                    "job_company": job.get("company", ""),
                    "job_description": full_desc,
                    "job_requirements": job.get("requirements", []),
                    "candidate_summary": candidate_summary,
                    "language": body.language,
                    "writing_style": body.writing_style,
                    "focus_areas": body.focus_areas,
                    "doc_type": body.doc_type,
                    "template": user_template,
                }
                if is_cv:
                    content = await pipeline.generate_cv(gen_input, queue=queue)
                else:
                    content = await pipeline.generate_application(gen_input, queue=queue)
                from app.agents.base import AgentResult, AgentUsage
                await queue.put(("ok", AgentResult(content=content, usage=AgentUsage())))
            except NoProviderKeyError as exc:
                await queue.put(("no_key", str(exc)))
            except Exception as exc:
                await queue.put(("err", str(exc)))

        task = asyncio.create_task(run_agent())
        result = None
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                if kind == "progress":
                    yield f"data: {_json.dumps({'type': 'progress', **payload})}\n\n"
                    continue
                elif kind == "ok":
                    result = payload
                elif kind == "no_key":
                    yield f"data: {_json.dumps({'type': 'error', 'code': 'no_api_key', 'message': payload})}\n\n"
                    task.cancel()
                    return
                else:
                    yield f"data: {_json.dumps({'type': 'error', 'message': f'AI fejlede: {payload}'})}\n\n"
                    task.cancel()
                    return
                break
            except TimeoutError:
                yield ": ping\n\n"

        try:
            doc = app_svc.save_cover_letter(
                user_id=user["id"],
                pipeline_id=pipeline_id,
                title=title,
                content=result.content,  # fuld JSON gemmes til PDF-export
                language=body.language,
                doc_type=body.doc_type,
            )
            app_svc.update_pipeline(user["id"], pipeline_id, {"current_status": new_status})
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'message': f'Kunne ikke gemme dokument: {exc}'})}\n\n"
            return

        # CV returnerer struktureret JSON — send kun cv_text til modal-visning
        display_content = result.content
        if is_cv:
            try:
                parsed_cv = _json.loads(result.content)
                if isinstance(parsed_cv, dict) and parsed_cv.get("_structured_cv_v2"):
                    display_content = parsed_cv.get("cv_text", result.content)
            except (ValueError, TypeError):
                pass

        yield f"data: {_json.dumps({'type': 'done', 'document_id': doc['id'], 'title': title, 'content': display_content, 'pipeline_id': pipeline_id, 'pipeline_status': new_status})}\n\n"

    return StreamingResponse(
        process(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Job Intake Interview ──────────────────────────────────────────────────────

class JobInterviewRequest(BaseModel):
    messages: list[dict] = []
    extract: bool = False


@router.post("/{job_id}/interview")
async def job_interview(
    job_id: str,
    body: JobInterviewRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """
    Stateless AI-intake interview om et specifikt job.

    messages=[]     → AI genererer første spørgsmål baseret på gap-analyse
    messages=[...]  → AI svarer på seneste besked (historik sendes med)
    extract=True    → udtrækker nøgleinfo, gemmer til job-noter OG career_memories

    SSE events (extract=False):
      data: {"type": "chunk", "content": "..."}
      data: {"type": "done"}
      data: {"type": "error", "content": "..."}
      : ping
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    from app.providers.litellm_provider import LiteLLMProvider
    from app.services.memory_snapshot_service import MemorySnapshotService

    svc = _svc(supabase)
    job = svc.get_job(job_id, user["id"])
    if not job:
        raise HTTPException(404, "Job ikke fundet")

    title = job.get("title", "Stilling")
    company = job.get("company", "Virksomhed")
    description = job.get("full_description") or job.get("description") or ""
    requirements: list = job.get("requirements") or []

    # ── Byg job-kontekst ──────────────────────────────────────────────────────
    job_ctx = f"STILLING: {title} hos {company}"
    if requirements:
        job_ctx += "\nKRAV FRA OPSLAGET:\n" + "\n".join(f"  - {r}" for r in requirements[:15])
    if description:
        job_ctx += f"\nJOBBESKRIVELSE:\n{description[:2000]}"

    # ── Hent kandidatprofil til gap-analyse ───────────────────────────────────
    try:
        snap = MemorySnapshotService(supabase).snapshot(user["id"])
        candidate_summary = snap.get("text_summary") or ""
    except Exception:
        snap = {}
        candidate_summary = ""

    # Byg kort profilsummary til systemprompten
    profile_ctx = ""
    if candidate_summary:
        profile_ctx = f"\nKANDIDATENS PROFIL (uddrag):\n{candidate_summary[:1200]}"

    SYSTEM = (
        "Du er en erfaren karrierecoach der forbereder en kandidat til at søge et specifikt job.\n\n"
        f"{job_ctx}"
        f"{profile_ctx}\n\n"
        "Din opgave:\n"
        "1. Sammenlign jobkravene med kandidatens profil og identificer 1-2 konkrete huller eller\n"
        "   styrker der ikke fremgår tydeligt af profilen\n"
        "2. Stil målrettede spørgsmål baseret på disse huller — fx 'Jobbet kræver X, men det fremgår\n"
        "   ikke af din profil — hvordan dækker du det?'\n"
        "3. Spørg om ansøgningsfrist og motivation\n"
        "4. Spørg om kontaktperson hvis det er relevant\n\n"
        "Regler:\n"
        "- Stil ét spørgsmål ad gangen — aldrig to på én gang\n"
        "- Vær konkret og direkte, maksimalt 3 sætninger per svar\n"
        "- Stil maksimalt 4-5 spørgsmål i alt\n"
        "- Svar altid på dansk\n"
        "- Afslut med en kort opsummering af hvad du vil gemme"
    )

    if body.extract:
        conversation = "\n".join(
            f"{'Kandidat' if m.get('role') == 'user' else 'Coach'}: {m.get('content', '')}"
            for m in body.messages
            if m.get("role") in ("user", "assistant")
        )
        try:
            llm = LiteLLMProvider(user["id"])
            resp = await llm.complete(
                "cv_agent",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Du analyserer en karrierecoach-samtale om stillingen '{title}' hos '{company}'.\n"
                            "Returner KUN JSON med disse felter:\n"
                            '  "deadline": "YYYY-MM-DD eller null",\n'
                            '  "contact_person": "navn/titel eller null",\n'
                            '  "motivation": "kandidatens motivation for stillingen, maks 2 sætninger, eller null",\n'
                            '  "gap_response": "hvordan kandidaten adresserer kompetencegab, maks 2 sætninger, eller null",\n'
                            '  "key_selling_points": "kandidatens stærkeste argumenter for stillingen, maks 2 sætninger, eller null"\n'
                            "Brug KUN oplysninger fra samtalen. Returner KUN JSON."
                        ),
                    },
                    {"role": "user", "content": f"Samtale om '{title}' hos '{company}':\n\n{conversation}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=500,
            )
            extracted = _json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:
            logger.warning("job_interview extract failed: %s", exc)
            extracted = {}

        # ── Gem til job-noter ─────────────────────────────────────────────────
        notes_parts = []
        if extracted.get("motivation"):
            notes_parts.append(f"Motivation: {extracted['motivation']}")
        if extracted.get("gap_response"):
            notes_parts.append(f"Gap-svar: {extracted['gap_response']}")
        if extracted.get("key_selling_points"):
            notes_parts.append(f"Salgspunkter: {extracted['key_selling_points']}")
        if extracted.get("contact_person"):
            notes_parts.append(f"Kontakt: {extracted['contact_person']}")

        if notes_parts:
            existing = job.get("notes") or ""
            new_note = "\n".join(notes_parts)
            merged = (f"{existing.strip()}\n\n{new_note}".strip() if existing.strip() else new_note)
            svc.update_job(job_id, user["id"], {"notes": merged})

        # ── Gem til career_memories (master CV-kontekst) ──────────────────────
        # Indsigterne fra jobinterviewet gemmes i career memory så de er
        # tilgængelige for CV- og ansøgningsgeneratorer via memory snapshot.
        try:
            from app.services.memory_service import MemoryService
            mem_svc = MemoryService(supabase)
            memory_parts = [f"Job-interview indsigt — {title} hos {company}:"]
            if extracted.get("motivation"):
                memory_parts.append(f"Motivation: {extracted['motivation']}")
            if extracted.get("gap_response"):
                memory_parts.append(f"Kompetencegab-svar: {extracted['gap_response']}")
            if extracted.get("key_selling_points"):
                memory_parts.append(f"Stærkeste argumenter: {extracted['key_selling_points']}")
            if len(memory_parts) > 1:
                mem_svc.create_memory(
                    user_id=user["id"],
                    content="\n".join(memory_parts),
                    memory_type="career_note",
                    source="ai_extracted",
                    relevance_score=0.8,
                )
                # Invalider snapshot-cache så næste CV-generering bruger de nye indsigter
                MemorySnapshotService(supabase).invalidate(user["id"])
        except Exception as exc:
            logger.warning("job_interview memory save failed: %s", exc)

        # ── Gem deadline på pipeline-entry ─────────────────────────────────────
        deadline = extracted.get("deadline")
        if deadline:
            try:
                rows = supabase.table("application_pipeline").select("id").eq("job_id", job_id).eq("user_id", user["id"]).limit(1).execute()
                if rows.data:
                    from app.services.application_service import ApplicationService
                    ApplicationService(supabase).update_pipeline(
                        user["id"], rows.data[0]["id"], {"deadline": deadline}
                    )
            except Exception as exc:
                logger.warning("job_interview deadline save failed: %s", exc)

        return {"saved": True, "deadline": deadline, "extracted": extracted}

    # ── Streaming SSE-svar ────────────────────────────────────────────────────
    async def event_stream():
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def producer():
            try:
                llm = LiteLLMProvider(user["id"])
                messages = [{"role": "system", "content": SYSTEM}] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in body.messages
                    if m.get("role") in ("user", "assistant")
                ]
                resp = await llm.complete(
                    "cv_agent", messages, stream=True, temperature=0.7, max_tokens=400,
                )
                async for chunk in resp:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        await queue.put(("data", _json.dumps({"type": "chunk", "content": delta})))
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                try:
                    await queue.put(("data", _json.dumps({"type": "error", "content": str(exc)})))
                except Exception:
                    pass
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

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

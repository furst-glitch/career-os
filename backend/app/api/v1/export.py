"""
Export API — PDF og DOCX download

GET /export/cv/pdf                   ?template=ats_professional
GET /export/cv/docx                  ?template=ats_professional
GET /export/document/{id}/pdf        ?template=corporate
GET /export/document/{id}/docx       ?template=corporate

CV templates:  ats_professional | modern_professional | executive | minimal_nordic | creative_professional
App templates: corporate | executive | modern | technical | graduate
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import get_current_user, get_supabase_admin
from app.services.export_service import (
    export_cv_as_docx,
    export_cv_as_pdf,
    export_generated_cv_as_docx,
    export_generated_cv_as_pdf,
    export_text_as_docx,
    export_text_as_pdf,
)

router = APIRouter(prefix="/export", tags=["Export"])

from pydantic import BaseModel

CV_TEMPLATES = {
    "ats_professional", "modern_professional", "executive",
    "minimal_nordic", "creative_professional",
}
APP_TEMPLATES = {"corporate", "executive", "modern", "technical", "graduate"}


class TemplatePreferences(BaseModel):
    default_cv_template: str | None = None
    default_app_template: str | None = None


def _safe_filename(text: str) -> str:
    return re.sub(r"[^\w\-.]", "_", text)[:60]


def _load_cv_data(supabase, user_id: str) -> dict:
    mcv_row = supabase.table("master_cvs").select("*").eq("user_id", user_id).limit(1).execute()
    if not mcv_row.data:
        raise HTTPException(404, "Ingen Master CV fundet — upload dit CV først")
    mcv = mcv_row.data[0]
    mcv_id = mcv["id"]
    profile = supabase.table("user_profiles").select(
        "display_name, full_name, email, phone, location, linkedin_url, default_cv_template, default_app_template"
    ).eq("user_id", user_id).limit(1).execute()
    profile_data = profile.data[0] if profile.data else {}
    return {
        "profile": profile_data,
        "master_cv": mcv,
        "experiences": supabase.table("cv_experiences").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or [],
        "skills": supabase.table("cv_skills").select("*").eq("master_cv_id", mcv_id).order("sort_order").execute().data or [],
        "educations": supabase.table("cv_educations").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or [],
        "certifications": supabase.table("cv_certifications").select("*").eq("master_cv_id", mcv_id).execute().data or [],
    }


# ── Master CV export ──────────────────────────────────────────────────────────

@router.get("/cv/pdf")
async def export_cv_pdf(
    template: str = Query(default="", description="CV template name"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    cv_data = _load_cv_data(supabase, user["id"])
    resolved = template if template in CV_TEMPLATES else (
        cv_data["profile"].get("default_cv_template") or "ats_professional"
    )
    pdf_bytes = export_cv_as_pdf(cv_data, resolved)
    name = cv_data["profile"].get("display_name") or "CV"
    filename = _safe_filename(f"{name}_CV_{resolved}") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cv/docx")
async def export_cv_docx_endpoint(
    template: str = Query(default="", description="CV template name"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    cv_data = _load_cv_data(supabase, user["id"])
    resolved = template if template in CV_TEMPLATES else (
        cv_data["profile"].get("default_cv_template") or "ats_professional"
    )
    docx_bytes = export_cv_as_docx(cv_data, resolved)
    name = cv_data["profile"].get("display_name") or "CV"
    filename = _safe_filename(f"{name}_CV_{resolved}") + ".docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── CV full data endpoint (for frontend preview) ──────────────────────────────

@router.get("/cv/full")
async def get_cv_full(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Return structured CV data for frontend template preview."""
    cv_data = _load_cv_data(supabase, user["id"])
    return cv_data


# ── Document (ansøgning) export ───────────────────────────────────────────────

@router.get("/document/{document_id}/pdf")
async def export_document_pdf(
    document_id: str,
    template: str = Query(default="", description="Application template name"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    doc_row = supabase.table("document_versions").select("*").eq("id", document_id).eq("user_id", user["id"]).limit(1).execute()
    if not doc_row.data:
        raise HTTPException(404, "Dokument ikke fundet")
    d = doc_row.data[0]

    # Fetch profile — inkl. kontaktfelter til CV-export
    profile_row = supabase.table("user_profiles").select(
        "display_name, full_name, email, phone, location, linkedin_url, "
        "default_cv_template, default_app_template"
    ).eq("user_id", user["id"]).limit(1).execute()
    profile = profile_row.data[0] if profile_row.data else {}

    title = d.get("title") or "Dokument"
    content = d.get("content") or ""
    doc_type = d.get("document_type") or ""
    is_cv = doc_type in ("cv", "cv_version") or title.startswith("CV")

    if is_cv:
        pdf_bytes = export_generated_cv_as_pdf(title, content, profile)
    else:
        resolved = template if template in APP_TEMPLATES else (
            profile.get("default_app_template") or "corporate"
        )
        pdf_bytes = export_text_as_pdf(title, content, resolved, profile=profile)

    filename = _safe_filename(title) + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/document/{document_id}/docx")
async def export_document_docx(
    document_id: str,
    template: str = Query(default="", description="Application template name"),
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    doc_row = supabase.table("document_versions").select("*").eq("id", document_id).eq("user_id", user["id"]).limit(1).execute()
    if not doc_row.data:
        raise HTTPException(404, "Dokument ikke fundet")
    d = doc_row.data[0]

    profile_row = supabase.table("user_profiles").select(
        "display_name, full_name, email, phone, location, linkedin_url, "
        "default_cv_template, default_app_template"
    ).eq("user_id", user["id"]).limit(1).execute()
    profile = profile_row.data[0] if profile_row.data else {}

    title = d.get("title") or "Dokument"
    content = d.get("content") or ""
    doc_type = d.get("document_type") or ""
    is_cv = doc_type in ("cv", "cv_version") or title.startswith("CV")

    if is_cv:
        docx_bytes = export_generated_cv_as_docx(title, content, profile)
    else:
        resolved = template if template in APP_TEMPLATES else (
            profile.get("default_app_template") or "corporate"
        )
        docx_bytes = export_text_as_docx(title, content, resolved, profile=profile)

    filename = _safe_filename(title) + ".docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Template preferences ──────────────────────────────────────────────────────

@router.get("/preferences")
async def get_template_preferences(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Return user's saved default template choices."""
    row = (
        supabase.table("user_profiles")
        .select("default_cv_template, default_app_template")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    data = row.data[0] if row.data else {}
    return {
        "default_cv_template": data.get("default_cv_template") or "ats_professional",
        "default_app_template": data.get("default_app_template") or "corporate",
    }


@router.put("/preferences")
async def set_template_preferences(
    body: TemplatePreferences,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    """Persist user's default template choices."""
    updates: dict = {}
    if body.default_cv_template:
        if body.default_cv_template not in CV_TEMPLATES:
            raise HTTPException(400, f"Ukendt CV-template: {body.default_cv_template}")
        updates["default_cv_template"] = body.default_cv_template
    if body.default_app_template:
        if body.default_app_template not in APP_TEMPLATES:
            raise HTTPException(400, f"Ukendt ansøgnings-template: {body.default_app_template}")
        updates["default_app_template"] = body.default_app_template
    if updates:
        supabase.table("user_profiles").update(updates).eq("user_id", user["id"]).execute()
    return {"ok": True, **updates}

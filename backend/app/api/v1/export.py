"""
Export API — PDF og DOCX download

GET /export/cv/pdf          - Download Master CV som PDF
GET /export/cv/docx         - Download Master CV som DOCX
GET /export/document/{id}/pdf   - Download dokument (ansøgning) som PDF
GET /export/document/{id}/docx  - Download dokument (ansøgning) som DOCX
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.deps import get_current_user, get_supabase_admin
from app.services.export_service import (
    export_cv_as_docx,
    export_cv_as_pdf,
    export_text_as_docx,
    export_text_as_pdf,
)

router = APIRouter(prefix="/export", tags=["Export"])


def _safe_filename(text: str) -> str:
    return re.sub(r"[^\w\-.]", "_", text)[:60]


# ── Master CV export ──────────────────────────────────────────────────────────

@router.get("/cv/pdf")
async def export_cv_pdf(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    user_id = user["id"]

    mcv_row = supabase.table("master_cvs").select("*").eq("user_id", user_id).limit(1).execute()
    if not mcv_row.data:
        raise HTTPException(404, "Ingen Master CV fundet — upload dit CV først")

    mcv = mcv_row.data[0]
    mcv_id = mcv["id"]

    profile = supabase.table("user_profiles").select("display_name").eq("user_id", user_id).limit(1).execute()
    profile_data = profile.data[0] if profile.data else {}

    experiences = supabase.table("cv_experiences").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or []
    skills = supabase.table("cv_skills").select("*").eq("master_cv_id", mcv_id).order("sort_order").execute().data or []
    educations = supabase.table("cv_educations").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or []
    certs = supabase.table("cv_certifications").select("*").eq("master_cv_id", mcv_id).execute().data or []

    cv_data = {
        "profile": profile_data,
        "master_cv": mcv,
        "experiences": experiences,
        "skills": skills,
        "educations": educations,
        "certifications": certs,
    }

    pdf_bytes = export_cv_as_pdf(cv_data)
    name = profile_data.get("display_name") or "CV"
    filename = _safe_filename(f"{name}_CV") + ".pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cv/docx")
async def export_cv_docx(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    user_id = user["id"]

    mcv_row = supabase.table("master_cvs").select("*").eq("user_id", user_id).limit(1).execute()
    if not mcv_row.data:
        raise HTTPException(404, "Ingen Master CV fundet — upload dit CV først")

    mcv = mcv_row.data[0]
    mcv_id = mcv["id"]

    profile = supabase.table("user_profiles").select("display_name").eq("user_id", user_id).limit(1).execute()
    profile_data = profile.data[0] if profile.data else {}

    experiences = supabase.table("cv_experiences").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or []
    skills = supabase.table("cv_skills").select("*").eq("master_cv_id", mcv_id).order("sort_order").execute().data or []
    educations = supabase.table("cv_educations").select("*").eq("master_cv_id", mcv_id).order("period_start", desc=True).execute().data or []
    certs = supabase.table("cv_certifications").select("*").eq("master_cv_id", mcv_id).execute().data or []

    cv_data = {
        "profile": profile_data,
        "master_cv": mcv,
        "experiences": experiences,
        "skills": skills,
        "educations": educations,
        "certifications": certs,
    }

    docx_bytes = export_cv_as_docx(cv_data)
    name = profile_data.get("display_name") or "CV"
    filename = _safe_filename(f"{name}_CV") + ".docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Document (ansøgning / cover letter) export ────────────────────────────────

@router.get("/document/{document_id}/pdf")
async def export_document_pdf(
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    doc = supabase.table("document_versions").select("*").eq("id", document_id).eq("user_id", user["id"]).limit(1).execute()
    if not doc.data:
        raise HTTPException(404, "Dokument ikke fundet")
    d = doc.data[0]
    pdf_bytes = export_text_as_pdf(d.get("title") or "Dokument", d.get("content") or "")
    filename = _safe_filename(d.get("title") or "dokument") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/document/{document_id}/docx")
async def export_document_docx(
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    doc = supabase.table("document_versions").select("*").eq("id", document_id).eq("user_id", user["id"]).limit(1).execute()
    if not doc.data:
        raise HTTPException(404, "Dokument ikke fundet")
    d = doc.data[0]
    docx_bytes = export_text_as_docx(d.get("title") or "Dokument", d.get("content") or "")
    filename = _safe_filename(d.get("title") or "dokument") + ".docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

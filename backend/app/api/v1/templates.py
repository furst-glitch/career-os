"""
P3 – Document Templates API

GET    /templates             - list brugerens templates (filter: ?type=cover_letter)
POST   /templates             - opret template
GET    /templates/{id}        - hent template
PUT    /templates/{id}        - opdater template
DELETE /templates/{id}        - slet template
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user, get_supabase_admin
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])


class TemplateBody(BaseModel):
    name: str
    type: str = "cover_letter"
    language: str = "da"
    content: str = ""
    writing_style: str = "professional"
    focus_areas: list[str] = []


@router.get("")
async def list_templates(
    type: str | None = None,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return TemplateService(supabase).list_templates(user["id"], template_type=type)


@router.post("", status_code=201)
async def create_template(
    body: TemplateBody,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    return TemplateService(supabase).create_template(user["id"], body.model_dump())


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    t = TemplateService(supabase).get_template(user["id"], template_id)
    if not t:
        raise HTTPException(404, "Template ikke fundet")
    return t


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateBody,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    t = TemplateService(supabase).update_template(user["id"], template_id, body.model_dump())
    if not t:
        raise HTTPException(404, "Template ikke fundet")
    return t


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    ok = TemplateService(supabase).delete_template(user["id"], template_id)
    if not ok:
        raise HTTPException(404, "Template ikke fundet")

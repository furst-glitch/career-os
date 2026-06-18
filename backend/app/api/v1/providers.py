"""
AI Provider API — BYOK (Bring Your Own Key)

GET    /providers              - List konfigurerede providers (hints, ikke rå nøgler)
POST   /providers              - Tilføj eller opdater en provider-nøgle / Ollama URL
DELETE /providers/{provider}   - Fjern en provider-nøgle
POST   /providers/validate     - Test om en nøgle/endpoint virker
GET    /providers/default      - Hent brugerens standard-provider
PUT    /providers/default      - Sæt brugerens standard-provider
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.core.deps import get_current_user, get_supabase_admin
from app.providers.key_manager import KeyManager

router = APIRouter(prefix="/providers", tags=["AI Udbydere"])

VALID_PROVIDERS = {"openai", "anthropic", "ollama", "custom"}
ProviderName = Literal["openai", "anthropic", "ollama", "custom"]


class UpsertProviderRequest(BaseModel):
    provider: ProviderName
    key: str  # API-nøgle for openai/anthropic, URL for ollama

    @field_validator("key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nøgle/URL må ikke være tom")
        return v


class SetDefaultProviderRequest(BaseModel):
    provider: ProviderName


class ValidateProviderRequest(BaseModel):
    provider: ProviderName
    key: str


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("")
async def list_providers(user=Depends(get_current_user)):
    """Returnerer alle aktive providers med de sidste 4 tegn af nøglen — aldrig den rå nøgle."""
    providers = await KeyManager.list_providers(user["id"])
    return {"providers": providers}


# ── Upsert ─────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def upsert_provider(
    body: UpsertProviderRequest,
    user=Depends(get_current_user),
):
    """Tilføj eller opdater en API-nøgle. For Ollama sendes base URL i 'key'-feltet."""
    await KeyManager.store_key(user["id"], body.provider, body.key)
    return {"provider": body.provider, "status": "gemt"}


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/{provider}", status_code=204)
async def delete_provider(
    provider: ProviderName,
    user=Depends(get_current_user),
):
    """Slet en provider-nøgle permanent."""
    await KeyManager.delete_key(user["id"], provider)


# ── Validate ───────────────────────────────────────────────────────────────────

@router.post("/validate")
async def validate_provider(body: ValidateProviderRequest):
    """
    Test om en nøgle/endpoint virker uden at gemme den.
    Sender en minimal API-forespørgsel og returnerer om den lykkedes.
    """
    import litellm

    provider = body.provider
    key = body.key.strip()

    try:
        if provider == "ollama":
            await litellm.acompletion(
                model="ollama/llama3.2",
                messages=[{"role": "user", "content": "ping"}],
                api_base=key,
                max_tokens=1,
            )
        elif provider == "openai":
            await litellm.acompletion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ping"}],
                api_key=key,
                max_tokens=1,
            )
        elif provider == "anthropic":
            await litellm.acompletion(
                model="anthropic/claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": "ping"}],
                api_key=key,
                max_tokens=1,
            )
        else:
            return {"valid": False, "error": f"Validering ikke understøttet for '{provider}'"}

        return {"valid": True}

    except Exception as exc:
        return {"valid": False, "error": str(exc)}


# ── Default provider ───────────────────────────────────────────────────────────

@router.get("/default")
async def get_default_provider(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    result = (
        supabase.table("user_profiles")
        .select("default_ai_provider")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    default = result.data[0].get("default_ai_provider") if result.data else None
    return {"default_provider": default}


@router.put("/default")
async def set_default_provider(
    body: SetDefaultProviderRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_admin),
):
    supabase.table("user_profiles").update(
        {"default_ai_provider": body.provider}
    ).eq("user_id", user["id"]).execute()
    return {"default_provider": body.provider}

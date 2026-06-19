from app.core.deps import get_supabase_admin
from app.core.security import decrypt, encrypt


class KeyManager:
    @staticmethod
    async def get_key(user_id: str, provider: str) -> str | None:
        supabase = get_supabase_admin()
        result = (
            supabase.table("user_api_keys")
            .select("encrypted_key")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return decrypt(result.data[0]["encrypted_key"])

    @staticmethod
    async def store_key(user_id: str, provider: str, plaintext_key: str) -> None:
        supabase = get_supabase_admin()
        supabase.table("user_api_keys").upsert(
            {
                "user_id": user_id,
                "provider": provider,
                "encrypted_key": encrypt(plaintext_key),
                "key_hint": plaintext_key[-4:] if len(plaintext_key) >= 4 else plaintext_key,
                "is_active": True,
            },
            on_conflict="user_id,provider",
        ).execute()

    @staticmethod
    async def revoke_key(user_id: str, provider: str) -> None:
        supabase = get_supabase_admin()
        supabase.table("user_api_keys").update({"is_active": False}).eq(
            "user_id", user_id
        ).eq("provider", provider).execute()

    @staticmethod
    async def delete_key(user_id: str, provider: str) -> None:
        supabase = get_supabase_admin()
        supabase.table("user_api_keys").delete().eq(
            "user_id", user_id
        ).eq("provider", provider).execute()

    @staticmethod
    async def list_providers(user_id: str) -> list[dict]:
        """Returnerer alle aktive providers med key_hint — aldrig den rå nøgle."""
        supabase = get_supabase_admin()
        result = (
            supabase.table("user_api_keys")
            .select("provider, key_hint, is_active, created_at")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        return result.data or []

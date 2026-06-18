from app.core.security import decrypt
from app.core.deps import get_supabase_admin


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
            .single()
            .execute()
        )
        if not result.data:
            return None
        return decrypt(result.data["encrypted_key"])

    @staticmethod
    async def store_key(user_id: str, provider: str, plaintext_key: str) -> None:
        from app.core.security import encrypt
        supabase = get_supabase_admin()
        supabase.table("user_api_keys").upsert({
            "user_id": user_id,
            "provider": provider,
            "encrypted_key": encrypt(plaintext_key),
            "key_hint": plaintext_key[-4:],
            "is_active": True,
        }).execute()

    @staticmethod
    async def revoke_key(user_id: str, provider: str) -> None:
        supabase = get_supabase_admin()
        supabase.table("user_api_keys").update({"is_active": False}).eq(
            "user_id", user_id
        ).eq("provider", provider).execute()

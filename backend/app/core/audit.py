from datetime import datetime, timezone
from supabase import Client


async def log_action(
    supabase: Client,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    supabase.table("audit_logs").insert({
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

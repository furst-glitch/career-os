import asyncio
import traceback
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def test():
    from app.providers.litellm_provider import LiteLLMProvider

    fake_user = "00000000-0000-0000-0000-000000000001"

    print("1. _get_agent_config('cv_agent')")
    try:
        llm = LiteLLMProvider(fake_user)
        cfg = await llm._get_agent_config("cv_agent")
        print(f"   OK — provider={cfg.get('default_provider')}, model={cfg.get('default_model')}")
    except Exception:
        traceback.print_exc()

    print("2. _resolve_model('cv_agent')")
    try:
        llm2 = LiteLLMProvider(fake_user)
        provider, model = await llm2._resolve_model("cv_agent")
        print(f"   OK — provider={provider}, model={model}")
    except Exception:
        traceback.print_exc()

    print("3. _resolve_api_key('anthropic')")
    try:
        llm3 = LiteLLMProvider(fake_user)
        key, base = await llm3._resolve_api_key("anthropic")
        klen = len(key) if key else 0
        print(f"   OK — key={'set (' + str(klen) + ' chars)' if key else 'None'}, base={base}")
    except Exception:
        traceback.print_exc()

    print("4. Test agent registry query count")
    try:
        from app.core.deps import get_supabase_admin
        db = get_supabase_admin()
        r = db.table("agent_registry").select("name").execute()
        print(f"   OK — {len(r.data)} agents: {[x['name'] for x in r.data]}")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())

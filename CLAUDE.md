# CareerOS — Developer Guide

AI-drevet karriereplatform. Claude Code er primær udvikler under menneskelig styring.

## Projektstruktur

```
CareerOS/
├── backend/          FastAPI + Python 3.12
├── frontend/         Next.js 15 + TypeScript
├── supabase/         Migrations + seed
├── docs/             Arkitektur og reference
├── .github/          CI/CD workflows
└── CLAUDE.md         Dette dokument
```

## Tech Stack

| Lag | Teknologi |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Shadcn/ui |
| Backend | FastAPI, Python 3.12, Pydantic v2 |
| Database | Supabase (PostgreSQL 15 + pgvector + Auth + Storage) |
| AI | LiteLLM (OpenAI, Anthropic, Ollama) |
| Betaling | Stripe |
| CI/CD | GitHub Actions → Vercel (frontend) + Render (backend) |

## Lokalt udviklingsmiljø

```bash
# 1. Start Supabase lokalt
supabase start

# 2. Start backend + frontend
make dev

# Eller separat:
make dev-backend    # http://localhost:8000
make dev-frontend   # http://localhost:3000
make dev-docs       # API docs: http://localhost:8000/api/docs
```

## Miljøvariabler

Kopier og udfyld:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

## Database

### Tilføj ny migration

```bash
# Opret fil med næste nummer
touch supabase/migrations/000XX_beskrivelse.sql

# Anvend lokalt
supabase db reset   # Nulstil og anvend alle migrations
# ELLER
supabase db push    # Anvend kun nye migrations
```

### Migrationskonventioner

- Brug `gen_random_uuid()` til alle primærnøgler
- Alle tabeller har `created_at timestamptz NOT NULL DEFAULT now()`
- Alle tabeller der tilhører en bruger har `user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE`
- Aktiver altid RLS: `ALTER TABLE table ENABLE ROW LEVEL SECURITY`
- Skriv RLS-policies i `00014_rls_policies.sql` — ikke i tabellens egne migrations
- Skriv performance-indexes i `00015_indexes.sql`

### Supabase klient-brug

Backend bruger Supabase Python-klient for CRUD og auth:

```python
# I services — brug altid service-role til server-side operationer
from app.core.deps import get_supabase_admin
supabase = get_supabase_admin()

# Hent data
result = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()

# Vector-søgning via RPC
result = supabase.rpc("match_memories", {"query_embedding": embedding, "user_id": user_id}).execute()
```

## AI Providers

### Tilføj ny provider

Alle AI-kald går igennem `backend/app/providers/litellm_provider.py`.
Providers konfigureres i `agent_registry`-tabellen, ikke i kode.

```python
# Sådan kalder du en agent
from app.providers.litellm_provider import LiteLLMProvider

provider = LiteLLMProvider(user_id=user_id)
response = await provider.complete(
    agent_name="cv_agent",
    messages=[...],
    stream=True,
)
```

### Brugerens egne API-nøgler

Krypterede nøgler hentes via `KeyManager`:

```python
from app.providers.key_manager import KeyManager
key = await KeyManager.get_key(user_id, provider="openai")
```

## Agent-arkitektur

### Tilføj ny agent

1. Registrer i `agent_registry`-tabellen (via seed eller migration)
2. Opret fil: `backend/app/agents/my_agent.py`
3. Extend `BaseAgent`:

```python
from app.agents.base import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    name = "my_agent"

    async def run(self, input_data: dict) -> AgentResult:
        context = await self.get_memory_context()  # Career Memory
        messages = self.build_messages(input_data, context)
        response = await self.provider.complete(self.name, messages)
        await self.log_usage(response)
        return AgentResult(content=response.content, usage=response.usage)
```

4. Registrer i `backend/app/agents/pipeline.py`

### Multi-agent review pipeline

Review Board orkestrerer: ATS → HR → Hiring Manager (parallelt), derefter Critic → Career Coach → Review Board (syntetiserer).

```python
from app.agents.pipeline import ReviewPipeline

pipeline = ReviewPipeline(user_id=user_id)
report = await pipeline.run(document_id=doc_id, job_id=job_id)
```

## API-konventioner

- Alle endpoints under `/api/v1/`
- Auth via Supabase JWT i `Authorization: Bearer <token>` header
- Streaming via Server-Sent Events (SSE) for AI-genererede svar
- Async background tasks returnerer `{ task_id: uuid }` — polling via `/api/v1/tasks/{id}`
- Alle responses bruger Pydantic schemas fra `backend/app/schemas/`

### Tilføj nyt endpoint

```python
# backend/app/api/v1/my_feature.py
from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.schemas.my_feature import MyRequest, MyResponse
from app.services.my_service import MyService

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

@router.post("/", response_model=MyResponse)
async def create_thing(
    request: MyRequest,
    user=Depends(get_current_user),
):
    service = MyService()
    return await service.create(user.id, request)
```

Tilføj routeren i `backend/app/api/v1/__init__.py`.

## AI Cost Management

**VIGTIGT:** Alle AI-kald SKAL gå igennem `LiteLLMProvider` — aldrig direkte til OpenAI/Anthropic.
`LiteLLMProvider` håndterer automatisk:
- Budget-check (bloker hvis hard_limit overskredet)
- Token-logging til `ai_usage`
- Aggregering til `ai_costs`

## Sikkerhed

- Brug aldrig `supabase_service_role_key` på klientsiden
- Bruger-API-nøgler krypteres med AES-256 via `KeyManager` — gem aldrig i plaintext
- Valider altid brugerens ejerab via `auth.uid()` i RLS (databaselaget) og `get_current_user()` i applikationslaget
- Log alle brugerhandlinger via `AuditService`

## GDPR

- Data-eksport: `GET /api/v1/gdpr/export` — returnerer komplet brugerdata som JSON
- Data-sletning: `DELETE /api/v1/gdpr/delete` — soft-delete, hard-delete efter 30 dage
- Samtykke logges i `audit_logs` med timestamp

## Testing

```bash
make test           # Kør alle tests
make test-backend   # Kun backend
make test-frontend  # Kun frontend (typecheck + lint)
```

Backend tests bruger `pytest` med `httpx.AsyncClient`.
Supabase mockes via lokalt Supabase (supabase start).

## Subscription-gates

Brug `require_plan` dependency til at gate features:

```python
from app.core.deps import require_plan

@router.post("/review")
async def multi_agent_review(
    user=Depends(require_plan("pro")),  # Bloker free-brugere
):
    ...
```

## Deployment

Se `docs/deployment.md` for detaljer.

- **Frontend:** Vercel (auto-deploy fra `main`-branch)
- **Backend:** Render (Python web service, `render.yaml` i roden, auto-deploy fra `main`)
- **Database:** Supabase Cloud (EU/Frankfurt)

## Faseplan

| Fase | Scope |
|---|---|
| 1 | Auth, CV Studio, Application Pipeline, Ansøgningsgenerering, Stripe |
| 2 | Experience Discovery, Career Memory, Interview Center, Search Intelligence |
| 3 | Multi-agent review, Voice interviews, ATS-integrationer, Enterprise |

## Vigtige filer at kende

| Fil | Formål |
|---|---|
| `backend/app/core/config.py` | Alle miljøvariabler |
| `backend/app/core/deps.py` | FastAPI dependencies (auth, DB, plan-gates) |
| `backend/app/agents/base.py` | BaseAgent alle agenter extender |
| `backend/app/agents/pipeline.py` | Multi-agent orchestration |
| `backend/app/providers/litellm_provider.py` | AI-kald med budget-check |
| `supabase/migrations/00014_rls_policies.sql` | Alle Row Level Security policies |
| `supabase/migrations/00015_indexes.sql` | Alle performance-indexes |

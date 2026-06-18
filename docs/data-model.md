# CareerOS — Datamodel Reference

41 tabeller fordelt på 11 moduler. Se migrations for komplet DDL.

## Tabel-oversigt

### Auth & Profil
- `user_profiles` — Display name, sprog, avatar
- `subscriptions` — Plan, status, Stripe IDs
- `user_api_keys` — Krypterede AI-nøgler pr. provider

### Career Memory
- `career_memories` — Semantisk søgbare minder (pgvector)
- `career_goals` — Kort- og langsigtede mål
- `career_preferences` — Industrier, arbejdsstil, værdier
- `career_milestones` — Vigtige karrieremilepæle

### Experience Discovery
- `experiences` — Erfaringer (job, projekter, frivillig)
- `star_stories` — Situation/Task/Action/Result historier
- `competency_library` — Kompetencer med belæg
- `discovery_sessions` — AI-interview sessioner

### CV Studio
- `master_cvs` — Brugerens kanoniske CV
- `cv_experiences` — CV-erfaringsafsnit
- `cv_educations` — CV-uddannelsesafsnit
- `cv_skills` — CV-kompetencer

### Agent Registry
- `agent_registry` — 11 agenter med model/temp/tokens
- `agent_capabilities` — Capabilities pr. agent med plan-gate
- `agent_configurations` — Per-bruger overrides

### Document Versioning
- `document_versions` — Alle genererede dokumenter
- `document_relationships` — Lineage: derived_from, replaces, etc.
- `pipeline_documents` — Junction: pipeline ↔ dokument

### Application Pipeline
- `jobs` — Fundne/gemte jobopslag
- `application_pipeline` — 10-state livscyklus
- `application_status_history` — Komplet status-historik

### Search Intelligence
- `user_keywords` — Keywords med type og vægt
- `job_relevance_signals` — Brugers reaktioner på jobs
- `search_profiles` — Gemte søgeprofiler
- `keyword_performance` — Daglig præstationsaggregering

### Interview Center
- `interview_packages` — Forberedelsespakker pr. job
- `company_research` — Cached virksomhedsresearch (30 dage TTL)
- `role_analyses` — Jobopslags-analyser
- `knowledge_guides` — Statisk indhold (DA + EN)
- `salary_prep_sessions` — Lønforhandlingsforberedelse
- `interview_sessions` — Træningssessioner
- `interview_items` — Spørgsmål + svar + feedback

### AI Cost Management
- `ai_usage` — Hvert AI-kald: tokens, cost, latency
- `ai_costs` — Månedlige aggregeringer pr. bruger
- `ai_budgets` — Budgetgrænser med hard/soft limit

### Audit & GDPR
- `audit_logs` — Alle brugerhandlinger
- `gdpr_requests` — Export/sletningsanmodninger

## Nøgle-relationer

```
auth.users
  └── user_profiles (1:1)
  └── subscriptions (1:1)
  └── user_api_keys (1:N)
  └── master_cvs (1:1)
       └── cv_experiences (1:N)
       └── cv_educations (1:N)
       └── cv_skills (1:N)
  └── career_memories (1:N) ← pgvector embedding
  └── jobs (1:N)
       └── application_pipeline (1:1 per user+job)
            └── application_status_history (1:N)
            └── pipeline_documents (M:N)
                 └── document_versions
  └── ai_usage (1:N) ← via agent_registry
  └── ai_budgets (1:1)
```

## Konventioner

- PK: `uuid DEFAULT gen_random_uuid()`
- FK til bruger: `uuid REFERENCES auth.users(id) ON DELETE CASCADE`
- Timestamps: `created_at timestamptz NOT NULL DEFAULT now()`
- Embeddings: `vector(1536)` — OpenAI text-embedding-3-small
- Alle tabeller har RLS aktiveret

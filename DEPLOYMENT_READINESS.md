# CareerOS — Deployment Readiness Report
**Sprint:** Validation & Deployment Sprint  
**Dato:** 2026-06-18  
**Status:** KLAR TIL LOKAL TEST — IKKE KLAR TIL PRODUCTION

---

## 1. GitHub Setup

| Check | Status | Handling |
|---|---|---|
| Git-repository initialiseret | ✅ | — |
| `.gitignore` korrekt (`.env`, `node_modules`, `__pycache__`) | ✅ | — |
| GitHub remote konfigureret | ❌ MANGLER | Kør: `git remote add origin https://github.com/ORG/careeros.git && git push -u origin master` |
| Branch-strategi (`main` + `develop`) | ⚠️ | Kun `master` branch eksisterer |
| CI/CD pipeline | ❌ MANGLER | Kræves til production |

**Handling:**
```bash
git remote add origin https://github.com/DIT-ORG/careeros.git
git push -u origin master
```

---

## 2. Supabase Setup

| Check | Status | Note |
|---|---|---|
| `supabase/config.toml` konfigureret | ✅ | project_id: `careeros` |
| Auth e-mail confirmation deaktiveret | ✅ | `enable_confirmations = false` |
| Email signup aktiveret | ✅ | `enable_signup = true` |
| 17 migration-filer klar | ✅ | 00001–00017 |
| RLS aktiveret på alle tabeller | ✅ | Via migrations |
| `supabase/seed.sql` eksisterer | ✅ | — |

### Migration-rækkefølge (kræver køres i orden)

```
00001_extensions.sql       — pgcrypto, uuid-ossp
00002_enums.sql            — alle enum-typer inkl. language_code, discovery_session_type
00003_user_profile.sql     — user_profiles, subscriptions
00004_career_memory.sql    — career_memories, goals, milestones
00005_experience_discovery.sql — discovery_sessions, competencies
00006_cv_studio.sql        — master_cvs, cv_experiences, cv_educations, cv_skills
00007_agent_registry.sql   — agent_configurations, usage_logs
00008_document_versioning.sql
00009_application_pipeline.sql
00010_jobs_search.sql
00011_interview_center.sql
00012_ai_cost_management.sql
00013_audit_gdpr.sql
00014_rls_policies.sql     — RLS på alle tabeller
00015_indexes.sql          — Performance indexes
00016_sprint1_profile_extensions.sql — cv_uploads, cv_projects, cv_achievements,
                                       cv_systems, cv_leadership, cv_certifications,
                                       profile_gaps + ALTER master_cvs, cv_experiences,
                                       discovery_sessions
00017_profile_scores.sql   — profile_scores tabel
```

### Kommandoer (lokal Supabase)
```bash
supabase start
supabase db push          # Anvend alle migrations
# eller reset + seed:
supabase db reset         # Nuller DB og køre migrations + seed
```

### Cloud Supabase
```bash
supabase link --project-ref DIT_PROJECT_REF
supabase db push
```

---

## 3. Environment Variables

### Backend (`backend/.env`)

| Variabel | Påkrævet | Default | Beskrivelse |
|---|---|---|---|
| `DEBUG` | Nej | `false` | `true` aktiverer `/api/docs` |
| `SECRET_KEY` | **JA** | — | Min. 32 tegn, random hex |
| `SUPABASE_URL` | **JA** | — | `http://localhost:54321` lokalt |
| `SUPABASE_ANON_KEY` | **JA** | — | Fra Supabase dashboard |
| `SUPABASE_SERVICE_ROLE_KEY` | **JA** | — | Fra Supabase dashboard |
| `ENCRYPTION_KEY` | **JA** | — | Fernet-nøgle (AES-256) |
| `OPENAI_API_KEY` | **JA*** | — | *Mindst én AI-nøgle kræves |
| `ANTHROPIC_API_KEY` | Nej | — | Alternativ til OpenAI |
| `OLLAMA_BASE_URL` | Nej | — | Lokal Ollama-instans |
| `STRIPE_SECRET_KEY` | Nej | — | Kræves ikke Sprint 1 |
| `STRIPE_WEBHOOK_SECRET` | Nej | — | Kræves ikke Sprint 1 |
| `CORS_ORIGINS` | Nej | `http://localhost:3000` | Kommasepareret |

**Generér nøgler:**
```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Frontend (`frontend/.env.local`)

| Variabel | Påkrævet | Default | Beskrivelse |
|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | **JA** | — | Samme som backend SUPABASE_URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **JA** | — | Samme anon key |
| `NEXT_PUBLIC_API_URL` | **JA** | `http://localhost:8000` | Backend URL |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Nej | — | Kræves ikke Sprint 1 |

---

## 4. Docker Setup

| Check | Status | Note |
|---|---|---|
| Backend `Dockerfile` | ✅ | Python 3.12-slim, uvicorn med `--reload` |
| Frontend `Dockerfile` | ✅ | Node 20-alpine, `npm run dev` |
| `docker-compose.yml` (development) | ✅ | Alle services + CORS_ORIGINS tilføjet |
| `docker-compose.prod.yml` | ⚠️ | Mangler frontend service |
| Backend healthcheck | ✅ | `GET /health` hvert 30s |
| Redis service | ⚠️ | Defineret men ubrugt i Sprint 1 |

**Kendte Docker-begrænsninger (development):**
- Backend kører med `--reload` — ikke til production
- Frontend kører `npm run dev` — ikke til production
- Til production: brug `docker-compose.prod.yml` + build Next.js (`npm run build && npm start`)

**Start lokalt:**
```bash
# Kopier og udfyld .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Redigér begge filer med dine værdier

# Start (kræver Docker Desktop)
docker compose up

# Eller uden Docker:
make dev-supabase   # Terminal 1
make dev-backend    # Terminal 2
make dev-frontend   # Terminal 3
```

---

## 5. Smoke Test

```bash
cd backend
pip install -e ".[dev]"
python smoke_test.py
```

Tester: Python-version, imports, config, Supabase-forbindelse, API-routes, services.

---

## 6. End-to-End Testplan

### TC-01: Login / Signup

| Trin | Forventet | Status |
|---|---|---|
| 1. Åbn `http://localhost:3000` | Redirect til `/login` | 🔲 |
| 2. Klik "Opret konto" → udfyld navn, email, adgangskode | Redirect til `/cv` | 🔲 |
| 3. Log ud og log ind igen | Redirect til `/cv` | 🔲 |
| 4. Besøg `/cv` uden session | Redirect til `/login` | 🔲 |

### TC-02: CV Upload

| Trin | Forventet | Status |
|---|---|---|
| 1. Upload en PDF | Progressindikator, derefter parsing-resultat | 🔲 |
| 2. Upload en DOCX | Samme | 🔲 |
| 3. Upload en ikke-tilladt filtype (fx .png) | Fejlbesked, ingen upload | 🔲 |
| 4. Upload fil > 10 MB | Fejlbesked | 🔲 |
| 5. Se parsed sections (antal erfaringer, skills osv.) | Korrekte tal | 🔲 |
| 6. Klik "Start AI-interview" | Redirect til `/cv/interview` | 🔲 |

### TC-03: PDF Parsing

| Trin | Forventet | Status |
|---|---|---|
| 1. Upload et dansk CV (PDF) | AI returnerer JSON med experiences, skills osv. | 🔲 |
| 2. Verificér at `cv_experiences` er oprettet i DB | Min. 1 erfaring med title, company, period_start | 🔲 |
| 3. Verificér at `profile_gaps` er oprettet | Gaps med section + priority | 🔲 |
| 4. Verificér at initial `profile_scores` er beregnet | overall > 0 | 🔲 |

### TC-04: Discovery Interview

| Trin | Forventet | Status |
|---|---|---|
| 1. Åbn `/cv/interview` | Velkomstbesked streames fra AI | 🔲 |
| 2. Skriv en besked + Enter | AI svarer med streaming tekst | 🔲 |
| 3. Svar er gemt i `discovery_sessions.messages` | Kat AI + user beskeder | 🔲 |
| 4. Profil-score opdateres i sidebar | Score stiger efter nyt svar | 🔲 |
| 5. Genopret siden | Eksisterende session genoptages | 🔲 |
| 6. Nyt browser-vindue → `/cv/interview` | Samme session | 🔲 |

### TC-05: Profile Completeness Score

| Trin | Forventet | Status |
|---|---|---|
| 1. Hent `GET /api/v1/profile/score` | JSON med overall + 7 sektioner | 🔲 |
| 2. Tom profil | overall = 0, missing_areas = 7 items | 🔲 |
| 3. Efter upload af CV med 3 erfaringer | experiences > 70, overall stiger | 🔲 |
| 4. Sidebar viser score med farver (grøn/gul/rød) | Correct farvekodning | 🔲 |
| 5. `POST /profile/score/recalculate` | Ny score beregnet | 🔲 |

### TC-06: Profile Review

| Trin | Forventet | Status |
|---|---|---|
| 1. Åbn `/cv/profile` | Alle 7 sektioner loader | 🔲 |
| 2. Skift fane til "Præstationer" | Viser achievements fra CV + interview | 🔲 |
| 3. Sektion-score bar korrekt | Farve og procent matcher API | 🔲 |
| 4. Åbne gaps vises | Gaps med priority badge | 🔲 |

### TC-07: Master CV Generation

| Trin | Forventet | Status |
|---|---|---|
| 1. Åbn `/cv/master` | Empty state med "Generér" knap | 🔲 |
| 2. Klik "Generér Master CV" | Tekst streamer ind i textarea | 🔲 |
| 3. CV indeholder alle sektioner | Erfaring, kompetencer, projekter osv. | 🔲 |
| 4. CV gemmes automatisk i DB | `master_cvs.raw_content` udfyldt | 🔲 |
| 5. Reload siden | CV vises stadig | 🔲 |
| 6. Klik "Kopiér" | Tekst i clipboard | 🔲 |
| 7. Redigér tekst manuelt | Ændringer bevaret | 🔲 |

---

## 7. Kendte Fejl og Begrænsninger

| Fejl / Begrænsning | Alvorlighed | Status |
|---|---|---|
| Ingen GitHub remote | Medium | Manuel handling kræves |
| Frontend `npm run dev` i Docker | Lav | Kun development |
| `docker-compose.prod.yml` mangler frontend | Medium | Sprint 2 |
| Ingen CI/CD pipeline | Medium | Sprint 2 |
| Ingen PDF-eksport af Master CV | Lav | Bevidst udeladt Sprint 1 |
| Profil-sektioner er read-only i UI | Lav | Sprint 2 |
| Ingen e-mail verification flow | Lav | `enable_confirmations = false` |
| Redis defineret i Docker men ubrugt | Lav | Fjernes eller bruges Sprint 2 |

---

## 8. Deployment Tjekliste

### Lokal Development
- [ ] `supabase start` kører
- [ ] `backend/.env` oprettet og udfyldt
- [ ] `frontend/.env.local` oprettet og udfyldt
- [ ] `supabase db push` kørt (17 migrations)
- [ ] `python smoke_test.py` passerer
- [ ] `npm run typecheck` passerer (frontend)
- [ ] Backend starter: `uvicorn app.main:app --reload`
- [ ] Frontend starter: `npm run dev`
- [ ] `GET http://localhost:8000/health` → `{"status":"ok"}`
- [ ] `GET http://localhost:8000/api/docs` → Swagger UI

### Pre-Production
- [ ] GitHub remote oprettet
- [ ] GitHub Actions CI opsat
- [ ] Supabase cloud projekt oprettet
- [ ] Cloud migrations kørt
- [ ] Production `.env` med production-nøgler
- [ ] `DEBUG=false` i production
- [ ] Frontend bygget: `npm run build`
- [ ] Docker prod-compose opdateret med frontend
- [ ] CORS_ORIGINS sat til production domain
- [ ] Supabase Auth site_url opdateret til production URL

---

## 9. Hurtig Opstart (lokal)

```bash
# 1. Klon og installer
git clone https://github.com/DIT-ORG/careeros.git
cd careeros
make install

# 2. Supabase
supabase start
# Notér anon key og service_role key fra output

# 3. Backend env
cp backend/.env.example backend/.env
# Redigér backend/.env — udfyld Supabase keys + OPENAI_API_KEY + generede SECRET_KEY + ENCRYPTION_KEY

# 4. Frontend env
cp frontend/.env.example frontend/.env.local
# Redigér frontend/.env.local — udfyld Supabase keys

# 5. Migrations
supabase db push

# 6. Smoke test
cd backend && python smoke_test.py

# 7. Start
make dev-backend   # Terminal 2: http://localhost:8000
make dev-frontend  # Terminal 3: http://localhost:3000
```

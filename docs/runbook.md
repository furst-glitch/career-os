# CareerOS — Operational Runbook

**Version:** 1.0 · **Gælder fra:** Release 1.0
**Ejer:** CTO · **Review:** Kvartalsvis

---

## 1. Arkitekturoverblik

```
Bruger → Vercel (Next.js frontend)
         ↓
Render (FastAPI backend, uvicorn)
         ↓
Supabase (PostgreSQL + Auth + Storage)
         ↓ (AI-kald)
Anthropic API / OpenAI API
         ↓
Render Redis (rate limiting + session cache)
```

**Kritiske afhængigheder (i prioriteret rækkefølge):**
1. Supabase Auth — uden auth virker intet
2. Supabase Database — uden DB virker intet
3. Render API — uden API virker frontend ikke
4. Anthropic API — AI-funktioner fejler (ikke auth, jobs, billing)
5. Stripe — kun betalingsflow påvirket
6. Redis — rate limiting falder tilbage til IP-baseret, ikke brugeradfærd

---

## 2. Deployment

### 2.1 Normal deployment (automatisk)
```
git push origin main
```
- **Frontend:** Vercel deployer automatisk. Normalt klar på 2-4 min.
- **Backend:** Render deployer automatisk. Normalt klar på 3-7 min.
- **Database migrations:** Skal køres MANUELT før backend starter.

### 2.2 Database migration
```bash
# Anvend ny migration på Supabase Cloud (production)
supabase db push --db-url "postgresql://..."

# Eller via Supabase Dashboard → SQL Editor → paste migration fil
```
**Vigtigt:** Kør altid migration INDEN deployment af backend der bruger nye kolonner.

### 2.3 Environment variables
Administreres i:
- **Frontend:** Vercel Dashboard → Project Settings → Environment Variables
- **Backend:** Render Dashboard → careeros-api → Environment

Nødvendige env vars (backend):
```
SECRET_KEY                 # Auto-genereret af Render
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
ENCRYPTION_KEY             # Fernet nøgle
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
ANTHROPIC_API_KEY          # Systemets default nøgle (BYOK-fallback)
ADMIN_EMAIL                # CTO Dashboard adgang
SENTRY_DSN                 # Valgfri
REDIS_URL                  # Auto-sat af Render fra careeros-redis service
```

### 2.4 Deployment-tjekliste
- [ ] Migration kørt på production DB
- [ ] Alle env vars sat i Render
- [ ] Health check bekræftet: `GET /health` returnerer `{"status": "ok"}`
- [ ] Test login og én AI-funktion manuelt
- [ ] Stripe webhook endpoint registreret i Stripe Dashboard

---

## 3. Rollback

### 3.1 Frontend rollback (Vercel)
1. Gå til Vercel Dashboard → Deployments
2. Find det forrige fungerende deployment
3. Klik "Promote to Production"
4. Tager ~1 min

### 3.2 Backend rollback (Render)
1. Gå til Render Dashboard → careeros-api → Deploys
2. Find det forrige fungerende deploy
3. Klik "Rollback to this deploy"
4. Tager ~3 min

### 3.3 Database rollback
**Der er ingen automatisk rollback.** Migrations er kumulative.
- Skriv altid en "down migration" ved risikable skemaændringer
- Down migration skrives som kommentar i toppen af migration-filen
- Eksempel: `-- DOWN: ALTER TABLE x DROP COLUMN y;`

For destruktive rollbacks (kolonnesletning):
```sql
-- Eksempel: fortryd tilføjelse af kolonne
ALTER TABLE document_facts DROP COLUMN IF EXISTS ny_kolonne;
```

---

## 4. Databasefejl

### 4.1 Symptomer
- 500-fejl fra alle endpoints
- Log: `supabase_error` eller `postgrest_error`
- Supabase status page viser incident

### 4.2 Diagnose
```bash
# Test direkte DB-forbindelse
curl https://<project>.supabase.co/rest/v1/health

# Check Supabase status
open https://status.supabase.com
```

### 4.3 Handling
| Problem | Handling |
|---------|----------|
| Supabase incident | Vent. Monitorér status.supabase.com |
| DB connection pool exhausted | Restart Render service (frigiver connections) |
| Slow queries | Kør `ANALYZE` i Supabase SQL Editor |
| Migration fejlet halvvejs | Kør `ROLLBACK` manuelt i SQL Editor |
| RLS-fejl (403 fra DB) | Tjek RLS-policies i 00014_rls_policies.sql |

### 4.4 Vigtigt
Supabase Free-tier har **500 MB** database storage. Monitor via:
Supabase Dashboard → Project Settings → Database → Database size

---

## 5. AI Provider-fejl

### 5.1 Symptomer
- 503 fra AI-endpoints
- Log: `litellm_error` eller `no_provider_key`
- Chat og CV-generering fejler

### 5.2 Diagnose
```bash
# Check Anthropic status
open https://status.anthropic.com

# Check AI-forbrug (kan have ramt budget)
# Kig i CTO Dashboard → Drift → AI Cost per User
```

### 5.3 Handling
| Problem | Handling |
|---------|----------|
| Anthropic incident | Vent. Funktioner degraderer gracefully (brugere ser fejlbesked) |
| API-nøgle udløbet | Forny nøgle i Anthropic Console → opdater ANTHROPIC_API_KEY i Render |
| Budget ramt | Øg limit i Anthropic Console billing |
| Høj AI-fejlrate | Tjek prompts for prompt injection-forsøg i logs |
| Model deprecated | Opdater standardmodel i `config.py` og agent_registry |

### 5.4 Graceful degradation
Eksisterende data (CV, jobs, fakta) er altid tilgængeligt.
Kun AI-generering er utilgængeligt ved AI-udfald.
Brugere ser: `"AI-svar fejlede — prøv igen"` (ikke crash).

---

## 6. Stripe-fejl

### 6.1 Symptomer
- Betalinger gennemføres ikke
- Webhook-log viser fejl i Stripe Dashboard
- Brugere rapporterer at abonnement ikke aktiveres

### 6.2 Webhook-diagnose
```bash
# Stripe Dashboard → Developers → Webhooks → careeros-api
# Check "Recent deliveries" for fejl
```

### 6.3 Handling
| Problem | Handling |
|---------|----------|
| Webhook ikke modtaget | Verify endpoint URL i Stripe Dashboard peger på Render URL |
| Signaturverifikation fejler | Opdater STRIPE_WEBHOOK_SECRET i Render |
| Event ikke håndteret | Check hvilken event-type og tilføj handler |
| Plan aktiveres ikke | Kør manuelt: INSERT INTO subscriptions... via Supabase SQL Editor |
| Charge fejler | Stripe håndterer retry automatisk (op til 4 forsøg) |

### 6.4 Manuel plan-aktivering (nødsituation)
```sql
INSERT INTO subscriptions (user_id, plan, stripe_customer_id, stripe_subscription_id)
VALUES ('<user-uuid>', 'pro', '<stripe_customer_id>', '<stripe_sub_id>')
ON CONFLICT (user_id) DO UPDATE SET plan = 'pro';
```

---

## 7. Redis-fejl

### 7.1 Symptomer
- Rate limiting falder tilbage til IP-baseret (acceptabelt)
- Log: `redis_connection_error`

### 7.2 Handling
Redis er **ikke kritisk** — applikationen har in-memory fallback.
| Problem | Handling |
|---------|----------|
| Redis nede | Accept. Rate limiting kører IP-baseret. Restart Redis i Render. |
| Redis memory fuld | Render Free Redis har 256 MB limit. Flush hvis nødvendigt: `FLUSHALL` |
| Stale cache | Redis bruger TTL-baseret expiry. Ingen manuel handling nødvendig. |

---

## 8. Incident Response

### 8.1 Alvorlighedsniveauer
| Level | Definition | Responstid |
|-------|-----------|------------|
| P1 | Alle brugere påvirket, ingen login | 15 min |
| P2 | AI-funktioner nede | 2 timer |
| P3 | Specifik feature nedsat | 4 timer |
| P4 | Kosmetisk fejl, ingen funktionspåvirkning | Næste sprint |

### 8.2 P1 Incident procedure
1. **Identificér årsag**: Check Render logs + Supabase status + Sentry
2. **Kommunikér**: Opdater status page (hvis oprettet)
3. **Afgrænse**: Er det infra eller kode?
   - Infra → Vent på udbyder eller failover
   - Kode → Rollback (se sektion 3)
4. **Fix**: Implementér rettelse
5. **Verify**: Test golden path efter fix
6. **Post-mortem**: Skriv incident report inden 48 timer

### 8.3 Diagnosekommandoer
```bash
# Backend health
curl https://api.careeros.dk/health

# Aktive brugere og events (CTO Dashboard)
GET /api/v1/intelligence/operational

# Seneste fejl i events
GET /api/v1/intelligence/events?event_type=document.failed&days=1
```

---

## 9. Backup & Restore

### 9.1 Database backup
**Supabase håndterer automatisk backup:**
- Supabase Pro: Point-in-time recovery, 7 dages backup retention
- Supabase Free: Daglig backup, 7 dages retention

**Manuel snapshot (før destruktive operationer):**
```bash
# Eksporter via Supabase Dashboard → Project → Database → Backups
# Eller brug pg_dump via connection string
pg_dump "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres" > backup_$(date +%Y%m%d).sql
```

### 9.2 Restore
```bash
# Restore fra snapshot
psql "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres" < backup_20260626.sql

# Eller brug Supabase Dashboard → Backups → Restore
```

### 9.3 Brugerdata-eksport (GDPR)
```bash
# Via API (bruger skal være logget ind)
GET /api/v1/gdpr/export

# Manuel eksport via SQL
SELECT * FROM user_profiles WHERE user_id = '<uuid>';
SELECT * FROM career_memories WHERE user_id = '<uuid>';
# ... etc.
```

### 9.4 Recovery Time Objective (RTO)
| Scenario | Estimeret RTO |
|----------|--------------|
| Render restart | 3-5 min |
| Vercel deployment | 2-4 min |
| Supabase failover | 30-60 min (managed) |
| DB restore fra backup | 30-120 min |

---

## 10. Vedligeholdelse

### 10.1 Ugentlige tjek
- [ ] CTO Dashboard → Platform Health Score
- [ ] AI-forbrug (budget alerts)
- [ ] Fejlrate og top errors
- [ ] Aktive brugere og retention

### 10.2 Månedlige tjek
- [ ] Supabase database størrelse (< 400 MB på Free tier)
- [ ] Supabase storage brug
- [ ] API-nøgle udløbsdatoer
- [ ] Stripe betalingsfejl
- [ ] Render plan-grænser (RAM, CPU)

### 10.3 Kvartalsvis
- [ ] Review og opdater denne runbook
- [ ] Test restore fra backup
- [ ] Gennemgå og rotér secrets
- [ ] Review AI-model priser og opdater cost model
- [ ] Sentry error budget review

# CareerOS — Deployment Guide

## Arkitektur

```
GitHub → GitHub Actions CI → Deploy
  Frontend: Vercel (auto-deploy fra main)
  Backend:  Railway (Docker container)
  Database: Supabase Cloud (EU/Frankfurt)
```

## Trin 1: Supabase Cloud

1. Opret projekt på supabase.com (vælg Frankfurt/EU region)
2. Notér: Project URL, anon key, service_role key, DB URL
3. Anvend migrations: `supabase db push --db-url <DB_URL>`
4. Kør seed: Kopier `supabase/seed.sql` og kør i SQL editor

## Trin 2: Stripe

1. Opret Stripe konto
2. Opret produkter: Free (0 DKK), Pro (99 DKK/md)
3. Notér: Secret key, publishable key
4. Opsæt webhook endpoint: `https://api.careeros.dk/api/v1/billing/webhook`
5. Notér webhook signing secret

## Trin 3: Railway (Backend)

1. Opret projekt på railway.app
2. Tilslut GitHub repository
3. Sæt root directory: `backend`
4. Tilsæt miljøvariabler (alle fra `.env.example`)
5. Deploy kører automatisk ved push til main

## Trin 4: Vercel (Frontend)

1. Importér projekt på vercel.com
2. Sæt root directory: `frontend`
3. Tilsæt environment variables
4. Deploy kører automatisk ved push til main

## Trin 5: GitHub Secrets

Tilsæt følgende secrets i repository settings:

```
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_URL
ENCRYPTION_KEY
RAILWAY_TOKEN
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_PROJECT_ID
```

## Environment Variables

### Backend (Railway)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SECRET_KEY=<random 64 chars>
ENCRYPTION_KEY=<fernet key>
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
CORS_ORIGINS=https://www.careeros.dk,https://careeros.dk
DEBUG=false
```

### Frontend (Vercel)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://api.careeros.dk
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

## Skalering

- **0-1000 brugere:** Railway Starter + Supabase Free/Pro
- **1000-10.000:** Railway Pro + Supabase Pro
- **10.000+:** Overvej AWS ECS + RDS

## Monitoring

- Backend logs: Railway dashboard
- Frontend: Vercel Analytics
- Database: Supabase Dashboard
- Errors: Tilsæt Sentry (anbefales ved launch)

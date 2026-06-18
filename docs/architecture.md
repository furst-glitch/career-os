# CareerOS — Arkitektur

## Oversigt

CareerOS er en AI-drevet karriereplatform bygget som en modulær monolit der kan skaleres til microservices.

**Stack:** FastAPI (Python 3.12) + Next.js 15 (TypeScript) + Supabase (PostgreSQL + pgvector) + LiteLLM

## Systemdiagram

```
Internet → Next.js Frontend → FastAPI Backend → Supabase DB
                                            → LiteLLM → AI Providers
                                            → Stripe
                                            → External APIs
```

## Moduler (15 services)

| Service | Ansvar |
|---|---|
| AuthService | Supabase Auth, JWT-validering |
| ProfileService | Brugerprofil, præferencer |
| CVService | Master CV, versioner, parsing |
| ExperienceService | Discovery sessions, STAR-stories |
| CareerMemoryService | Minder, mål, vector-søgning |
| JobService | Jobsøgning, caching |
| ApplicationService | Pipeline, generering |
| InterviewCenterService | Pakker, research, guides |
| SalaryService | Analyse, forhandlingsprep |
| SearchIntelligenceService | Keywords, lærende profil |
| ReviewService | Multi-agent pipeline |
| BillingService | Stripe |
| GDPRService | Eksport, sletning |

## AI-agenter (11)

Alle agenter er konfigureret i `agent_registry`-tabellen.

Multi-agent review pipeline:
1. ATS + HR + Hiring Manager (parallelt)
2. Critic Agent
3. Career Coach Agent
4. Review Board (synthesizes)

## Deployment

- Frontend: Vercel
- Backend: Railway (Docker)
- Database: Supabase Cloud (EU/Frankfurt)
- CI/CD: GitHub Actions

Se `docs/deployment.md` for detaljer.

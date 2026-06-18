# CareerOS — Agent System

## Oversigt

11 AI-agenter koordineret via `ReviewPipeline`. Alle konfigureret i `agent_registry`-tabellen.

## De 11 agenter

| Agent | `name` i DB | Default model | Min. plan |
|---|---|---|---|
| CV Specialist | `cv_agent` | claude-sonnet-4-6 | free |
| Ansøgningsskribent | `application_agent` | claude-sonnet-4-6 | free |
| Jobscout | `job_agent` | gpt-4o | free |
| Interviewtræner | `interview_agent` | claude-sonnet-4-6 | free |
| Lønekspert | `salary_agent` | gpt-4o | pro |
| ATS Simulator | `ats_agent` | gpt-4o | pro |
| HR Fagperson | `hr_agent` | gpt-4o | pro |
| Hiring Manager | `hiring_manager_agent` | claude-sonnet-4-6 | pro |
| Djævelens Advokat | `critic_agent` | gpt-4o | pro |
| Karriererådgiver | `career_coach_agent` | claude-sonnet-4-6 | pro |
| Review Board | `review_board_agent` | claude-sonnet-4-6 | pro |

## Multi-agent pipeline

```
Submit dokument
  → Review Board (orchestrerer)
  → [Parallelt] ATS + HR + Hiring Manager
  → Critic Agent (syntetiserer og angriber)
  → Career Coach (kontekstualiserer ift. Career Memory)
  → Review Board (final rapport)
```

## Career Memory som kontekstlag

Agenter der har `requires_memory = true` kalder automatisk `get_memory_snapshot()` som tilføjes til system prompt.

## Tilføj ny agent

1. Indsæt i `agent_registry` (SQL eller via API)
2. Opret `backend/app/agents/my_agent.py` og extend `BaseAgent`
3. Registrer i `ReviewPipeline.DEFAULT_AGENTS` hvis relevant

## AI Provider abstraktionslag

Alle kald går via `LiteLLMProvider`:
- Budget-check før kald
- Auto-logging til `ai_usage`
- Brugerens egne nøgler via `KeyManager`
- Fallback til fallback_model ved fejl

## Streaming

Agenter der `supports_streaming = true` returnerer SSE via `/api/v1/review/{id}/stream`.
Frontend lytter med `apiStream()` fra `lib/api.ts`.

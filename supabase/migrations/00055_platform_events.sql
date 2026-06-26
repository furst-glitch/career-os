-- 00055_platform_events.sql
-- Platform Intelligence Engine — WP1: Event Instrumentation
--
-- Append-only event log. Alle centrale platformhandlinger skrives hertil.
-- Bruges af IntelligenceService til at beregne KPI'er, sundhedsscore,
-- driftsanalyse og prioriteringsforslag — ingen hardkodede dashboards.
--
-- Navnekonvention: kategori.handling (punktum-separeret, lowercase)
--   document.uploaded, document.analyzed, document.failed
--   fact.verified
--   chat.completed
--   recommendation.resolved, recommendation.dismissed
--   employment.created
--   subscription.started, subscription.cancelled
--   ai.error
--
-- Ingen RLS-policy til slutbrugere — kun service-role (admin) læser/skriver.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS public.platform_events (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type    text        NOT NULL,
    user_id       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    employment_id uuid,
    document_id   uuid,
    properties    jsonb       NOT NULL DEFAULT '{}',
    occurred_at   timestamptz NOT NULL DEFAULT now()
);

-- Primær tidsserieindeks (nyeste hændelser først)
CREATE INDEX IF NOT EXISTS idx_platform_events_occurred_at
    ON public.platform_events (occurred_at DESC);

-- Til at filtrere på hændelsestype + tid (analytics queries)
CREATE INDEX IF NOT EXISTS idx_platform_events_type_time
    ON public.platform_events (event_type, occurred_at DESC);

-- Til per-bruger aktivitetsanalyse
CREATE INDEX IF NOT EXISTS idx_platform_events_user_time
    ON public.platform_events (user_id, occurred_at DESC)
    WHERE user_id IS NOT NULL;

-- RLS: aktivér, men ingen bruger-policy — kun admin via service-role
ALTER TABLE public.platform_events ENABLE ROW LEVEL SECURITY;

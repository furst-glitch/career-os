-- Migration 00050: Document Facts — AI Document Intelligence
-- Provenance-tracked structured facts extracted from employment documents.
-- Facts link back to coach_documents (source), career_memories (search), and experiences (Work Graph).
-- Idempotent: uses IF NOT EXISTS, DO-blocks for enum and policies.

-- ── Enum ─────────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE fact_confidence AS ENUM ('high', 'medium', 'low');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Table ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.document_facts (
    id                    uuid            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               uuid            NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    document_id           uuid            NOT NULL REFERENCES public.coach_documents(id) ON DELETE CASCADE,

    -- The extracted fact
    fact_type             text            NOT NULL,     -- e.g. monthly_salary, pension_pct_total
    value                 text            NOT NULL,     -- e.g. "42500", "ja", "3"
    unit                  text,                         -- e.g. DKK, months, pct, hours/week

    -- Confidence and confirmation
    confidence            fact_confidence NOT NULL,
    requires_confirmation bool            NOT NULL DEFAULT false,

    -- Provenance — where exactly the fact was found
    source_text           text            NOT NULL,     -- exact quote from the document
    source_page           int,                          -- page number (NULL if unknown)

    -- Extraction metadata
    ai_model              text            NOT NULL,     -- model that extracted the fact
    ai_version            text            NOT NULL DEFAULT '1',
    extraction_run_id     uuid            NOT NULL,     -- groups all facts from one pipeline run

    -- Cross-references
    career_memory_id      uuid            REFERENCES public.career_memories(id),
    employment_id         uuid            REFERENCES public.experiences(id),

    created_at            timestamptz     NOT NULL DEFAULT now()
);

-- ── RLS ──────────────────────────────────────────────────────────────────────

ALTER TABLE public.document_facts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "document_facts: own"
        ON public.document_facts FOR ALL USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_document_facts_user
    ON public.document_facts (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_facts_document
    ON public.document_facts (document_id);

CREATE INDEX IF NOT EXISTS idx_document_facts_type
    ON public.document_facts (user_id, fact_type);

CREATE INDEX IF NOT EXISTS idx_document_facts_run
    ON public.document_facts (extraction_run_id);

-- ── Agent Registry ────────────────────────────────────────────────────────────

INSERT INTO public.agent_registry
    (name, display_name, version, description, is_active, is_system,
     default_provider, default_model, temperature, max_tokens, timeout_seconds)
VALUES
    ('fact_extraction_agent',
     'Fact Extraction Agent', '1.0.0',
     'Udtrækker strukturerede fakta med confidence og provenance fra ansættelseskontrakter, overenskomster og lønsedler',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.1, 2048, 90)
ON CONFLICT (name) DO NOTHING;

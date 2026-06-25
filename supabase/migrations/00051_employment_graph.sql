-- 00051_employment_graph.sql
-- Sprint 6: Employment Graph — additive links and new domain objects.
--
-- Makes Employment (experiences) the central relation for all documents,
-- facts, analyses and recommendations.
--
-- ADDITIVE ONLY: no existing columns, tables or data are altered.

-- ── 1. Link coach_documents → experiences ─────────────────────────────────────

ALTER TABLE public.coach_documents
    ADD COLUMN IF NOT EXISTS employment_id uuid
        REFERENCES public.experiences(id) ON DELETE SET NULL;

-- ── 2. Link coach_analyses → experiences ──────────────────────────────────────

ALTER TABLE public.coach_analyses
    ADD COLUMN IF NOT EXISTS employment_id uuid
        REFERENCES public.experiences(id) ON DELETE SET NULL;

-- ── 3. Cross-document analysis results ────────────────────────────────────────
-- Deterministic rule-based comparisons across documents for one Employment.
-- NOT AI-generated — produced by CrossDocumentAnalysisService.

CREATE TABLE IF NOT EXISTS public.employment_analyses (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    employment_id       uuid        NOT NULL REFERENCES public.experiences(id) ON DELETE CASCADE,
    analysis_type       text        NOT NULL,       -- 'cross_document' | 'salary_check' | ...
    document_ids        uuid[]      NOT NULL DEFAULT '{}',
    discrepancies_found int         NOT NULL DEFAULT 0,
    result_json         jsonb       NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.employment_analyses ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "employment_analyses: own"
        ON public.employment_analyses
        FOR ALL
        USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── 4. Recommendation domain objects ──────────────────────────────────────────
-- Created by analysis, not by AI. Lifecycle: pending → confirmed | dismissed | resolved.

CREATE TABLE IF NOT EXISTS public.employment_recommendations (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    employment_id       uuid        NOT NULL REFERENCES public.experiences(id) ON DELETE CASCADE,
    analysis_id         uuid        REFERENCES public.employment_analyses(id) ON DELETE SET NULL,
    recommendation_type text        NOT NULL,   -- 'salary_mismatch' | 'pension_mismatch' | 'hours_mismatch'
    severity            text        NOT NULL
                            CHECK (severity IN ('high', 'medium', 'low', 'info')),
    title               text        NOT NULL,
    description         text        NOT NULL,
    fact_types          text[]      NOT NULL DEFAULT '{}',
    affected_fact_ids   uuid[]      NOT NULL DEFAULT '{}',
    status              text        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'confirmed', 'dismissed', 'resolved')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.employment_recommendations ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "employment_recommendations: own"
        ON public.employment_recommendations
        FOR ALL
        USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── 5. Indexes ────────────────────────────────────────────────────────────────

-- Sparse indexes on the new optional FKs
CREATE INDEX IF NOT EXISTS idx_coach_documents_employment
    ON public.coach_documents (employment_id)
    WHERE employment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_coach_analyses_employment
    ON public.coach_analyses (employment_id)
    WHERE employment_id IS NOT NULL;

-- Employment analyses
CREATE INDEX IF NOT EXISTS idx_employment_analyses_employment
    ON public.employment_analyses (employment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_employment_analyses_user
    ON public.employment_analyses (user_id, created_at DESC);

-- Employment recommendations
CREATE INDEX IF NOT EXISTS idx_employment_recommendations_employment
    ON public.employment_recommendations (employment_id, status);

CREATE INDEX IF NOT EXISTS idx_employment_recommendations_user
    ON public.employment_recommendations (user_id, status, created_at DESC);

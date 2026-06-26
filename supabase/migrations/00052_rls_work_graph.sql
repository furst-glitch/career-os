-- 00052_rls_work_graph.sql
-- Tilføj manglende RLS-policies til Work Graph-tabeller.
-- coach_documents, document_facts, employment_analyses og employment_recommendations
-- manglede RLS — backend bruger service role (bypass), men defense-in-depth kræver det.
-- Idempotent: DROP IF EXISTS + CREATE.

-- ── DOCUMENT INTELLIGENCE ────────────────────────────────────────────────────

ALTER TABLE public.coach_documents             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_facts              ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "coach_documents: own"   ON public.coach_documents;
DROP POLICY IF EXISTS "document_facts: own"    ON public.document_facts;

CREATE POLICY "coach_documents: own"
    ON public.coach_documents
    FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "document_facts: own"
    ON public.document_facts
    FOR ALL
    USING (auth.uid() = user_id);

-- ── EMPLOYMENT GRAPH ─────────────────────────────────────────────────────────

ALTER TABLE public.employment_analyses         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employment_recommendations  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "employment_analyses: own"        ON public.employment_analyses;
DROP POLICY IF EXISTS "employment_recommendations: own" ON public.employment_recommendations;

CREATE POLICY "employment_analyses: own"
    ON public.employment_analyses
    FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "employment_recommendations: own"
    ON public.employment_recommendations
    FOR ALL
    USING (auth.uid() = user_id);

-- ── NOTIFICATIONS ────────────────────────────────────────────────────────────

ALTER TABLE public.notifications               ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "notifications: own"     ON public.notifications;

CREATE POLICY "notifications: own"
    ON public.notifications
    FOR ALL
    USING (auth.uid() = user_id);

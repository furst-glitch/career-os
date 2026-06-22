-- Migration 00040: AI Arbejdsliv & Løncoach
-- Tabeller til dokumentupload, analyseresultater og lønsamtalepakker.
-- Registrerer 8 nye agenter i agent_registry.

-- ── Tabeller ─────────────────────────────────────────────────────────────────

CREATE TABLE public.coach_documents (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    doc_type        text        NOT NULL
                    CHECK (doc_type IN ('contract','agreement','payslip','schedule','other')),
    file_name       text        NOT NULL,
    file_size       int,
    extracted_text  text,
    metadata        jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.coach_analyses (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    analysis_type   text        NOT NULL,
    title           text,
    input_data      jsonb       NOT NULL DEFAULT '{}',
    result_text     text,
    result_json     jsonb,
    document_ids    uuid[]      NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.salary_prep_sessions (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    messages        jsonb       NOT NULL DEFAULT '[]',
    package_text    text,
    package_a4_text text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER salary_prep_sessions_updated_at
    BEFORE UPDATE ON public.salary_prep_sessions
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ── RLS ──────────────────────────────────────────────────────────────────────

ALTER TABLE public.coach_documents      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coach_analyses       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_prep_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "coach_documents: own"
    ON public.coach_documents FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "coach_analyses: own"
    ON public.coach_analyses FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "salary_prep_sessions: own"
    ON public.salary_prep_sessions FOR ALL USING (auth.uid() = user_id);

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX idx_coach_documents_user
    ON public.coach_documents (user_id, created_at DESC);
CREATE INDEX idx_coach_analyses_user_type
    ON public.coach_analyses (user_id, analysis_type, created_at DESC);
CREATE INDEX idx_salary_prep_user
    ON public.salary_prep_sessions (user_id, created_at DESC);

-- ── Agent Registry ───────────────────────────────────────────────────────────

INSERT INTO public.agent_registry
    (name, display_name, version, description, is_active, is_system,
     default_provider, default_model, temperature, max_tokens, timeout_seconds)
VALUES
    ('salary_check_agent',
     'Salary Check Agent', '1.0.0',
     'Analyserer markedsløn og kompensationspakke baseret på stillingsprofil',
     true, true, 'anthropic', 'claude-haiku-4-5-20251001', 0.3, 1200, 30),

    ('contract_analysis_agent',
     'Contract Analysis Agent', '1.0.0',
     'Analyserer ansættelseskontrakter for rettigheder, risici og usædvanlige vilkår',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.3, 2000, 60),

    ('agreement_analysis_agent',
     'Agreement Analysis Agent', '1.0.0',
     'Analyserer overenskomster for løntrin, tillæg, rettigheder og regler',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.3, 2000, 60),

    ('payslip_check_agent',
     'Payslip Check Agent', '1.0.0',
     'Kontrollerer lønseddel mod kontrakt og overenskomst for potentielle fejl',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.2, 1500, 60),

    ('worktime_check_agent',
     'Worktime Check Agent', '1.0.0',
     'Analyserer vagtplan og timeseddel for overtid, hvile og tillæg',
     true, true, 'anthropic', 'claude-haiku-4-5-20251001', 0.2, 1200, 45),

    ('career_value_agent',
     'Career Value Agent', '1.0.0',
     'Beregner kandidatens markedsværdi og forhandlingsstyrke baseret på karriereprofil',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.4, 1500, 45),

    ('salary_prep_agent',
     'Salary Prep Agent', '1.0.0',
     'Forbereder kandidaten til lønsamtale og genererer lønsamtalepakke',
     true, true, 'anthropic', 'claude-sonnet-4-6', 0.6, 2500, 90),

    ('labor_rights_agent',
     'Labor Rights Agent', '1.0.0',
     'Fagforeningsassistent der forklarer arbejdsretlige regler og rettigheder',
     true, true, 'anthropic', 'claude-haiku-4-5-20251001', 0.5, 1000, 30)
ON CONFLICT (name) DO UPDATE SET
    default_provider  = EXCLUDED.default_provider,
    default_model     = EXCLUDED.default_model,
    temperature       = EXCLUDED.temperature,
    max_tokens        = EXCLUDED.max_tokens,
    timeout_seconds   = EXCLUDED.timeout_seconds,
    updated_at        = now();

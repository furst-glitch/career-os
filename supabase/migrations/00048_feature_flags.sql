-- 00048_feature_flags.sql
-- feature_flags: per-platform feature gating.
-- AIPolicyService consults these to enable/disable features for specific plans or users.
--   globally_enabled:   master switch; if false, only plan/user overrides apply
--   enabled_for_plans:  empty array = no plan-based enablement; populated = those plans
--   enabled_for_users:  empty array = no user-specific overrides
-- Additive only — IF NOT EXISTS + ON CONFLICT DO NOTHING for idempotency.

CREATE TABLE IF NOT EXISTS public.feature_flags (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_key          text UNIQUE NOT NULL,
    description       text,
    globally_enabled  boolean NOT NULL DEFAULT false,
    enabled_for_plans subscription_plan[] NOT NULL DEFAULT '{}',
    enabled_for_users uuid[] NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.feature_flags ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "feature_flags_read" ON public.feature_flags;
CREATE POLICY "feature_flags_read" ON public.feature_flags
    FOR SELECT TO authenticated USING (true);

-- updated_at trigger (handle_updated_at defined in 00003_user_profile.sql).
DROP TRIGGER IF EXISTS feature_flags_updated_at ON public.feature_flags;
CREATE TRIGGER feature_flags_updated_at
    BEFORE UPDATE ON public.feature_flags
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Seed: initial feature flags.
INSERT INTO public.feature_flags (flag_key, description, globally_enabled, enabled_for_plans) VALUES
    ('gateway_policy_service', 'Enable AIPolicyService for all requests',   false, '{pro,professional,enterprise}'),
    ('multi_agent_review',     'Enable multi-agent review pipeline',        false, '{professional,enterprise}'),
    ('voice_interview',        'Enable voice interview feature',            false, '{}'),
    ('byok_enabled',           'Allow users to bring their own API keys',   true,  '{pro,professional,enterprise}'),
    ('streaming_responses',    'Enable SSE streaming for AI responses',     true,  '{free,pro,professional,enterprise}'),
    ('career_memory_search',   'Enable semantic search in career memory',   true,  '{pro,professional,enterprise}'),
    ('export_pdf',             'Enable PDF export of CV and documents',     true,  '{pro,professional,enterprise}')
ON CONFLICT (flag_key) DO NOTHING;

-- 00047_plan_capabilities.sql
-- plan_capabilities: which capabilities each plan can access, plus rate limits.
-- Consulted by AIPolicyService.evaluate() to gate capabilities by plan.
-- Capability identifiers must match GatewayRequest.task_capability values
-- (see app/gateway/routing/defaults.py _ALL_CAPABILITIES).
-- requests_per_minute / requests_per_day: NULL = unlimited.
-- Additive only — IF NOT EXISTS + ON CONFLICT DO NOTHING for idempotency.

CREATE TABLE IF NOT EXISTS public.plan_capabilities (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan                subscription_plan NOT NULL,
    capability          text NOT NULL,
    enabled             boolean NOT NULL DEFAULT true,
    requests_per_minute integer,    -- NULL = unlimited
    requests_per_day    integer,    -- NULL = unlimited
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT plan_capabilities_unique UNIQUE (plan, capability)
);

ALTER TABLE public.plan_capabilities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "plan_capabilities_read" ON public.plan_capabilities;
CREATE POLICY "plan_capabilities_read" ON public.plan_capabilities
    FOR SELECT TO authenticated USING (true);

-- Seed: capabilities per plan.
--   free:         basic capabilities only
--   pro:          all standard capabilities (no multi-agent review)
--   professional: all + heavy analysis + multi-agent review
--   enterprise:   all capabilities, unlimited
INSERT INTO public.plan_capabilities (plan, capability, enabled, requests_per_minute, requests_per_day) VALUES
    -- free plan
    ('free', 'chat',                true,  5,    100),
    ('free', 'cv_parsing',          true,  2,    20),
    ('free', 'cv_generation',       true,  1,    10),
    ('free', 'job_matching',        true,  3,    50),
    ('free', 'contract_analysis',   false, NULL, NULL),
    ('free', 'agreement_analysis',  false, NULL, NULL),
    ('free', 'payslip_extraction',  false, NULL, NULL),
    ('free', 'interview_prep',      false, NULL, NULL),
    ('free', 'salary_negotiation',  false, NULL, NULL),
    ('free', 'career_coaching',     false, NULL, NULL),
    ('free', 'document_review',     false, NULL, NULL),
    ('free', 'multi_agent_review',  false, NULL, NULL),
    -- pro plan
    ('pro', 'chat',                 true, 30,   1000),
    ('pro', 'cv_parsing',           true, 10,   200),
    ('pro', 'cv_generation',        true,  5,   100),
    ('pro', 'job_matching',         true, 20,   500),
    ('pro', 'contract_analysis',    true, 10,   100),
    ('pro', 'agreement_analysis',   true, 10,   100),
    ('pro', 'payslip_extraction',   true, 10,   100),
    ('pro', 'interview_prep',       true, 10,   100),
    ('pro', 'salary_negotiation',   true, 10,   100),
    ('pro', 'career_coaching',      true, 10,   200),
    ('pro', 'document_review',      true,  5,    50),
    ('pro', 'multi_agent_review',   false, NULL, NULL),
    -- professional plan
    ('professional', 'chat',                 true, 100, 5000),
    ('professional', 'cv_parsing',           true,  30, 1000),
    ('professional', 'cv_generation',        true,  20,  500),
    ('professional', 'job_matching',         true,  50, 2000),
    ('professional', 'contract_analysis',    true,  30,  500),
    ('professional', 'agreement_analysis',   true,  30,  500),
    ('professional', 'payslip_extraction',   true,  30,  500),
    ('professional', 'interview_prep',       true,  30,  500),
    ('professional', 'salary_negotiation',   true,  30,  500),
    ('professional', 'career_coaching',      true,  30,  500),
    ('professional', 'document_review',      true,  20,  200),
    ('professional', 'multi_agent_review',   true,  10,  100),
    -- enterprise plan (all unlimited)
    ('enterprise', 'chat',                 true, NULL, NULL),
    ('enterprise', 'cv_parsing',           true, NULL, NULL),
    ('enterprise', 'cv_generation',        true, NULL, NULL),
    ('enterprise', 'job_matching',         true, NULL, NULL),
    ('enterprise', 'contract_analysis',    true, NULL, NULL),
    ('enterprise', 'agreement_analysis',   true, NULL, NULL),
    ('enterprise', 'payslip_extraction',   true, NULL, NULL),
    ('enterprise', 'interview_prep',       true, NULL, NULL),
    ('enterprise', 'salary_negotiation',   true, NULL, NULL),
    ('enterprise', 'career_coaching',      true, NULL, NULL),
    ('enterprise', 'document_review',      true, NULL, NULL),
    ('enterprise', 'multi_agent_review',   true, NULL, NULL)
ON CONFLICT (plan, capability) DO NOTHING;

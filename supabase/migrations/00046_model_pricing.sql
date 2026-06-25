-- 00046_model_pricing.sql
-- model_pricing: stores pricing per model for the DB-backed CostEngine.
-- Prices are per 1M tokens in USD with 8 decimal precision.
-- Read by the CostEngine (Sprint 2) when pricing is loaded from DB.
-- Default data seeded below matches PRICING_TABLE in app/gateway/cost/defaults.py.
-- Additive only — IF NOT EXISTS + ON CONFLICT DO NOTHING for idempotency.

CREATE TABLE IF NOT EXISTS public.model_pricing (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model             text NOT NULL,
    provider          text NOT NULL,
    input_per_1m_usd  numeric(12, 8) NOT NULL CHECK (input_per_1m_usd >= 0),
    output_per_1m_usd numeric(12, 8) NOT NULL CHECK (output_per_1m_usd >= 0),
    effective_from    timestamptz NOT NULL DEFAULT now(),
    effective_until   timestamptz,  -- NULL = currently active
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_pricing_unique_active UNIQUE NULLS NOT DISTINCT (model, provider, effective_until)
);

ALTER TABLE public.model_pricing ENABLE ROW LEVEL SECURITY;

-- model_pricing is read-only for authenticated users (service role manages it).
DROP POLICY IF EXISTS "model_pricing_read" ON public.model_pricing;
CREATE POLICY "model_pricing_read" ON public.model_pricing
    FOR SELECT TO authenticated USING (true);

-- Seed default pricing (matches cost/defaults.py PRICING_TABLE).
INSERT INTO public.model_pricing (model, provider, input_per_1m_usd, output_per_1m_usd) VALUES
    ('claude-haiku-4-5-20251001', 'anthropic', 0.80000000, 4.00000000),
    ('claude-sonnet-4-6',         'anthropic', 3.00000000, 15.00000000),
    ('claude-opus-4-8',           'anthropic', 15.00000000, 75.00000000),
    ('claude-fable-5',            'anthropic', 3.00000000, 15.00000000),
    ('gpt-4o',                    'openai',    2.50000000, 10.00000000),
    ('gpt-4o-mini',               'openai',    0.15000000, 0.60000000),
    ('gemini-2.0-flash',          'gemini',    0.10000000, 0.40000000),
    ('gemini-1.5-pro',            'gemini',    3.50000000, 10.50000000),
    ('llama3.2',                  'ollama',    0.00000000, 0.00000000)
ON CONFLICT DO NOTHING;

-- Migration 00036: Registrér DesignerAgent i agent_registry
--
-- DesignerAgent oversætter brugerens valgte template (ats_professional, executive, etc.)
-- til konkrete stil-instruktioner der bruges af ReviewBoardAgent og ApplicationAgent.
-- Kører efter CriticAgent i begge pipelines (CV og ansøgning).
--
-- Brug Haiku (hurtig + billig) da outputtet er strukturerede instruktioner (200-400 tokens).

INSERT INTO public.agent_registry (
    name,
    display_name,
    version,
    description,
    is_active,
    is_system,
    default_provider,
    default_model,
    temperature,
    max_tokens,
    timeout_seconds
) VALUES (
    'designer_agent',
    'Designer Agent',
    '1.0.0',
    'Oversætter valgt template til konkrete stil-instruktioner for layout, typografi og præsentation',
    true,
    true,
    'anthropic',
    'claude-haiku-4-5-20251001',
    0.20,
    400,
    20
)
ON CONFLICT (name) DO UPDATE SET
    default_provider  = EXCLUDED.default_provider,
    default_model     = EXCLUDED.default_model,
    temperature       = EXCLUDED.temperature,
    max_tokens        = EXCLUDED.max_tokens,
    timeout_seconds   = EXCLUDED.timeout_seconds,
    updated_at        = now();

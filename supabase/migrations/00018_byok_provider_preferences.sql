-- BYOK: Default AI provider per bruger
-- Tilføjer default_ai_provider til user_profiles

ALTER TABLE public.user_profiles
  ADD COLUMN IF NOT EXISTS default_ai_provider ai_provider;

-- Kommentar: NULL = ingen global default, bruger agent-registrets default_provider pr. agent

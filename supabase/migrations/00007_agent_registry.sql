-- Agent Registry
-- Alle 11 CareerOS-agenter registreret og konfigureret i databasen

CREATE TABLE public.agent_registry (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL UNIQUE,
  display_name      text NOT NULL,
  version           text NOT NULL DEFAULT '1.0.0',
  description       text,
  is_active         bool NOT NULL DEFAULT true,
  is_system         bool NOT NULL DEFAULT true,
  default_provider  ai_provider NOT NULL DEFAULT 'openai',
  default_model     text NOT NULL DEFAULT 'gpt-4o',
  fallback_model    text,
  temperature       numeric(3,2) NOT NULL DEFAULT 0.7,
  max_tokens        int NOT NULL DEFAULT 4096,
  timeout_seconds   int NOT NULL DEFAULT 60,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.agent_capabilities (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id            uuid REFERENCES public.agent_registry(id) ON DELETE CASCADE NOT NULL,
  capability          text NOT NULL,
  input_schema        jsonb NOT NULL DEFAULT '{}',
  output_schema       jsonb NOT NULL DEFAULT '{}',
  requires_memory     bool NOT NULL DEFAULT false,
  supports_streaming  bool NOT NULL DEFAULT false,
  min_plan            subscription_plan NOT NULL DEFAULT 'free',
  UNIQUE (agent_id, capability)
);

CREATE TABLE public.agent_configurations (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  agent_id              uuid REFERENCES public.agent_registry(id) ON DELETE CASCADE NOT NULL,
  provider_override     ai_provider,
  model_override        text,
  temperature_override  numeric(3,2),
  custom_instructions   text,
  is_enabled            bool NOT NULL DEFAULT true,
  updated_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, agent_id)
);

CREATE TRIGGER agent_registry_updated_at
  BEFORE UPDATE ON public.agent_registry
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Seed af alle 11 agenter indsættes i 00015_seed.sql

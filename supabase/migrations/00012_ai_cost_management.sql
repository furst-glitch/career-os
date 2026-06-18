-- AI Cost Management
-- Tracking af tokens, omkostninger og budgetstyring pr. bruger

CREATE TABLE public.ai_usage (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  agent_id          uuid REFERENCES public.agent_registry(id) ON DELETE SET NULL,
  provider          ai_provider NOT NULL,
  model             text NOT NULL,
  operation         text NOT NULL,
  prompt_tokens     int NOT NULL DEFAULT 0,
  completion_tokens int NOT NULL DEFAULT 0,
  total_tokens      int NOT NULL DEFAULT 0,
  cost_usd          numeric(10,6) NOT NULL DEFAULT 0,
  latency_ms        int NOT NULL DEFAULT 0,
  used_user_key     bool NOT NULL DEFAULT false,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- Nu tilføj FK fra document_versions til ai_usage
ALTER TABLE public.document_versions
  ADD CONSTRAINT fk_document_ai_usage
  FOREIGN KEY (ai_usage_id) REFERENCES public.ai_usage(id) ON DELETE SET NULL;

CREATE TABLE public.ai_costs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  period_start      date NOT NULL,
  period_end        date NOT NULL,
  total_tokens      int NOT NULL DEFAULT 0,
  total_cost_usd    numeric(10,4) NOT NULL DEFAULT 0,
  cost_by_agent     jsonb NOT NULL DEFAULT '{}',
  cost_by_provider  jsonb NOT NULL DEFAULT '{}',
  operations_count  int NOT NULL DEFAULT 0,
  calculated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, period_start)
);

CREATE TABLE public.ai_budgets (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  monthly_limit_usd     numeric(8,2) NOT NULL DEFAULT 10.00,
  warning_threshold     numeric(3,2) NOT NULL DEFAULT 0.80 CHECK (warning_threshold BETWEEN 0 AND 1),
  hard_limit            bool NOT NULL DEFAULT false,
  current_spend_usd     numeric(10,4) NOT NULL DEFAULT 0,
  period_reset_at       date NOT NULL DEFAULT date_trunc('month', CURRENT_DATE + interval '1 month')::date,
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER ai_budgets_updated_at
  BEFORE UPDATE ON public.ai_budgets
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Auto-opret budget ved ny bruger
CREATE OR REPLACE FUNCTION public.handle_new_user_budget()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.ai_budgets (user_id) VALUES (NEW.user_id)
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_subscription_created_budget
  AFTER INSERT ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user_budget();

-- Aggreger AI-forbrug dagligt (kaldes via Supabase cron eller baggrundsjob)
CREATE OR REPLACE FUNCTION public.aggregate_ai_costs(p_user_id uuid, p_date date DEFAULT CURRENT_DATE)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_period_start date := date_trunc('month', p_date)::date;
  v_period_end   date := (date_trunc('month', p_date) + interval '1 month - 1 day')::date;
BEGIN
  INSERT INTO public.ai_costs (
    user_id, period_start, period_end,
    total_tokens, total_cost_usd, cost_by_agent, cost_by_provider, operations_count
  )
  SELECT
    p_user_id,
    v_period_start,
    v_period_end,
    COALESCE(SUM(total_tokens), 0),
    COALESCE(SUM(cost_usd), 0),
    COALESCE(
      jsonb_object_agg(agent_name, agent_cost) FILTER (WHERE agent_name IS NOT NULL),
      '{}'::jsonb
    ),
    COALESCE(jsonb_object_agg(provider, provider_cost), '{}'::jsonb),
    COUNT(*)
  FROM (
    SELECT
      au.total_tokens,
      au.cost_usd,
      au.provider::text,
      SUM(au.cost_usd) OVER (PARTITION BY au.provider) AS provider_cost,
      ar.name AS agent_name,
      SUM(au.cost_usd) OVER (PARTITION BY ar.name) AS agent_cost
    FROM public.ai_usage au
    LEFT JOIN public.agent_registry ar ON ar.id = au.agent_id
    WHERE au.user_id = p_user_id
      AND au.created_at >= v_period_start
      AND au.created_at < v_period_end + interval '1 day'
  ) sub
  ON CONFLICT (user_id, period_start)
  DO UPDATE SET
    total_tokens = EXCLUDED.total_tokens,
    total_cost_usd = EXCLUDED.total_cost_usd,
    cost_by_agent = EXCLUDED.cost_by_agent,
    cost_by_provider = EXCLUDED.cost_by_provider,
    operations_count = EXCLUDED.operations_count,
    calculated_at = now();

  -- Opdater løbende forbrug på budget
  UPDATE public.ai_budgets
  SET current_spend_usd = (
    SELECT COALESCE(SUM(cost_usd), 0)
    FROM public.ai_usage
    WHERE user_id = p_user_id
      AND created_at >= v_period_start
      AND used_user_key = false
  )
  WHERE user_id = p_user_id;
END;
$$;

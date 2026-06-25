-- 00049_increment_ai_spend.sql
-- increment_ai_spend: atomically add actual AI cost to a user's running budget.
--
-- Called by AIPolicyService.release_budget_reservation() after an AI call
-- completes, to persist the actual cost to ai_budgets.current_spend_usd.
--
-- ai_budgets is defined in 00012_ai_cost_management.sql with:
--   user_id uuid NOT NULL UNIQUE, current_spend_usd numeric(10,4) NOT NULL DEFAULT 0,
--   and a row auto-created per subscription. The ON CONFLICT branch covers the
--   normal case; the INSERT branch is a safety net for users without a budget row.
--
-- SECURITY DEFINER so the service role / RPC can update regardless of RLS.
-- Idempotent: CREATE OR REPLACE.

CREATE OR REPLACE FUNCTION public.increment_ai_spend(p_user_id uuid, p_amount numeric)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.ai_budgets (user_id, current_spend_usd)
    VALUES (p_user_id, p_amount)
    ON CONFLICT (user_id) DO UPDATE
    SET current_spend_usd = public.ai_budgets.current_spend_usd + p_amount,
        updated_at = now();
END;
$$;

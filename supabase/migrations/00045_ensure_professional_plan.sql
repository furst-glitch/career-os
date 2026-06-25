-- 00045_ensure_professional_plan.sql
-- Defensive guard: ensure 'professional' exists in subscription_plan enum.
--
-- Rationale: migrations 00046+ (plan_capabilities, feature_flags) seed rows
-- referencing the 'professional' plan. On main this value is added by
-- 00042_add_professional_plan.sql, but to keep this migration chain
-- self-contained and idempotent we re-assert it here. If 00042 already ran,
-- this is a no-op.
--
-- NOTE: ALTER TYPE ... ADD VALUE must commit before the new label can be used
-- in a subsequent statement, so this lives in its own migration ahead of any
-- migration that inserts 'professional' rows.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'professional'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_plan')
    ) THEN
        ALTER TYPE subscription_plan ADD VALUE 'professional' BEFORE 'enterprise';
    END IF;
END$$;

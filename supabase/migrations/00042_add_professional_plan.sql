-- Add 'professional' to subscription_plan enum
-- Uses IF NOT EXISTS to be idempotent
-- Enum type is named 'subscription_plan' (defined in 00002_enums.sql)
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

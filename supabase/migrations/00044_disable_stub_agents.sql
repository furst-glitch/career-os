-- Disable agents that are registered but not yet implemented.
-- These agents previously raised NotImplementedError; they now return a structured
-- "agent_not_implemented" error. Marking is_active=false prevents accidental routing to them.
--
-- Note: agent_registry.is_active already exists (defined in 00007_agent_registry.sql).

UPDATE agent_registry
SET is_active = false,
    updated_at = now()
WHERE name IN ('interview_agent', 'salary_agent');

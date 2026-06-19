-- Migration 00029: Ret review-agenter til Anthropic Haiku
--
-- Migration 00028 brugte WHERE default_provider = 'anthropic', men ats_agent,
-- hr_agent og critic_agent har default_provider = 'openai' i seed.sql.
-- Den WHERE-klausul matchede derfor kun hiring_manager_agent (som allerede var
-- på anthropic). Denne migration retter alle 4 review-agenter til Haiku.

UPDATE public.agent_registry
SET
    default_provider = 'anthropic',
    default_model    = 'claude-haiku-4-5-20251001',
    timeout_seconds  = 30
WHERE name IN ('ats_agent', 'hr_agent', 'hiring_manager_agent', 'critic_agent');

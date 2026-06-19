-- Migration 00027: Revert agent model names to Claude 4 versions
--
-- Migration 00026 changed to 'claude-3-5-sonnet-20241022' (Claude 3.5) but the
-- user's Anthropic API key only has access to Claude 4.x models.
-- Reverting to 'claude-sonnet-4-6' which is the correct Claude 4 Sonnet ID.
-- Also align OpenAI agents to gpt-4o-mini for cost efficiency.

UPDATE public.agent_registry
SET default_model = 'claude-sonnet-4-6'
WHERE default_provider = 'anthropic';

-- OpenAI agents stay on gpt-4o (already correct from seed)
-- No change needed for OpenAI agents.

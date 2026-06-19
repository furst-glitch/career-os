-- Migration 00026: Fix AI model names in agent_registry
--
-- Problem: 'claude-sonnet-4-6' er et internt alias brugt i Claude Code CLI.
-- Anthropic's offentlige API og LiteLLM accepterer dette format,
-- men 'claude-3-5-sonnet-20241022' er garanteret at virke på alle LiteLLM-versioner.
-- Vi sætter anthropic-agenter til claude-3-5-sonnet-20241022 som safe fallback
-- og beholder claude-sonnet-4-6 som primary model for de agenter der kan drage
-- fordel af det (om muligt).

UPDATE public.agent_registry
SET default_model = 'claude-3-5-sonnet-20241022'
WHERE default_provider = 'anthropic'
  AND name IN ('cv_agent', 'application_agent', 'career_coach_agent',
               'hiring_manager_agent', 'review_board_agent');

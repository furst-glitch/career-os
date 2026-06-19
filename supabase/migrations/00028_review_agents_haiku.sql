-- Migration 00028: Sæt review-agenter til Haiku for hastighed og omkostningseffektivitet
--
-- ATS, HR, HiringManager og Critic agenterne genererer kun kort feedback
-- (300-400 tokens) og kører nu som del af ApplicationAgent's review-pipeline.
-- De kører parallelt og behøver ikke Sonnet's fulde kapacitet.
-- Haiku er ~10x hurtigere og ~30x billigere for disse korte analyseopgaver.

UPDATE public.agent_registry
SET
    default_model = 'claude-haiku-4-5-20251001',
    timeout_seconds = 30
WHERE
    name IN ('ats_agent', 'hr_agent', 'hiring_manager_agent', 'critic_agent')
    AND default_provider = 'anthropic';

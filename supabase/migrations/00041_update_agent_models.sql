-- Migration 00041: Opdatér pipeline-agenter til Claude 4 modeller
--
-- cv_agent, application_agent og review_board_agent brugte claude-3-5-sonnet-20241022
-- (migration 00026). Denne model giver "Anthropic fejl" ved generering.
-- Vi opdaterer til claude-sonnet-4-6 og sætter timeout op til 120s
-- (pipeline estimat: 80-110s samlet, individuelle kald 25-40s).

UPDATE public.agent_registry
SET
    default_model   = 'claude-sonnet-4-6',
    timeout_seconds = 120
WHERE name IN ('cv_agent', 'application_agent', 'review_board_agent');

-- career_coach_agent opdateres også — bruges til interview-streaming
UPDATE public.agent_registry
SET
    default_model   = 'claude-sonnet-4-6',
    timeout_seconds = 45
WHERE name = 'career_coach_agent';

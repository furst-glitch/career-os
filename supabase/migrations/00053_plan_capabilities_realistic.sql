-- 00053_plan_capabilities_realistic.sql
-- Korrigér plan_capabilities til realistiske grænser.
--
-- Problem: originale grænser (Pro: 1.000 chat/dag, 100 docs/dag) giver
-- $944 USD AI-udgifter/måned pr. bruger vs. $21.59 USD i abonnementsindtægt.
--
-- Nye grænser designet til:
--   - Pro (149 DKK/md = ~$22): normalt forbrug ~$3-8 AI-udgifter/md
--   - Worst-case heavy user: ~$25 AI-udgifter/md (acceptabelt ved beta)
--   - BYOK-brugere har ingen AI-udgifter for os (de betaler selv)
--
-- Beregning:
--   - Chat-besked:   ~$0.028 (Sonnet input+output)
--   - Dok-analyse:   ~$0.027 (Sonnet + embeddings)
--   - Pro worst-case: 30 chat × $0.028 + 3 dok × $0.027 = $0.92/dag
--                    × 22 arbejdsdage = ~$20/md (marginal)
--
-- Plan_capabilities er pt. ikke håndhævet af API'en (AIPolicyService
-- er ikke fuldt integreret endnu) — disse grænser gælder fra integration.
-- Aktiv håndhævelse sker via ai_budgets.hard_limit i LiteLLMProvider.

-- Opdatér eksisterende Pro-rækker med realistiske daglige grænser
UPDATE public.plan_capabilities
SET requests_per_day = 30,   requests_per_minute = 5
WHERE plan = 'pro' AND capability = 'chat';

UPDATE public.plan_capabilities
SET requests_per_day = 3,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'contract_analysis';

UPDATE public.plan_capabilities
SET requests_per_day = 3,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'agreement_analysis';

UPDATE public.plan_capabilities
SET requests_per_day = 5,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'payslip_extraction';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 3
WHERE plan = 'pro' AND capability = 'cv_parsing';

UPDATE public.plan_capabilities
SET requests_per_day = 5,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'cv_generation';

UPDATE public.plan_capabilities
SET requests_per_day = 20,   requests_per_minute = 5
WHERE plan = 'pro' AND capability = 'job_matching';

UPDATE public.plan_capabilities
SET requests_per_day = 5,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'interview_prep';

UPDATE public.plan_capabilities
SET requests_per_day = 3,    requests_per_minute = 1
WHERE plan = 'pro' AND capability = 'salary_negotiation';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 3
WHERE plan = 'pro' AND capability = 'career_coaching';

UPDATE public.plan_capabilities
SET requests_per_day = 5,    requests_per_minute = 2
WHERE plan = 'pro' AND capability = 'document_review';

-- Professional-plan: 3-5× Pro (for $43/md = ~$65 AI-budget)
UPDATE public.plan_capabilities
SET requests_per_day = 100,  requests_per_minute = 15
WHERE plan = 'professional' AND capability = 'chat';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'contract_analysis';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'agreement_analysis';

UPDATE public.plan_capabilities
SET requests_per_day = 15,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'payslip_extraction';

UPDATE public.plan_capabilities
SET requests_per_day = 30,   requests_per_minute = 10
WHERE plan = 'professional' AND capability = 'cv_parsing';

UPDATE public.plan_capabilities
SET requests_per_day = 15,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'cv_generation';

UPDATE public.plan_capabilities
SET requests_per_day = 50,   requests_per_minute = 15
WHERE plan = 'professional' AND capability = 'job_matching';

UPDATE public.plan_capabilities
SET requests_per_day = 15,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'interview_prep';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 3
WHERE plan = 'professional' AND capability = 'salary_negotiation';

UPDATE public.plan_capabilities
SET requests_per_day = 30,   requests_per_minute = 10
WHERE plan = 'professional' AND capability = 'career_coaching';

UPDATE public.plan_capabilities
SET requests_per_day = 20,   requests_per_minute = 5
WHERE plan = 'professional' AND capability = 'document_review';

UPDATE public.plan_capabilities
SET requests_per_day = 10,   requests_per_minute = 3
WHERE plan = 'professional' AND capability = 'multi_agent_review';

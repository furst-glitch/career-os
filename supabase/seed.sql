-- CareerOS Seed Data
-- Indsætter agent registry og knowledge guides

-- ── AGENT REGISTRY ─────────────────────────────────────────────────────────────

INSERT INTO public.agent_registry (name, display_name, version, description, default_provider, default_model, temperature, max_tokens, timeout_seconds)
VALUES
  ('cv_agent',              'CV Specialist',          '1.0.0', 'Parser, strukturerer og optimerer CV',                   'anthropic', 'claude-sonnet-4-6', 0.4, 8192, 120),
  ('application_agent',     'Ansøgningsskribent',     '1.0.0', 'Analyserer jobopslag og skriver ansøgninger',             'anthropic', 'claude-sonnet-4-6', 0.7, 4096, 90),
  ('job_agent',             'Jobscout',               '1.0.0', 'Søger og rangerer jobopslag baseret på profil',           'openai',    'gpt-4o',            0.3, 2048, 60),
  ('interview_agent',       'Interviewtræner',        '1.0.0', 'Genererer spørgsmål og evaluerer svar',                   'anthropic', 'claude-sonnet-4-6', 0.6, 4096, 60),
  ('salary_agent',          'Lønekspert',             '1.0.0', 'Analyserer lønniveauer og forbereder forhandling',        'openai',    'gpt-4o',            0.4, 2048, 60),
  ('ats_agent',             'ATS Simulator',          '1.0.0', 'Simulerer ATS-scoring og identificerer keyword-gaps',     'openai',    'gpt-4o',            0.2, 2048, 45),
  ('hr_agent',              'HR Fagperson',           '1.0.0', 'Vurderer kulturfit, sprogtone og røde flag',              'openai',    'gpt-4o',            0.5, 2048, 45),
  ('hiring_manager_agent',  'Hiring Manager',         '1.0.0', 'Vurderer faglig relevans og erfaringsmatch',              'anthropic', 'claude-sonnet-4-6', 0.5, 2048, 45),
  ('critic_agent',          'Djævelens Advokat',      '1.0.0', 'Finder svagheder, huller og potentielle indvendinger',    'openai',    'gpt-4o',            0.6, 2048, 45),
  ('career_coach_agent',    'Karriererådgiver',       '1.0.0', 'Strategisk karriereplanlægning og gap-analyse',           'anthropic', 'claude-sonnet-4-6', 0.7, 4096, 60),
  ('review_board_agent',    'Review Board',           '1.0.0', 'Orchestrerer andre agenter og syntetiserer final rapport','anthropic', 'claude-sonnet-4-6', 0.4, 8192, 180)
ON CONFLICT (name) DO NOTHING;

-- ── AGENT CAPABILITIES ─────────────────────────────────────────────────────────

INSERT INTO public.agent_capabilities (agent_id, capability, requires_memory, supports_streaming, min_plan)
SELECT id, 'cv_parsing',       false, false, 'free'       FROM public.agent_registry WHERE name = 'cv_agent'
UNION ALL
SELECT id, 'cv_optimization',  true,  true,  'free'       FROM public.agent_registry WHERE name = 'cv_agent'
UNION ALL
SELECT id, 'application_write',true,  true,  'free'       FROM public.agent_registry WHERE name = 'application_agent'
UNION ALL
SELECT id, 'job_search',       false, false, 'free'       FROM public.agent_registry WHERE name = 'job_agent'
UNION ALL
SELECT id, 'job_ranking',      true,  false, 'pro'        FROM public.agent_registry WHERE name = 'job_agent'
UNION ALL
SELECT id, 'interview_qa',     true,  true,  'free'       FROM public.agent_registry WHERE name = 'interview_agent'
UNION ALL
SELECT id, 'salary_analysis',  true,  false, 'pro'        FROM public.agent_registry WHERE name = 'salary_agent'
UNION ALL
SELECT id, 'ats_scoring',      false, false, 'pro'        FROM public.agent_registry WHERE name = 'ats_agent'
UNION ALL
SELECT id, 'hr_review',        false, false, 'pro'        FROM public.agent_registry WHERE name = 'hr_agent'
UNION ALL
SELECT id, 'hiring_mgr_review',false, false, 'pro'        FROM public.agent_registry WHERE name = 'hiring_manager_agent'
UNION ALL
SELECT id, 'critique',         false, false, 'pro'        FROM public.agent_registry WHERE name = 'critic_agent'
UNION ALL
SELECT id, 'career_coaching',  true,  true,  'pro'        FROM public.agent_registry WHERE name = 'career_coach_agent'
UNION ALL
SELECT id, 'full_review',      true,  false, 'pro'        FROM public.agent_registry WHERE name = 'review_board_agent'
ON CONFLICT (agent_id, capability) DO NOTHING;

-- ── KNOWLEDGE GUIDES ───────────────────────────────────────────────────────────

INSERT INTO public.knowledge_guides (title, category, content, tags, language)
VALUES
  ('Fortæl om dig selv',     'Interviewspørgsmål', 'Strukturér svaret: 1) Nuværende rolle, 2) Relevant erfaring, 3) Hvorfor dette job. Maks 2 minutter.',              ARRAY['åbning', 'intro', 'elevator pitch'], 'da'),
  ('STAR-metoden',           'Interviewteknik',    'Situation → Task → Action → Result. Brug konkrete tal og resultater. Øv 5-7 historier fra din karriere.',           ARRAY['star', 'storytelling', 'adfærdsspørgsmål'], 'da'),
  ('Løn­forhandling',        'Lønforhandling',     'Research markedsløn. Lad dem byde først. Anchor højt. Forhandl på pakken — ikke kun grundløn.',                    ARRAY['løn', 'forhandling', 'tilbud'], 'da'),
  ('Spørgsmål til dem',      'Interviewteknik',    'Stil altid 3-5 spørgsmål: om teamet, succes i rollen, udfordringer, og næste skridt i processen.',                 ARRAY['spørgsmål', 'engagement', 'nysgerrighed'], 'da'),
  ('ATS-optimering',         'CV-tips',            'Brug nøgleord fra jobopslaget. Undgå tabeller/billeder. Brug standard sektionsnavne. Gem som PDF.',                 ARRAY['ats', 'cv', 'keywords', 'format'], 'da'),
  ('Tell me about yourself', 'Interview Questions', 'Structure: 1) Current role, 2) Key achievements, 3) Why this opportunity. Keep it under 2 minutes.',              ARRAY['opening', 'intro', 'elevator pitch'], 'en'),
  ('STAR Method',            'Interview Technique', 'Situation → Task → Action → Result. Use specific numbers. Prepare 5-7 stories spanning your career.',             ARRAY['star', 'storytelling', 'behavioral'], 'en'),
  ('Salary Negotiation',     'Salary',              'Research market rates. Let them anchor first. Counter high. Negotiate the full package, not just base salary.',    ARRAY['salary', 'negotiation', 'offer'], 'en')
ON CONFLICT DO NOTHING;

-- Alle custom enum types for CareerOS
-- Opret her FØR tabeller der bruger dem

CREATE TYPE subscription_plan     AS ENUM ('free', 'pro', 'enterprise');
CREATE TYPE subscription_status   AS ENUM ('active', 'canceled', 'past_due', 'trialing');
CREATE TYPE ai_provider           AS ENUM ('openai', 'anthropic', 'ollama', 'custom');
CREATE TYPE language_code         AS ENUM ('da', 'en');

-- Career Memory
CREATE TYPE memory_type           AS ENUM ('milestone', 'insight', 'preference', 'goal', 'lesson', 'achievement');
CREATE TYPE memory_source         AS ENUM ('user_input', 'ai_extracted', 'behavioral');
CREATE TYPE goal_type             AS ENUM ('short_term', 'long_term', 'aspirational');
CREATE TYPE goal_status           AS ENUM ('active', 'achieved', 'abandoned');
CREATE TYPE milestone_impact      AS ENUM ('low', 'medium', 'high', 'defining');
CREATE TYPE milestone_category    AS ENUM ('promotion', 'award', 'project', 'pivot', 'skill', 'education', 'personal');

-- Experience Discovery
CREATE TYPE experience_type         AS ENUM ('job', 'project', 'freelance', 'volunteer', 'education', 'personal');
CREATE TYPE competency_category     AS ENUM ('technical', 'leadership', 'communication', 'analytical', 'domain');
CREATE TYPE competency_proficiency  AS ENUM ('awareness', 'working', 'practitioner', 'expert', 'thought_leader');
CREATE TYPE discovery_session_type  AS ENUM ('experience_interview', 'competency_mapping', 'achievement_mining');
CREATE TYPE discovery_session_status AS ENUM ('active', 'completed', 'paused');

-- Application Pipeline
CREATE TYPE application_status    AS ENUM ('draft', 'preparing', 'ready', 'submitted', 'screening', 'interviewing', 'offer', 'rejected', 'withdrawn', 'hired');
CREATE TYPE application_priority  AS ENUM ('low', 'medium', 'high', 'dream');
CREATE TYPE changed_by_type       AS ENUM ('user', 'system', 'ai');

-- Document Versioning
CREATE TYPE document_type         AS ENUM ('master_cv', 'cv_version', 'cover_letter', 'motivation_letter', 'portfolio', 'other');
CREATE TYPE document_generated_by AS ENUM ('user', 'ai', 'ai_assisted');
CREATE TYPE doc_relationship_type AS ENUM ('derived_from', 'inspired_by', 'replaces', 'complemented_by');

-- Search Intelligence
CREATE TYPE keyword_type          AS ENUM ('user_defined', 'ai_suggested', 'learned');
CREATE TYPE job_signal_type       AS ENUM ('viewed', 'saved', 'applied', 'dismissed', 'ignored', 'shared');

-- Interview Center
CREATE TYPE seniority_level       AS ENUM ('junior', 'mid', 'senior', 'lead', 'principal');

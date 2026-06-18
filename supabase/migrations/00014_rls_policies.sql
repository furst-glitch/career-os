-- Row Level Security Policies
-- Alle tabeller med brugerdata er isoleret via RLS

-- ── AUTH & PROFIL ──────────────────────────────────────────────────────────────

ALTER TABLE public.user_profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_api_keys        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_profiles: own"      ON public.user_profiles      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "subscriptions: own"      ON public.subscriptions       FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "user_api_keys: own"      ON public.user_api_keys       FOR ALL USING (auth.uid() = user_id);

-- ── CAREER MEMORY ──────────────────────────────────────────────────────────────

ALTER TABLE public.career_memories      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.career_goals         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.career_preferences   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.career_milestones    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "career_memories: own"    ON public.career_memories     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "career_goals: own"       ON public.career_goals        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "career_preferences: own" ON public.career_preferences  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "career_milestones: own"  ON public.career_milestones   FOR ALL USING (auth.uid() = user_id);

-- ── EXPERIENCE DISCOVERY ───────────────────────────────────────────────────────

ALTER TABLE public.experiences          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.star_stories         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competency_library   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.discovery_sessions   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "experiences: own"        ON public.experiences         FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "star_stories: own"       ON public.star_stories        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "competency_library: own" ON public.competency_library  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "discovery_sessions: own" ON public.discovery_sessions  FOR ALL USING (auth.uid() = user_id);

-- ── CV STUDIO ──────────────────────────────────────────────────────────────────

ALTER TABLE public.master_cvs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_experiences       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_educations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_skills            ENABLE ROW LEVEL SECURITY;

CREATE POLICY "master_cvs: own"         ON public.master_cvs          FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "cv_experiences: own"     ON public.cv_experiences
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid())
  );

CREATE POLICY "cv_educations: own"      ON public.cv_educations
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid())
  );

CREATE POLICY "cv_skills: own"          ON public.cv_skills
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid())
  );

-- ── AGENT REGISTRY (offentlig læsning, admin-skrivning) ───────────────────────

ALTER TABLE public.agent_registry       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_capabilities   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_configurations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agent_registry: read"    ON public.agent_registry      FOR SELECT USING (true);
CREATE POLICY "agent_capabilities: read" ON public.agent_capabilities FOR SELECT USING (true);

CREATE POLICY "agent_configurations: own" ON public.agent_configurations
  FOR ALL USING (user_id IS NULL OR auth.uid() = user_id);

-- ── DOCUMENT VERSIONING ────────────────────────────────────────────────────────

ALTER TABLE public.document_versions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_documents   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "document_versions: own"  ON public.document_versions   FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "document_relationships: own" ON public.document_relationships
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.document_versions d WHERE d.id = parent_doc_id AND d.user_id = auth.uid())
  );

CREATE POLICY "pipeline_documents: own" ON public.pipeline_documents
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.application_pipeline p WHERE p.id = pipeline_id AND p.user_id = auth.uid())
  );

-- ── APPLICATION PIPELINE ───────────────────────────────────────────────────────

ALTER TABLE public.jobs                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_pipeline         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_status_history   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "jobs: own"                       ON public.jobs                       FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "application_pipeline: own"       ON public.application_pipeline       FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "application_status_history: own" ON public.application_status_history
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.application_pipeline p WHERE p.id = pipeline_id AND p.user_id = auth.uid())
  );

-- ── SEARCH INTELLIGENCE ────────────────────────────────────────────────────────

ALTER TABLE public.user_keywords        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_relevance_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.keyword_performance  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_keywords: own"      ON public.user_keywords       FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "job_relevance_signals: own" ON public.job_relevance_signals FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "search_profiles: own"    ON public.search_profiles     FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "keyword_performance: own" ON public.keyword_performance
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.user_keywords k WHERE k.id = keyword_id AND k.user_id = auth.uid())
  );

-- ── INTERVIEW CENTER ───────────────────────────────────────────────────────────

ALTER TABLE public.company_research     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_analyses        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_prep_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_guides     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_packages   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_sessions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_items      ENABLE ROW LEVEL SECURITY;

CREATE POLICY "company_research: own"       ON public.company_research      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "role_analyses: own"          ON public.role_analyses         FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "salary_prep_sessions: own"   ON public.salary_prep_sessions  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "knowledge_guides: read"      ON public.knowledge_guides      FOR SELECT USING (true);
CREATE POLICY "interview_packages: own"     ON public.interview_packages    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "interview_sessions: own"     ON public.interview_sessions    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "interview_items: own"        ON public.interview_items
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.interview_sessions s WHERE s.id = session_id AND s.user_id = auth.uid())
  );

-- ── AI COST MANAGEMENT ─────────────────────────────────────────────────────────

ALTER TABLE public.ai_usage             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_costs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_budgets           ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_usage: own"           ON public.ai_usage            FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "ai_costs: own"           ON public.ai_costs            FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "ai_budgets: own"         ON public.ai_budgets          FOR ALL USING (auth.uid() = user_id);

-- ── AUDIT & GDPR ───────────────────────────────────────────────────────────────

ALTER TABLE public.audit_logs           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gdpr_requests        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_logs: own read"    ON public.audit_logs          FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "gdpr_requests: own"      ON public.gdpr_requests       FOR ALL USING (auth.uid() = user_id);

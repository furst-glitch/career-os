-- Performance Indexes
-- Inkl. pgvector index til semantisk søgning

-- ── CAREER MEMORY ──────────────────────────────────────────────────────────────
CREATE INDEX idx_career_memories_user       ON public.career_memories (user_id);
CREATE INDEX idx_career_memories_type       ON public.career_memories (user_id, memory_type);

-- pgvector IVFFlat index til cosine similarity søgning
-- lists = sqrt(antal rows) — justér ved > 1M minder
CREATE INDEX idx_career_memories_embedding  ON public.career_memories
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX idx_career_goals_user_status   ON public.career_goals (user_id, status);
CREATE INDEX idx_career_milestones_user     ON public.career_milestones (user_id, occurred_at DESC);

-- ── EXPERIENCE DISCOVERY ───────────────────────────────────────────────────────
CREATE INDEX idx_experiences_user           ON public.experiences (user_id);
CREATE INDEX idx_star_stories_user          ON public.star_stories (user_id);
CREATE INDEX idx_star_stories_experience    ON public.star_stories (experience_id);
CREATE INDEX idx_competency_library_user    ON public.competency_library (user_id, category);
CREATE INDEX idx_discovery_sessions_user    ON public.discovery_sessions (user_id, status);

-- ── CV STUDIO ──────────────────────────────────────────────────────────────────
CREATE INDEX idx_cv_experiences_cv          ON public.cv_experiences (master_cv_id, sort_order);
CREATE INDEX idx_cv_educations_cv           ON public.cv_educations (master_cv_id, sort_order);
CREATE INDEX idx_cv_skills_cv               ON public.cv_skills (master_cv_id, category);

-- ── DOCUMENT VERSIONING ────────────────────────────────────────────────────────
CREATE INDEX idx_document_versions_user     ON public.document_versions (user_id, document_type);
CREATE INDEX idx_document_versions_pipeline ON public.document_versions (pipeline_id) WHERE pipeline_id IS NOT NULL;
CREATE INDEX idx_document_versions_hash     ON public.document_versions (content_hash);
CREATE INDEX idx_document_relationships_parent ON public.document_relationships (parent_doc_id);
CREATE INDEX idx_document_relationships_child  ON public.document_relationships (child_doc_id);

-- ── APPLICATION PIPELINE ───────────────────────────────────────────────────────
CREATE INDEX idx_jobs_user                  ON public.jobs (user_id, created_at DESC);
CREATE INDEX idx_jobs_source                ON public.jobs (source) WHERE source IS NOT NULL;
CREATE INDEX idx_pipeline_user_status       ON public.application_pipeline (user_id, current_status);
CREATE INDEX idx_pipeline_job               ON public.application_pipeline (job_id);
CREATE INDEX idx_status_history_pipeline    ON public.application_status_history (pipeline_id, changed_at DESC);
CREATE INDEX idx_pipeline_documents_pipeline ON public.pipeline_documents (pipeline_id);

-- ── SEARCH INTELLIGENCE ────────────────────────────────────────────────────────
CREATE INDEX idx_user_keywords_user         ON public.user_keywords (user_id, is_active);
CREATE INDEX idx_user_keywords_type         ON public.user_keywords (user_id, keyword_type, weight DESC);
CREATE INDEX idx_relevance_signals_user     ON public.job_relevance_signals (user_id, signal_type);
CREATE INDEX idx_relevance_signals_job      ON public.job_relevance_signals (job_id);
CREATE INDEX idx_keyword_performance_kw     ON public.keyword_performance (keyword_id, recorded_at DESC);

-- ── INTERVIEW CENTER ───────────────────────────────────────────────────────────
CREATE INDEX idx_company_research_user      ON public.company_research (user_id, company_domain);
CREATE INDEX idx_company_research_cache     ON public.company_research (cached_until);
CREATE INDEX idx_role_analyses_job          ON public.role_analyses (job_id);
CREATE INDEX idx_interview_packages_user    ON public.interview_packages (user_id);
CREATE INDEX idx_interview_sessions_user    ON public.interview_sessions (user_id, status);
CREATE INDEX idx_interview_items_session    ON public.interview_items (session_id, sort_order);
CREATE INDEX idx_knowledge_guides_tags      ON public.knowledge_guides USING gin(tags);
CREATE INDEX idx_knowledge_guides_lang      ON public.knowledge_guides (language, category);

-- ── AI COST MANAGEMENT ─────────────────────────────────────────────────────────
CREATE INDEX idx_ai_usage_user_date         ON public.ai_usage (user_id, created_at DESC);
CREATE INDEX idx_ai_usage_agent             ON public.ai_usage (agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_ai_costs_user_period       ON public.ai_costs (user_id, period_start DESC);

-- ── AUDIT ──────────────────────────────────────────────────────────────────────
CREATE INDEX idx_audit_logs_user_date       ON public.audit_logs (user_id, created_at DESC);
CREATE INDEX idx_audit_logs_resource        ON public.audit_logs (resource_type, resource_id);
CREATE INDEX idx_gdpr_requests_user         ON public.gdpr_requests (user_id, status);
